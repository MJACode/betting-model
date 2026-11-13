"""EuroLeague first-half, quarter, team-total and alternate lines from The Odds
API's history: one per-event call per game at each of eight times before the
tip, stored in Supabase in the same run.

WHAT THE FEED HOLDS (measured 2026-11-12, docs/sports/euroleague.md). The bulk
odds endpoint never returns these markets; the per-event endpoint does, and
its history starts in 2023: a 2022-12 game answered HTTP 422, a 2024-12 game
held first-half lines at two offshore books, and 2025-12 and 2026-10 games held
them at FanDuel, BetMGM, BetRivers and Fanatics too, with first-quarter lines
at two or three of them. DraftKings priced none of these in any sample.

THE BILL. 10 credits per market RETURNED per region (a call asking ten markets
that all came back billed 100; one asking five, three of which came back,
billed 60 at two regions = 3 x 2 x 10). Ten named books are one region, so a
call costs 10 x the markets the books actually hold, and an empty answer 0.
Every market key the feed has served for EuroLeague is asked (PERIOD_MARKETS),
because asking for one no book holds costs nothing.

THE TIMES (MARKS): 24 h, 12 h, 6 h, 3 h, 2 h, 1 h, 30 and 10 minutes before
EuroLeague's start. A time that falls before the game's event appears is
answered with no event (free), and is ledgered as such.

THE EVENT IDS. The per-event endpoint needs the feed's event id. One historical
event list per UTC game date (1 credit), asked at the earliest planned time of
that date's games and resolved onto EuroLeague's games
(euroleague_teams.Resolver); a game it misses is asked again at its own 1-hour
mark.

WHAT IS STORED, per answer, in one transaction with its ledger row:
  * `odds`, source SOURCE, snapshot_type 'open', snapshot_at the market's own
    last_update (the asked time is the ledger's asked_at), only quotes last
    updated at or before EuroLeague's start, the home club's orientation (names
    swapped first when the feed calls EuroLeague's away club home). Markets:
    h2h_<p>, spreads_<p>, totals_<p> for each period p the feed returns (h1, h2,
    q1 ... q4); team_totals_home / _away (and _h1, _q1); the alternate_* ladders
    under their own names, every rung; and for each laddered main market the
    main number under the market's name and every other rung under
    <market>_alternate (two prices, closest to even, ties to the lower line).
  * euroleague_period_fetches: one row per (game, mark): the event, the
    snapshot the feed answered with, the markets and books returned, the rows
    stored, the credits billed (x-requests-last). A re-run buys no (game, mark)
    the ledger holds as done.

CREDITS. The plan prints the most it can cost (every market at every time).
The run stops before the balance would cross --floor, or the spend --max-credits.

    python -m data.ingestors.euroleague_period_history --seasons 2024 2027             # plan
    python -m data.ingestors.euroleague_period_history --seasons 2024 2027 --apply --floor N
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection
from data.ingestors import euroleague_teams as et
from data.ingestors.odds_ingestor import _insert_odds

SPORT = et.SPORT
BASE = f"https://api.the-odds-api.com/v4/historical/sports/{et.ODDS_API_SPORT_KEY}"
SOURCE = "odds_api_euroleague_period_history"
FIRST_SEASON = 2024           # 2023-24: the per-event history answers from 2023
PERIODS = ("h1", "h2", "q1", "q2", "q3", "q4")
PERIOD_MARKETS = tuple(
    [f"{m}_{p}" for p in PERIODS for m in ("h2h", "spreads", "totals")]
    + ["team_totals", "team_totals_h1", "team_totals_q1",
       "alternate_spreads", "alternate_totals", "alternate_team_totals",
       "alternate_spreads_h1", "alternate_totals_h1",
       "alternate_spreads_q1", "alternate_totals_q1",
       "h2h_3_way", "h2h_3_way_h1", "h2h_3_way_q1"])
MARKS = (("T-1440", 1440), ("T-720", 720), ("T-360", 360), ("T-180", 180),
         ("T-120", 120), ("T-60", 60), ("T-30", 30), ("T-10", 10))
MAX_CALL_COST = 10 * len(PERIOD_MARKETS)
DEFAULT_CONCURRENCY = 6
ODDS_KEYS = ("game_id", "sport", "market", "bookmaker", "snapshot_type", "snapshot_at",
             "home_price", "away_price", "draw_price", "spread_home", "total_line",
             "over_price", "under_price", "home_link", "away_link", "draw_link",
             "over_link", "under_link", "home_sid", "away_sid", "draw_sid",
             "over_sid", "under_sid", "source")

LEDGER = "euroleague_period_fetches"
LEDGER_COLS = ("game_id", "mark", "asked_at", "event_id", "snapshot_ts", "status",
               "markets", "books", "rows_stored", "credits", "fetched_at")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS euroleague_period_fetches (
    game_id      TEXT NOT NULL,
    mark         TEXT NOT NULL,
    asked_at     TIMESTAMPTZ NOT NULL,
    event_id     TEXT,
    snapshot_ts  TIMESTAMPTZ,
    status       TEXT NOT NULL,
    markets      TEXT[],
    books        TEXT[],
    rows_stored  INTEGER NOT NULL DEFAULT 0,
    credits      INTEGER NOT NULL DEFAULT 0,
    fetched_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, mark)
)
"""
_LEDGER_UPSERT = f"""
INSERT INTO {LEDGER} (game_id, mark, asked_at, event_id, snapshot_ts, status, markets, books,
                      rows_stored, credits, fetched_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (game_id, mark) DO UPDATE SET
    asked_at = EXCLUDED.asked_at, event_id = EXCLUDED.event_id,
    snapshot_ts = EXCLUDED.snapshot_ts, status = EXCLUDED.status,
    markets = EXCLUDED.markets, books = EXCLUDED.books, rows_stored = EXCLUDED.rows_stored,
    credits = {LEDGER}.credits + EXCLUDED.credits, fetched_at = NOW()
"""
# A (game, mark) with one of these statuses is never asked again.
DONE = ("ok", "no_markets", "no_event")


def ensure_tables(conn) -> None:
    if not schema_is_current(conn, LEDGER, columns=LEDGER_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(LEDGER_DDL)
        lock_down(conn, LEDGER)
        conn.commit()


def _utc(v) -> datetime | None:
    return et._ts(v)


def _stamp(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── parsing ──────────────────────────────────────────────────────────────────

def _side_team(o: dict) -> tuple[str, str]:
    name, desc = (o.get("name") or ""), (o.get("description") or "")
    return (name, desc) if name.lower() in ("over", "under") else (desc, name)


def parse_book(book_markets: list[dict], home: str, away: str) -> list[dict]:
    """One book's markets -> odds-row dicts, one per number listed. `home` and
    `away` are the feed's names in EuroLeague's orientation. A spread is keyed on
    the HOME number: the home outcome at p and the away outcome at -p. Pure."""
    rows: list[dict] = []
    for m in book_markets:
        key, outs = m.get("key") or "", m.get("outcomes") or []
        stamp = m.get("last_update")
        if key.startswith("h2h"):
            row = {"market": key, "snapshot_at": stamp}
            for o in outs:
                n = o.get("name") or ""
                slot = ("draw" if n.lower() in ("draw", "tie") else "home" if n == home
                        else "away" if n == away else None)
                if slot:
                    row.update({f"{slot}_price": o.get("price"), f"{slot}_link": o.get("link"),
                                f"{slot}_sid": o.get("sid")})
            if row.get("home_price") is not None or row.get("away_price") is not None:
                rows.append(row)
        elif key.startswith(("spreads", "alternate_spreads")):
            slots: dict[float, dict] = {}
            for o in outs:
                n, pt = o.get("name") or "", o.get("point")
                if pt is None:
                    continue
                if n == home:
                    slots.setdefault(float(pt), {}).update(
                        home_price=o.get("price"), home_link=o.get("link"), home_sid=o.get("sid"))
                elif n == away:
                    slots.setdefault(-float(pt), {}).update(
                        away_price=o.get("price"), away_link=o.get("link"), away_sid=o.get("sid"))
            rows += [{"market": key, "snapshot_at": stamp, "spread_home": p, **v}
                     for p, v in slots.items()]
        elif key.startswith(("team_totals", "alternate_team_totals")):
            slots_t: dict[tuple, dict] = {}
            for o in outs:
                side, team = _side_team(o)
                side = side.lower()
                if side not in ("over", "under") or o.get("point") is None:
                    continue
                which = "home" if team == home else "away" if team == away else None
                if which is None:
                    continue
                slots_t.setdefault((f"{key}_{which}", float(o["point"])), {}).update(
                    {f"{side}_price": o.get("price"), f"{side}_link": o.get("link"),
                     f"{side}_sid": o.get("sid")})
            rows += [{"market": mk, "snapshot_at": stamp, "total_line": p, **v}
                     for (mk, p), v in slots_t.items()]
        elif key.startswith(("totals", "alternate_totals")):
            slots = {}
            for o in outs:
                side = (o.get("name") or "").lower()
                if side not in ("over", "under") or o.get("point") is None:
                    continue
                slots.setdefault(float(o["point"]), {}).update(
                    {f"{side}_price": o.get("price"), f"{side}_link": o.get("link"),
                     f"{side}_sid": o.get("sid")})
            rows += [{"market": key, "snapshot_at": stamp, "total_line": p, **v}
                     for p, v in slots.items()]
    return rows


def _implied(price) -> float | None:
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p == 0:
        return None
    return 100.0 / (p + 100.0) if p > 0 else -p / (-p + 100.0)


def split_main(rows: list[dict]) -> list[dict]:
    """Rename every non-main rung of a laddered main market to
    <market>_alternate. The main rung of a (book, market): both prices present,
    the two implied probabilities closest to each other, ties to the lower line.
    A book with no two-sided rung keeps nothing under the main name. alternate_*
    ladders and h2h markets are returned unchanged. Pure; returns new dicts."""
    out = [dict(r) for r in rows]
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in out:
        mk = r["market"]
        if mk.startswith(("alternate_", "h2h")):
            continue
        groups[(r["bookmaker"], mk)].append(r)
    for (_, mk), rs in groups.items():
        def gap(r):
            a, b = ((r.get("home_price"), r.get("away_price")) if "spread_home" in r
                    and r.get("spread_home") is not None
                    else (r.get("over_price"), r.get("under_price")))
            ia, ib = _implied(a), _implied(b)
            return None if ia is None or ib is None else abs(ia - ib)
        line = (lambda r: r.get("spread_home") if r.get("spread_home") is not None
                else r.get("total_line"))
        two = [r for r in rs if gap(r) is not None]
        main = min(two, key=lambda r: (gap(r), line(r))) if two else None
        for r in rs:
            if r is not main:
                r["market"] = f"{mk}_alternate"
    return out


def answer_rows(body: dict, game_id: str, home: str, away: str, asked: datetime) -> tuple:
    """One per-event answer -> (odds rows, markets returned, books returned)."""
    data = (body or {}).get("data") or {}
    rows: list[dict] = []
    markets: set[str] = set()
    books: set[str] = set()
    for b in data.get("bookmakers") or []:
        key = b.get("key")
        if key not in config.EUROLEAGUE_PERIOD_BOOKMAKERS:
            continue
        for p in parse_book(b.get("markets") or [], home, away):
            row = dict.fromkeys(ODDS_KEYS)
            row.update(p)
            row.update(game_id=game_id, sport=SPORT, bookmaker=key, snapshot_type="open",
                       source=SOURCE)
            row["snapshot_at"] = row.get("snapshot_at") or b.get("last_update") or _stamp(asked)
            rows.append(row)
            books.add(key)
        markets |= {m.get("key") for m in b.get("markets") or [] if m.get("key")}
    return split_main(rows), sorted(markets), sorted(books)


# ── the plan ─────────────────────────────────────────────────────────────────

def load_games(conn, first: int, last: int) -> list[dict]:
    rows = conn.execute(
        f"SELECT game_id, season, game_date, commence_time, home_code, away_code "
        f"FROM {et.EVENTS} WHERE season BETWEEN %s AND %s AND played "
        f"AND COALESCE(status, '') <> 'Cancelled' AND commence_time IS NOT NULL",
        (first, last)).fetchall()
    return [{"game_id": r[0], "season": int(r[1]), "game_date": r[2], "commence_time": r[3],
             "home_code": r[4], "away_code": r[5]} for r in rows]


def held(conn) -> set[tuple[str, str]]:
    if conn.execute(f"SELECT to_regclass('public.{LEDGER}')").fetchone()[0] is None:
        conn.commit()
        return set()
    out = {(r[0], r[1]) for r in conn.execute(
        f"SELECT game_id, mark FROM {LEDGER} WHERE status = ANY(%s)", (list(DONE),)).fetchall()}
    conn.commit()
    return out


class LedgerMismatch(RuntimeError):
    """`odds` holds rows under SOURCE that the ledger does not account for."""


def check_resume(conn, game_ids: list[str]) -> tuple[int, int]:
    """(rows `odds` holds under SOURCE on these games, rows the ledger says it
    stored on them). The resume skips every (game, mark) the ledger holds, and
    `odds` has no unique key on a quote, so that is only safe while the ledger
    accounts for what `odds` holds under the marker: rows and ledger row are one
    transaction. Were the ledger lost, a re-run would store every row twice, so
    this REFUSES instead. Read through the games' ids (indexed), never a scan of
    `odds` by source."""
    if not game_ids:
        return 0, 0
    have = int(conn.execute(
        "SELECT COUNT(*) FROM odds WHERE game_id = ANY(%s) AND source = %s",
        (list(game_ids), SOURCE)).fetchone()[0])
    ledgered = 0
    if conn.execute(f"SELECT to_regclass('public.{LEDGER}')").fetchone()[0] is not None:
        ledgered = int(conn.execute(
            f"SELECT COALESCE(SUM(rows_stored), 0) FROM {LEDGER} WHERE game_id = ANY(%s)",
            (list(game_ids),)).fetchone()[0])
    conn.commit()
    if have > ledgered:
        raise LedgerMismatch(f"odds holds {have:,} rows under {SOURCE} on these games but the "
                             f"ledger accounts for {ledgered:,}: a re-run would store them again")
    return have, ledgered


def plan(games: list[dict], done: set, now: datetime) -> list[tuple[dict, str, datetime]]:
    """[(game, mark, asked_at)] not yet done, newest game first. A time not yet
    past is left for a later run. Pure."""
    out = []
    for g in sorted(games, key=lambda g: g["commence_time"], reverse=True):
        tip = _utc(g["commence_time"])
        for mark, lead in MARKS:
            t = tip - timedelta(minutes=lead)
            if (g["game_id"], mark) not in done and t < now:
                out.append((g, mark, t))
    return out


# ── the fetch ────────────────────────────────────────────────────────────────

class Meter:
    """Spend and balance, shared by the threads. stop() is True once one more
    call at its most could cross the ceiling or the floor."""

    def __init__(self, ceiling: int, floor: int):
        self.ceiling, self.floor = ceiling, floor
        self.spent = 0
        self.remaining: int | None = None
        self.lock = threading.Lock()
        self.session = threading.local()

    def get(self, url: str, params: dict):
        s = getattr(self.session, "s", None)
        if s is None:
            s = self.session.s = requests.Session()
        for attempt in range(6):
            r = s.get(url, params={**params, "apiKey": config.ODDS_API_KEY}, timeout=90)
            with self.lock:
                self.spent += int(float(r.headers.get("x-requests-last") or 0))
                rem = r.headers.get("x-requests-remaining")
                if rem is not None:
                    self.remaining = int(float(rem))
            if r.status_code != 429:
                return r
            threading.Event().wait(min(30, 2 ** attempt))
        return r

    def stop(self) -> str | None:
        with self.lock:
            if self.spent + MAX_CALL_COST > self.ceiling:
                return f"the next call could pass the ceiling ({self.spent:,} of {self.ceiling:,})"
            if self.remaining is not None and self.remaining - MAX_CALL_COST < self.floor:
                return f"the balance {self.remaining:,} is at the floor {self.floor:,}"
        return None


def event_ids(meter: Meter, resolver: et.Resolver, when: datetime) -> dict[str, tuple]:
    """{game_id: (event_id, feed home name, feed away name, flipped)} from the
    historical event list at `when` (1 credit)."""
    r = meter.get(f"{BASE}/events", {"date": _stamp(when)})
    if r.status_code != 200:
        return {}
    out = {}
    for ev in r.json().get("data") or []:
        hit = resolver(ev.get("home_team") or "", ev.get("away_team") or "",
                       ev.get("commence_time") or "")
        if hit:
            out[hit[0]] = (ev["id"], ev.get("home_team"), ev.get("away_team"), hit[1])
    return out


def fetch_one(meter: Meter, g: dict, mark: str, asked: datetime, ev: tuple | None) -> dict:
    if ev is None:
        return {"game": g, "mark": mark, "asked": asked, "status": "no_event_id", "rows": [],
                "event_id": None, "snapshot": None, "markets": [], "books": [], "credits": 0}
    eid, fhome, faway, flipped = ev
    home, away = (faway, fhome) if flipped else (fhome, faway)
    if meter.stop():
        # not asked: no ledger row, so a later run asks it
        return {"game": g, "mark": mark, "asked": asked, "status": "not_asked", "rows": [],
                "event_id": eid, "snapshot": None, "markets": [], "books": [], "credits": 0}
    r = meter.get(f"{BASE}/events/{eid}/odds", {
        "date": _stamp(asked), "markets": ",".join(PERIOD_MARKETS),
        "bookmakers": ",".join(config.EUROLEAGUE_PERIOD_BOOKMAKERS), "oddsFormat": "american"})
    credits = int(float(r.headers.get("x-requests-last") or 0))
    out = {"game": g, "mark": mark, "asked": asked, "event_id": eid, "credits": credits,
           "rows": [], "snapshot": None, "markets": [], "books": []}
    if r.status_code == 404:
        out["status"] = "no_event"
        return out
    if r.status_code != 200:
        out["status"] = f"http_{r.status_code}"
        return out
    body = r.json()
    out["snapshot"] = _utc(body.get("timestamp"))
    rows, markets, books = answer_rows(body, g["game_id"], home, away, asked)
    tip = _utc(g["commence_time"])
    rows = [x for x in rows if (_utc(x["snapshot_at"]) or asked) <= tip]
    out.update(rows=rows, markets=markets, books=books,
               status="ok" if rows else "no_markets")
    return out


def store_result(conn, res: dict) -> None:
    rows = res["rows"]
    if rows:
        _insert_odds(conn, rows)
    conn.execute(_LEDGER_UPSERT, (
        res["game"]["game_id"], res["mark"], res["asked"], res["event_id"], res["snapshot"],
        res["status"], res["markets"], res["books"], len(rows), res["credits"]))
    conn.commit()


def run(first: int, last: int, apply: bool, floor: int, max_credits: int | None,
        concurrency: int) -> dict:
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        if apply:
            ensure_tables(conn)
        games = load_games(conn, first, last)
        if apply:
            check_resume(conn, [g["game_id"] for g in games])
        done = held(conn)
        et.reset_registry_cache()
        resolver = et.Resolver(et.load_registry(conn), games)
        conn.commit()
    todo = plan(games, done, now)
    dates = sorted({t.date() for _, _, t in todo})
    most = len(todo) * MAX_CALL_COST + len(dates) * 2
    print(f"EuroLeague period history, seasons {first}-{last}: {len(games):,} played games, "
          f"{len(done):,} (game, time) pairs done, {len(todo):,} to ask over {len(dates):,} dates")
    print(f"  at most {most:,} credits ({MAX_CALL_COST} a call if every market came back at "
          f"every time, plus event lists); markets asked: {len(PERIOD_MARKETS)}")
    if not apply:
        print("dry run: nothing spent (add --apply)")
        return {"planned": len(todo), "most": most}
    meter = Meter(max_credits if max_credits is not None else most, floor)
    # event ids: one list per UTC date at its earliest planned time
    by_date: dict = defaultdict(list)
    for g, mark, t in todo:
        by_date[t.date()].append((g, mark, t))
    stats: dict = defaultdict(int)
    with get_connection() as conn:
        for day in sorted(by_date, reverse=True):
            stop = meter.stop()
            if stop:
                stats["stopped"] = stop
                break
            jobs = by_date[day]
            ids = event_ids(meter, resolver, min(t for _, _, t in jobs))
            missing = {g["game_id"] for g, _, _ in jobs} - set(ids)
            for gid in missing:
                g = next(g for g, _, _ in jobs if g["game_id"] == gid)
                ids.update({k: v for k, v in event_ids(
                    meter, resolver, _utc(g["commence_time"]) - timedelta(minutes=60)).items()
                    if k == gid})
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futs = [pool.submit(fetch_one, meter, g, mark, t, ids.get(g["game_id"]))
                        for g, mark, t in jobs]
                for f in as_completed(futs):
                    res = f.result()
                    if res["status"] in ("not_asked", "no_event_id"):
                        stats[res["status"]] += 1
                        continue
                    store_result(conn, res)
                    stats[res["status"]] += 1
                    stats["rows"] += len(res["rows"])
            stats["dates"] += 1
            if stats["dates"] % 10 == 0:
                logger.info(f"EuroLeague period history: {stats['dates']} dates, "
                            f"{dict(stats)}, spent {meter.spent:,}, balance {meter.remaining}")
    stats["spent"] = meter.spent
    stats["balance"] = meter.remaining
    print("EuroLeague period history:", json.dumps(dict(stats), default=str))
    return dict(stats)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EuroLeague period-market history")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"), required=True)
    ap.add_argument("--apply", action="store_true", help="spend credits and store")
    ap.add_argument("--floor", type=int, default=None,
                    help="stop before the balance would fall under this (required with --apply)")
    ap.add_argument("--max-credits", type=int, default=None)
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    a = ap.parse_args(argv)
    if a.apply and a.floor is None:
        print("REFUSED: --apply needs --floor (the balance the run must not go under)")
        return 2
    stats = run(a.seasons[0], a.seasons[1], a.apply, a.floor or 0, a.max_credits,
                a.concurrency)
    return 1 if stats.get("stopped") else 0


if __name__ == "__main__":
    sys.exit(main())
