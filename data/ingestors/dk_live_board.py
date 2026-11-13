"""DraftKings' own in-play boards, every second, into Supabase: every sport with
an in-play model (NCAAB, women's college basketball, NBA, NCAAF, NFL; mike,
2026-11-13: "Move everything over to the fast way").

    python -m data.ingestors.dk_live_board                 # every league, until none is live for a while
    python -m data.ingestors.dk_live_board --sports NBA NCAAB --dry-run
    python -m data.ingestors.dk_live_board --log feed.log  # the scheduled task's form

One process reads every league in turn: a league with a game live every second,
an idle one every 30 s, and never two requests closer than MIN_GAP_SEC (0.5 s),
so three live leagues read each about every 1.5 s at two requests a second.
Each sport's DraftKings names resolve onto OUR games rows by their own rule
(RESOLVERS): NBA and NFL by DraftKings' nickname, college football by school
name, both college basketballs through the team registries; every one refuses
an ambiguous pair, and an unmatched game is logged and skipped.

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

# DraftKings' league ids, each read off its own board's `leagues` key (2026-11-13):
# 92483 "NCAAB", 36647 "College Basketball (W)", 42648 "NBA", 87637 "College
# Football", 88808 "NFL".
LEAGUES = {"NCAAB": "92483", "NCAABW": "36647", "NBA": "42648", "NCAAF": "87637", "NFL": "88808"}
BOARD_URL = "https://sportsbook-nash.draftkings.com/api/sportscontent/dkusoh/v1/leagues/{league}"
BOOT_URL = "https://sportsbook.draftkings.com/leagues/basketball/ncaab"
HALVES = {"NCAAB"}                     # every other sport here plays quarters
FOOTBALL = {"NCAAF", "NFL"}
# Between ANY two requests, whichever leagues are live: an evening with three
# leagues live reads each about every 1.5 s, and this address never sends more
# than two requests a second (mike's home address is the one DraftKings would block).
MIN_GAP_SEC = float(os.environ.get("DK_LIVE_MIN_GAP_SEC", "0.5"))
POLL_SEC = float(os.environ.get("DK_LIVE_POLL_SEC", "1.0"))
# A refusal doubles the gap between reads, up to MAX_POLL_SEC; a minute without
# one halves it back toward POLL_SEC (his home address is the one at stake).
MAX_POLL_SEC = 5.0
# One feed at a time on this machine: a second start finds the port taken and exits.
# 47232 since the all-sports feed (2026-11-13): the NCAAB-only feed of #1268
# holds 47231 until its last game ends, and the two may run side by side that day.
LOCK_PORT = int(os.environ.get("DK_LIVE_LOCK_PORT", "47232"))
# --exit-on-new-master (the scheduled task's launcher passes it): every
# MASTER_CHECK_SEC the feed fetches origin/master, and when a merge changed one
# of FEED_FILES it exits with NEW_MASTER_EXIT; the launcher checks the new
# master out and starts it again at once. Any other merge is ignored, so the
# feed is not down for a merge that does not touch it.
MASTER_CHECK_SEC = 300.0
NEW_MASTER_EXIT = 3
FEED_FILES = ("data/ingestors/dk_live_board.py", "data/ingestors/ncaab_teams.py", "data/ingestors/ncaabw_teams.py",
              "data/db.py", "scripts/dk_live_board_run.ps1")
IDLE_POLL_SEC = float(os.environ.get("DK_LIVE_IDLE_POLL_SEC", "30"))
RESOLVE_RETRY_SEC = 60.0
RESOLVER_REFRESH_SEC = 600.0
# Consecutive refusals before the feed backs off for BACKOFF_SEC (his home
# address is the one at stake).
REFUSALS_BEFORE_BACKOFF = 5
BACKOFF_SEC = 120.0

# DraftKings' period names, seen live: NCAAB "1st Half", "2nd Half", "Halftime",
# "OT" (2026-11-12); college football "3rd Quarter", "4th Quarter" (2026-11-13).
# Halftime is the end of the first half: the last period before it, clock 0.
# A label not listed here is no period: the reader skips the game and the feed
# logs the label once, so a new name costs a decision, never a wrong one.
_HALF_PERIODS = {"1st Half": 1, "2nd Half": 2, "Halftime": 1}
_QUARTER_PERIODS = {"1st Quarter": 1, "2nd Quarter": 2, "3rd Quarter": 3, "4th Quarter": 4, "Halftime": 2}
_unknown_labels: set = set()


def period_of(label: str | None, sport: str = "NCAAB") -> int | None:
    if not label:
        return None
    table = _HALF_PERIODS if sport in HALVES else _QUARTER_PERIODS
    if label in table:
        return table[label]
    if "OT" in label.upper() or "OVERTIME" in label.upper():
        return 3 if sport in HALVES else 5      # overtime: in no phase of any rule
    if (sport, label) not in _unknown_labels:
        _unknown_labels.add((sport, label))
        log.warning("%s: DraftKings period %r is not a known period - its games are skipped", sport, label)
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
    home_nick: str | None = None       # DraftKings' nickname ("Pacers"): how NBA and NFL teams resolve
    away_nick: str | None = None
    home_ml: float | None = None       # the main moneyline
    away_ml: float | None = None
    possession: str | None = None      # football: 'home' / 'away' on DraftKings' sides
    down: int | None = None
    distance: int | None = None
    yardline: int | None = None        # DraftKings' own number; its scale is not yet measured against ESPN


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


_MAIN = {"Spread": "Spread", "Point Spread": "Spread", "Total": "Total", "Total Points": "Total",
         "Moneyline": "Moneyline"}


def parse_board(body: dict, sport: str = "NCAAB") -> list[BoardEvent]:
    """Every STARTED event of one league board. Pure: no clock, no network."""
    events = [e for e in body.get("events") or [] if e.get("status") == "STARTED"]
    markets: dict = {}
    for m in body.get("markets") or []:
        if m.get("main") and m.get("name") in _MAIN and not _suspended(m):
            markets[str(m.get("id"))] = (str(m.get("eventId")), _MAIN[m["name"]])
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
        per = period_of(label, sport)
        clock = 0.0 if label == "Halftime" else (float(lg["gameTime"]) if lg.get("gameTime") is not None else None)
        sp = sels.get((eid, "Spread"), {})
        to = sels.get((eid, "Total"), {})
        ml = sels.get((eid, "Moneyline"), {})
        sh = sp.get("Home")
        fb = {}
        if sport in FOOTBALL:
            ls = sc.get("liveScoreData") or {}
            pos = str(ls.get("americanFootballPossession") or "")
            # "Possession [T1]" is the first-listed team (sortOrder 1); T2 the other
            first_is_home = first is not None and home is not None and first is home
            if "[T1]" in pos:
                fb["possession"] = "home" if first_is_home else "away"
            elif "[T2]" in pos:
                fb["possession"] = "away" if first_is_home else "home"
            fb["down"] = _int(ls.get("americanFootballCurrentDown"))
            fb["distance"] = _int(ls.get("americanFootballYardsToGo"))
            fb["yardline"] = _int(ls.get("americanFootballYardLine"))
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
            under_price=None if to.get("Under") is None else american(to["Under"]),
            home_nick=((home or {}).get("metadata") or {}).get("rosettaTeamName"),
            away_nick=((away or {}).get("metadata") or {}).get("rosettaTeamName"),
            home_ml=None if ml.get("Home") is None else american(ml["Home"]),
            away_ml=None if ml.get("Away") is None else american(ml["Away"]),
            **fb))
    return out


def oriented(ev: BoardEvent, flipped: bool) -> dict:
    """The row's columns on OUR games row's sides. When DraftKings' home is
    our away (flipped), scores and spread sides swap and the spread's sign
    turns over: spread_home is always OUR home team's number (CLAUDE.md 4)."""
    if not flipped:
        h, a = ev.home_score, ev.away_score
        sp, hp, ap = ev.spread_home, ev.spread_home_price, ev.spread_away_price
        hml, aml, pos = ev.home_ml, ev.away_ml, ev.possession
    else:
        h, a = ev.away_score, ev.home_score
        sp = None if ev.spread_home is None else -ev.spread_home
        hp, ap = ev.spread_away_price, ev.spread_home_price
        hml, aml = ev.away_ml, ev.home_ml
        pos = {"home": "away", "away": "home"}.get(ev.possession or "")
    return {"dk_event_id": ev.dk_event_id, "flipped": bool(flipped), "period_label": ev.period_label,
            "period": ev.period, "clock_s": ev.clock_s, "clock_running": ev.clock_running,
            "home_score": h, "away_score": a, "spread_home": sp, "spread_home_price": hp,
            "spread_away_price": ap, "total_line": ev.total_line, "over_price": ev.over_price,
            "under_price": ev.under_price, "home_ml": hml, "away_ml": aml, "possession": pos,
            "down": ev.down, "distance": ev.distance, "yardline": ev.yardline}


CHANGE_KEY = ("period_label", "home_score", "away_score", "spread_home", "spread_home_price",
              "spread_away_price", "total_line", "over_price", "under_price", "home_ml", "away_ml",
              "possession", "down", "distance", "yardline")
READ_COLS = ("sport", "game_id", "read_at", "dk_event_id", "flipped", "period_label", "period", "clock_s",
             "clock_running", "home_score", "away_score", "spread_home", "spread_home_price",
             "spread_away_price", "total_line", "over_price", "under_price", "home_ml", "away_ml",
             "possession", "down", "distance", "yardline")


LINE_KEYS = ("spread_home", "spread_home_price", "spread_away_price", "total_line", "over_price", "under_price",
             "home_ml", "away_ml")


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
        home, away = ((ev.home_nick, ev.away_nick) if self.sport in NICKNAME_SPORTS
                      else (ev.home_name, ev.away_name))
        hit = None if self.resolver is None else self.resolver(home or "", away or "", ev.start or "")
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
            evs = parse_board(r.json(), self.sport)
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


def feed_changed_on_master(root: Path = ROOT) -> bool:
    """True when origin/master changes one of FEED_FILES against this
    checkout's HEAD. Any git failure is False: never restart on a doubt."""
    import subprocess
    try:
        subprocess.run(["git", "-C", str(root), "fetch", "-q", "origin", "master"], capture_output=True, timeout=60)
        out = subprocess.run(["git", "-C", str(root), "diff", "--name-only", "HEAD", "origin/master", "--",
                              *FEED_FILES], capture_output=True, text=True, timeout=30)
        return out.returncode == 0 and bool(out.stdout.strip())
    except Exception:                     # noqa: BLE001
        return False


def columns_ready(conn) -> bool:
    row = conn.execute("""SELECT COUNT(*) FROM information_schema.columns
                           WHERE table_schema = 'public' AND table_name = 'dk_live_reads'
                             AND column_name IN ('home_ml', 'away_ml', 'possession', 'down', 'distance', 'yardline')
                       """).fetchone()
    conn.commit()
    return bool(row and int(row[0]) == 6)


def tables_ready(conn) -> bool:
    row = conn.execute("SELECT to_regclass('public.dk_live_reads') IS NOT NULL "
                       "AND to_regclass('public.dk_live_feed') IS NOT NULL").fetchone()
    conn.commit()
    return bool(row and row[0])


def dk_session(sport: str):
    from curl_cffi import requests as cr
    s = cr.Session(impersonate="chrome124")
    try:
        s.get(BOOT_URL, timeout=15)
    except Exception:                     # noqa: BLE001
        pass
    return s


# ─── each sport's DraftKings names onto OUR games rows ────────────────────────
#
# A wrong match puts one game's line on another game's row and nothing
# downstream can tell; an unmatched game only costs a decision and is logged.
# So every resolver refuses on ambiguity and on anything it does not know.

def _today_et() -> str:
    from zoneinfo import ZoneInfo
    return datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York")).date().isoformat()


# DraftKings' college basketball school names our team registry does not
# resolve, each mapped to the registry's own name (read off DraftKings' NCAAB
# board on 2026-11-13: 10 of that night's 55 games did not resolve, all ten do
# through these). A wrong one cannot mis-place a line: the game must still
# match its opponent and its date, so it would only stay unmatched.
CBB_ALIASES = {"A&M-Corpus Christi": "Texas A&M-Corpus Christi", "Miami FL": "Miami",
               "Appalachian State": "App State", "LIU": "Long Island University",
               "Mount Saint Marys": "Mount St. Mary's", "SE Missouri State": "Southeast Missouri State",
               "Alcorn": "Alcorn State", "ULM": "UL Monroe", "Mississippi Valley": "Mississippi Valley State",
               "Illinois Chicago": "UIC"}


def _cbb(name: str) -> str:
    n = (name or "").replace("[W]", "").strip()
    return CBB_ALIASES.get(n, n)


def ncaab_resolver(conn):
    from data.ingestors.ncaab_teams import make_resolver
    inner = make_resolver(conn, _today_et())
    if inner is None:
        return None
    return lambda home, away, start: inner(_cbb(home), _cbb(away), start)


def ncaabw_resolver(conn):
    """Women's college basketball: DraftKings writes "Florida [W]"; the tag is
    dropped and the name goes through the women's team registry, as the odds
    feed's names do (data.ingestors.ncaabw_teams.make_resolver)."""
    from data.ingestors.ncaabw_teams import make_resolver
    inner = make_resolver(conn, _today_et())
    if inner is None:
        return None

    def resolve(home: str, away: str, start: str):
        return inner(_cbb(home), _cbb(away), start)
    return resolve


# DraftKings' nickname (participants[].metadata.rosettaTeamName) -> OUR team id,
# pinned against the ids the games table holds (tests/test_dk_live_board_all.py).
NBA_NICKNAMES = {
    "Hawks": "ATL", "Nets": "BKN", "Celtics": "BOS", "Hornets": "CHA", "Bulls": "CHI", "Cavaliers": "CLE",
    "Mavericks": "DAL", "Nuggets": "DEN", "Pistons": "DET", "Warriors": "GSW", "Rockets": "HOU",
    "Pacers": "IND", "Clippers": "LAC", "Lakers": "LAL", "Grizzlies": "MEM", "Heat": "MIA", "Bucks": "MIL",
    "Timberwolves": "MIN", "Pelicans": "NOP", "Knicks": "NYK", "Thunder": "OKC", "Magic": "ORL",
    "76ers": "PHI", "Suns": "PHX", "Trail Blazers": "POR", "Kings": "SAC", "Spurs": "SAS", "Raptors": "TOR",
    "Jazz": "UTA", "Wizards": "WAS"}
NFL_NICKNAMES = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF", "Panthers": "CAR", "Bears": "CHI",
    "Bengals": "CIN", "Browns": "CLE", "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX", "Chiefs": "KC", "Rams": "LA", "Chargers": "LAC",
    "Raiders": "LV", "Dolphins": "MIA", "Vikings": "MIN", "Patriots": "NE", "Saints": "NO", "Giants": "NYG",
    "Jets": "NYJ", "Eagles": "PHI", "Steelers": "PIT", "Seahawks": "SEA", "49ers": "SF", "Buccaneers": "TB",
    "Titans": "TEN", "Commanders": "WAS"}
NICKNAME_SPORTS = {"NBA": NBA_NICKNAMES, "NFL": NFL_NICKNAMES}

# DraftKings' college football school names that differ from OUR (CFBD) names
# once accents and punctuation are folded; read off the 2026-11-13..15 slate
# (132 of 138 names matched as they stand).
NCAAF_ALIASES = {"Appalachian State": "App State", "FIU": "Florida International", "Miami FL": "Miami",
                 "ULM": "UL Monroe"}


def _fold(name: str) -> str:
    import re
    import unicodedata
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", n.lower())


def _slate_games(conn, sport: str) -> list:
    from datetime import date, timedelta
    d = date.fromisoformat(_today_et())
    rows = conn.execute("""
        SELECT game_id, game_date, home_team, away_team FROM games
         WHERE sport = %s AND game_date BETWEEN %s AND %s
    """, (sport, (d - timedelta(days=1)).isoformat(), (d + timedelta(days=1)).isoformat())).fetchall()
    conn.commit()
    return [(str(g), str(gd)[:10], str(h or ""), str(a or "")) for g, gd, h, a in rows]


def pair_match(games: list, home_key: str, away_key: str, start: str, key) -> tuple | None:
    """(game_id, flipped) for the one game on the start's ET date (else the
    day either side) whose two teams are these two, either way round; None
    when there is none or more than one."""
    import pandas as pd
    try:
        et = pd.Timestamp(start).tz_convert("America/New_York").date().isoformat()
    except (ValueError, TypeError):
        et = None
    hits = [(g, gd, key(h) == home_key) for g, gd, h, a in games
            if {key(h), key(a)} == {home_key, away_key} and home_key != away_key]
    if et is not None:
        same = [x for x in hits if x[1] == et]
        hits = same or hits
    if len(hits) != 1:
        return None
    return hits[0][0], not hits[0][2]


def nickname_resolver(sport: str):
    nick = NICKNAME_SPORTS[sport]

    def factory(conn):
        games = _slate_games(conn, sport)

        def resolve(home: str, away: str, start: str):
            h, a = nick.get(home), nick.get(away)
            if not h or not a:
                return None
            return pair_match(games, h, a, start, key=lambda t: t)
        return resolve
    return factory


def ncaaf_resolver(conn):
    games = _slate_games(conn, "NCAAF")

    def resolve(home: str, away: str, start: str):
        h, a = (_fold(NCAAF_ALIASES.get(home, home)), _fold(NCAAF_ALIASES.get(away, away)))
        if not h or not a:
            return None
        return pair_match(games, h, a, start, key=_fold)
    return resolve


RESOLVERS = {"NCAAB": ncaab_resolver, "NCAABW": ncaabw_resolver, "NBA": nickname_resolver("NBA"),
             "NFL": nickname_resolver("NFL"), "NCAAF": ncaaf_resolver}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sports", nargs="*", default=sorted(LEAGUES), choices=sorted(LEAGUES))
    ap.add_argument("--poll", type=float, default=POLL_SEC, help="seconds between reads of a league with a game live")
    ap.add_argument("--minutes", type=float, default=None, help="stop after this long (default: idle exit)")
    ap.add_argument("--idle-exit", type=float, default=45.0, help="minutes with no live event before exiting")
    ap.add_argument("--log", type=Path, default=None, help="log to this file (UTF-8) instead of the console")
    ap.add_argument("--exit-on-new-master", action="store_true",
                    help="exit with code 3 when a merge to master changes the feed's files")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.log is not None:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                            filename=str(a.log), encoding="utf-8")
    else:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    from data.db import get_connection
    lock = single_instance()
    if lock is None:
        log.info("a DraftKings board feed is already running on this machine - exiting")
        return 0
    boards = {sp: Board(sp, get_connection, dk_session, RESOLVERS[sp], dry_run=a.dry_run) for sp in a.sports}
    first = next(iter(boards.values()))
    if not a.dry_run and not tables_ready(first.c()):
        log.warning("dk_live_reads / dk_live_feed do not exist yet (data/migrations/dk_live_reads_2026_11_12.sql, "
                    "applied by data.view_migrations) - exiting without reading DraftKings")
        return 0
    if not a.dry_run and not columns_ready(first.c()):
        log.warning("dk_live_reads lacks the moneyline and football columns "
                    "(data/migrations/dk_live_reads_all_sports_2026_11_13.sql) - exiting without reading DraftKings")
        return 0
    for b in boards.values():
        b.load_last()
    log.info("reading %s; a live league every %.1f s, an idle one every %.0f s, at least %.1f s between requests",
             ", ".join(boards), a.poll, IDLE_POLL_SEC, MIN_GAP_SEC)
    plan = Pacer(list(boards), a.poll)
    end = None if a.minutes is None else time.monotonic() + a.minutes * 60
    idle_since = None
    n = 0
    checked = time.monotonic()
    while end is None or time.monotonic() < end:
        if a.exit_on_new_master and time.monotonic() - checked >= MASTER_CHECK_SEC:
            checked = time.monotonic()
            if feed_changed_on_master():
                log.info("a merge to master changed the feed - exiting so the launcher starts the new one")
                return NEW_MASTER_EXIT
        sp, wait = plan.next()
        if wait > 0:
            time.sleep(wait)
        res = boards[sp].read()
        n += 1
        plan.done(sp, res, boards[sp])
        if n % 100 == 1:
            log.info("read %d (%s): %s", n, sp, res)
        if plan.any_live():
            idle_since = None
        elif idle_since is None:
            idle_since = time.monotonic()
        elif time.monotonic() - idle_since > a.idle_exit * 60:
            log.info("no live event in %s for %.0f minutes - exiting", ", ".join(boards), a.idle_exit)
            return 0
    return 0


class Pacer:
    """Which league to read next, and when: a league with a game live every
    `poll` seconds (doubled on a refusal up to MAX_POLL_SEC, halved back after
    a quiet minute), an idle one every IDLE_POLL_SEC, five refusals in a row
    BACKOFF_SEC, and never two requests closer than MIN_GAP_SEC."""

    def __init__(self, sports: list, poll: float, clock=time.monotonic):
        self.clock, self.poll = clock, float(poll)
        now = clock()
        self.due = {sp: now for sp in sports}
        self.gap = {sp: float(poll) for sp in sports}
        self.quiet_since = {sp: now for sp in sports}
        self.live = {sp: False for sp in sports}
        self.last_request = None

    def next(self) -> tuple:
        now = self.clock()
        sp = min(self.due, key=lambda k: self.due[k])
        at = self.due[sp]
        if self.last_request is not None:
            at = max(at, self.last_request + MIN_GAP_SEC)
        return sp, max(0.0, at - now)

    def done(self, sp: str, res: dict, board=None) -> None:
        now = self.clock()
        self.last_request = now
        self.live[sp] = bool(res.get("live"))
        refused = not res.get("ok") and "HTTP" in str(res.get("detail") or "")
        if refused:
            self.quiet_since[sp] = now
        g = next_gap(self.gap[sp], refused, now - self.quiet_since[sp], base=self.poll)
        if g != self.gap[sp]:
            log.warning("%s: reading every %.1f s (was %.1f s)", sp, g, self.gap[sp])
            if not refused:
                self.quiet_since[sp] = now
            self.gap[sp] = g
        if board is not None and board.refusals >= REFUSALS_BEFORE_BACKOFF:
            log.error("%s: %d refusals in a row - backing off %.0f s", sp, board.refusals, BACKOFF_SEC)
            board.refusals = 0
            self.due[sp] = now + BACKOFF_SEC
            return
        self.due[sp] = now + (self.gap[sp] if self.live[sp] else IDLE_POLL_SEC)

    def any_live(self) -> bool:
        return any(self.live.values())


if __name__ == "__main__":
    sys.exit(main())
