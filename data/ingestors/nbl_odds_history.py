"""NBL odds history from The Odds API: every snapshot the feed holds of
moneyline, spread and total, pre-game and in play, for the ten books named in
config.NBL_HISTORY_BOOKMAKERS.

A FORK OF data/ingestors/euroleague_odds_history.py (2026-11-12), itself the
women's college purchase. The fetch, the spool, the change-only store, the
ledger and the thinned cadence are that module's, unchanged; what differs is
the schedule it resolves onto (ESPN's NBL games, data/ingestors/nbl_espn.py,
read from `games`), the books, the sources and the tables.

WHAT THE FEED HOLDS (measured 2026-11-14, docs/sports/nbl.md). The key
basketball_nbl starts at 2024-09-24T05:05:38Z: a history event list asked at
2020-07, 2021-02, 2021-12, 2022-12 and 2023-12 answered empty with that first
snapshot as `next_timestamp`. So three seasons: 2024-25, 2025-26 and 2026-27 to
date. Snapshots are five minutes apart (23:50:38, 23:55:38, 00:00:38 on
2024-11-30), and the board holds the next round about a week ahead.

THE BOOKS AND THE BILL. Ten named books bill as one region: 30 credits a
snapshot for three markets (x-requests-last on the historical endpoint,
2026-11-14). BetRivers is the only book a pick may name that prices the NBL in
any snapshot read; Pinnacle is there only from 2026-27; the Betfair exchange is
the one sharp moneyline of the two earlier seasons; the other seven are the
Australian and European books that priced every sampled game.

THE FEED KEEPS NO SNAPSHOT WHILE NOTHING MOVES, AND AN ASK FOR A TIME IT HAS
NONE AT IS BILLED FOR THE ONE BEFORE, so the purchase walks the feed's own
chain (`next_timestamp`), one ask per snapshot the feed really kept.

TWO STEPS:
  1. FETCH (--fetch): one chain a UTC day, answers spooled to disk
     (--spool DIR/<day>/<snapshot time>.json.gz) with the day's state beside
     them; a stopped run resumes where each day stopped. With
     --pregame-step-min N, every snapshot from 30 minutes before each tip to
     2.5 hours after it, and one every N minutes otherwise (an NBL tip is
     02:00-11:30 UTC, so a game's dense window never crosses a UTC day).
  2. STORE (--store): the spool, oldest snapshot first, into Supabase.
     Pre-game quotes (last updated at or before ESPN's start) into `odds`,
     change-only, source PREGAME_SOURCE; in-play quotes into nbl_inplay_quotes,
     every one of every snapshot; unplaced events raw into nbl_odds_unmatched;
     one ledger row a snapshot in nbl_odds_snapshots, in the same transaction.

A PURCHASE RUNS AT SCALE ONLY ONCE ITS SOURCES ARE PROTECTED IN PRODUCTION
(data/prune_odds.PROTECTED_SOURCES): until that merges, the worker's odds
clean-up thins what was bought to an opener and a close.

CREDITS. plan_credit_budget with --reserve-days: the floor is that many days
of the platform's measured burn. Run it with a floor that covers the days to
the plan's next reset as well as the reserve, so the purchase can never leave
the live feeds short before the refill (CLAUDE.md, the September 2026 outage).
Seasons are bought newest first, so a stop at the floor leaves the oldest
season for the next cycle, and a re-run resumes it.

    python -m data.ingestors.nbl_odds_history --seasons 2025 2027 --spool DIR
    python -m data.ingestors.nbl_odds_history --seasons 2026 2026 --spool DIR --fetch --store --only-days 2025-12-11 2025-12-11 --pregame-step-min 15
    python -m data.ingestors.nbl_odds_history --seasons 2025 2027 --spool DIR --fetch --store --chunk-days 30 --reserve-days 30 --pregame-step-min 15
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests
from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection
from data.ingestors import nbl_teams as nt
from data.ingestors.nba_odds_history import _write_with_retry
from data.ingestors.ncaab_odds_history import PoolMeter, _stamp, _utc
from data.ingestors.odds_ingestor import _insert_odds, _mark_in_play, _process_events
from data.ingestors.odds_quota import persist_quota, plan_credit_budget

SPORT = nt.SPORT
BASE = f"https://api.the-odds-api.com/v4/historical/sports/{nt.ODDS_API_SPORT_KEY}"
MARKETS = ["h2h", "spreads", "totals"]
STEP_MIN = 5                       # the feed's snapshots are five minutes apart at their finest
SNAPSHOT_COST = 30                 # 10 x 3 markets x 1 region (ten named books)
DAY_SLOTS = 24 * 60 // STEP_MIN    # the most snapshots a day can hold
DAY_MAX_COST = (DAY_SLOTS + 1) * SNAPSHOT_COST
FIRST_HISTORY_DAY = date(2024, 9, 24)    # the feed's first NBL snapshot, 2024-09-24T05:05:38Z
LEAD_DAYS = 10                     # a season's days start this long before its first game
PREGAME_SOURCE = "odds_api_nbl_history"
INPLAY_SOURCE = "odds_api_nbl_inplay_history"
LEDGER = "nbl_odds_snapshots"
INPLAY_TABLE = "nbl_inplay_quotes"
UNMATCHED = "nbl_odds_unmatched"
DEFAULT_CONCURRENCY = 8
STORE_BATCH = 20                   # snapshots written per transaction
LOCK_STALE_S = 15 * 60             # a day's lock nobody has refreshed for this long is dead
SPOOL_COMPRESSION = 1              # gzip level of a spooled answer: level 9 made the fetch CPU-bound
MIN_SEASON_GAMES = 150             # a stored season's NBL league games (159 in 2024-25; the season in progress is exempt)
QUOTE_COLS = ("home_price", "away_price", "draw_price", "spread_home", "total_line",
              "over_price", "under_price")
INPLAY_VALUE_COLS = ("home_price", "away_price", "spread_home", "total_line",
                     "over_price", "under_price")

LEDGER_COLS = ("snapshot_ts", "asked_at", "events", "events_in_play", "pregame_rows",
               "inplay_rows", "unmatched", "credits", "stored_at")
LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS nbl_odds_snapshots (
    snapshot_ts     TIMESTAMPTZ PRIMARY KEY,
    asked_at        TIMESTAMPTZ,
    events          INTEGER,
    events_in_play  INTEGER,
    pregame_rows    INTEGER,
    inplay_rows     INTEGER,
    unmatched       INTEGER,
    credits         INTEGER,
    stored_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
INPLAY_COLS = ("snapshot_ts", "game_id", "bookmaker", "market", "last_update",
               *INPLAY_VALUE_COLS, "source")
INPLAY_DDL = """
CREATE TABLE IF NOT EXISTS nbl_inplay_quotes (
    snapshot_ts   TIMESTAMPTZ NOT NULL,
    game_id       TEXT NOT NULL,
    bookmaker     TEXT NOT NULL,
    market        TEXT NOT NULL,
    last_update   TIMESTAMPTZ,
    home_price    NUMERIC,
    away_price    NUMERIC,
    spread_home   NUMERIC,
    total_line    NUMERIC,
    over_price    NUMERIC,
    under_price   NUMERIC,
    source        TEXT NOT NULL,
    PRIMARY KEY (snapshot_ts, game_id, bookmaker, market)
)
"""
INPLAY_INDEX = "idx_nbl_inplay_quotes_game"
INPLAY_INDEX_DDL = ("CREATE INDEX IF NOT EXISTS idx_nbl_inplay_quotes_game "
                    "ON nbl_inplay_quotes (game_id, snapshot_ts)")
UNMATCHED_COLS = ("snapshot_at", "event_id", "home_name", "away_name", "commence_time",
                  "payload", "source", "stored_at")
UNMATCHED_DDL = """
CREATE TABLE IF NOT EXISTS nbl_odds_unmatched (
    snapshot_at    TIMESTAMPTZ NOT NULL,
    event_id       TEXT NOT NULL,
    home_name      TEXT,
    away_name      TEXT,
    commence_time  TEXT,
    payload        JSONB NOT NULL,
    source         TEXT NOT NULL,
    stored_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (event_id, snapshot_at, source)
)
"""
_LEDGER_INSERT = f"""
    INSERT INTO {LEDGER} (snapshot_ts, asked_at, events, events_in_play, pregame_rows,
                          inplay_rows, unmatched, credits, stored_at)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
    ON CONFLICT (snapshot_ts) DO NOTHING
"""
_INPLAY_INSERT = f"""
    INSERT INTO {INPLAY_TABLE} ({", ".join(INPLAY_COLS)})
    VALUES ({", ".join(["%s"] * len(INPLAY_COLS))})
    ON CONFLICT (snapshot_ts, game_id, bookmaker, market) DO NOTHING
"""
_UNMATCHED_INSERT = f"""
    INSERT INTO {UNMATCHED}
           (snapshot_at, event_id, home_name, away_name, commence_time, payload, source)
    VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
    ON CONFLICT (event_id, snapshot_at, source) DO NOTHING
"""


class PreconditionError(RuntimeError):
    """The purchase would pay for snapshots nothing can be matched to."""


class LedgerMismatch(RuntimeError):
    """`odds` holds rows under PREGAME_SOURCE that the ledger does not account for."""


def ensure_tables(conn) -> None:
    """The ledger, the in-play quotes and the unmatched store, once, locked
    down (all three are worker-only, data/anon_readable.WORKER_ONLY_TABLES)."""
    changed = False
    if not schema_is_current(conn, LEDGER, columns=LEDGER_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(LEDGER_DDL)
        lock_down(conn, LEDGER)
        changed = True
    if not schema_is_current(conn, INPLAY_TABLE, columns=INPLAY_COLS, indexes=(INPLAY_INDEX,),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(INPLAY_DDL)
        conn.execute(INPLAY_INDEX_DDL)
        lock_down(conn, INPLAY_TABLE)
        changed = True
    if not schema_is_current(conn, UNMATCHED, columns=UNMATCHED_COLS, rls=True,
                             revoked_from=API_ROLES):
        conn.execute(UNMATCHED_DDL)
        lock_down(conn, UNMATCHED)
        changed = True
    if changed:
        conn.commit()


# ── the plan: which UTC days ─────────────────────────────────────────────────

def season_days(games: list[dict], now: datetime) -> dict[int, list[date]]:
    """{season: its UTC days, oldest first}: from LEAD_DAYS before the season's
    first game (the feed lists a round about a week ahead; never before the
    feed's first day) to the day after its last, and never past today. The
    season is the stored one (ESPN's own label), never derived from a date.
    Pure."""
    by_season: dict[int, list[date]] = defaultdict(list)
    for g in games:
        by_season[int(g["season"])].append(date.fromisoformat(str(g["game_date"])[:10]))
    out = {}
    for season, days in by_season.items():
        first = max(min(days) - timedelta(days=LEAD_DAYS), FIRST_HISTORY_DAY)
        last = min(max(days) + timedelta(days=1), now.date())
        if first <= last:
            out[season] = [first + timedelta(days=k) for k in range((last - first).days + 1)]
    return out


def load_games(conn, first: int, last: int) -> list[dict]:
    """The stored NBL league games for seasons first..last (the NBL rows of
    `games`, which nbl_espn writes only for regular-season and finals games
    between two NBL clubs, never a cancelled, postponed or stale one):
    game_id, season, game_date, commence_time, home_code, away_code."""
    rows = conn.execute(
        "SELECT game_id, season, game_date, commence_time, home_team, away_team "
        "FROM games WHERE sport = 'NBL' AND season BETWEEN %s AND %s",
        (first, last)).fetchall()
    return [{"game_id": r[0], "season": int(r[1]), "game_date": r[2], "commence_time": r[3],
             "home_code": r[4], "away_code": r[5]} for r in rows]


def check_precondition(conn, seasons: list[int], this_season: int) -> dict[int, int]:
    """Raise unless every past season named holds its NBL schedule."""
    counts = dict(conn.execute(
        "SELECT season, COUNT(*) FROM games WHERE sport = 'NBL' AND season = ANY(%s) "
        "GROUP BY season", (list(seasons),)).fetchall())
    conn.commit()
    short = {s: int(counts.get(s, 0)) for s in seasons
             if s < this_season and int(counts.get(s, 0)) < MIN_SEASON_GAMES}
    if short:
        raise PreconditionError(
            "the NBL schedule is not stored for every season, so these snapshots "
            "would match nothing and still be ledgered as stored: "
            + ", ".join(f"{s}: {n:,} games" for s, n in sorted(short.items()))
            + f" (each needs {MIN_SEASON_GAMES:,}). Run "
              "data.ingestors.nbl_espn --seasons FIRST LAST --apply first.")
    return {s: int(counts.get(s, 0)) for s in seasons}


# ── step 1: fetch, one chain a day ───────────────────────────────────────────

class KeepAliveMeter(PoolMeter):
    """PoolMeter over one kept-alive connection a thread.

    PoolMeter._send calls requests.get, which builds a new TLS context and a
    new connection for every call. Walking a day is ~150 calls in a row from
    one thread, and at 40 calls in flight that set-up kept four processes at
    0.84 of a core each (measured 2026-11-09, 20 seconds) for 138 snapshots a
    minute between them. A requests.Session per thread reuses both."""

    def __init__(self, ceiling: int, floor: int, workers: int = 1):
        super().__init__(ceiling, floor, workers)
        self._local = threading.local()

    def _send(self, url: str, params: dict):
        session = getattr(self._local, "session", None)
        if session is None:
            session = self._local.session = requests.Session()
        return session.get(url, params={**params, "apiKey": config.ODDS_API_KEY}, timeout=90)


def _params(when: datetime) -> dict:
    return {"date": _stamp(when), "markets": ",".join(MARKETS),
            "bookmakers": ",".join(config.NBL_HISTORY_BOOKMAKERS), "oddsFormat": "american"}


def _day_dir(spool: Path, day: date) -> Path:
    return spool / day.strftime("%Y%m%d")


def _state_path(spool: Path, day: date) -> Path:
    return _day_dir(spool, day) / "_state.json"


def read_state(spool: Path, day: date) -> dict:
    """A day's fetch state: {"done": bool, "next": the next snapshot time to
    ask for or None, "snapshots": [{"ts", "asked", "credits", "events"}],
    "wasted_credits": billed for answers that were another day's}."""
    p = _state_path(spool, day)
    if not p.exists():
        return {"done": False, "next": None, "snapshots": [], "wasted_credits": 0}
    return json.loads(p.read_text(encoding="utf-8"))


def _write_state(spool: Path, day: date, state: dict) -> None:
    """Replace the day's state file whole. On Windows the replace is refused
    while any other process has the file open (a reader counting progress did
    it 15 times on 2026-11-09, and each refusal stopped that day's walk with
    its last answer paid for and unrecorded), so it is retried for a few
    seconds before it is allowed to fail."""
    p = _state_path(spool, day)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(state), encoding="utf-8")
    for attempt in range(40):
        try:
            tmp.replace(p)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.1)


def snapshot_path(spool: Path, ts: datetime) -> Path:
    return _day_dir(spool, ts.date()) / f"{ts:%Y%m%dT%H%M%SZ}.json.gz"


class _Billed:
    """An answer's status and billing headers, without its body. The header
    names are lower-cased: the meter asks for them in lower case, and a plain
    dict of the feed's own spelling would answer None and bill nothing."""

    def __init__(self, r):
        self.status_code = getattr(r, "status_code", None)
        self.headers = {str(k).lower(): v
                        for k, v in (getattr(r, "headers", None) or {}).items()}


def _take_day(spool: Path, day: date) -> Path | None:
    """Claim a day for this process, or None when another process holds it.

    Several fetch processes may share one spool (each a different part of the
    seasons, or overlapping). Two walking the same day would each pay for the
    same snapshots, so a day is claimed with a lock file created exclusively.
    A lock whose file has not been touched for LOCK_STALE_S belongs to a
    process that died, and is taken over."""
    lock = _day_dir(spool, day) / "_lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return lock
        except FileExistsError:
            try:
                if time.time() - lock.stat().st_mtime < LOCK_STALE_S:
                    return None
                lock.unlink()
            except FileNotFoundError:
                pass
    return None


# EuroLeague's cadence (mike, 2026-11-13, docs/sports/euroleague.md): every
# snapshot while a game is near or in play, one every --pregame-step-min
# otherwise. The NBL keeps it so the two leagues' research reads alike.
DENSE_BEFORE = timedelta(minutes=30)     # every snapshot from here before a tip (the close)
DENSE_AFTER = timedelta(hours=2, minutes=30)   # ... to here after it (in play)


def dense(t: datetime, tips: list[datetime]) -> bool:
    """True while some game is within DENSE_BEFORE of its tip or in play. Pure."""
    return any(tip - DENSE_BEFORE <= t <= tip + DENSE_AFTER for tip in tips)


def next_ask(ts: datetime, nxt: datetime, tips: list[datetime],
             step: timedelta | None) -> datetime:
    """The next time to ask for, after an answer holding snapshot `ts` whose
    successor is `nxt`. With no step, `nxt` (every snapshot). With a step: `nxt`
    while a game is near or in play; otherwise `ts + step`, never later than the
    start of the next dense window and never earlier than `nxt`, so the asks
    only move forward. Pure."""
    if step is None or dense(nxt, tips):
        return nxt
    starts = [tip - DENSE_BEFORE for tip in tips if tip - DENSE_BEFORE > ts]
    target = ts + step
    if starts:
        target = min(target, min(starts))
    return max(nxt, target)


def walk_day(fetch, spool: Path, day: date, stop_at: datetime,
             tips: list[datetime] | None = None, step: timedelta | None = None) -> list:
    """Fetch one UTC day's snapshots by walking the feed's own chain. Runs on
    a pool thread; touches no accounting. Returns every paid call's Fetched,
    for the main thread to bill.

    `fetch(params)` makes one paid call (PoolMeter.fetch). The first ask is
    for 00:05: the feed answers with its latest snapshot at or before that
    time, which is the day's own 00:00 snapshot when games were on the board
    at midnight UTC (7pm ET, most nights of a season), and an older one
    otherwise. An older one is not stored (its own day's chain stores it); it
    is counted as wasted credits, and its next_timestamp still says where this
    day's chain starts. Each kept answer goes to the spool before the state
    file names it, so a crash can lose only a call's worth of work. A day is
    done when the chain leaves it; a day the feed has no later snapshot for
    yet (the present) is left open and resumes from `next`."""
    paid: list = []
    if read_state(spool, day)["done"]:
        return paid
    lock = _take_day(spool, day)
    if lock is None:
        return paid                 # another process is walking this day
    try:
        _walk(fetch, spool, day, stop_at, paid, lock, tips or [], step)
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass
    return paid


def _walk(fetch, spool: Path, day: date, stop_at: datetime, paid: list, lock: Path,
          tips: list[datetime], step: timedelta | None) -> None:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    state = read_state(spool, day)          # read again, now that the day is ours
    if state["done"]:
        return
    ask = _utc(state["next"]) if state.get("next") else start + timedelta(minutes=STEP_MIN)
    while ask is not None and ask < end and ask <= stop_at:
        os.utime(lock)                      # still alive
        f = fetch(_params(ask))
        r = f.response
        # keep what the meter bills from (status and headers), not the body: a
        # day's answers held until the main thread settles them are ~100 MB
        f.attempts = [_Billed(a) for a in f.attempts]
        f.response = None
        paid.append(f)
        if r is None or r.status_code != 200:
            raise RuntimeError(f"{_stamp(ask)}: HTTP {getattr(r, 'status_code', 'network')}")
        body = r.json()
        credits = int(float(r.headers.get("x-requests-last") or 0))
        ts = _utc(body.get("timestamp"))
        nxt = _utc(body.get("next_timestamp"))
        if nxt is not None and ts is not None and nxt <= ts:
            raise RuntimeError(f"{_stamp(ask)}: next_timestamp {nxt} is not after {ts}")
        if ts is not None and start <= ts < end:
            if not any(s["ts"] == _stamp(ts) for s in state["snapshots"]):
                with gzip.open(snapshot_path(spool, ts), "wt", encoding="utf-8",
                               compresslevel=SPOOL_COMPRESSION) as fh:
                    json.dump(body, fh)
                state["snapshots"].append({"ts": _stamp(ts), "asked": _stamp(ask),
                                           "credits": credits,
                                           "events": len(body.get("data") or [])})
        else:
            state["wasted_credits"] = state.get("wasted_credits", 0) + credits
        if nxt is None:
            # the feed has nothing later yet: leave the day open, and ask again
            # from the slot after this snapshot on the next run
            state["next"] = _stamp((ts or ask) + timedelta(minutes=STEP_MIN))
            _write_state(spool, day, state)
            break
        ask = next_ask(ts, nxt, tips, step) if ts is not None else nxt
        state["next"] = _stamp(ask)
        state["done"] = ask >= end
        _write_state(spool, day, state)


def fetch_days(meter: PoolMeter, spool: Path, days: list[date], now: datetime,
               tips_by_day: dict | None = None, step: timedelta | None = None) -> dict:
    """Walk every day not yet done, `meter.workers` at once. Before a day
    starts it is cleared against the ceiling and the floor at its most (every
    5-minute slot asked), with every day in flight counted the same way."""
    stats: dict = defaultdict(int)
    stop_at = now - timedelta(minutes=10)
    todo = [d for d in days if not read_state(spool, d)["done"]]
    stats["days"] = len(days)
    stats["days_already_done"] = len(days) - len(todo)

    def one(day):
        return day, walk_day(lambda params: meter.fetch(f"{BASE}/odds", params),
                             spool, day, stop_at, (tips_by_day or {}).get(day, []), step)

    def settle(fut):
        meter.reserved -= DAY_MAX_COST
        try:
            _, paid = fut.result()
        except Exception as exc:                                # noqa: BLE001
            stats["day_errors"] += 1
            logger.warning(f"NBL odds fetch: a day stopped early ({exc}); a re-run resumes it")
            return
        for f in paid:
            meter.settle(f)
        stats["calls"] += len(paid)
        stats["days_walked"] += 1
        if stats["days_walked"] % 20 == 0:
            logger.info(f"NBL odds fetch: {stats['days_walked']} days, {stats['calls']:,} "
                        f"calls, spent {meter.spent:,}, balance {meter.remaining}")

    stop = None
    with ThreadPoolExecutor(max_workers=meter.workers, thread_name_prefix="nbl-day") as pool:
        inflight = set()
        for day in todo:
            while len(inflight) >= meter.workers:
                done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
                for fut in done:
                    settle(fut)
            stop = meter.stop_reason(DAY_MAX_COST)
            if stop:
                break
            meter.reserved += DAY_MAX_COST
            inflight.add(pool.submit(one, day))
        while inflight:
            done, inflight = wait(inflight, return_when=FIRST_COMPLETED)
            for fut in done:
                settle(fut)
    if stop:
        stats["stopped"] = stop
        logger.warning(f"NBL odds fetch stopping: {stop}")
    stats["rate_limited_429"] = meter.rate_limited
    stats["spent"] = meter.spent
    stats["balance"] = meter.remaining
    return dict(stats)


def spool_snapshots(spool: Path, days: list[date]) -> list[dict]:
    """Every fetched snapshot of `days`, oldest first: {"ts", "asked",
    "credits", "events", "path"}."""
    out = []
    for d in days:
        for s in read_state(spool, d)["snapshots"]:
            ts = _utc(s["ts"])
            out.append({**s, "ts": ts, "path": snapshot_path(spool, ts)})
    return sorted(out, key=lambda s: s["ts"])


# ── resolving the feed's events onto NBL's games ──────────────────────

class EventResolver(nt.Resolver):
    """nbl_teams.Resolver over whole seasons, with the miss bookkeeping
    the store's split calls (note_miss, counted once per event)."""

    def __init__(self, registry: list[dict], games: list[dict]):
        super().__init__(registry, games)
        self.by_pair: dict[frozenset, list[dict]] = defaultdict(list)
        for g in games:
            self.by_pair[frozenset((g["home_code"], g["away_code"]))].append(g)
        self._seen: set[str] = set()

    def __call__(self, home_name: str, away_name: str, commence_time: str):
        home, away = self.code(home_name), self.code(away_name)
        if not home or not away:
            return None
        return nt.match_event(self.by_pair.get(frozenset((home, away)), []), home, away,
                              commence_time)

    def note_miss(self, ev: dict) -> None:
        eid = str(ev.get("id"))
        if eid in self._seen:
            return
        self._seen.add(eid)
        home, away = ev.get("home_team") or "", ev.get("away_team") or ""
        codes = [self.code(home), self.code(away)]
        for name, c in zip((home, away), codes):
            if c is None:
                self.unresolved_names[name] = self.unresolved_names.get(name, 0) + 1
        if None not in codes:
            k = f"{away} @ {home}"
            self.no_game[k] = self.no_game.get(k, 0) + 1


def build_resolver(conn, games: list[dict]) -> EventResolver:
    nt.reset_registry_cache()
    registry = nt.load_registry(conn)
    conn.commit()
    if not registry:
        raise PreconditionError("nbl_teams is empty, so only the config map can "
                                "resolve; run data.ingestors.nbl_espn first")
    return EventResolver(registry, games)


# ── step 2: store ────────────────────────────────────────────────────────────

def _quote(row: dict) -> tuple:
    return tuple(None if row.get(c) is None else round(float(row[c]), 4) for c in QUOTE_COLS)


class ChangeKeeper:
    """Which pre-game rows are stored: a (game, market, book)'s first quote
    and every quote that differs from its last in price or line. The men's
    opener-grid rule (ncaab_odds_history.ChangeKeeper)."""

    def __init__(self):
        self.last: dict[tuple[str, str, str], tuple] = {}

    def wanted(self, row: dict) -> bool:
        key = (row["game_id"], row.get("market") or "", row.get("bookmaker") or "")
        quote = _quote(row)
        if self.last.get(key) == quote:
            return False
        self.last[key] = quote
        return True


def split_snapshot(body: dict, resolver: EventResolver, tips: dict[str, str],
                   keeper: ChangeKeeper) -> dict:
    """One fetched snapshot -> what is stored. Pure apart from the resolver's
    miss counts and the keeper's memory.

    The parse is odds_ingestor._process_events with the resolver itself, the
    path the live capture takes: the NBL game id, the names swapped first
    when the feed calls ESPN's away club home, so spread_home is the home
    club's number (CLAUDE.md section 4). Each row is then labelled by its own
    last_update against ESPN's start (the feed's where none is stored)."""
    events = body.get("data") or []
    served = _utc(body.get("timestamp"))
    hits = {}
    unmatched = []
    for ev in events:
        hit = resolver(ev.get("home_team") or "", ev.get("away_team") or "",
                       ev.get("commence_time") or "")
        hits[str(ev.get("id"))] = hit
        if hit is None:
            unmatched.append(ev)
            resolver.note_miss(ev)
    _, rows = _process_events(events, SPORT, "open", _stamp(served), resolve_game_id=resolver)
    got = {r["game_id"] for r in rows}
    # resolved, priced, and no row out of the parser: kept raw too, because the
    # ledger row means this snapshot is never stored again
    dropped = [ev for ev in events
               if (hit := hits.get(str(ev.get("id")))) and hit[0] not in got
               and any(b.get("markets") for b in ev.get("bookmakers") or [])]
    fed = {hit[0]: ev.get("commence_time") for ev in events
           if (hit := hits.get(str(ev.get("id"))))}
    starts = []
    for gid in got:
        tip = _utc(tips.get(gid)) or _utc(fed.get(gid))
        starts.append({"game_id": gid, "commence_time": tip.isoformat() if tip else None})
    _mark_in_play(starts, rows)
    pregame, inplay = [], []
    for r in rows:
        if r.get("snapshot_type") == "in_play":
            r["source"] = INPLAY_SOURCE
            inplay.append(r)
        elif keeper.wanted(r):
            r["source"] = PREGAME_SOURCE
            pregame.append(r)
    in_play_events = sum(1 for ev in events
                         if (_utc(ev.get("commence_time")) or served) < served)
    return {"served": served, "pregame": pregame, "inplay": inplay,
            "lost": unmatched + dropped, "events": len(events),
            "events_in_play": in_play_events}


def _inplay_tuple(served: datetime, r: dict) -> tuple:
    return (served, r["game_id"], r["bookmaker"], r["market"], _utc(r.get("snapshot_at")),
            *(r.get(c) for c in INPLAY_VALUE_COLS), r["source"])


def held_snapshots(conn) -> set[datetime]:
    if conn.execute(f"SELECT to_regclass('public.{LEDGER}')").fetchone()[0] is None:
        conn.commit()
        return set()
    out = {_utc(r[0]) for r in conn.execute(f"SELECT snapshot_ts FROM {LEDGER}").fetchall()}
    conn.commit()
    return out


def check_resume(conn, first: int, last: int) -> tuple[int, int]:
    """(pre-game rows `odds` holds under PREGAME_SOURCE, rows the ledger says
    were stored). The store skips every snapshot the ledger holds, and `odds`
    has no unique key on a quote, so that is only safe while the ledger
    accounts for what `odds` holds under the marker. Rows and ledger row are
    written in one transaction, so the two agree; were the ledger lost or
    cleared, a re-run would store every pre-game row a second time, so this
    REFUSES instead. Read through the seasons' game ids, passed as a list so
    the game_id index is the only plan: as a sub-select (`game_id IN (SELECT
    ...)`) the planner scanned `odds` by source and hit the 120-second
    statement timeout on 2026-11-13, after a whole season had been fetched."""
    ids = [r[0] for r in conn.execute(
        "SELECT game_id FROM games WHERE sport = 'NBL' AND season BETWEEN %s AND %s",
        (first, last)).fetchall()]
    have = int(conn.execute(
        "SELECT COUNT(*) FROM odds WHERE game_id = ANY(%s) AND source = %s",
        (ids, PREGAME_SOURCE)).fetchone()[0]) if ids else 0
    ledgered = int(conn.execute(
        f"SELECT COALESCE(SUM(pregame_rows), 0) FROM {LEDGER}").fetchone()[0])
    conn.commit()
    if have > ledgered:
        raise LedgerMismatch(f"odds holds {have:,} rows under {PREGAME_SOURCE} but the ledger "
                             f"accounts for {ledgered:,}: a re-run would store them again")
    return have, ledgered


def store_season(conn, snapshots: list[dict], resolver: EventResolver, tips: dict[str, str],
                 held: set[datetime], stats: dict) -> None:
    """One season's spool into the database, oldest snapshot first.

    EVERY snapshot is read and split, so the change-only memory is what an
    unbroken run would hold; only the snapshots the ledger lacks are written,
    STORE_BATCH to a transaction, each with its ledger row."""
    keeper = ChangeKeeper()
    lost_hash: dict[str, str] = {}
    batch: list[tuple] = []

    def flush():
        if not batch:
            return
        pending = list(batch)
        batch.clear()

        def _write():
            # A replay after a dropped connection must not store a snapshot
            # twice: `odds` has no unique key on a quote, and a connection
            # that drops at the commit leaves it unknown whether the commit
            # landed. A snapshot's rows and its ledger row are one
            # transaction, so a ledger row means its rows are in.
            done = {_utc(r[0]) for r in conn.execute(
                f"SELECT snapshot_ts FROM {LEDGER} WHERE snapshot_ts = ANY(%s)",
                ([part["served"] for _, part, _ in pending],)).fetchall()}
            for snap, part, lost in pending:
                if part["served"] in done:
                    continue
                if part["pregame"]:
                    _insert_odds(conn, part["pregame"])
                if part["inplay"]:
                    conn.executemany(_INPLAY_INSERT,
                                     [_inplay_tuple(part["served"], r) for r in part["inplay"]])
                if lost:
                    conn.executemany(_UNMATCHED_INSERT, lost)
                conn.execute(_LEDGER_INSERT, (
                    part["served"], _utc(snap["asked"]), part["events"], part["events_in_play"],
                    len(part["pregame"]), len(part["inplay"]), len(part["lost"]),
                    snap["credits"]))
            conn.commit()

        what = f"{len(pending)} snapshots to {_stamp(pending[-1][1]['served'])}"
        if not _write_with_retry(conn, _write, what):
            stats["errors"] += len(pending)
            return
        for _, part, _ in pending:
            stats["stored"] += 1
            stats["pregame_rows"] += len(part["pregame"])
            stats["inplay_rows"] += len(part["inplay"])
            stats["unmatched_events"] += len(part["lost"])
        if stats["stored"] % 1000 < len(pending):
            logger.info(f"NBL odds store: {stats['stored']:,} snapshots, "
                        f"{stats['pregame_rows']:,} pre-game rows, "
                        f"{stats['inplay_rows']:,} in-play rows")

    for snap in snapshots:
        with gzip.open(snap["path"], "rt", encoding="utf-8") as fh:
            body = json.load(fh)
        part = split_snapshot(body, resolver, tips, keeper)
        if part["served"] != snap["ts"]:
            raise RuntimeError(f"{snap['path']}: holds {part['served']}, named {snap['ts']}")
        lost = []
        for ev in part["lost"]:
            eid = str(ev.get("id"))
            digest = hashlib.sha1(json.dumps(ev.get("bookmakers") or [],
                                             sort_keys=True).encode()).hexdigest()
            if lost_hash.get(eid) != digest:
                lost_hash[eid] = digest
                lost.append((part["served"], eid, ev.get("home_team"), ev.get("away_team"),
                             ev.get("commence_time"), json.dumps(ev), PREGAME_SOURCE))
        if snap["ts"] in held:
            stats["already_stored"] += 1
            continue
        batch.append((snap, part, lost))
        if len(batch) >= STORE_BATCH:
            flush()
    flush()


def store(conn, spool: Path, first: int, last: int, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    this_season = now.year + 1 if now.month >= 7 else now.year
    check_precondition(conn, list(range(first, last + 1)), this_season)
    ensure_tables(conn)
    check_resume(conn, first, last)
    games = load_games(conn, first, last)
    resolver = build_resolver(conn, games)
    tips = {g["game_id"]: g.get("commence_time") for g in games}
    held = held_snapshots(conn)
    stats: dict = defaultdict(int)
    for season, days in sorted(season_days(games, now).items(), reverse=True):
        if not first <= season <= last:
            continue
        snaps = spool_snapshots(spool, days)
        logger.info(f"NBL odds store, season {season}: {len(snaps):,} fetched snapshots")
        store_season(conn, snaps, resolver, tips, held, stats)
    print("NBL odds store", resolver.report())
    return dict(stats)


# ── the command ──────────────────────────────────────────────────────────────

def plan_days(conn, first: int, last: int, now: datetime) -> tuple[list[dict], list[date]]:
    games = load_games(conn, first, last)
    conn.commit()
    days = [d for season, ds in sorted(season_days(games, now).items(), reverse=True)
            if first <= season <= last for d in ds]
    return games, days


def _dry_run(conn, spool: Path, first: int, last: int, now: datetime) -> None:
    games, days = plan_days(conn, first, last, now)
    states = [read_state(spool, d) for d in days]
    done = sum(1 for s in states if s["done"])
    fetched = sum(len(s["snapshots"]) for s in states)
    paid = sum(x["credits"] for s in states for x in s["snapshots"])
    wasted = sum(s.get("wasted_credits", 0) for s in states)
    held = held_snapshots(conn)
    print(f"NBL odds history, seasons {first}-{last}: {len(games):,} NBL games stored")
    print(f"  UTC days {len(days):,}; fetched to the end {done:,}; to fetch {len(days) - done:,}")
    print(f"  snapshots in the spool {fetched:,} ({paid:,} credits billed for them, "
          f"{wasted:,} more for answers that belonged to an earlier day)")
    print(f"  snapshots in the database ledger {len(held):,}")
    print(f"  the days left cost at most {DAY_MAX_COST * (len(days) - done):,} credits "
          f"({DAY_MAX_COST:,} a day if every 5-minute slot holds a snapshot). Nothing was spent.")


def chunk_plan(games: list[dict], now: datetime, first: int, last: int,
               chunk_days: int) -> list[tuple[int, list[date]]]:
    """[(season, days)] in the order the chunked run fetches them: seasons
    newest first, and inside a season chunks of `chunk_days` newest first, each
    chunk's days oldest first. Pure."""
    out = []
    for season, days in sorted(season_days(games, now).items(), reverse=True):
        if not first <= season <= last:
            continue
        for end in range(len(days), 0, -chunk_days):
            out.append((season, days[max(0, end - chunk_days):end]))
    return out


def tips_by_utc_day(games: list[dict]) -> dict[date, list[datetime]]:
    """{UTC day: the stored starts of that day's games}. Pure."""
    out: dict[date, list[datetime]] = defaultdict(list)
    for g in games:
        t = _utc(g.get("commence_time"))
        if t is not None:
            out[t.date()].append(t)
    return dict(out)


def run_chunked(spool: Path, first: int, last: int, chunk_days: int, reserve_days: int,
                concurrency: int, do_store: bool, now: datetime,
                step: timedelta | None = None) -> int:
    """The whole purchase, newest season first, a chunk at a time (module
    docstring, THE WHOLE HISTORY IN ONE COMMAND). 0 when every chunk was
    fetched, 1 when it stopped at the floor or a day stopped early, 2 refused."""
    with get_connection() as conn:
        games = load_games(conn, first, last)
        conn.commit()
    plan = chunk_plan(games, now, first, last, chunk_days)
    tips = tips_by_utc_day(games)
    unstored: list[int] = []
    code = 0
    stopped = False
    for season in sorted({s for s, _ in plan}, reverse=True):
        for _, days in [c for c in plan if c[0] == season]:
            todo = [d for d in days if not read_state(spool, d)["done"]]
            if not todo:
                continue
            with get_connection() as conn:
                budget, problems = plan_credit_budget(
                    conn, shard_calls=len(todo) * (DAY_SLOTS + 1),
                    total_calls=len(todo) * (DAY_SLOTS + 1),
                    credits_per_call=SNAPSHOT_COST, reserve_days=reserve_days)
                conn.commit()
            if problems:
                for problem in problems:
                    print("REFUSED:", problem)
                code, stopped = 2, True
                break
            meter = KeepAliveMeter(budget.ceiling, budget.floor, workers=concurrency)
            meter.remaining = budget.remaining_at_start
            try:
                stats = fetch_days(meter, spool, todo, now, tips, step)
            finally:
                try:
                    with get_connection() as conn:
                        persist_quota(conn)
                        conn.commit()
                except Exception as exc:                        # noqa: BLE001
                    logger.warning(f"quota not persisted: {exc}")
            print(f"NBL odds fetch, season {season}, {todo[0]} to {todo[-1]}:",
                  json.dumps(stats, default=str))
            if stats.get("day_errors"):
                code = max(code, 1)
            if stats.get("stopped"):
                code, stopped = max(code, 1), True
                break
        if do_store and not _store_one(spool, season, now):
            unstored.append(season)
            code = max(code, 1)
        if stopped:
            print(f"NBL odds history stopped in season {season}; a re-run resumes")
            break
    # A season whose store failed is fetched and paid for, so it is tried again
    # once every fetch is done rather than left on one disk.
    for season in list(unstored):
        if _store_one(spool, season, now):
            unstored.remove(season)
    if unstored:
        print(f"NBL odds store: seasons {unstored} are in the spool and NOT in Supabase; "
              "re-run with --store")
    return code


def _store_one(spool: Path, season: int, now: datetime) -> bool:
    """Store one season's spool; False (logged, never raised) when it failed."""
    try:
        with get_connection() as conn:
            st = store(conn, spool, season, season, now)
    except Exception as exc:                                    # noqa: BLE001
        logger.error(f"NBL odds store, season {season}, failed: {exc}")
        return False
    print(f"NBL odds store, season {season}:", json.dumps(st, default=str))
    return not st.get("errors")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NBL odds history: every snapshot the feed holds")
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"), required=True,
                    help="ending-year season labels, e.g. 2025 2027")
    ap.add_argument("--spool", type=Path, required=True,
                    help="the folder fetched snapshots are written to and stored from")
    ap.add_argument("--fetch", action="store_true", help="spend credits: fetch what is missing")
    ap.add_argument("--store", action="store_true", help="write the spool to Supabase")
    ap.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY)
    ap.add_argument("--reserve-days", type=int, default=7,
                    help="stop before the balance falls under this many days of measured burn")
    ap.add_argument("--only-days", nargs=2, metavar=("FIRST", "LAST"),
                    help="fetch only these UTC days (YYYY-MM-DD), e.g. to try one day")
    ap.add_argument("--chunk-days", type=int, default=None,
                    help="run the whole history newest season first, this many days a chunk")
    ap.add_argument("--pregame-step-min", type=int, default=None,
                    help="away from tips, ask one snapshot every N minutes (default: every one)")
    a = ap.parse_args(argv)
    first, last = a.seasons
    now = datetime.now(timezone.utc)
    code = 0
    if a.chunk_days and a.fetch:
        a.spool.mkdir(parents=True, exist_ok=True)
        step = timedelta(minutes=a.pregame_step_min) if a.pregame_step_min else None
        return run_chunked(a.spool, first, last, a.chunk_days, a.reserve_days,
                           a.concurrency, a.store, now, step)
    # Three short connections, not one held open: the fetch runs for hours and
    # touches the database only before it starts and after it ends.
    with get_connection() as conn:
        if not a.fetch and not a.store:
            _dry_run(conn, a.spool, first, last, now)
            return 0
        _, days = plan_days(conn, first, last, now)
        if a.only_days:
            lo, hi = (date.fromisoformat(x) for x in a.only_days)
            days = [d for d in days if lo <= d <= hi]
        budget = None
        if a.fetch:
            todo = [d for d in days if not read_state(a.spool, d)["done"]]
            budget, problems = plan_credit_budget(
                conn, shard_calls=len(todo) * (DAY_SLOTS + 1),
                total_calls=len(todo) * (DAY_SLOTS + 1),
                credits_per_call=SNAPSHOT_COST, reserve_days=a.reserve_days)
            conn.commit()
            if problems:
                for problem in problems:
                    print("REFUSED:", problem)
                return 2
            print(f"budget: {budget}")
    if a.fetch:
        meter = KeepAliveMeter(budget.ceiling, budget.floor, workers=a.concurrency)
        meter.remaining = budget.remaining_at_start
        a.spool.mkdir(parents=True, exist_ok=True)
        # the one-day path honours the thinned cadence too, so a trial
        # measures what the purchase will cost
        step = timedelta(minutes=a.pregame_step_min) if a.pregame_step_min else None
        with get_connection() as conn:
            tips = tips_by_utc_day(load_games(conn, first, last))
            conn.commit()
        try:
            stats = fetch_days(meter, a.spool, days, now, tips, step)
        finally:
            try:
                with get_connection() as conn:
                    persist_quota(conn)
                    conn.commit()
            except Exception as exc:                            # noqa: BLE001
                logger.warning(f"quota not persisted: {exc}")
        print("NBL odds fetch:", json.dumps(stats, default=str))
        if stats.get("day_errors") or stats.get("stopped"):
            code = 1
    if a.store:
        with get_connection() as conn:
            stats = store(conn, a.spool, first, last, now)
        print("NBL odds store:", json.dumps(stats, default=str))
        if stats.get("errors"):
            code = 1
    return code


if __name__ == "__main__":
    sys.exit(main())
