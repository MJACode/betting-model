"""Buy NFL in-game history from The Odds API into `nfl_odds_history`.

mike, 2026-10-12: "3) yes" -- buy the two purchases docs/nfl_edge_search.md §7
priced, in the same run as they are stored (CLAUDE.md §1b):

  --mode halftime   second-half spreads and totals (`spreads_h2`, `totals_h2`)
                    at halftime, every 2023-2025 game. One historical
                    EVENT-odds call per halftime snapshot: 10 credits x markets
                    returned x regions, so <= 20 a call. Snapshots are taken
                    from the end of the second quarter to the third-quarter
                    kickoff, both read off nflverse play-by-play wall clocks.
                    Plan: ~855 games x ~2-3 snapshots ~= 40-55k credits.
  --mode inplay     full-game h2h / spreads / totals every 5 minutes while a
                    2025 game is in progress (kickoff - 5 min to kickoff +
                    3h45m, the union per day). One bulk historical call per
                    snapshot covers the whole slate: 10 x 3 markets = 30.
                    Plan: ~5,200 snapshots ~= 155-170k credits.

WHERE IT LANDS. `nfl_odds_history`, never pruned (scripts/nfl_odds_backfill.py
explains why not `odds`, whose pruner would thin every non-DraftKings row of a
finished game). Same grain as every other row there -- one row per (served
snapshot, game, book, market) -- with `point` the HOME handicap or the total,
`price_home`/`price_away` home/away or over/under, and lead_hours negative once
the game has started. game_id is the bare nflverse id, as for 2020-2025.

    source = 'historical_h2|ev=<event id>|req=<requested>|served=<served>'
    source = 'historical_inplay|req=<requested>|served=<served>'

RESUME. Every paid call is recorded in `nfl_odds_history_pulls`, including a
call that returned no rows (an event with no second-half market), so a re-run
buys nothing twice. The stored rows are read back by `source LIKE` for the
summary and for the in-play served-snapshot dedupe.

BOOKS. Ten books that share DraftKings' region (config: the us2 books add a
region to every call, measured 2026-09-11), so every call bills one region.

MONEY. `--apply` stops when x-requests-remaining falls under --floor (default
1,000,000: the worker's own month must survive the purchase) or when this run
has spent --max-credits (default: 1.25x the printed plan).

    python -m data.ingestors.nfl_inplay_history --mode halftime --dry-run
    python -m data.ingestors.nfl_inplay_history --probe
    python -m data.ingestors.nfl_inplay_history --mode halftime --apply
    python -m data.ingestors.nfl_inplay_history --mode inplay --season 2025 --apply
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from loguru import logger

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from config import ODDS_API_BASE, ODDS_API_KEY  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ingestors.odds_quota import persist_quota, record_quota_headers  # noqa: E402

SPORT_KEY = "americanfootball_nfl"
BASE = f"{ODDS_API_BASE}/historical/sports/{SPORT_KEY}"
SOURCE_PREFIX = "historical_"            # historical_h2| and historical_inplay|
SRC_H2 = "historical_h2|"
SRC_INPLAY = "historical_inplay|"
# DraftKings' region only: one billing region per call (config._US2_BOOKMAKERS
# would add a second). betonlineag / lowvig are the in-region sharp-ish books.
BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics",
         "bovada", "betonlineag", "lowvig", "mybookieag", "betus")
H2_MARKETS = ("spreads_h2", "totals_h2")
INPLAY_MARKETS = ("h2h", "spreads", "totals")
CREDITS_PER_MARKET = 10
STEP = timedelta(minutes=5)
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"
PBP_DIRS = [Path(os.environ.get("NFL_PBP_DIR", ROOT / "nfl" / "data" / "pbp")),
            Path(os.environ.get("TEMP", "/tmp")) / "nfl_edge"]


# ─── time helpers ──────────────────────────────────────────────────────────

def _ts(s) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _floor5(d: datetime) -> datetime:
    d = d.replace(second=0, microsecond=0)
    return d - timedelta(minutes=d.minute % 5)


# ─── schedule and halftime clocks (free nflverse data) ────────────────────

def schedule(seasons) -> "pd.DataFrame":
    import pandas as pd
    r = requests.get(f"{NFLVERSE}/schedules/games.csv", timeout=120)
    r.raise_for_status()
    g = pd.read_csv(io.BytesIO(r.content), low_memory=False)
    g = g[g["season"].isin(list(seasons)) & g["home_score"].notna()].copy()
    g["kick"] = pd.to_datetime(g["gameday"] + " " + g["gametime"].fillna("13:00")
                               ).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
    return g


def _pbp(season: int) -> "pd.DataFrame":
    import pandas as pd
    cols = ["game_id", "qtr", "time_of_day", "end_clock_time"]
    for d in PBP_DIRS:
        for name in (f"play_by_play_{season}.parquet", f"pbp_{season}.parquet"):
            p = d / name
            if p.exists():
                return pd.read_parquet(p, columns=cols)
    r = requests.get(f"{NFLVERSE}/pbp/play_by_play_{season}.parquet", timeout=600)
    r.raise_for_status()
    return pd.read_parquet(io.BytesIO(r.content), columns=cols)


def halftime_windows(seasons) -> dict:
    """{game_id: (end of Q2, Q3 kickoff)} from play wall clocks.

    End of Q2 = the latest end_clock_time (else time_of_day) of a Q2 play; Q3
    kickoff = the earliest time_of_day of a Q3 play. A game missing either is
    left out and counted, never guessed."""
    import pandas as pd
    out, missing = {}, 0
    for s in seasons:
        p = _pbp(s)
        p = p[p["qtr"].isin([2, 3])].copy()
        p["t"] = pd.to_datetime(p["time_of_day"], utc=True, errors="coerce")
        p["te"] = pd.to_datetime(p["end_clock_time"], utc=True, errors="coerce").fillna(p["t"])
        q2 = p[p["qtr"] == 2].groupby("game_id")["te"].max()
        q3 = p[p["qtr"] == 3].groupby("game_id")["t"].min()
        for gid in set(q2.index) | set(q3.index):
            a, b = q2.get(gid), q3.get(gid)
            if a is None or b is None or pd.isna(a) or pd.isna(b) or b <= a:
                missing += 1
                continue
            out[gid] = (a.to_pydatetime(), b.to_pydatetime())
    logger.info(f"halftime clocks: {len(out)} games, {missing} without a usable clock")
    return out


def halftime_requests(end_q2: datetime, q3_kick: datetime) -> list[datetime]:
    """Request times inside the break. The feed snaps a request to the newest
    snapshot at or before it, so asking at +3 / +8 / +13 ... minutes walks the
    5-minute grid through the break. Stops before the Q3 kickoff."""
    out, t = [], end_q2 + timedelta(minutes=3)
    while t < q3_kick:
        out.append(t)
        t += STEP
    return out[:6]


def inplay_windows(sched) -> list[tuple[datetime, datetime]]:
    """Union of [kickoff - 5 min, kickoff + 3h45m] per day, merged."""
    spans = sorted((k - timedelta(minutes=5), k + timedelta(hours=3, minutes=45))
                   for k in (x.to_pydatetime() for x in sched["kick"]))
    merged: list[list[datetime]] = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return [(_floor5(lo), hi) for lo, hi in merged]


def inplay_requests(windows) -> list[datetime]:
    out = []
    for lo, hi in windows:
        t = lo
        while t <= hi:
            out.append(t)
            t += STEP
    return out


# ─── the feed ──────────────────────────────────────────────────────────────

def _get(url: str, params: dict):
    for i in range(6):
        try:
            resp = requests.get(url, params=params, timeout=60)
        except requests.RequestException as exc:
            logger.warning(f"  {type(exc).__name__}; retry {i + 1}")
            time.sleep(2 ** (i + 1))
            continue
        if resp.status_code == 429:
            time.sleep(5 * (i + 1))
            continue
        record_quota_headers(resp)
        return resp
    return None


def _team_map() -> dict:
    sys.path.insert(0, str(ROOT / "nfl"))
    from nfl.data_ingest.parse import TEAM_MAP
    return TEAM_MAP


def match_events(events: list, sched, team_map) -> dict:
    """{event id: nflverse game row} by home/away abbreviation and the nearest
    kickoff within 36 hours. Unknown names are skipped, never guessed."""
    out = {}
    for ev in events or []:
        h, a = team_map.get(ev.get("home_team")), team_map.get(ev.get("away_team"))
        ct = ev.get("commence_time")
        if not (h and a and ct):
            continue
        c = sched[(sched["home_team"] == h) & (sched["away_team"] == a)]
        if c.empty:
            continue
        dt = (c["kick"] - _ts(ct)).abs()
        if dt.min() > timedelta(hours=36):
            continue
        out[ev["id"]] = c.loc[dt.idxmin()]
    return out


def rows_from_event(ev: dict, g, served: datetime, source: str, markets) -> list[tuple]:
    """nfl_odds_history rows from one event payload, home-relative."""
    home, away = ev.get("home_team"), ev.get("away_team")
    lead = (g["kick"].to_pydatetime() - served).total_seconds() / 3600.0
    rows = []
    for bk in ev.get("bookmakers", []) or []:
        book = bk.get("key")
        for m in bk.get("markets", []) or []:
            key = m.get("key")
            if key not in markets:
                continue
            oc = {o.get("name"): o for o in m.get("outcomes", []) or []}
            if key.startswith("spreads"):
                ho, ao = oc.get(home), oc.get(away)
                if not ho or not ao or ho.get("point") is None:
                    continue
                pt, ph, pa = float(ho["point"]), ho.get("price"), ao.get("price")
            elif key.startswith("totals"):
                ov, un = oc.get("Over"), oc.get("Under")
                if not ov or not un or ov.get("point") is None:
                    continue
                pt, ph, pa = float(ov["point"]), ov.get("price"), un.get("price")
            else:  # h2h
                ho, ao = oc.get(home), oc.get(away)
                if not ho or not ao:
                    continue
                pt, ph, pa = None, ho.get("price"), ao.get("price")
            rows.append((_iso(served), g["game_id"], int(g["season"]), int(g["week"]),
                         _iso(g["kick"].to_pydatetime()), book, key, pt, ph, pa,
                         round(lead, 4), source))
    return rows


_INSERT = """
    INSERT INTO nfl_odds_history
        (snapshot_at, game_id, season, week, commence_time, bookmaker, market,
         point, price_home, price_away, lead_hours, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (snapshot_at, game_id, bookmaker, market) DO NOTHING
"""
_LEDGER = """
    INSERT INTO nfl_odds_history_pulls
        (request_key, kind, season, requested_at, served_at, http_status,
         credits_last, rows_written)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (request_key) DO NOTHING
"""


def _ledger_keys(conn, kind: str) -> set:
    return {r[0] for r in conn.execute(
        "SELECT request_key FROM nfl_odds_history_pulls WHERE kind = %s",
        (kind,)).fetchall()}


def _stored_rows(conn, prefix: str, seasons) -> int:
    return conn.execute(
        "SELECT count(*) FROM nfl_odds_history WHERE source LIKE %s AND season = ANY(%s)",
        (prefix + "%", list(seasons))).fetchone()[0]


class Budget:
    def __init__(self, ceiling: int, floor: int):
        self.ceiling, self.floor, self.spent, self.stop = ceiling, floor, 0, None

    def charge(self, resp, assumed: int) -> None:
        last = resp.headers.get("x-requests-last") if resp is not None else None
        self.spent += int(float(last)) if last not in (None, "") else assumed
        rem = resp.headers.get("x-requests-remaining") if resp is not None else None
        if rem not in (None, "") and float(rem) < self.floor:
            self.stop = f"x-requests-remaining {float(rem):,.0f} < floor {self.floor:,}"
        if self.spent >= self.ceiling:
            self.stop = f"spent {self.spent:,} >= ceiling {self.ceiling:,}"


# ─── the two purchases ─────────────────────────────────────────────────────

def events_for(conn, kick: datetime, season: int, budget: Budget | None, cache: dict):
    """The event list as it stood shortly before a kickoff (1 credit a call),
    memoised per requested timestamp."""
    req = _iso(_floor5(kick - timedelta(minutes=20)))
    if req in cache:
        return cache[req]
    resp = _get(f"{BASE}/events", {"apiKey": ODDS_API_KEY, "date": req})
    if resp is None:
        return []
    if budget:
        budget.charge(resp, 1)
    data = resp.json().get("data", []) if resp.status_code == 200 else []
    conn.execute(_LEDGER, (f"events|{req}", "events", season, req,
                           resp.json().get("timestamp") if resp.status_code == 200 else None,
                           resp.status_code, _last(resp), 0))
    conn.commit()
    cache[req] = data
    return data


def _last(resp):
    v = resp.headers.get("x-requests-last") if resp is not None else None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def buy_halftime(conn, seasons, budget: Budget, limit: int | None = None) -> None:
    sched = schedule(seasons)
    clocks = halftime_windows(seasons)
    team_map = _team_map()
    done = _ledger_keys(conn, "halftime")
    ev_cache: dict = {}
    games = sched[sched["game_id"].isin(clocks)].sort_values("kick")
    calls = rows_total = 0
    for _, g in games.iterrows():
        if budget.stop:
            break
        evs = events_for(conn, g["kick"].to_pydatetime(), int(g["season"]), budget, ev_cache)
        ids = [eid for eid, row in match_events(evs, sched, team_map).items()
               if row["game_id"] == g["game_id"]]
        if not ids:
            logger.warning(f"{g['game_id']}: no Odds API event matched")
            continue
        eid = ids[0]
        last_served = None
        for t in halftime_requests(*clocks[g["game_id"]]):
            req = _iso(t)
            key = f"halftime|{eid}|{req}"
            if key in done:
                continue
            if budget.stop:
                break
            resp = _get(f"{BASE}/events/{eid}/odds",
                        {"apiKey": ODDS_API_KEY, "regions": "us",
                         "bookmakers": ",".join(BOOKS), "markets": ",".join(H2_MARKETS),
                         "oddsFormat": "american", "date": req})
            if resp is None:
                budget.stop = "network gave up"
                break
            budget.charge(resp, CREDITS_PER_MARKET * len(H2_MARKETS))
            calls += 1
            body = resp.json() if resp.status_code == 200 else {}
            served_s = body.get("timestamp")
            served = _ts(served_s) if served_s else t
            n = 0
            if resp.status_code == 200 and served_s and served_s != last_served:
                ev = body.get("data") or {}
                rows = rows_from_event(ev, g, served, f"{SRC_H2}ev={eid}|req={req}|served={_iso(served)}",
                                       H2_MARKETS) if ev else []
                if rows:
                    conn.executemany(_INSERT, rows)
                n = len(rows)
            last_served = served_s or last_served
            conn.execute(_LEDGER, (key, "halftime", int(g["season"]), req, served_s,
                                   resp.status_code, _last(resp), n))
            conn.commit()
            rows_total += n
            if resp.status_code in (401, 403):
                budget.stop = f"HTTP {resp.status_code}"
                break
            time.sleep(0.2)
        if limit is not None and calls >= limit:
            break
    persist_quota(conn)
    logger.success(f"halftime: {calls} calls, {rows_total} rows, spent {budget.spent:,}"
                   + (f" -- STOPPED: {budget.stop}" if budget.stop else ""))


def buy_inplay(conn, season: int, budget: Budget, limit: int | None = None,
               start_at: datetime | None = None) -> None:
    sched = schedule([season])
    team_map = _team_map()
    done = _ledger_keys(conn, "inplay")
    reqs = inplay_requests(inplay_windows(sched))
    if start_at is not None:
        reqs = [t for t in reqs if t >= start_at]
    calls = rows_total = 0
    seen_served: set = set()
    for t in reqs:
        req = _iso(t)
        key = f"inplay|{season}|{req}"
        if key in done:
            continue
        if budget.stop:
            break
        resp = _get(f"{BASE}/odds", {"apiKey": ODDS_API_KEY, "regions": "us",
                                     "bookmakers": ",".join(BOOKS),
                                     "markets": ",".join(INPLAY_MARKETS),
                                     "oddsFormat": "american", "date": req})
        if resp is None:
            budget.stop = "network gave up"
            break
        budget.charge(resp, CREDITS_PER_MARKET * len(INPLAY_MARKETS))
        calls += 1
        body = resp.json() if resp.status_code == 200 else {}
        served_s = body.get("timestamp")
        n = 0
        if resp.status_code == 200 and served_s and served_s not in seen_served:
            served = _ts(served_s)
            evs = body.get("data") or []
            matched = match_events(evs, sched, team_map)
            src = f"{SRC_INPLAY}req={req}|served={_iso(served)}"
            rows = []
            for ev in evs:
                g = matched.get(ev.get("id"))
                if g is None or g["kick"].to_pydatetime() > served:
                    continue          # pre-game rows for 2025 are already stored
                rows += rows_from_event(ev, g, served, src, INPLAY_MARKETS)
            if rows:
                conn.executemany(_INSERT, rows)
            n = len(rows)
            seen_served.add(served_s)
        conn.execute(_LEDGER, (key, "inplay", season, req, served_s, resp.status_code,
                               _last(resp), n))
        conn.commit()
        rows_total += n
        if calls % 100 == 0:
            logger.info(f"inplay {season}: {calls} calls, {rows_total} rows, "
                        f"spent {budget.spent:,}, at {req}")
        if resp.status_code in (401, 403):
            budget.stop = f"HTTP {resp.status_code}"
            break
        if limit is not None and calls >= limit:
            break
        time.sleep(0.2)
    persist_quota(conn)
    logger.success(f"inplay {season}: {calls} calls, {rows_total} rows, spent {budget.spent:,}"
                   + (f" -- STOPPED: {budget.stop}" if budget.stop else ""))


def plan(mode: str, seasons) -> tuple[int, int]:
    """(calls, credits) upper bound, no network beyond free nflverse."""
    if mode == "halftime":
        clocks = halftime_windows(seasons)
        calls = sum(len(halftime_requests(a, b)) for a, b in clocks.values())
        days = len({a.date() for a, _ in clocks.values()})
        return calls + days, calls * CREDITS_PER_MARKET * len(H2_MARKETS) + days
    sched = schedule(seasons)
    n = len(inplay_requests(inplay_windows(sched)))
    return n, n * CREDITS_PER_MARKET * len(INPLAY_MARKETS)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["halftime", "inplay"])
    ap.add_argument("--season", type=int, nargs="+")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--probe", action="store_true",
                    help="one halftime game and one in-play snapshot, stored, then stop")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-credits", type=int, default=None)
    ap.add_argument("--floor", type=int, default=1_000_000)
    a = ap.parse_args()

    if a.probe:
        if not ODDS_API_KEY:
            raise SystemExit("ODDS_API_KEY not set")
        conn = get_connection()
        try:
            b = Budget(ceiling=200, floor=a.floor)
            buy_halftime(conn, [2023], b, limit=1)
            logger.info(f"probe halftime spent {b.spent}")
            b2 = Budget(ceiling=200, floor=a.floor)
            first = schedule([2025])["kick"].min().to_pydatetime()
            buy_inplay(conn, 2025, b2, limit=1, start_at=first + timedelta(minutes=70))
            logger.info(f"probe inplay spent {b2.spent}")
        finally:
            conn.close()
        return
    if not a.mode:
        ap.error("--mode required")
    seasons = a.season or ([2023, 2024, 2025] if a.mode == "halftime" else [2025])
    calls, credits = plan(a.mode, seasons)
    logger.info(f"{a.mode} {seasons}: {calls:,} planned calls, <= {credits:,} credits")
    if a.dry_run:
        return
    if not a.apply:
        ap.error("one of --dry-run / --probe / --apply")
    if not ODDS_API_KEY:
        raise SystemExit("ODDS_API_KEY not set")
    budget = Budget(ceiling=a.max_credits or int(credits * 1.25), floor=a.floor)
    conn = get_connection()
    try:
        before = _stored_rows(conn, SRC_H2 if a.mode == "halftime" else SRC_INPLAY, seasons)
        if a.mode == "halftime":
            buy_halftime(conn, seasons, budget)
        else:
            for s in seasons:
                buy_inplay(conn, s, budget)
                if budget.stop:
                    break
        after = _stored_rows(conn, SRC_H2 if a.mode == "halftime" else SRC_INPLAY, seasons)
        logger.success(f"stored rows {before:,} -> {after:,}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
