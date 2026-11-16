"""Buy back the line-shop odds history the cleanup removed (#1384).

mike, 2026-11-15: "we might as well do all of it from odds api", and on the
build: "Yes, build it". From 2026-08-15 to 2026-11-14 `data/prune_odds.py`
cut every book except DraftKings (and, for props, the sharp book) down to an
opener and a close for games more than 2 days old. This puts the middle back,
from The Odds API historical endpoints.

WHEN IT BUYS. At the moments the all-books refresh actually ran:
`pipeline_runs` rows of kind `hourly` and `evening`, rounded up to the API's
5-minute snapshots. Not at DraftKings' own capture times: most DraftKings rows
come from DraftKings-only pollers (NFL 2026-10, 25,270 DraftKings timestamps,
29 shared with another book, measured on the PC copy 2026-11-15), so those
times were never times the other books were fetched. Before 2026-08-27, where
the run log starts, the plan uses one snapshot an hour (BEFORE_LOG_EVERY).

WHAT IT BUYS, per game. Only a game the cleanup thinned (the other books hold
at most THIN_MAX_ROWS rows per line, while DraftKings holds more), only the
books that game was stored with, only the markets it was stored with, and only
strictly between the other books' stored opener and stored close, before the
start. The opener and close rows that survived stay the only ones at those
moments, the close stays the close, and a back-dated insert does not move the
latest-line tables (their triggers keep the newer row,
data/migrations/latest_line_state_tables.sql).

WHERE THE PLAN COMES FROM. The PC copy, through betting.duckdb
(scripts/local_mirror_duckdb.py): no load on Supabase and no egress. The
buyer writes to Supabase, which is the record.

WHAT A ROW CARRIES. Game odds: `source = 'odds_api_rebuy'`, protected by name
in data/prune_odds.py. Props (the table has no source column): the ledger
`odds_rebuy_requests` names every request, its served snapshot and the games
it filled, so every bought prop row is (game_id, snapshot_at = served_at,
bookmaker <> draftkings) of a ledger row. No `games` row is ever written. No
links or selection ids are requested (a finished game's betslip link is dead,
and they are most of a stored prop row's bytes).

ONLY MOVES ARE STORED. A book's row is written where its price or line
changed since that book's previous known price for the proposition (the
stored opener, then each row bought after it), the rule the cleanup's repeat
thinning kept. Measured on the first test day (NHL 2026-10-14): 978 of 1,051
game-odds rows bought for one game repeated the row before, because the feed's
last_update keeps ticking while a price stands still.

SAFE TO RE-RUN. A request already in the ledger is skipped. The insert and its
ledger row commit together. The ceiling is the plan's own credit total
(odds_quota.plan_credit_budget), and the run refuses to start if it would
leave less than the measured reserve.

    python -m data.ingestors.odds_rebuy plan --kind game --sport NHL --start 2026-10-01 --end 2026-11-12
    python -m data.ingestors.odds_rebuy buy  --kind game --sport NHL --start 2026-10-01 --end 2026-11-12 --limit 1
    python -m data.ingestors.odds_rebuy compare --sport NBA --at 2026-11-12T23:20:00Z
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

REBUY_SOURCE = "odds_api_rebuy"
DEFAULT_COPY_DB = r"C:\Users\micha\Documents\betting_local_copies\betting.duckdb"
DK = "draftkings"
GAME_MARKETS = ("h2h", "spreads", "totals")
THIN_MAX_ROWS = 3          # other-book rows per line at or under this = thinned
CLEANUP_START = "2026-08-15"
CLEANUP_STOP = "2026-11-14"
RUN_LOG_START = "2026-08-27T22:20:00+00:00"   # first pipeline_runs refresh row
BEFORE_LOG_EVERY = timedelta(hours=1)
SNAP = timedelta(minutes=5)
MAX_BOOKS_ONE_REGION = 10  # every 10 bookmakers bill as one region
REQUEST_SLEEP = 0.3
_ET = ZoneInfo("America/New_York")

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS odds_rebuy_requests (
    kind          TEXT        NOT NULL,
    sport         TEXT        NOT NULL,
    event_key     TEXT        NOT NULL,
    requested_at  TIMESTAMPTZ NOT NULL,
    served_at     TIMESTAMPTZ,
    markets       TEXT        NOT NULL,
    books         TEXT        NOT NULL,
    games         TEXT        NOT NULL,
    credits       INTEGER,
    rows_written  INTEGER     NOT NULL,
    dk_checked    INTEGER,
    dk_matched    INTEGER,
    pulled_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (kind, sport, event_key, requested_at)
)
"""
LEDGER_COLUMNS = ("kind", "sport", "event_key", "requested_at", "served_at", "markets",
                  "books", "games", "credits", "rows_written", "dk_checked", "dk_matched",
                  "pulled_at")


@dataclass
class Request:
    kind: str                      # 'game' | 'prop'
    sport: str
    at: datetime                   # UTC, on the 5-minute grid
    games: list[str]               # game ids this request fills
    starts: dict[str, datetime]    # game id -> start (UTC)
    markets: list[str]
    books: list[str]               # non-DraftKings books to store
    snapshot_type: str = "open"
    event_key: str = ""            # '' for game odds; the game id for props
    windows: dict = field(default_factory=dict)  # game id -> (stored opener, stored close)

    @property
    def est_credits(self) -> int:
        # 10 x markets per request (one region); a prop request also lists
        # events once per game (1 credit), counted on the game's first request.
        return 10 * len(self.markets)

    def key(self) -> tuple:
        return (self.kind, self.sport, self.event_key, self.at)


# ── Planning, on the PC copy ─────────────────────────────────────────────────

def _ceil_snap(ts: datetime) -> datetime:
    ts = ts.astimezone(timezone.utc)
    floor = ts.replace(second=0, microsecond=0) - timedelta(minutes=ts.minute % 5)
    return floor if floor == ts else floor + SNAP


def pass_times(con, start: datetime, end: datetime) -> list[datetime]:
    """The all-books refresh moments in [start, end], on the 5-minute grid."""
    log_start = datetime.fromisoformat(RUN_LOG_START)
    rows = con.execute("""
        SELECT DISTINCT epoch(try_cast(started_at AS TIMESTAMPTZ)) FROM pipeline_runs
         WHERE run_kind IN ('hourly', 'evening')
           AND try_cast(started_at AS TIMESTAMPTZ) BETWEEN to_timestamp(?) AND to_timestamp(?)""",
        [start.timestamp(), end.timestamp()]).fetchall()
    out = {_ceil_snap(_from_epoch(r[0])) for r in rows if r[0] is not None}
    t = _ceil_snap(start)
    while t < min(end, log_start):
        out.add(t)
        t += BEFORE_LOG_EVERY
    return sorted(out)


def _utc(x) -> datetime:
    return x.astimezone(timezone.utc) if x.tzinfo else x.replace(tzinfo=timezone.utc)


def _from_epoch(x) -> datetime | None:
    # DuckDB returns TIMESTAMPTZ to Python through pytz; epoch seconds avoid it.
    return None if x is None else datetime.fromtimestamp(float(x), tz=timezone.utc)


_GAME_PLAN_SQL = f"""
WITH g AS (
  SELECT game_id, try_cast(commence_time AS TIMESTAMPTZ) AS start
    FROM games WHERE sport = ?
     AND try_cast(commence_time AS TIMESTAMPTZ) BETWEEN to_timestamp(?) AND to_timestamp(?)),
o AS (
  SELECT o.game_id, o.market, o.bookmaker, o.snapshot_type,
         try_cast(o.snapshot_at AS TIMESTAMPTZ) AS ts, g.start
    FROM odds o JOIN g USING (game_id)
   WHERE coalesce(o.snapshot_type, '') <> 'in_play' AND coalesce(o.source, '') = ''
     AND o.market IN {GAME_MARKETS})
SELECT game_id, epoch(any_value(start)) AS start,
       count(*) FILTER (WHERE bookmaker = '{DK}')
         / nullif(count(DISTINCT market) FILTER (WHERE bookmaker = '{DK}'), 0) AS dk_per_line,
       count(*) FILTER (WHERE bookmaker <> '{DK}')
         / nullif(count(DISTINCT market || bookmaker) FILTER (WHERE bookmaker <> '{DK}'), 0) AS other_per_line,
       epoch(min(ts) FILTER (WHERE bookmaker <> '{DK}')) AS opener,
       epoch(max(ts) FILTER (WHERE bookmaker <> '{DK}' AND ts <= start)) AS close,
       list(DISTINCT bookmaker) FILTER (WHERE bookmaker <> '{DK}') AS books,
       list(DISTINCT market) FILTER (WHERE bookmaker <> '{DK}') AS markets,
       'open' AS snapshot_type
  FROM o GROUP BY game_id
"""

_PROP_PLAN_SQL = f"""
WITH g AS (
  SELECT game_id, try_cast(commence_time AS TIMESTAMPTZ) AS start
    FROM games WHERE sport = ?
     AND try_cast(commence_time AS TIMESTAMPTZ) BETWEEN to_timestamp(?) AND to_timestamp(?)),
p AS (
  SELECT p.game_id, p.market, p.player_name, p.bookmaker, p.snapshot_type,
         try_cast(p.snapshot_at AS TIMESTAMPTZ) AS ts, g.start
    FROM player_prop_odds p JOIN g USING (game_id)
   WHERE p.bookmaker <> 'pinnacle')
SELECT game_id, epoch(any_value(start)) AS start,
       count(*) FILTER (WHERE bookmaker = '{DK}')
         / nullif(count(DISTINCT market || player_name) FILTER (WHERE bookmaker = '{DK}'), 0) AS dk_per_line,
       count(*) FILTER (WHERE bookmaker <> '{DK}')
         / nullif(count(DISTINCT market || player_name || bookmaker)
                  FILTER (WHERE bookmaker <> '{DK}'), 0) AS other_per_line,
       epoch(min(ts) FILTER (WHERE bookmaker <> '{DK}')) AS opener,
       epoch(max(ts) FILTER (WHERE bookmaker <> '{DK}' AND ts <= start)) AS close,
       list(DISTINCT bookmaker) FILTER (WHERE bookmaker <> '{DK}') AS books,
       list(DISTINCT market) FILTER (WHERE bookmaker <> '{DK}') AS markets,
       'open' AS snapshot_type
  FROM p GROUP BY game_id
"""


def thinned_games(con, kind: str, sport: str, start: str, end: str) -> list[dict]:
    sql = _GAME_PLAN_SQL if kind == "game" else _PROP_PLAN_SQL
    lo = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)
    hi = datetime.fromisoformat(end).replace(tzinfo=timezone.utc) + timedelta(days=1)
    cols = ("game_id", "start", "dk_per_line", "other_per_line", "opener", "close",
            "books", "markets", "snapshot_type")
    out = []
    for row in con.execute(sql, [sport, lo.timestamp(), hi.timestamp()]).fetchall():
        g = dict(zip(cols, row))
        if (g["other_per_line"] is None or g["dk_per_line"] is None
                or g["other_per_line"] > THIN_MAX_ROWS or g["dk_per_line"] <= THIN_MAX_ROWS
                or g["opener"] is None or g["close"] is None or g["start"] is None):
            continue
        g["start"], g["opener"], g["close"] = (_from_epoch(g["start"]), _from_epoch(g["opener"]),
                                               _from_epoch(g["close"]))
        g["books"] = sorted(b for b in (g["books"] or []) if b and b != DK)
        g["markets"] = sorted(m for m in (g["markets"] or []) if m)
        out.append(g)
    return out


def plan(con, kind: str, sport: str, start: str, end: str) -> list[Request]:
    """Every request that would fill the thinned games of one sport, in time order."""
    games = thinned_games(con, kind, sport, start, end)
    if not games:
        return []
    lo = min(g["opener"] for g in games)
    hi = max(g["close"] for g in games)
    times = pass_times(con, lo, hi)
    if kind == "prop":
        reqs = []
        for g in games:
            upper = min(g["close"], g["start"])
            for t in times:
                if g["opener"] < t < upper:
                    reqs.append(Request("prop", sport, t, [g["game_id"]],
                                        {g["game_id"]: g["start"]}, g["markets"],
                                        g["books"][:MAX_BOOKS_ONE_REGION - 1],
                                        "open", g["game_id"],
                                        {g["game_id"]: (g["opener"], g["close"])}))
        return sorted(reqs, key=lambda r: (r.at, r.event_key))
    by_time: dict[datetime, list[dict]] = {}
    for t in times:
        live = [g for g in games if g["opener"] < t < min(g["close"], g["start"])]
        if live:
            by_time[t] = live
    reqs = []
    for t, live in sorted(by_time.items()):
        books = sorted({b for g in live for b in g["books"]})[:MAX_BOOKS_ONE_REGION - 1]
        markets = sorted({m for g in live for m in g["markets"]})
        reqs.append(Request("game", sport, t, [g["game_id"] for g in live],
                            {g["game_id"]: g["start"] for g in live}, markets, books,
                            "open", "", {g["game_id"]: (g["opener"], g["close"]) for g in live}))
    return reqs


def summarize(reqs: list[Request]) -> dict:
    games = {g for r in reqs for g in r.games}
    events = {r.event_key for r in reqs if r.kind == "prop"}
    return {"requests": len(reqs), "games": len(games),
            "credits": sum(r.est_credits for r in reqs) + len(events),
            "first": min(r.at for r in reqs).isoformat() if reqs else None,
            "last": max(r.at for r in reqs).isoformat() if reqs else None}


# ── The API ──────────────────────────────────────────────────────────────────

def _api_get(path: str, params: dict):
    from config import ODDS_API_BASE, ODDS_API_KEY
    from data.ingestors.odds_quota import record_quota_headers
    if not ODDS_API_KEY:
        raise ValueError("ODDS_API_KEY is not set")
    resp = requests.get(f"{ODDS_API_BASE}{path}", params={"apiKey": ODDS_API_KEY, **params},
                        timeout=30)
    record_quota_headers(resp)
    credits = resp.headers.get("x-requests-last")
    return resp, (int(float(credits)) if credits not in (None, "") else None)


def _iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch_game_snapshot(sport: str, at: datetime, markets, books):
    from data.ingestors.odds_ingestor import SPORT_KEYS
    resp, credits = _api_get(f"/historical/sports/{SPORT_KEYS[sport]}/odds", {
        "date": _iso(at), "markets": ",".join(markets),
        "bookmakers": ",".join([DK, *books]), "oddsFormat": "american"})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    return body.get("data", []) or [], body.get("timestamp"), credits


def fetch_events(sport: str, at: datetime):
    from data.ingestors.odds_ingestor import SPORT_KEYS
    resp, credits = _api_get(f"/historical/sports/{SPORT_KEYS[sport]}/events",
                             {"date": _iso(at), "dateFormat": "iso"})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    return resp.json().get("data", []) or [], credits


def fetch_event_props(sport: str, event_id: str, at: datetime, markets, books):
    from data.ingestors.odds_ingestor import SPORT_KEYS
    resp, credits = _api_get(
        f"/historical/sports/{SPORT_KEYS[sport]}/events/{event_id}/odds",
        {"date": _iso(at), "markets": ",".join(markets),
         "bookmakers": ",".join([DK, *books]), "oddsFormat": "american"})
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
    body = resp.json()
    data = body.get("data", {}) or {}
    return data.get("bookmakers", []) or [], body.get("timestamp"), credits


def _event_game_id(sport: str, ev: dict, conn) -> str | None:
    """Our game id for an Odds API event, with the same rule each prop ingestor uses."""
    from data.ingestors.odds_ingestor import _build_game_id, _normalize_team
    commence = ev.get("commence_time", "")
    try:
        kick = datetime.fromisoformat(commence.replace("Z", "+00:00"))
    except ValueError:
        return None
    game_date = kick.astimezone(_ET).strftime("%Y-%m-%d")
    if sport == "NFL":
        from data.ingestors.nfl_prop_odds_ingestor import _load_nfl_games, resolve_nfl_game_id
        d = kick.date()
        games = _load_nfl_games(conn, (d - timedelta(days=2)).isoformat(),
                                (d + timedelta(days=2)).isoformat())
        hit = resolve_nfl_game_id(games, ev.get("home_team", ""), ev.get("away_team", ""), commence)
        return hit[0] if hit else None
    if sport == "NCAAF":
        from data.ingestors.cfbd_ingestor import build_ncaaf_game_id, resolve_odds_api_school
        return build_ncaaf_game_id(game_date, resolve_odds_api_school(ev["away_team"], conn),
                                   resolve_odds_api_school(ev["home_team"], conn))
    return _build_game_id(sport, game_date, _normalize_team(ev.get("away_team", ""), sport),
                          _normalize_team(ev.get("home_team", ""), sport))


# ── Rows ─────────────────────────────────────────────────────────────────────

def game_rows(req: Request, events: list[dict], served: str, conn=None) -> tuple[list, list]:
    """(rows to store, DraftKings rows for the check) from one game-odds snapshot."""
    from data.ingestors.odds_ingestor import (RESOLVE_ONLY_SPORTS, _process_events,
                                              _schedule_resolver)
    resolver = None
    if req.sport in RESOLVE_ONLY_SPORTS:
        resolver = _schedule_resolver(req.sport, conn, served[:10])
    _games, rows = _process_events(events, req.sport, req.snapshot_type, served,
                                   resolve_game_id=resolver)
    served_t = datetime.fromisoformat(served.replace("Z", "+00:00"))
    keep, dk = [], []
    wanted, books, markets = set(req.games), set(req.books), set(req.markets)
    for r in rows:
        if r.get("game_id") not in wanted or r.get("market") not in markets:
            continue
        if served_t >= req.starts[r["game_id"]]:
            continue
        if r.get("bookmaker") == DK:
            dk.append(r)
            continue
        if r.get("bookmaker") not in books:
            continue
        # The feed stamps a game-odds row with the book's own last change
        # (`_process_events`: snapshot_at = the market's last_update). A change
        # at or before the stored opener, or at or after the stored close, is
        # already a stored row; only a move between them is missing.
        changed = _parse_ts(r.get("snapshot_at"))
        window = req.windows.get(r["game_id"])
        if window and changed is not None and not (window[0] < changed < window[1]):
            continue
        keep.append({**r, "source": REBUY_SOURCE})
    return keep, dk


def _parse_ts(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return _utc(v)
    try:
        return _utc(datetime.fromisoformat(str(v).replace("Z", "+00:00")))
    except ValueError:
        return None


def _gkey(r: dict) -> tuple:
    return (r["game_id"], r["market"], r["bookmaker"], str(r["snapshot_at"]))


_STORED_GAME_OPENERS_SQL = f"""
SELECT game_id, market, bookmaker, {", ".join(("home_price", "away_price", "spread_home",
                                              "total_line", "over_price", "under_price"))}
  FROM odds
 WHERE game_id IN (SELECT unnest(?)) AND bookmaker <> '{DK}'
   AND coalesce(snapshot_type, '') <> 'in_play' AND coalesce(source, '') = ''
   AND try_cast(snapshot_at AS TIMESTAMPTZ) <= to_timestamp(?)
QUALIFY row_number() OVER (PARTITION BY game_id, market, bookmaker
                           ORDER BY try_cast(snapshot_at AS TIMESTAMPTZ) DESC) = 1
"""


def _game_price(r: dict) -> tuple:
    return tuple(None if r.get(k) is None else float(r[k]) for k in
                 ("home_price", "away_price", "spread_home", "total_line",
                  "over_price", "under_price"))


def drop_unchanged_game_rows(copy_con, req: Request, rows: list[dict], last: dict) -> list[dict]:
    """Keep a book's game-odds row only where its price or line moved since the
    book's previous known price: the row bought before it in this run (`last`),
    else the stored opener in the PC copy, read once per game. The feed's
    last_update keeps ticking while a price stands still (978 of 1,051 rows
    bought for one NHL game on the first test day repeated the row before), so
    the price is the change signal, not the time."""
    new_games = sorted({r["game_id"] for r in rows} - set(last))
    for gid in new_games:
        last[gid] = {}
    if new_games and copy_con is not None:
        for g, m, b, *price in copy_con.execute(
                _STORED_GAME_OPENERS_SQL, [new_games, req.at.timestamp()]).fetchall():
            last[g][(m, b)] = tuple(None if v is None else float(v) for v in price)
    out = []
    for r in rows:
        k, p = (r["market"], r["bookmaker"]), _game_price(r)
        if last[r["game_id"]].get(k) == p:
            continue
        last[r["game_id"]][k] = p
        out.append(r)
    return out


def drop_stored_game_rows(conn, rows: list[dict], seen: set) -> list[dict]:
    """Drop game-odds rows already stored: the same book's same change
    (game, market, book, snapshot_at) bought by an earlier request in this run
    (`seen`), or already in Supabase (an earlier run). Two requests an hour apart
    return the same row when the book did not move; it is stored once."""
    fresh, batch = [], set()
    for r in rows:
        k = _gkey(r)
        if k in seen or k in batch:
            continue
        batch.add(k)
        fresh.append(r)
    if fresh and conn is not None:
        have = conn.execute("""
            SELECT game_id, market, bookmaker, snapshot_at FROM odds
             WHERE game_id = ANY(%s) AND bookmaker = ANY(%s) AND snapshot_at = ANY(%s)""",
            (sorted({r["game_id"] for r in fresh}), sorted({r["bookmaker"] for r in fresh}),
             sorted({str(r["snapshot_at"]) for r in fresh}))).fetchall()
        have = {(g, m, b, str(t)) for g, m, b, t in have}
        fresh = [r for r in fresh if _gkey(r) not in have]
    seen.update(_gkey(r) for r in fresh)
    return fresh


def prop_rows(req: Request, bookmakers: list, served: str) -> tuple[list, list]:
    from data.ingestors.prop_odds_ingestor import _parse_prop_markets
    game_id = req.event_key
    if datetime.fromisoformat(served.replace("Z", "+00:00")) >= req.starts[game_id]:
        return [], []
    game_date = req.starts[game_id].astimezone(_ET).strftime("%Y-%m-%d")
    keep, dk = [], []
    for bk in bookmakers:
        key = bk.get("key", "")
        if key != DK and key not in req.books:
            continue
        rows = _parse_prop_markets(bk.get("markets", []), game_id, game_date,
                                   req.snapshot_type, served,
                                   allowed_markets=set(req.markets), bookmaker=key,
                                   book_last_update=bk.get("last_update"))
        (dk if key == DK else keep).extend(rows)
    return keep, dk


def _prop_key(r: dict) -> tuple:
    # An alternate market holds one row per line, so the line is part of what
    # the proposition IS; a standard market's line is part of its price.
    line = r.get("line") if str(r.get("market", "")).endswith("_alternate") else None
    return (r["market"], r["player_name"], r["bookmaker"],
            None if line is None else float(line))


def _prop_price(r: dict) -> tuple:
    return tuple(None if r.get(k) is None else float(r[k])
                 for k in ("line", "over_price", "under_price"))


_LAST_STORED_PROPS_SQL = r"""
SELECT market, player_name, bookmaker, line, over_price, under_price
  FROM player_prop_odds
 WHERE game_id = ? AND bookmaker NOT IN ('draftkings', 'pinnacle')
   AND try_cast(snapshot_at AS TIMESTAMPTZ) <= to_timestamp(?)
QUALIFY row_number() OVER (
    PARTITION BY market, player_name, bookmaker,
                 CASE WHEN market LIKE '%alternate' THEN line END
    ORDER BY snapshot_at DESC) = 1
"""


def drop_unchanged_props(copy_con, req: Request, rows: list[dict], last: dict) -> list[dict]:
    """Keep a book's prop row only where it moved since the book's previous
    known price for that proposition: the row bought just before it in this run
    (`last`), else the newest stored row at or before the request in the PC copy
    (the stored opener). The rule the cleanup's repeat thinning kept
    (`prune_odds.thin_repeats`) and the archive design asks of every writer
    (docs/data_archive.md, "Stop writing repeats")."""
    gid = req.event_key
    if gid not in last:
        last[gid] = {}
        if copy_con is not None:
            for row in copy_con.execute(_LAST_STORED_PROPS_SQL,
                                        [gid, req.at.timestamp()]).fetchall():
                r = dict(zip(("market", "player_name", "bookmaker", "line",
                              "over_price", "under_price"), row))
                last[gid][_prop_key(r)] = _prop_price(r)
    out = []
    for r in rows:
        k, p = _prop_key(r), _prop_price(r)
        if last[gid].get(k) == p:
            continue
        last[gid][k] = p
        out.append(r)
    return out


# ── The ledger ───────────────────────────────────────────────────────────────

def ensure_ledger(conn) -> None:
    from data.anon_readable import lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, "odds_rebuy_requests", columns=LEDGER_COLUMNS,
                             rls=True, revoked_from=("anon", "authenticated")):
        conn.execute(LEDGER_DDL)
        lock_down(conn, "odds_rebuy_requests")
        conn.commit()


def done_keys(conn, kind: str, sport: str) -> set:
    rows = conn.execute("SELECT event_key, requested_at FROM odds_rebuy_requests "
                        "WHERE kind = %s AND sport = %s", (kind, sport)).fetchall()
    return {(kind, sport, e, _utc(t)) for e, t in rows}


def _ledger(conn, req: Request, served, credits, n_rows, dk_checked, dk_matched) -> None:
    conn.execute("""
        INSERT INTO odds_rebuy_requests (kind, sport, event_key, requested_at, served_at,
            markets, books, games, credits, rows_written, dk_checked, dk_matched)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (kind, sport, event_key, requested_at) DO NOTHING""",
        (req.kind, req.sport, req.event_key, req.at, served, ",".join(req.markets),
         ",".join(req.books), ",".join(req.games), credits, n_rows, dk_checked, dk_matched))


# ── The DraftKings check ─────────────────────────────────────────────────────

_DK_GAME_SQL = """
SELECT game_id, market, home_price, away_price, spread_home, total_line, over_price, under_price
  FROM odds
 WHERE game_id IN (SELECT unnest(?)) AND bookmaker = 'draftkings'
   AND coalesce(snapshot_type, '') <> 'in_play'
   AND try_cast(snapshot_at AS TIMESTAMPTZ) <= to_timestamp(?)
QUALIFY row_number() OVER (PARTITION BY game_id, market
                           ORDER BY try_cast(snapshot_at AS TIMESTAMPTZ) DESC) = 1
"""
_DK_PROP_SQL = """
SELECT game_id, market, player_name, line, over_price, under_price
  FROM player_prop_odds
 WHERE game_id IN (SELECT unnest(?)) AND bookmaker = 'draftkings'
   AND market NOT LIKE '%alternate'
   AND try_cast(snapshot_at AS TIMESTAMPTZ) <= to_timestamp(?)
QUALIFY row_number() OVER (PARTITION BY game_id, market, player_name
                           ORDER BY try_cast(snapshot_at AS TIMESTAMPTZ) DESC) = 1
"""
_GAME_FIELDS = ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price")
_PROP_FIELDS = ("line", "over_price", "under_price")


def _num(v):
    return None if v is None else float(v)


def dk_agreement(copy_con, kind: str, dk_rows: list[dict], served: str) -> tuple[int, int]:
    """(checked, matched): bought DraftKings prices against the PC copy's newest
    DraftKings row at or before the served snapshot. A cheap proof that the
    snapshot is the market we recorded."""
    if copy_con is None or not dk_rows:
        return 0, 0
    at = _parse_ts(served).timestamp()
    games = sorted({r["game_id"] for r in dk_rows})
    if kind == "game":
        stored = {(g, m): tuple(_num(v) for v in rest)
                  for g, m, *rest in copy_con.execute(_DK_GAME_SQL, [games, at]).fetchall()}
        pairs = [((r["game_id"], r["market"]), tuple(_num(r.get(k)) for k in _GAME_FIELDS))
                 for r in dk_rows]
    else:
        stored = {(g, m, pl): tuple(_num(v) for v in rest)
                  for g, m, pl, *rest in copy_con.execute(_DK_PROP_SQL, [games, at]).fetchall()}
        pairs = [((r["game_id"], r["market"], r["player_name"]),
                  tuple(_num(r.get(k)) for k in _PROP_FIELDS))
                 for r in dk_rows if not str(r.get("market", "")).endswith("_alternate")]
    checked = matched = 0
    for key, theirs in pairs:
        mine = stored.get(key)
        if mine is None:
            continue
        checked += 1
        matched += int(mine == theirs)
    return checked, matched


# ── The buyer ────────────────────────────────────────────────────────────────

def buy(reqs: list[Request], *, conn=None, copy_con=None, write: bool = True,
        limit: int | None = None, max_credits: int | None = None,
        reserve_days: int | None = None, sleep: float = REQUEST_SLEEP, log=logger.info) -> dict:
    """Buy the requests not yet in the ledger. Returns what it did."""
    from data.ingestors.odds_ingestor import _insert_odds
    from data.ingestors.odds_quota import DEFAULT_RESERVE_DAYS, persist_quota, plan_credit_budget
    from data.ingestors.prop_odds_ingestor import _insert_prop_odds

    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    stats = {"requests": 0, "skipped_done": 0, "credits": 0, "rows": 0, "errors": 0,
             "dk_checked": 0, "dk_matched": 0, "stopped": None, "write": write}
    try:
        if write:
            ensure_ledger(conn)
            done = set()
            for kind, sport in {(r.kind, r.sport) for r in reqs}:
                done |= done_keys(conn, kind, sport)
        else:
            done = set()
        todo = [r for r in reqs if r.key() not in done]
        stats["skipped_done"] = len(reqs) - len(todo)
        if limit is not None:
            todo = todo[:limit]
        if not todo:
            return stats
        planned = summarize(todo)["credits"]
        budget, problems = plan_credit_budget(
            conn, shard_calls=len(todo), total_calls=len(todo),
            credits_per_call=math.ceil(planned / len(todo)), max_credits=max_credits,
            reserve_days=DEFAULT_RESERVE_DAYS if reserve_days is None else reserve_days)
        if problems:
            stats["stopped"] = "refused: " + "; ".join(problems)
            return stats
        event_ids: dict[str, str | None] = {}
        seen_game_rows: set = set()
        last_game: dict = {}
        last_props: dict = {}
        for req in todo:
            if stats["credits"] + req.est_credits > budget.ceiling:
                stats["stopped"] = f"ceiling {budget.ceiling:,} reached"
                break
            try:
                spent = 0
                if req.kind == "game":
                    events, served, c = fetch_game_snapshot(req.sport, req.at, req.markets, req.books)
                    spent += c or 0
                    served = served or _iso(req.at)
                    keep, dk = game_rows(req, events, served, conn)
                    keep = drop_unchanged_game_rows(copy_con, req, keep, last_game)
                    keep = drop_stored_game_rows(conn if write else None, keep, seen_game_rows)
                else:
                    gid = req.event_key
                    if gid not in event_ids:
                        evs, c = fetch_events(req.sport, req.at)
                        spent += c or 0
                        event_ids[gid] = next((e["id"] for e in evs
                                               if _event_game_id(req.sport, e, conn) == gid), None)
                    if not event_ids[gid]:
                        raise RuntimeError(f"no Odds API event for {gid} at {_iso(req.at)}")
                    books, served, c = fetch_event_props(req.sport, event_ids[gid], req.at,
                                                         req.markets, req.books)
                    spent += c or 0
                    served = served or _iso(req.at)
                    keep, dk = prop_rows(req, books, served)
                    keep = drop_unchanged_props(copy_con, req, keep, last_props)
                checked, matched = dk_agreement(copy_con, req.kind, dk, served)
                if write:
                    n = (_insert_odds(conn, keep) if req.kind == "game"
                         else _insert_prop_odds(conn, keep)) if keep else 0
                    _ledger(conn, req, served, spent, n, checked, matched)
                    conn.commit()
                else:
                    n = len(keep)
                stats["requests"] += 1
                stats["credits"] += spent
                stats["rows"] += n
                stats["dk_checked"] += checked
                stats["dk_matched"] += matched
                log(f"{req.kind} {req.sport} {_iso(req.at)} served {served}: {n} rows, "
                    f"{spent} credits, DraftKings {matched}/{checked} agree")
            except Exception as exc:  # noqa: BLE001 -- one bad request must not end the run
                stats["errors"] += 1
                logger.warning(f"{req.kind} {req.sport} {_iso(req.at)} failed: {exc}")
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(sleep)
        try:
            persist_quota(conn)
        except Exception:  # noqa: BLE001
            pass
    finally:
        if own:
            conn.close()
    return stats


# ── Ground truth: buy a moment we still hold in full, write nothing, compare ─

def compare(copy_con, sport: str, at: datetime) -> dict:
    """Fetch one game-odds snapshot for a sport and moment the copy still holds
    every book for, and compare each book's price with the copy's row from the
    newest stored row at or before the served time (a stored game-odds row is
    stamped with the book's own last change, so that row is the price in force).
    Writes nothing."""
    games = [r[0] for r in copy_con.execute("""
        SELECT game_id FROM games WHERE sport = ?
           AND try_cast(commence_time AS TIMESTAMPTZ) BETWEEN to_timestamp(?) AND to_timestamp(?)""",
        [sport, at.timestamp(), (at + timedelta(days=2)).timestamp()]).fetchall()]
    books = sorted({r[0] for r in copy_con.execute(f"""
        SELECT DISTINCT bookmaker FROM odds WHERE game_id IN (SELECT unnest(?))
           AND bookmaker <> '{DK}' AND coalesce(source,'') = ''""", [games]).fetchall()})
    books = books[:MAX_BOOKS_ONE_REGION - 1]
    starts = {r[0]: _from_epoch(r[1]) for r in copy_con.execute("""
        SELECT game_id, epoch(try_cast(commence_time AS TIMESTAMPTZ)) FROM games
         WHERE game_id IN (SELECT unnest(?))""", [games]).fetchall()}
    req = Request("game", sport, at, games, starts, list(GAME_MARKETS), books)
    events, served, credits = fetch_game_snapshot(sport, at, req.markets, books)
    served = served or _iso(at)
    keep, _dk = game_rows(req, events, served)
    served_t = datetime.fromisoformat(served.replace("Z", "+00:00"))
    fields = ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price")
    out = {"sport": sport, "served": served, "credits": credits, "bought_rows": len(keep),
           "compared": 0, "matched": 0, "same_change_time": 0, "no_stored_row": 0,
           "by_book": {}}
    for r in keep:
        got = copy_con.execute(f"""
            SELECT {', '.join(fields)}, snapshot_at FROM odds
             WHERE game_id = ? AND market = ? AND bookmaker = ? AND coalesce(source,'') = ''
               AND coalesce(snapshot_type,'') <> 'in_play'
               AND try_cast(snapshot_at AS TIMESTAMPTZ) <= to_timestamp(?)
             ORDER BY try_cast(snapshot_at AS TIMESTAMPTZ) DESC LIMIT 1""",
            [r["game_id"], r["market"], r["bookmaker"], served_t.timestamp()]).fetchone()
        b = out["by_book"].setdefault(r["bookmaker"], [0, 0])
        if got is None:
            out["no_stored_row"] += 1
            continue
        mine = tuple(None if v is None else float(v) for v in got[:6])
        theirs = tuple(None if r.get(k) is None else float(r[k]) for k in fields)
        out["compared"] += 1
        b[0] += 1
        if mine == theirs:
            out["matched"] += 1
            b[1] += 1
        if _parse_ts(got[6]) == _parse_ts(r.get("snapshot_at")):
            out["same_change_time"] += 1
    return out


# ── CLI ──────────────────────────────────────────────────────────────────────

def _copy(path: str):
    import duckdb
    return duckdb.connect(path, read_only=True)


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "buy"):
        p = sub.add_parser(name)
        p.add_argument("--kind", choices=("game", "prop"), required=True)
        p.add_argument("--sport", required=True)
        p.add_argument("--start", default=CLEANUP_START)
        p.add_argument("--end", default=CLEANUP_STOP)
        p.add_argument("--copy-db", default=DEFAULT_COPY_DB)
        if name == "buy":
            p.add_argument("--limit", type=int)
            p.add_argument("--max-credits", type=int)
            p.add_argument("--dry-run", action="store_true",
                           help="fetch and parse, write nothing (still spends credits)")
    c = sub.add_parser("compare")
    c.add_argument("--sport", required=True)
    c.add_argument("--at", required=True)
    c.add_argument("--copy-db", default=DEFAULT_COPY_DB)
    a = ap.parse_args(argv)
    con = _copy(a.copy_db)
    if a.cmd == "compare":
        at = datetime.fromisoformat(a.at.replace("Z", "+00:00"))
        print(json.dumps(compare(con, a.sport.upper(), at), indent=1, default=str))
        return 0
    reqs = plan(con, a.kind, a.sport.upper(), a.start, a.end)
    print(json.dumps(summarize(reqs), indent=1))
    if a.cmd == "plan":
        return 0
    stats = buy(reqs, copy_con=con, write=not a.dry_run, limit=a.limit,
                max_credits=a.max_credits, log=print)
    print(json.dumps(stats, indent=1, default=str))
    return 1 if stats["errors"] or (stats["stopped"] or "").startswith("refused") else 0


if __name__ == "__main__":
    sys.exit(main())
