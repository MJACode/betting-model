"""Buy the 2025 in-play DK totals history from The Odds API, 5 minutes at a time.

WHY. The live total-runs model's cut was swept on 47 slates of our own
in-play feed (docs/thresholds.md, 2026-09-09). The historical endpoint stores a
snapshot every ~5 minutes back to 2022 and an in-progress game's DK total is in
it (probed 2025-06-18T01:00Z: 25 of 29 events carried DK). That is ~85,000
priced in-play moments for one season, against a model trained on 2015-2024
plays -- 2025 is out of sample. mike authorised the spend on 2026-09-09.

WHAT IT WRITES. One `odds` row per (served snapshot, in-progress game) with
DK totals: snapshot_type='in_play', bookmaker='draftkings', market='totals',
snapshot_at = the timestamp the API SERVED (ends in 'Z', the paid-history
signature `backfilled_dates` relies on), and

    source = 'historical_inplay|req=<requested>|served=<served>|lu=<DK last_update>'

`served` is what the row is keyed on for resume and dedupe -- the API snaps a
request to its nearest stored snapshot, so two requests can land on one
snapshot and there is no unique key on `odds`. `lu` keeps DK's own
last_update beside it, which is the field the phantom-edge check needs
(scripts/inplay_history_backtest.py): a quote whose last_update predates a
run is a stale quote, not an edge.

Only IN-PROGRESS events are written (commence_time <= served). Pre-game rows
for 2025 already exist from the pregame backfill.

COST. 10 credits per call, one call per stored snapshot inside each slate
day's window (first pitch - 5 min -> last first pitch + 4 h). `--dry-run`
prints the planned call count and credits and spends nothing. `--apply`
refuses to start above `--max-credits` and stops the moment
x-requests-remaining drops under `--floor`.

    python -m data.ingestors.mlb_inplay_history --season 2025 --dry-run
    python -m data.ingestors.mlb_inplay_history --season 2025 --apply --shard 0/4

Resumable: a day whose latest served snapshot is already stored resumes from
the snapshot after it. Shards split the slate days round-robin so several
processes can run at once.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
import statsapi
from loguru import logger

from config import ODDS_API_BASE, ODDS_API_KEY
from data.db import get_connection
from data.ingestors.odds_ingestor import (
    _build_game_id, _insert_odds, _normalize_team, _parse_total_outcomes,
    record_quota_headers)

SPORT_KEY = "baseball_mlb"
SOURCE_PREFIX = "historical_inplay|"
CREDITS_PER_CALL = 10
STEP = timedelta(minutes=5)
PRE_MARGIN = timedelta(minutes=5)
POST_MARGIN = timedelta(hours=4)
# Regular season, wild card, division, league championship, world series.
GAME_TYPES = {"R", "F", "D", "L", "W"}
_ET = ZoneInfo("America/New_York")


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def slate_windows(season: int) -> list[tuple[str, datetime, datetime]]:
    """(date, window start, window end) for every day with a real MLB game.

    From the Stats API schedule, not `games.commence_time`: the 2025
    postseason rows in `games` carry no commence_time.
    """
    out = []
    d = datetime(season, 3, 1).date()
    end = datetime(season, 11, 15).date()
    while d <= end:
        try:
            sched = statsapi.schedule(date=d.isoformat(), sportId=1)
        except Exception as exc:
            logger.warning(f"schedule {d}: {exc}")
            sched = []
        starts = [_ts(g["game_datetime"]) for g in sched
                  if g.get("game_type") in GAME_TYPES and g.get("game_datetime")]
        if starts:
            lo = min(starts) - PRE_MARGIN
            lo = lo.replace(second=0, microsecond=0, minute=lo.minute - lo.minute % 5)
            out.append((d.isoformat(), lo, max(starts) + POST_MARGIN))
        d += timedelta(days=1)
        time.sleep(0.1)
    return out


def planned_calls(windows) -> int:
    return sum(int((hi - lo) / STEP) + 1 for _, lo, hi in windows)


def _served_already(conn, lo: datetime, hi: datetime) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT split_part(split_part(source, '|served=', 2), '|', 1) "
        "FROM odds WHERE snapshot_type = 'in_play' AND source LIKE %s "
        "AND snapshot_at >= %s AND snapshot_at <= %s",
        (SOURCE_PREFIX + "%", _iso(lo), _iso(hi))).fetchall()
    return {r[0] for r in rows if r[0]}


def _get(params: dict):
    """GET with retry on the network layer AND on 429; other statuses are answers."""
    url = f"{ODDS_API_BASE}/historical/sports/{SPORT_KEY}/odds"
    for i in range(6):
        try:
            resp = requests.get(url, params=params, timeout=60)
        except requests.RequestException as exc:
            logger.warning(f"  {type(exc).__name__}; retry {i + 1}")
            time.sleep(2 ** (i + 1))
            continue
        if resp.status_code == 429:
            logger.warning("  429; backing off")
            time.sleep(5 * (i + 1))
            continue
        return resp
    return None


def rows_for(events: list[dict], requested: str, served: datetime,
             known_games: set[str] | None = None, skipped: dict | None = None) -> list[dict]:
    """`known_games`: game_ids present in `games`. odds.game_id is a foreign
    key, so an event whose id is not there (a postponement the schedule never
    filed, a name the normaliser does not know) cannot be written; it is
    counted in `skipped` rather than crashing a paid run -- shard 0 of the 2025
    pull died on MLB_2025-06-12_LAA_BAL after 24,710 credits."""
    rows = []
    for ev in events:
        ct = ev.get("commence_time")
        if not ct or _ts(ct) > served:
            continue
        dk = next((b for b in ev.get("bookmakers", []) if b.get("key") == "draftkings"), None)
        if not dk:
            continue
        mkt = next((m for m in dk.get("markets", []) if m.get("key") == "totals"), None)
        if not mkt:
            continue
        parsed = _parse_total_outcomes(mkt.get("outcomes", []))
        if parsed.get("total_line") is None:
            continue
        game_date = _ts(ct).astimezone(_ET).strftime("%Y-%m-%d")
        home = _normalize_team(ev.get("home_team", ""), "MLB")
        away = _normalize_team(ev.get("away_team", ""), "MLB")
        game_id = _build_game_id("MLB", game_date, away, home)
        if known_games is not None and game_id not in known_games:
            if skipped is not None:
                skipped[game_id] = skipped.get(game_id, 0) + 1
            continue
        rows.append({
            "game_id": game_id,
            "sport": "MLB", "market": "totals", "bookmaker": "draftkings",
            "snapshot_type": "in_play", "snapshot_at": _iso(served),
            "home_price": None, "away_price": None, "draw_price": None,
            "spread_home": None,
            "total_line": parsed.get("total_line"),
            "over_price": parsed.get("over_price"),
            "under_price": parsed.get("under_price"),
            "home_link": None, "away_link": None, "draw_link": None,
            "over_link": parsed.get("over_link"), "under_link": parsed.get("under_link"),
            "home_sid": None, "away_sid": None, "draw_sid": None,
            "over_sid": parsed.get("over_sid"), "under_sid": parsed.get("under_sid"),
            "source": f"{SOURCE_PREFIX}req={requested}|served={_iso(served)}"
                      f"|lu={mkt.get('last_update')}",
        })
    return rows


def pull_day(conn, day: str, lo: datetime, hi: datetime, floor: int,
             budget: dict, known_games: set[str]) -> None:
    have = _served_already(conn, lo, hi)
    skipped: dict = {}
    t = lo
    if have:
        t = max(_ts(s) for s in have) + STEP
        logger.info(f"{day}: {len(have)} snapshots stored, resuming at {_iso(t)}")
    calls = wrote = 0
    while t <= hi:
        if budget["spent"] + CREDITS_PER_CALL > budget["max"]:
            logger.error(f"{day}: credit budget {budget['max']} reached; stopping")
            budget["stop"] = True
            return
        requested = _iso(t)
        resp = _get({"apiKey": ODDS_API_KEY, "regions": "us", "markets": "totals",
                     "bookmakers": "draftkings", "oddsFormat": "american",
                     "date": requested, "includeLinks": "true", "includeSids": "true"})
        if resp is None:
            logger.error(f"{day}: network gave up at {requested}; stopping")
            budget["stop"] = True
            return
        record_quota_headers(resp)
        remaining = resp.headers.get("x-requests-remaining")
        budget["spent"] += int(resp.headers.get("x-requests-last") or CREDITS_PER_CALL)
        calls += 1
        if resp.status_code != 200:
            logger.warning(f"{day}: HTTP {resp.status_code} at {requested}: {resp.text[:120]}")
            if resp.status_code == 401 or resp.status_code == 422:
                budget["stop"] = True
                return
            t += STEP
            continue
        body = resp.json()
        served_s = body.get("timestamp")
        served = _ts(served_s) if served_s else t
        nxt = body.get("next_timestamp")
        if _iso(served) not in have:
            rows = rows_for(body.get("data") or [], requested, served, known_games, skipped)
            if rows:
                _insert_odds(conn, rows)
                conn.commit()
                wrote += len(rows)
            have.add(_iso(served))
        if remaining is not None and int(remaining) < floor:
            logger.error(f"quota {remaining} under floor {floor}; stopping")
            budget["stop"] = True
            return
        if nxt:
            t = max(_ts(nxt), t + timedelta(seconds=1))
        else:
            t += STEP
        time.sleep(0.25)
    if skipped:
        logger.warning(f"{day}: not in games, skipped: "
                       + ", ".join(f"{g} x{n}" for g, n in sorted(skipped.items())))
    logger.info(f"{day}: {calls} calls, {wrote} rows, spent so far {budget['spent']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-credits", type=int, default=350_000)
    ap.add_argument("--floor", type=int, default=2_600_000,
                    help="stop when x-requests-remaining drops under this")
    ap.add_argument("--shard", default="0/1", help="i/n: this process takes days i, i+n, ...")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        ap.error("one of --dry-run / --apply")
    if not ODDS_API_KEY:
        raise SystemExit("ODDS_API_KEY not set")

    windows = slate_windows(args.season)
    calls = planned_calls(windows)
    logger.info(f"{args.season}: {len(windows)} slate days, {calls} planned calls, "
                f"{calls * CREDITS_PER_CALL:,} credits at {CREDITS_PER_CALL}/call")
    if args.dry_run:
        for day, lo, hi in windows[:3] + windows[-3:]:
            logger.info(f"  {day}: {_iso(lo)} -> {_iso(hi)}  {int((hi - lo) / STEP) + 1} calls")
        return
    if calls * CREDITS_PER_CALL > args.max_credits:
        raise SystemExit(f"planned {calls * CREDITS_PER_CALL:,} credits exceeds "
                         f"--max-credits {args.max_credits:,}; refusing")
    i, n = (int(x) for x in args.shard.split("/"))
    mine = [w for k, w in enumerate(windows) if k % n == i]
    budget = {"spent": 0, "max": args.max_credits, "stop": False}
    conn = get_connection()
    try:
        known = {r[0] for r in conn.execute(
            "SELECT game_id FROM games WHERE sport = 'MLB' AND season = %s",
            (args.season,)).fetchall()}
        for day, lo, hi in mine:
            pull_day(conn, day, lo, hi, args.floor, budget, known)
            if budget["stop"]:
                break
    finally:
        conn.close()
    logger.success(f"shard {args.shard}: spent {budget['spent']:,} credits"
                   f"{' (STOPPED EARLY)' if budget['stop'] else ''}")


if __name__ == "__main__":
    main()
