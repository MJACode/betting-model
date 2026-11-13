"""DraftKings' own in-play board, every few seconds, into Supabase.

    python -m data.ingestors.dk_live_board                 # NCAAB, until no game is live for a while
    python -m data.ingestors.dk_live_board --dry-run       # read and print, write nothing
    python -m data.ingestors.dk_live_board --minutes 240 --poll 2.5

RUNS ON MIKE'S MACHINE, NOT THE WORKER. DraftKings answers a residential
address with a browser TLS fingerprint and refuses the Railway worker
(docs/live_odds_freshness.md, measured 2026-08-31; 200 from this machine on
2026-11-12). The worker's in-play loop reads what this writes
(models/ncaab_live_dk.py), so this is the hand-off and nothing else.

WHY (mike, 2026-11-12: "This is live betting ... This needs to be as close to
Real time as possible"). Measured that night (scripts/ncaab_live_latency_probe.py,
run 2026-11-12-ncaab): the odds provider's DraftKings quote was a median 32.5 s
old when served and a different number from DraftKings' board 28% of the time;
ESPN showed a basket 20 s (scoreboard) to 42 s (play-by-play) late. DraftKings'
board showed the score a median 3.7 s after a basket and moved its line in the
same read or after it in 177 of 180 baskets, and a DraftKings live spread was
still up 10 s later 77% of the time. So the line and the score come from here,
read together.

ONE READ: the league board (every event, market and selection in one ~200 KB
response). For each STARTED event: DraftKings' score, period, clock (seconds
left in the period; it counts down, a median 5.5 s ahead of ESPN's), whether
the clock runs, the main spread and the main total with both prices. The event
is resolved onto OUR games row by the same resolver the odds feed uses
(data.ingestors.ncaab_teams.make_resolver: team names to ESPN ids, the
unordered pair, the tip), and turned into OUR home and away when DraftKings
lists the teams the other way round (a neutral court).

WHAT IS WRITTEN (data/migrations/dk_live_reads_2026_11_12.sql):
  dk_live_reads  a row for a game only when its score, period, spread or total
                 (number or price) differs from its last row: the read time a
                 state was FIRST seen, which is what a quote's stamp means in
                 the model. Its clock is the clock at that read.
  dk_live_feed   upserted on every read, in the same transaction and after the
                 reads: the read's time and whether it answered. A reader
                 trusts dk_live_reads only while this is seconds old.

THE POLL. Every --poll seconds (default DK_LIVE_POLL_SEC, 1.0; mike, 2026-11-12:
"can it run even faster") while a game is live, every IDLE_POLL_SEC when none
is; a refusal doubles the gap (to 5 s) and a quiet minute halves it back. It
exits after --idle-exit minutes with no live event, and at once when another
feed holds the lock port or the tables do not exist yet. Measured from this
machine: 2.5 s reads 2026-11-13 00:15-00:40 and 03:25-04:4x UTC and 1 s reads for two minutes
at 04:4x, no refusal; a request takes a median 0.22 s. DraftKings' terms forbid
automated access however a request is shaped, and mike has made that call
(docs/live_odds_freshness.md).
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

log = logging.getLogger("data.ingestors.dk_live_board")

LEAGUES = {"NCAAB": "92483"}          # DraftKings' league ids, read off the board's own `leagues`
BOARD_URL = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/{league}"
BOOT_URL = {"NCAAB": "https://sportsbook.draftkings.com/leagues/basketball/ncaab"}
POLL_SEC = float(os.environ.get("DK_LIVE_POLL_SEC", "1.0"))
# A refusal doubles the gap between reads, up to MAX_POLL_SEC; a minute without
# one halves it back toward POLL_SEC (his home address is the one at stake).
MAX_POLL_SEC = 5.0
# One feed at a time on this machine: a second start finds the port taken and exits.
LOCK_PORT = int(os.environ.get("DK_LIVE_LOCK_PORT", "47231"))
IDLE_POLL_SEC = float(os.environ.get("DK_LIVE_IDLE_POLL_SEC", "30"))
RESOLVE_RETRY_SEC = 60.0
RESOLVER_REFRESH_SEC = 600.0
# Consecutive refusals before the feed backs off for BACKOFF_SEC (his home
# address is the one at stake).
REFUSALS_BEFORE_BACKOFF = 5
BACKOFF_SEC = 120.0

# DraftKings' period names (seen 2026-11-12: "1st Half", "2nd Half",
# "Halftime", "OT") -> (period, the clock to use). Halftime is the end of the
# first half: period 1, clock 0, and the model reads it as the break.
_PERIODS = {"1st Half": 1, "2nd Half": 2, "Halftime": 1}


def period_of(label: str | None) -> int | None:
    if not label:
        return None
    if label in _PERIODS:
        return _PERIODS[label]
    if "OT" in label.upper():
        return 3                        # overtime: in no phase of any rule
    return None


def american(sel: dict) -> float | None:
    """DraftKings writes American odds with a UNICODE minus (U+2212)."""
    disp = (sel.get("displayOdds") or {}).get("american")
    if isinstance(disp, str):
        try:
            return float(int(disp.replace("−", "-").replace("+", "").strip()))
        except ValueError:
            pass
    return None


@dataclass
class BoardEvent:
    dk_event_id: str
    name: str
    start: str | None
    home_name: str | None              # DraftKings' home (venueRole), before any flip
    away_name: str | None
    period_label: str | None
    period: int | None
    clock_s: float | None
    clock_running: bool
    home_score: int | None
    away_score: int | None
    spread_home: float | None          # DraftKings' home team's number
    spread_home_price: float | None
    spread_away_price: float | None
    total_line: float | None
    over_price: float | None
    under_price: float | None


def _suspended(obj: dict) -> bool:
    """A market or selection DraftKings marks suspended is no line. Not seen
    on 2026-11-12 (8,520 reads, every live game's spread and total present on
    every read); read defensively from the tags and status fields."""
    tags = [str(t).lower() for t in obj.get("tags") or []]
    status = str(obj.get("status") or obj.get("marketStatus") or "").lower()
    return any("suspend" in t for t in tags) or "suspend" in status or obj.get("isSuspended") is True


def _int(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def parse_board(body: dict) -> list[BoardEvent]:
    """Every STARTED event of one league board. Pure: no clock, no network."""
    events = [e for e in body.get("events") or [] if e.get("status") == "STARTED"]
    markets: dict = {}
    for m in body.get("markets") or []:
        if m.get("main") and m.get("name") in ("Spread", "Total") and not _suspended(m):
            markets[str(m.get("id"))] = (str(m.get("eventId")), m["name"])
    sels: dict = {}
    for s in body.get("selections") or []:
        k = markets.get(str(s.get("marketId")))
        if k and s.get("main") is not False and not _suspended(s):
            sels.setdefault(k, {})[s.get("outcomeType")] = s
    out = []
    for e in events:
        eid = str(e.get("id"))
        parts = e.get("participants") or []
        role = {p.get("venueRole"): p for p in parts}
        home, away = role.get("Home"), role.get("Away")
        # firstTeamScore is the participant listed first (sortOrder 1): "Away @ Home".
        first = min(parts, key=lambda p: p.get("sortOrder") or 99) if parts else None
        sc = ((e.get("eventScorecard") or {}).get("mainScorecard") or {})
        s1, s2 = _int(sc.get("firstTeamScore")), _int(sc.get("secondTeamScore"))
        if first is not None and home is not None and first is home:
            h_sc, a_sc = s1, s2
        else:
            h_sc, a_sc = s2, s1
        lg = e.get("liveGameState") or {}
        label = lg.get("period")
        per = period_of(label)
        clock = 0.0 if label == "Halftime" else (float(lg["gameTime"]) if lg.get("gameTime") is not None else None)
        sp = sels.get((eid, "Spread"), {})
        to = sels.get((eid, "Total"), {})
        sh = sp.get("Home")
        out.append(BoardEvent(
            dk_event_id=eid, name=str(e.get("name") or ""), start=e.get("startEventDate"),
            home_name=(home or {}).get("name"), away_name=(away or {}).get("name"),
            period_label=label, period=per, clock_s=clock, clock_running=bool(lg.get("isClockRunning")),
            home_score=h_sc, away_score=a_sc,
            spread_home=None if sh is None or sh.get("points") is None else float(sh["points"]),
            spread_home_price=None if sh is None else american(sh),
            spread_away_price=None if sp.get("Away") is None else american(sp["Away"]),
            total_line=None if to.get("Over") is None or to["Over"].get("points") is None
            else float(to["Over"]["points"]),
            over_price=None if to.get("Over") is None else american(to["Over"]),
            under_price=None if to.get("Under") is None else american(to["Under"])))
    return out


def oriented(ev: BoardEvent, flipped: bool) -> dict:
    """The row's columns on OUR games row's sides. When DraftKings' home is
    our away (flipped), scores and spread sides swap and the spread's sign
    turns over: spread_home is always OUR home team's number (CLAUDE.md 4)."""
    if not flipped:
        h, a = ev.home_score, ev.away_score
        sp, hp, ap = ev.spread_home, ev.spread_home_price, ev.spread_away_price
    else:
        h, a = ev.away_score, ev.home_score
        sp = None if ev.spread_home is None else -ev.spread_home
        hp, ap = ev.spread_away_price, ev.spread_home_price
    return {"dk_event_id": ev.dk_event_id, "flipped": bool(flipped), "period_label": ev.period_label,
            "period": ev.period, "clock_s": ev.clock_s, "clock_running": ev.clock_running,
            "home_score": h, "away_score": a, "spread_home": sp, "spread_home_price": hp,
            "spread_away_price": ap, "total_line": ev.total_line, "over_price": ev.over_price,
            "under_price": ev.under_price}


CHANGE_KEY = ("period_label", "home_score", "away_score", "spread_home", "spread_home_price",
              "spread_away_price", "total_line", "over_price", "under_price")
READ_COLS = ("sport", "game_id", "read_at", "dk_event_id", "flipped", "period_label", "period", "clock_s",
             "clock_running", "home_score", "away_score", "spread_home", "spread_home_price",
             "spread_away_price", "total_line", "over_price", "under_price")


LINE_KEYS = ("spread_home", "spread_home_price", "spread_away_price", "total_line", "over_price", "under_price")


def changed(prev: dict | None, row: dict) -> bool:
    return prev is None or any(prev.get(k) != row.get(k) for k in CHANGE_KEY)


class Board:
    """One sport's feed: read, resolve, write the changes and the beat."""

    def __init__(self, sport: str, connect, session_factory, resolver_factory, *, dry_run: bool = False,
                 clock=None, on_rows=None):
        self.sport, self.connect, self.dry_run = sport, connect, dry_run
        # Dry runs hand each read's changed rows here instead of the database
        # (a local measurement of the loop on the live board).
        self.on_rows = on_rows
        self.session_factory, self.resolver_factory = session_factory, resolver_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.sess = None
        self.conn = None
        self.resolver = None
        self.resolver_at = 0.0
        self.ids: dict = {}              # dk_event_id -> (game_id, flipped) | None
        self.tried: dict = {}            # dk_event_id -> monotonic time of the last failed resolve
        self.last: dict = {}             # game_id -> last written row
        self.refusals = 0

    def c(self):
        if self.conn is None:
            self.conn = self.connect()
        return self.conn

    def _resolve(self, ev: BoardEvent):
        if ev.dk_event_id in self.ids:
            return self.ids[ev.dk_event_id]
        if time.monotonic() - self.tried.get(ev.dk_event_id, -1e9) < RESOLVE_RETRY_SEC:
            return None
        if self.resolver is None or time.monotonic() - self.resolver_at > RESOLVER_REFRESH_SEC:
            self.resolver = self.resolver_factory(self.c())
            self.resolver_at = time.monotonic()
        hit = None if self.resolver is None else self.resolver(ev.home_name or "", ev.away_name or "",
                                                               ev.start or "")
        if hit is None:
            self.tried[ev.dk_event_id] = time.monotonic()
            log.warning("%s: DraftKings event %s (%s) does not resolve onto a game", self.sport, ev.dk_event_id,
                        ev.name)
            return None
        self.ids[ev.dk_event_id] = (str(hit[0]), bool(hit[1]))
        return self.ids[ev.dk_event_id]

    def read(self) -> dict:
        """One read. Returns counters; never raises upward."""
        if self.sess is None:
            self.sess = self.session_factory(self.sport)
        try:
            r = self.sess.get(BOARD_URL.format(league=LEAGUES[self.sport]), timeout=10)
        except Exception as exc:          # noqa: BLE001
            return self._beat(False, 0, 0, f"{type(exc).__name__}: {exc}"[:300])
        at = self.clock()
        if r.status_code != 200:
            self.refusals += 1
            if self.refusals >= REFUSALS_BEFORE_BACKOFF:
                self.sess = None          # a fresh session after the back-off
            return self._beat(False, 0, 0, f"HTTP {r.status_code}", at)
        self.refusals = 0
        try:
            evs = parse_board(r.json())
        except Exception as exc:          # noqa: BLE001
            return self._beat(False, 0, 0, f"unparsable board: {type(exc).__name__}", at)
        rows, present = [], set()
        for ev in evs:
            hit = self._resolve(ev)
            if hit is None:
                continue
            present.add(hit[0])
            row = {"sport": self.sport, "game_id": hit[0], "read_at": at, **oriented(ev, hit[1])}
            if changed(self.last.get(hit[0]), row):
                rows.append(row)
        # A game off the board (finished, pulled) gets a row with no line, so
        # a reader never takes its last line for one still on offer.
        for gid, prev in self.last.items():
            if gid not in present and any(prev.get(k) is not None for k in LINE_KEYS):
                rows.append({**prev, "read_at": at, **{k: None for k in LINE_KEYS}})
        matched = sum(1 for ev in evs if self.ids.get(ev.dk_event_id))
        if self.dry_run:
            if self.on_rows is not None:
                self.on_rows(at, rows)
            for row in rows:
                log.info("[dry-run] %s %s %s-%s %s spread %s (%s/%s) total %s (%s/%s)", row["game_id"],
                         row["period_label"], row["home_score"], row["away_score"], row["clock_s"],
                         row["spread_home"], row["spread_home_price"], row["spread_away_price"],
                         row["total_line"], row["over_price"], row["under_price"])
            for row in rows:
                self.last[row["game_id"]] = row
            return {"ok": True, "live": len(evs), "matched": matched, "written": len(rows)}
        try:
            conn = self.c()
            if rows:
                cols = ", ".join(READ_COLS)
                vals = ", ".join(f"%({c})s" for c in READ_COLS)
                conn.executemany(f"INSERT INTO dk_live_reads ({cols}) VALUES ({vals}) "
                                 f"ON CONFLICT (game_id, read_at) DO NOTHING", rows)
            self._upsert_beat(conn, at, True, len(evs), matched, "")
            conn.commit()
        except Exception as exc:          # noqa: BLE001
            log.error("%s: write failed: %s", self.sport, exc)
            self._recycle()
            return {"ok": False, "live": len(evs), "matched": matched, "written": 0}
        for row in rows:
            self.last[row["game_id"]] = row
        return {"ok": True, "live": len(evs), "matched": matched, "written": len(rows)}

    def _upsert_beat(self, conn, at, ok: bool, live: int, matched: int, detail: str) -> None:
        conn.execute("""
            INSERT INTO dk_live_feed (sport, last_read_at, ok, live_events, matched, detail)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (sport) DO UPDATE SET last_read_at = EXCLUDED.last_read_at, ok = EXCLUDED.ok,
                live_events = EXCLUDED.live_events, matched = EXCLUDED.matched, detail = EXCLUDED.detail
        """, (self.sport, at, ok, live, matched, detail))

    def _beat(self, ok: bool, live: int, matched: int, detail: str, at=None) -> dict:
        log.warning("%s: %s", self.sport, detail)
        if not self.dry_run:
            try:
                conn = self.c()
                self._upsert_beat(conn, at or self.clock(), ok, live, matched, detail)
                conn.commit()
            except Exception as exc:      # noqa: BLE001
                log.error("%s: beat failed: %s", self.sport, exc)
                self._recycle()
        return {"ok": ok, "live": live, "matched": matched, "written": 0, "detail": detail}

    def _recycle(self):
        try:
            if self.conn is not None:
                self.conn.close()
        except Exception:                 # noqa: BLE001
            pass
        self.conn = None

    def load_last(self) -> None:
        """Each game's newest row of the last six hours, so a restart does not
        write a second first-seen row for a state already stored."""
        if self.dry_run:
            return
        cols = ", ".join(READ_COLS)
        rows = self.c().execute(f"""
            SELECT DISTINCT ON (game_id) {cols} FROM dk_live_reads
             WHERE sport = %s AND read_at > NOW() - INTERVAL '6 hours'
             ORDER BY game_id, read_at DESC
        """, (self.sport,)).fetchall()
        self.c().commit()
        for r in rows:
            d = dict(zip(READ_COLS, r))
            self.last[d["game_id"]] = d


def next_gap(gap: float, refused: bool, quiet_s: float, base: float = POLL_SEC) -> float:
    """The gap before the next read: doubled after a refusal (to MAX_POLL_SEC),
    halved back toward `base` after a quiet minute."""
    if refused:
        return min(MAX_POLL_SEC, max(gap, base) * 2.0)
    if quiet_s >= 60.0 and gap > base:
        return max(base, gap / 2.0)
    return gap


def single_instance(port: int = LOCK_PORT):
    """A socket bound to a localhost port, held for the process's life, or
    None when another feed holds it. Windows frees it when the process dies."""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", port))
    except OSError:
        s.close()
        return None
    return s


def tables_ready(conn) -> bool:
    row = conn.execute("SELECT to_regclass('public.dk_live_reads') IS NOT NULL "
                       "AND to_regclass('public.dk_live_feed') IS NOT NULL").fetchone()
    conn.commit()
    return bool(row and row[0])


def dk_session(sport: str):
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome124")
    try:
        s.get(BOOT_URL[sport], timeout=15)
    except Exception:                     # noqa: BLE001
        pass
    return s


def ncaab_resolver(conn):
    from data.ingestors.ncaab_teams import make_resolver
    return make_resolver(conn, datetime.now(timezone.utc).astimezone().date().isoformat())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", default="NCAAB", choices=sorted(LEAGUES))
    ap.add_argument("--poll", type=float, default=POLL_SEC)
    ap.add_argument("--minutes", type=float, default=None, help="stop after this long (default: idle exit)")
    ap.add_argument("--idle-exit", type=float, default=45.0, help="minutes with no live event before exiting")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from data.db import get_connection
    lock = single_instance()
    if lock is None:
        log.info("a DraftKings board feed is already running on this machine - exiting")
        return 0
    board = Board(a.sport, get_connection, dk_session, ncaab_resolver, dry_run=a.dry_run)
    if not a.dry_run and not tables_ready(board.c()):
        log.warning("dk_live_reads / dk_live_feed do not exist yet (data/migrations/dk_live_reads_2026_11_12.sql, "
                    "applied by data.view_migrations) - exiting without reading DraftKings")
        return 0
    board.load_last()
    gap, last_refusal = a.poll, time.monotonic()
    end = None if a.minutes is None else time.monotonic() + a.minutes * 60
    idle_since = None
    n = 0
    while end is None or time.monotonic() < end:
        t0 = time.monotonic()
        res = board.read()
        n += 1
        if n % 40 == 1:
            log.info("%s read %d: %s", a.sport, n, res)
        if res.get("live"):
            idle_since = None
        elif idle_since is None:
            idle_since = time.monotonic()
        elif time.monotonic() - idle_since > a.idle_exit * 60:
            log.info("%s: no live event for %.0f minutes - exiting", a.sport, a.idle_exit)
            return 0
        if board.refusals >= REFUSALS_BEFORE_BACKOFF:
            log.error("%s: %d refusals in a row - backing off %.0f s", a.sport, board.refusals, BACKOFF_SEC)
            time.sleep(BACKOFF_SEC)
            board.refusals = 0
            continue
        refused = not res.get("ok") and "HTTP" in str(res.get("detail") or "")
        if refused:
            last_refusal = time.monotonic()
        new_gap = next_gap(gap, refused, time.monotonic() - last_refusal, base=a.poll)
        if new_gap != gap:
            log.warning("%s: reading every %.1f s (was %.1f s)", a.sport, new_gap, gap)
            if not refused:
                last_refusal = time.monotonic()      # the next halving waits another quiet minute
            gap = new_gap
        wait = gap if res.get("live") else IDLE_POLL_SEC
        time.sleep(max(0.0, wait - (time.monotonic() - t0)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
