"""Tennis odds history from The Odds API, stored in Supabase in the same run.

THE FEED SELLS TENNIS AS ONE KEY PER TOURNAMENT. `/v4/sports?all=true` listed 53
tennis keys on 2026-11-13: 26 men's (the four Grand Slams, the nine 1000-level
events, the ATP Finals and twelve 500-level events) and 27 women's. Each key is
active only while its event runs, so a key list is read from the feed, never
hardcoded, and a key's history is a set of yearly windows.

HISTORY. Snapshots from 2020 (13 events listed on 2020-09-05 at the US Open),
five minutes apart while prices move. An ask for a time the key holds no
snapshot at is answered with the one before, and billed: asked at 2026-10-29 the
Paris Masters key answered 2025-11-02, a year old (30 credits). So every walk
reads the feed's own `timestamp` and `next_timestamp` and never trusts the asked
time. An answer with no events is free (x-requests-last 0).

THE BILL (x-requests-last, 2026-11-13): 10 credits per market per region on the
historical endpoint; the `bookmakers` parameter bills each group of ten named
books as one region. The historical events list costs 1.

TWO TABLES, both worker-only (data/anon_readable):
  tennis_odds_fetches  one row per paid call: what was asked, the snapshot the
                       feed answered with, its neighbours, the events and the
                       credits. The coverage sweep's answers live here too.
  tennis_odds_quotes   change-only quotes: a row when a book's quote for an
                       event and market differs from the last one stored.
Neither is the shared `odds` table, so the odds clean-up (data/prune_odds)
never thins them.

    python -m data.ingestors.tennis_odds_history --sweep 2020 2026
    python -m data.ingestors.tennis_odds_history --window tennis_atp_us_open \
        2025-08-24 2025-09-08 --step-min 60 --max-credits 30000
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date, datetime, timedelta, timezone

import requests
from loguru import logger

# config installs the Odds API call logger on import (monitoring/probe.py);
# without it this module's paid calls never reach api_call_log
# (tests/test_odds_call_log_everywhere.py).
import config  # noqa: F401,E402
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

BASE = "https://api.the-odds-api.com/v4"
MARKETS = ("h2h", "spreads", "totals")
# Two groups of ten (two regions on the bill). Group one is the line-shop ten
# (config.LINE_SHOP_BOOKMAKERS): every book a pick may name, plus Pinnacle,
# Bovada and betPARX. Group two holds the sharp and offshore references tennis
# has (the Betfair and Matchbook exchanges, LowVig, BetOnline) and the books
# that carry the games spread and total line when the named books do not.
# Read off the 2026-08-31 US Open snapshot and the 2026-11-13 board.
BOOK_GROUPS = (
    ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics",
     "bovada", "pinnacle", "betrivers", "hardrockbet", "betparx"),
    ("betfair_ex_eu", "matchbook", "lowvig", "betonlineag", "ballybet",
     "espnbet", "marathonbet", "unibet", "williamhill", "betanysports"),
)
CREDITS_PER_SNAPSHOT = 10 * len(MARKETS) * len(BOOK_GROUPS)

# Every paid call is a ledger row carrying the run that bought it, so a re-run
# reads back what is already held (held_snapshots) and buys nothing twice.
SOURCE = "odds_api_tennis_history"
LIVE_SOURCE = "odds_api_tennis_live"
SWEEP_SOURCE = "odds_api_tennis_sweep"
FETCHES = "tennis_odds_fetches"
FETCH_COLS = ("id", "asked_at", "endpoint", "sport_key", "asked_ts", "snapshot_ts",
              "previous_ts", "next_ts", "events", "credits", "remaining", "body", "source")
FETCHES_DDL = """
CREATE TABLE IF NOT EXISTS tennis_odds_fetches (
    id           BIGSERIAL PRIMARY KEY,
    asked_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    endpoint     TEXT NOT NULL,
    sport_key    TEXT NOT NULL,
    asked_ts     TIMESTAMPTZ NOT NULL,
    snapshot_ts  TIMESTAMPTZ,
    previous_ts  TIMESTAMPTZ,
    next_ts      TIMESTAMPTZ,
    events       INTEGER,
    credits      INTEGER,
    remaining    BIGINT,
    body         JSONB,
    source       TEXT
)
"""
# Added after the table's first rows (2026-11-13); the gate in ensure_tables
# runs it once.
FETCHES_SOURCE_DDL = "ALTER TABLE tennis_odds_fetches ADD COLUMN IF NOT EXISTS source TEXT"
FETCHES_INDEX = "idx_tennis_odds_fetches_key_snap"
FETCHES_INDEX_DDL = (f"CREATE INDEX IF NOT EXISTS {FETCHES_INDEX} "
                     f"ON {FETCHES} (sport_key, endpoint, snapshot_ts)")

QUOTES = "tennis_odds_quotes"
QUOTE_COLS = ("sport_key", "event_id", "commence_time", "home_name", "away_name",
              "bookmaker", "market", "last_update", "snapshot_ts",
              "home_price", "away_price", "home_point", "away_point",
              "over_price", "under_price", "total_point")
QUOTES_DDL = """
CREATE TABLE IF NOT EXISTS tennis_odds_quotes (
    sport_key      TEXT NOT NULL,
    event_id       TEXT NOT NULL,
    commence_time  TIMESTAMPTZ,
    home_name      TEXT,
    away_name      TEXT,
    bookmaker      TEXT NOT NULL,
    market         TEXT NOT NULL,
    last_update    TIMESTAMPTZ,
    snapshot_ts    TIMESTAMPTZ NOT NULL,
    home_price     INTEGER,
    away_price     INTEGER,
    home_point     DOUBLE PRECISION,
    away_point     DOUBLE PRECISION,
    over_price     INTEGER,
    under_price    INTEGER,
    total_point    DOUBLE PRECISION,
    PRIMARY KEY (event_id, bookmaker, market, snapshot_ts)
)
"""
QUOTES_INDEX = "idx_tennis_odds_quotes_key_commence"
QUOTES_INDEX_DDL = (f"CREATE INDEX IF NOT EXISTS {QUOTES_INDEX} "
                    f"ON {QUOTES} (sport_key, commence_time)")


def ensure_tables(conn) -> None:
    changed = False
    if not schema_is_current(conn, FETCHES, columns=FETCH_COLS, indexes=(FETCHES_INDEX,),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(FETCHES_DDL)
        conn.execute(FETCHES_SOURCE_DDL)
        conn.execute(FETCHES_INDEX_DDL)
        lock_down(conn, FETCHES)
        changed = True
    if not schema_is_current(conn, QUOTES, columns=QUOTE_COLS, indexes=(QUOTES_INDEX,),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(QUOTES_DDL)
        conn.execute(QUOTES_INDEX_DDL)
        lock_down(conn, QUOTES)
        changed = True
    if changed:
        conn.commit()


# ── the feed ─────────────────────────────────────────────────────────────────

def _key() -> str:
    k = os.environ.get("ODDS_API_KEY")
    if not k:
        import config  # noqa: F401  (loads .env)
        k = os.environ.get("ODDS_API_KEY")
    if not k:
        raise SystemExit("ODDS_API_KEY is not set")
    return k


def _iso(ts: datetime) -> str:
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_ts(s):
    if not s:
        return None
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def tennis_keys() -> list[str]:
    """Every tennis key the feed lists, active or not (a free call)."""
    r = requests.get(f"{BASE}/sports", params={"apiKey": _key(), "all": "true"}, timeout=60)
    r.raise_for_status()
    return sorted(s["key"] for s in r.json() if s["key"].startswith("tennis_"))


class Floor(Exception):
    pass


class Meter:
    """Stops a run at a ceiling of its own spend, or when the account falls
    under a floor. Billed at x-requests-last, the feed's own figure."""

    def __init__(self, max_credits: int, floor: int):
        self.max_credits, self.floor, self.spent = max_credits, floor, 0
        self.remaining = None

    def before(self, cost: int) -> None:
        if self.spent + cost > self.max_credits:
            raise Floor(f"ceiling {self.max_credits:,} reached (spent {self.spent:,})")
        if self.remaining is not None and self.remaining - cost < self.floor:
            raise Floor(f"account at {self.remaining:,}, floor {self.floor:,}")

    def after(self, resp) -> int:
        try:
            last = int(resp.headers.get("x-requests-last"))
        except (TypeError, ValueError):
            last = None
        try:
            self.remaining = int(float(resp.headers.get("x-requests-remaining")))
        except (TypeError, ValueError):
            pass
        self.spent += last or 0
        return last


def _get(meter: Meter, url: str, params: dict, cost: int):
    meter.before(cost)
    for attempt in range(4):
        try:
            r = requests.get(url, params=params, timeout=90)
        except requests.RequestException as exc:
            logger.warning(f"{url}: {exc}; retry {attempt + 1}")
            time.sleep(2 ** attempt)
            continue
        if r.status_code == 429:
            time.sleep(2 ** attempt)
            continue
        credits = meter.after(r)
        return r, credits
    raise RuntimeError(f"{url}: no answer after 4 tries")


_FETCH_INSERT = (f"INSERT INTO {FETCHES} (endpoint, sport_key, asked_ts, snapshot_ts, "
                 "previous_ts, next_ts, events, credits, remaining, body, source) "
                 "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)")
_SOURCE_OF = {"odds": SOURCE, "live": LIVE_SOURCE, "events": SWEEP_SOURCE}


def _ledger(conn, endpoint, sport_key, asked, j, credits, remaining, body) -> None:
    conn.execute(_FETCH_INSERT, (
        endpoint, sport_key, _iso(asked), j.get("timestamp"), j.get("previous_timestamp"),
        j.get("next_timestamp"), len(j.get("data") or []), credits, remaining,
        json.dumps(body) if body is not None else None, _SOURCE_OF[endpoint]))


# ── the coverage sweep: where each key's yearly window is ────────────────────

def events_at(conn, meter: Meter, key: str, when: datetime) -> dict:
    """One historical events list (1 credit), recorded in the ledger with the
    event list itself (ids, names, starts)."""
    r, credits = _get(meter, f"{BASE}/historical/sports/{key}/events",
                      {"apiKey": _key(), "date": _iso(when)}, cost=1)
    j = r.json() if r.status_code == 200 else {"error": r.status_code, "data": []}
    body = [{"id": e["id"], "home": e["home_team"], "away": e["away_team"],
             "commence": e["commence_time"]} for e in (j.get("data") or [])]
    _ledger(conn, "events", key, when, j, credits, meter.remaining, body)
    conn.commit()
    return j


def sweep_key_year(conn, meter: Meter, key: str, year: int) -> list[dict]:
    """Every window the key held in `year`, newest first, from event lists.

    1. Asked at the end of the year, the feed answers with the key's last
       snapshot at or before then: the end of that year's last event, or an
       earlier year's when the key held nothing this year.
    2. Asked 40 days before that end, it answers with a snapshot from before the
       event; its `next_timestamp` is the first snapshot after it, the event's
       first listing.
    3. When the snapshot from step 2 is itself in `year`, the key held an
       earlier window that year (the women's Rome key: May 2025, then a stray
       July listing), so the walk repeats from it.
    """
    out: list[dict] = []
    ask = min(datetime(year, 12, 31, 23, 0, tzinfo=timezone.utc),
              datetime.now(timezone.utc) - timedelta(minutes=10))
    for _ in range(6):
        last = events_at(conn, meter, key, ask)
        last_ts = _parse_ts(last.get("timestamp"))
        if last_ts is None or last_ts.year != year:
            return out
        before = events_at(conn, meter, key, last_ts - timedelta(days=40))
        first_ts = _parse_ts(before.get("next_timestamp"))
        if first_ts is None or first_ts > last_ts:
            out.append({"key": key, "year": year, "first": None, "last": _iso(last_ts)})
            return out
        first = events_at(conn, meter, key, first_ts)
        out.append({"key": key, "year": year, "first": first.get("timestamp"),
                    "last": _iso(last_ts), "first_events": len(first.get("data") or []),
                    "last_events": len(last.get("data") or [])})
        prev_ts = _parse_ts(before.get("timestamp"))
        if prev_ts is None or prev_ts.year != year:
            return out
        ask = prev_ts
    return out


# ── the snapshot walk ────────────────────────────────────────────────────────

def _prices(m: dict, home: str, away: str) -> tuple:
    hp = ap = hpt = apt = op = up = tp = None
    for o in m.get("outcomes", []):
        name, price, point = o.get("name"), o.get("price"), o.get("point")
        if m["key"] == "totals":
            if name == "Over":
                op, tp = price, point
            elif name == "Under":
                up = price
        elif name == home:
            hp, hpt = price, point
        elif name == away:
            ap, apt = price, point
    return hp, ap, hpt, apt, op, up, tp


def quote_rows(key: str, body: dict) -> list[tuple]:
    """Every (event, book, market) quote in one snapshot, in QUOTE_COLS order."""
    snap = body.get("timestamp")
    out = []
    for e in body.get("data") or []:
        home, away = e.get("home_team"), e.get("away_team")
        for b in e.get("bookmakers", []):
            for m in b.get("markets", []):
                if m.get("key") not in MARKETS:
                    continue
                out.append((key, e["id"], e.get("commence_time"), home, away, b["key"],
                            m["key"], m.get("last_update") or b.get("last_update"), snap,
                            *_prices(m, home, away)))
    return out


_QUOTE_INSERT = (f"INSERT INTO {QUOTES} ({', '.join(QUOTE_COLS)}) VALUES "
                 f"({', '.join(['%s'] * len(QUOTE_COLS))}) ON CONFLICT DO NOTHING")
_VALUE = slice(9, 16)


def _last_values(conn, key: str) -> dict:
    """The newest stored quote values per (event, book, market) for one key,
    so a resumed walk stays change-only."""
    rows = conn.execute(
        f"SELECT DISTINCT ON (event_id, bookmaker, market) event_id, bookmaker, market, "
        f"home_price, away_price, home_point, away_point, over_price, under_price, total_point "
        f"FROM {QUOTES} WHERE sport_key = %s "
        f"ORDER BY event_id, bookmaker, market, snapshot_ts DESC", (key,)).fetchall()
    return {(r[0], r[1], r[2]): tuple(r[3:]) for r in rows}


def held_snapshots(conn, key: str) -> set:
    rows = conn.execute(f"SELECT snapshot_ts FROM {FETCHES} WHERE source = %s "
                        f"AND sport_key = %s AND snapshot_ts IS NOT NULL", (SOURCE, key)).fetchall()
    return {r[0] for r in rows}


def held_asks(conn, key: str) -> dict:
    """Every ask this purchase already made for `key`: asked time -> (the
    snapshot the feed answered with, its next snapshot). A resumed walk replays
    these from the ledger without calling the feed, so it pays for nothing
    twice. Measured cost of not doing this: 30 credits a held hour, because the
    first group's answer was the only way to see the hour was held."""
    rows = conn.execute(f"SELECT asked_ts, max(snapshot_ts), max(next_ts) FROM {FETCHES} "
                        f"WHERE source = %s AND sport_key = %s AND endpoint = 'odds' "
                        f"GROUP BY asked_ts", (SOURCE, key)).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def walk_window(conn, meter: Meter, key: str, start: datetime, end: datetime,
                step: timedelta) -> dict:
    """Bulk snapshots of one key from `start` to `end`, one ask per `step`, each
    ask moved forward to the feed's next real snapshot when the feed kept none
    in between (never paying twice for one snapshot). Each answer is stored in
    the same transaction as its ledger row. An ask already in the ledger is
    replayed from it, not asked again: if a run stopped between the two book
    groups of one ask, that ask's second group is not re-bought (at most one
    snapshot's second group per stop)."""
    ensure_tables(conn)
    last = _last_values(conn, key)
    held = held_snapshots(conn, key)
    done = held_asks(conn, key)
    params_base = {"apiKey": _key(), "markets": ",".join(MARKETS), "oddsFormat": "american"}
    t, asks, stored, empty, replayed = start, 0, 0, 0, 0
    prev_snap = None
    while t <= end:
        if t in done:
            snap, nxt_snap = done[t]
            replayed += 1
            prev_snap = snap
            nxt = t + step
            if nxt_snap is not None and nxt_snap > nxt:
                nxt = nxt_snap
            t = nxt
            continue
        rows_total = 0
        snap = nxt_snap = None
        for gi, group in enumerate(BOOK_GROUPS):
            params = {**params_base, "date": _iso(t), "bookmakers": ",".join(group)}
            r, credits = _get(meter, f"{BASE}/historical/sports/{key}/odds", params, cost=30)
            asks += 1
            j = r.json() if r.status_code == 200 else {"error": r.status_code, "data": []}
            snap = _parse_ts(j.get("timestamp"))
            if gi == 0:
                nxt_snap = _parse_ts(j.get("next_timestamp"))
            _ledger(conn, "odds", key, t, j, credits, meter.remaining, None)
            if gi == 0 and snap is not None and (snap in held or snap == prev_snap):
                conn.commit()
                break                       # this snapshot is already bought
            rows = quote_rows(key, j)
            fresh = []
            for row in rows:
                k3 = (row[1], row[5], row[6])
                if last.get(k3) != row[_VALUE]:
                    last[k3] = row[_VALUE]
                    fresh.append(row)
            if fresh:
                conn.executemany(_QUOTE_INSERT, fresh)
            conn.commit()
            rows_total += len(fresh)
            if not (j.get("data") or []):
                empty += 1
        stored += rows_total
        prev_snap = snap
        nxt = t + step
        # The feed kept nothing between this snapshot and its next one: ask at
        # the next one itself rather than paying an hour at a time for a copy.
        if nxt_snap is not None and nxt_snap > nxt:
            nxt = nxt_snap
        if snap is not None:
            held.add(snap)
        logger.info(f"{key} asked {_iso(t)} got {snap and _iso(snap)} rows {rows_total} "
                    f"spent {meter.spent:,} left {meter.remaining}")
        t = nxt
    return {"key": key, "asks": asks, "rows": stored, "empty": empty, "replayed": replayed,
            "spent": meter.spent}


# The plan reset to 15,000,000 credits on 2026-11-08 (odds_api_quota: used
# 19,666 that day against 4,630,560 the day before, total 15M from then); the
# earlier cycles reset on the 1st. Which day the next reset falls on is not
# measured, so the floor assumes the later one.
DEFAULT_RESET = date(2026, 12, 8)


def credit_floor(conn, reset: date, reserve_days: int) -> int:
    """What the account must keep: the measured daily burn
    (odds_quota.daily_burn, a median over its lookback) for every day to the
    reset, plus `reserve_days` more. Refuses to guess when no burn is stored."""
    from data.ingestors.odds_quota import daily_burn
    burn = daily_burn(conn)
    if not burn:
        raise SystemExit("no measured burn in odds_api_quota: pass --floor explicitly")
    days = max((reset - datetime.now(timezone.utc).date()).days, 0) + reserve_days
    return int(burn * days)


# ── the forward log: every active tennis key, from today ─────────────────────

def poll_live(conn, meter: Meter, keys: list[str]) -> int:
    """One pass of the live endpoint for `keys`, both book groups, stored
    change-only like the history (snapshot_ts is the fetch time). In-play
    quotes are stored too; every reader bounds on the listed start."""
    params_base = {"apiKey": _key(), "markets": ",".join(MARKETS), "oddsFormat": "american"}
    stored = 0
    for key in keys:
        last = _last_values(conn, key)
        for group in BOOK_GROUPS:
            asked = datetime.now(timezone.utc).replace(microsecond=0)
            r, credits = _get(meter, f"{BASE}/sports/{key}/odds",
                              {**params_base, "bookmakers": ",".join(group)}, cost=6)
            data = r.json() if r.status_code == 200 else []
            body = {"timestamp": _iso(asked), "data": data if isinstance(data, list) else []}
            _ledger(conn, "live", key, asked, body, credits, meter.remaining, None)
            fresh = []
            for row in quote_rows(key, body):
                k3 = (row[1], row[5], row[6])
                if last.get(k3) != row[_VALUE]:
                    last[k3] = row[_VALUE]
                    fresh.append(row)
            if fresh:
                conn.executemany(_QUOTE_INSERT, fresh)
            conn.commit()
            stored += len(fresh)
    return stored


def active_keys() -> list[str]:
    r = requests.get(f"{BASE}/sports", params={"apiKey": _key()}, timeout=60)
    r.raise_for_status()
    return sorted(s["key"] for s in r.json() if s["key"].startswith("tennis_") and s.get("active"))


def load_windows(path: str, pad_before: timedelta = timedelta(0)) -> list[dict]:
    """The sweep's windows, newest first: [{key, year, start, end}]."""
    with open(path, encoding="utf-8") as fh:
        items = json.load(fh)
    out = []
    for w in items:
        if not w.get("first") or not w.get("last"):
            continue
        out.append({"key": w["key"], "year": w["year"],
                    "start": _parse_ts(w["first"]) - pad_before,
                    "end": _parse_ts(w["last"])})
    return sorted(out, key=lambda w: w["end"], reverse=True)


def shard(windows: list[dict], spec: str | None) -> list[dict]:
    """`i/n`: every n-th window from the i-th (0-based), so n processes split
    the purchase and each one's ceiling is its own share of the plan."""
    if not spec:
        return windows
    i, n = (int(x) for x in spec.split("/"))
    if not 0 <= i < n:
        raise SystemExit(f"--shard {spec}: need 0 <= i < n")
    return windows[i::n]


def spent_on(conn, windows: list[dict]) -> int:
    """Credits the ledger shows this purchase spent inside `windows`."""
    total = 0
    for w in windows:
        r = conn.execute(f"SELECT coalesce(sum(credits), 0) FROM {FETCHES} WHERE source = %s "
                         f"AND sport_key = %s AND asked_ts BETWEEN %s AND %s",
                         (SOURCE, w["key"], w["start"], w["end"])).fetchone()
        total += int(r[0])
    return total


def wait_for_exit(pid: int, poll_s: float = 30.0) -> None:
    """Block until process `pid` has exited (any reason: done, the floor, a
    lost connection). A pid that is not running returns at once."""
    import psutil
    while True:
        try:
            proc = psutil.Process(pid)
            if proc.status() == psutil.STATUS_ZOMBIE:
                return
        except psutil.NoSuchProcess:
            return
        time.sleep(poll_s)


def plan(windows: list[dict], step: timedelta) -> dict:
    """The most this purchase can bill: every step of every window, both book
    groups. Gaps the feed did not keep are jumped, so the real bill is lower."""
    asks = 0
    for w in windows:
        asks += int((w["end"] - w["start"]) / step) + 1
    return {"windows": len(windows), "asks": asks,
            "max_credits": asks * CREDITS_PER_SNAPSHOT}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Tennis odds history -> Supabase")
    ap.add_argument("--sweep", nargs=2, type=int, metavar=("FIRST", "LAST"))
    ap.add_argument("--keys", nargs="*")
    ap.add_argument("--window", nargs=3, metavar=("KEY", "START", "END"))
    ap.add_argument("--step-min", type=int, default=60)
    ap.add_argument("--max-credits", type=int, help="this run's ceiling (required to spend)")
    ap.add_argument("--floor", type=int, help="override the computed floor")
    ap.add_argument("--reset-date", default=DEFAULT_RESET.isoformat(),
                    help="the credit plan's next reset (the later of the two candidates)")
    ap.add_argument("--reserve-days", type=int, default=7)
    ap.add_argument("--live-until", help="poll every active tennis key until this UTC time")
    ap.add_argument("--plan", help="the sweep's JSON: print the purchase's ceiling")
    ap.add_argument("--buy", help="the sweep's JSON: walk every window, newest first")
    ap.add_argument("--shard", help="i/n: this process buys every n-th window from the i-th")
    ap.add_argument("--after-pid", type=int,
                    help="wait for this process to exit, then continue its shard")
    ap.add_argument("--share", type=int,
                    help="this shard's share of the plan: the ceiling becomes the share minus "
                         "what the ledger shows already spent on the shard's windows")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    step = timedelta(minutes=a.step_min)
    if a.plan:
        print(json.dumps(plan(shard(load_windows(a.plan), a.shard), step)))
        return 0
    if not a.max_credits and not a.share:
        raise SystemExit("--max-credits (or --share) is required for any call that spends")
    if a.after_pid:
        logger.info(f"waiting for process {a.after_pid} to exit")
        wait_for_exit(a.after_pid)
        logger.info(f"process {a.after_pid} has exited; continuing")
    import psycopg2
    from data.db import ConnectionLost, get_connection
    LOST = (ConnectionLost, psycopg2.OperationalError, psycopg2.InterfaceError)
    conn = get_connection()
    ensure_tables(conn)
    floor = a.floor if a.floor is not None else credit_floor(
        conn, date.fromisoformat(a.reset_date), a.reserve_days)
    logger.info(f"credit floor {floor:,}")
    if a.share:
        if not a.buy:
            raise SystemExit("--share needs --buy")
        a.max_credits = max(a.share - spent_on(conn, shard(load_windows(a.buy), a.shard)), 0)
        logger.info(f"ceiling {a.max_credits:,}: share {a.share:,} minus the ledger's spend")
    meter = Meter(a.max_credits, floor)
    result = []
    try:
        if a.sweep:
            keys = a.keys or tennis_keys()
            for key in keys:
                for y in range(a.sweep[0], a.sweep[1] + 1):
                    for w in sweep_key_year(conn, meter, key, y):
                        result.append(w)
                        logger.info(json.dumps(w))
        if a.buy:
            for w in shard(load_windows(a.buy), a.shard):
                for attempt in range(6):
                    try:
                        result.append(walk_window(conn, meter, w["key"], w["start"], w["end"], step))
                        break
                    except LOST as exc:
                        # The database dropped the connection (shard 5 stopped
                        # on this, 2026-11-13 11:58 ET). Reconnect and resume the
                        # window from the ledger: the ask whose commit was lost
                        # is not in it, so it is the one asked again.
                        logger.warning(f"{w['key']}: connection lost ({exc}); "
                                       f"resuming, attempt {attempt + 1}")
                        time.sleep(30)
                        try:
                            conn.close()
                        except Exception:                       # noqa: BLE001
                            pass
                        conn = get_connection()
                else:
                    raise SystemExit(f"{w['key']}: six connection losses in a row")
                logger.info(json.dumps(result[-1]))
        if a.live_until:
            until = datetime.fromisoformat(a.live_until).replace(tzinfo=timezone.utc)
            while datetime.now(timezone.utc) < until:
                keys = active_keys()
                n = poll_live(conn, meter, keys)
                logger.info(f"live {keys}: {n} new quotes, spent {meter.spent:,}, "
                            f"left {meter.remaining}")
                time.sleep(a.step_min * 60)
        if a.window:
            key, s, e = a.window
            start = datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(e).replace(tzinfo=timezone.utc)
            result.append(walk_window(conn, meter, key, start, end, step))
    except Floor as exc:
        logger.warning(f"stopped: {exc}")
    finally:
        conn.close()
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=1)
    print(json.dumps({"spent": meter.spent, "remaining": meter.remaining,
                      "items": len(result)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
