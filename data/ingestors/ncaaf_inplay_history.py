"""Buy the 2025 season's in-play DraftKings NCAAF snapshots from The Odds API.

WHY. Both NCAAF live lanes were paused on 2026-09-11 (config.PAUSED_MODELS):
the engine was gated on CALIBRATION only and the phase-3 edge harness -- the
one thing that could show a profitable rule -- was never started. Three weeks
of a forward "calibration set" produced 55 settled totals bets at 28-27, -2.99u,
claiming 67.5% and winning 50.9%. The unpause condition is a replay of the
production rule over a whole season of stored in-play quotes, out of sample for
the artifact (Stage 1 trained through 2024, 2025 held out).

This is the NCAAF port of data/ingestors/mlb_inplay_history.py, which bought
the 2025 MLB season the same way on 2026-09-10 (260,190 credits). Same shape,
same markers, same resume rule -- and the same rule about money: `--apply`
refuses to start above `--max-credits` and stops the moment
x-requests-remaining drops under `--floor`.

WHAT IT WRITES. One `odds` row per (served snapshot, in-progress game,
market) with DraftKings priced: snapshot_type='in_play', bookmaker='draftkings',
market in {'h2h','totals'}, snapshot_at = the timestamp the API SERVED (ends in
'Z', the paid-history signature), and

    source = 'historical_inplay|req=<requested>|served=<served>|lu=<DK last_update>'

`served` is what the row is keyed on for resume and dedupe (the API snaps a
request to its nearest stored snapshot); `lu` is the MARKET's own last_update,
which the replay's freshness split needs -- a quote whose last_update predates
a score is the score priced twice, not an edge.

Only IN-PROGRESS events are written (commence_time <= served). Pregame rows for
2025 already exist from the pregame backfill.

COST. 10 credits per market per region per call; one region (us). One call per
5-minute snapshot inside each slate day's window (first kickoff - 5 min ->
last kickoff + 4 h). `--dry-run` prints the planned call count and credits and
spends nothing; it reads only `games`.

    python -m data.ingestors.ncaaf_inplay_history --season 2025 --dry-run
    python -m data.ingestors.ncaaf_inplay_history --season 2025 --apply --shard 0/4
    python -m data.ingestors.ncaaf_inplay_history --season 2025 --markets totals --dry-run

Resumable: a day whose latest served snapshot is already stored resumes from
the snapshot after it. Shards split the slate days round-robin so several
processes can run at once.

GAME IDENTITY. NCAAF ids are `NCAAF_<date>_<away-slug>_<home-slug>` with CFBD
school names (data/ingestors/cfbd_ingestor.build_ncaaf_game_id). The Odds API
appends mascots and spells some schools differently; `_normalize_team` resolves
through the ncaaf_teams registry. The DATE half of the id is CFBD's, which for
a late kickoff can be the UTC date rather than the ET one (#301 mirrored finals
across exactly that pair), so an event is tried on its ET date first and its
UTC date second, and written only if one of them exists in `games`. Unresolved
events are counted and skipped, never invented.
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from config import ODDS_API_BASE, ODDS_API_KEY
from data.db import get_connection
from data.ingestors.odds_ingestor import (
    _build_game_id, _insert_odds, _normalize_team, _parse_outcomes,
    _parse_total_outcomes, record_quota_headers)
from data.ingestors.odds_quota import (
    DEFAULT_RESERVE_DAYS, plan_credit_budget)

SPORT = "NCAAF"
SPORT_KEY = "americanfootball_ncaaf"
SOURCE_PREFIX = "historical_inplay|"
CREDITS_PER_MARKET = 10
DEFAULT_MARKETS = ("h2h", "totals")
STEP = timedelta(minutes=5)
PRE_MARGIN = timedelta(minutes=5)
# A college game runs ~3.5h; four hours after the LAST kickoff of the day
# closes every game on the slate, overtime included.
POST_MARGIN = timedelta(hours=4)
_ET = ZoneInfo("America/New_York")


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _floor5(d: datetime) -> datetime:
    d = d.replace(second=0, microsecond=0)
    return d - timedelta(minutes=d.minute % 5)


def slate_windows(conn, season: int) -> list[tuple[str, datetime, datetime]]:
    """(date, window start, window end) for every day with a scheduled game.

    From `games.commence_time` -- every NCAAF row carries one (1,306 of 1,306
    for 2025, measured 2026-09-11), unlike MLB's postseason rows.
    """
    rows = conn.execute("""
        SELECT game_date, MIN(commence_time), MAX(commence_time)
        FROM games
        WHERE sport = %s AND season = %s AND commence_time IS NOT NULL
        GROUP BY game_date ORDER BY game_date
    """, (SPORT, season)).fetchall()
    out = []
    for day, first, last in rows:
        lo = _floor5(_ts(str(first)) - PRE_MARGIN)
        hi = _ts(str(last)) + POST_MARGIN
        out.append((str(day), lo, hi))
    return out


def planned_calls(windows) -> int:
    return sum(int((hi - lo) / STEP) + 1 for _, lo, hi in windows)


def calls_in(day_window) -> int:
    """Planned calls for ONE slate day."""
    _, lo, hi = day_window
    return int((hi - lo) / STEP) + 1


def parse_shard(spec: str) -> tuple[int, int]:
    """`i/n` -> (i, n), refusing anything that would silently drop days.

    A bad spec used to raise deep inside main() as a ValueError from int(), or
    worse, quietly select nothing: `4/4` matches no day at all, so a fourth
    shard launched as 4/4 rather than 3/4 exits SUCCESSFULLY having pulled
    nothing, and the gap only shows up as a hole in the replay.
    """
    parts = str(spec).split("/")
    if len(parts) != 2:
        raise ValueError(f"--shard must be i/n, got {spec!r}")
    try:
        i, n = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"--shard must be i/n with integers, got {spec!r}")
    if n < 1 or i < 0 or i >= n:
        raise ValueError(f"--shard {spec!r}: need 0 <= i < n and n >= 1")
    return i, n


def shard_windows(windows, spec: str) -> list:
    """This shard's slate days, round-robin so every day is taken exactly once."""
    i, n = parse_shard(spec)
    return [w for k, w in enumerate(windows) if k % n == i]


def budget_for(conn, windows, spec: str, markets, *, max_credits=None,
               reserve_days: int = DEFAULT_RESERVE_DAYS, burn_per_day=None,
               remaining=None, calls_per_day=None):
    """This shard's credit budget: its OWN planned calls, its OWN share.

    The seam the 2026-09-11 bug needed and did not have. Everything about how
    much may be spent is decided here, from the shard's real work and the
    measured burn rate -- see `data/ingestors/odds_quota.py` for why both
    numbers are derived rather than chosen.
    """
    per_day = calls_per_day or (lambda w: calls_in(w))
    mine = shard_windows(windows, spec)
    return plan_credit_budget(
        conn,
        shard_calls=sum(per_day(w) for w in mine),
        total_calls=sum(per_day(w) for w in windows),
        credits_per_call=CREDITS_PER_MARKET * len(markets),
        max_credits=max_credits, reserve_days=reserve_days,
        burn_per_day=burn_per_day, remaining=remaining)


def _served_already(conn, lo: datetime, hi: datetime) -> set[str]:
    rows = conn.execute(
        "SELECT DISTINCT split_part(split_part(source, '|served=', 2), '|', 1) "
        "FROM odds WHERE sport = %s AND snapshot_type = 'in_play' "
        "AND source LIKE %s AND snapshot_at >= %s AND snapshot_at <= %s",
        (SPORT, SOURCE_PREFIX + "%", _iso(lo), _iso(hi))).fetchall()
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


def _blank_row(game_id: str, market: str, served: datetime, requested: str,
               last_update) -> dict:
    return {
        "game_id": game_id, "sport": SPORT, "market": market,
        "bookmaker": "draftkings", "snapshot_type": "in_play",
        "snapshot_at": _iso(served),
        "home_price": None, "away_price": None, "draw_price": None,
        "spread_home": None, "total_line": None,
        "over_price": None, "under_price": None,
        "home_link": None, "away_link": None, "draw_link": None,
        "over_link": None, "under_link": None,
        "home_sid": None, "away_sid": None, "draw_sid": None,
        "over_sid": None, "under_sid": None,
        "source": f"{SOURCE_PREFIX}req={requested}|served={_iso(served)}"
                  f"|lu={last_update}",
    }


def resolve_game_id(ev: dict, known_games: set[str] | None) -> str | None:
    """The `games` id for an event: ET date first, UTC date second.

    With no `known_games` (tests), the ET-dated id is returned unchecked."""
    ct = ev.get("commence_time")
    if not ct:
        return None
    home = _normalize_team(ev.get("home_team", ""), SPORT)
    away = _normalize_team(ev.get("away_team", ""), SPORT)
    when = _ts(ct)
    dates = [when.astimezone(_ET).strftime("%Y-%m-%d"),
             when.strftime("%Y-%m-%d")]
    for d in dict.fromkeys(dates):
        gid = _build_game_id(SPORT, d, away, home)
        if known_games is None or gid in known_games:
            return gid
    return None


def rows_for(events: list[dict], requested: str, served: datetime,
             markets=DEFAULT_MARKETS, known_games: set[str] | None = None,
             skipped: dict | None = None) -> list[dict]:
    """`odds` rows for every in-progress event DraftKings priced in `markets`.

    odds.game_id is a foreign key, so an event whose id is not in `games` is
    counted in `skipped` rather than crashing a paid run."""
    rows = []
    for ev in events:
        ct = ev.get("commence_time")
        if not ct or _ts(ct) > served:
            continue
        dk = next((b for b in ev.get("bookmakers", []) if b.get("key") == "draftkings"), None)
        if not dk:
            continue
        game_id = resolve_game_id(ev, known_games)
        if game_id is None:
            if skipped is not None:
                key = f"{ev.get('away_team')} @ {ev.get('home_team')} {ct}"
                skipped[key] = skipped.get(key, 0) + 1
            continue
        for mkt in dk.get("markets", []):
            key = mkt.get("key")
            if key not in markets:
                continue
            if key == "totals":
                parsed = _parse_total_outcomes(mkt.get("outcomes", []))
                if parsed.get("total_line") is None:
                    continue
                row = _blank_row(game_id, "totals", served, requested, mkt.get("last_update"))
                for c in ("total_line", "over_price", "under_price",
                          "over_link", "under_link", "over_sid", "under_sid"):
                    row[c] = parsed.get(c)
            elif key == "h2h":
                parsed = _parse_outcomes(mkt.get("outcomes", []), SPORT,
                                         home_team_name=ev.get("home_team", ""))
                if parsed.get("home_price") is None or parsed.get("away_price") is None:
                    continue
                row = _blank_row(game_id, "h2h", served, requested, mkt.get("last_update"))
                for c in ("home_price", "away_price", "home_link", "away_link",
                          "home_sid", "away_sid"):
                    row[c] = parsed.get(c)
            else:
                continue
            rows.append(row)
    return rows


def pull_day(conn, day: str, lo: datetime, hi: datetime,
             budget, known_games: set[str], markets) -> None:
    have = _served_already(conn, lo, hi)
    skipped: dict = {}
    t = lo
    if have:
        t = max(_ts(s) for s in have) + STEP
        logger.info(f"{day}: {len(have)} snapshots stored, resuming at {_iso(t)}")
    per_call = CREDITS_PER_MARKET * len(markets)
    calls = wrote = 0
    while t <= hi:
        if not budget.can_afford(per_call):
            logger.error(f"{day}: {budget.stopped_reason}; stopping")
            return
        requested = _iso(t)
        resp = _get({"apiKey": ODDS_API_KEY, "regions": "us",
                     "markets": ",".join(markets),
                     "bookmakers": "draftkings", "oddsFormat": "american",
                     "date": requested, "includeLinks": "true", "includeSids": "true"})
        if resp is None:
            logger.error(f"{day}: network gave up at {requested}; stopping")
            budget.stopped_reason = "network gave up"
            return
        record_quota_headers(resp)
        remaining = resp.headers.get("x-requests-remaining")
        budget.charge(resp, assumed=per_call)
        calls += 1
        if resp.status_code != 200:
            logger.warning(f"{day}: HTTP {resp.status_code} at {requested}: {resp.text[:120]}")
            if resp.status_code in (401, 422):
                budget.stopped_reason = f"HTTP {resp.status_code}"
                return
            t += STEP
            continue
        body = resp.json()
        served_s = body.get("timestamp")
        served = _ts(served_s) if served_s else t
        nxt = body.get("next_timestamp")
        if _iso(served) not in have:
            rows = rows_for(body.get("data") or [], requested, served, markets,
                            known_games, skipped)
            if rows:
                _insert_odds(conn, rows)
                conn.commit()
                wrote += len(rows)
            have.add(_iso(served))
        if not budget.check_remaining(remaining):
            logger.error(f"{budget.stopped_reason}; stopping")
            return
        if nxt:
            t = max(_ts(nxt), t + timedelta(seconds=1))
        else:
            t += STEP
        time.sleep(0.25)
    if skipped:
        logger.warning(f"{day}: not in games, skipped: "
                       + ", ".join(f"{g} x{n}" for g, n in sorted(skipped.items())))
    logger.info(f"{day}: {calls} calls, {wrote} rows, "
                f"spent so far {budget.spent:,} of {budget.ceiling:,}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--markets", default=",".join(DEFAULT_MARKETS),
                    help="comma list from h2h,totals (default both)")
    # THE GUARDS ARE DERIVED, NOT CHOSEN -- see data/ingestors/odds_quota.py.
    # --max-credits is the budget for the WHOLE pull across every shard and
    # defaults to the run's own printed plan; --floor is gone, replaced by a
    # reserve measured off odds_api_quota.
    ap.add_argument("--max-credits", type=int, default=None,
                    help="whole-run budget across ALL shards (default: the "
                         "printed plan). Split by each shard's share of the work.")
    ap.add_argument("--reserve-days", type=int, default=DEFAULT_RESERVE_DAYS,
                    help="days of MEASURED burn the account must keep after "
                         f"this pull (default {DEFAULT_RESERVE_DAYS})")
    ap.add_argument("--burn-per-day", type=int, default=None,
                    help="override the measured burn rate (refuses without one)")
    ap.add_argument("--remaining", type=int, default=None,
                    help="override the quota reading (refuses without one)")
    ap.add_argument("--shard", default="0/1", help="i/n: this process takes days i, i+n, ...")
    args = ap.parse_args()
    if not (args.dry_run or args.apply):
        ap.error("one of --dry-run / --apply")
    markets = tuple(m.strip() for m in args.markets.split(",") if m.strip())
    bad = [m for m in markets if m not in DEFAULT_MARKETS]
    if bad or not markets:
        ap.error(f"--markets must be from {DEFAULT_MARKETS}; got {markets}")

    conn = get_connection()
    try:
        windows = slate_windows(conn, args.season)
        calls = planned_calls(windows)
        per_call = CREDITS_PER_MARKET * len(markets)
        logger.info(f"{args.season}: {len(windows)} slate days, {calls} planned calls, "
                    f"{calls * per_call:,} credits at {per_call}/call "
                    f"({','.join(markets)})")
        # The budget is built for THIS SHARD from its own work and the measured
        # burn rate, and it is printed whether or not we are about to spend --
        # a dry run that does not show the guards cannot be used to approve
        # them, which is how the 2026-09-11 numbers went unexamined.
        budget, problems = budget_for(
            conn, windows, args.shard, markets,
            max_credits=args.max_credits, reserve_days=args.reserve_days,
            burn_per_day=args.burn_per_day, remaining=args.remaining)
        logger.info("credit guards (all derived -- odds_quota.py):\n"
                    + budget.describe())
        for p in problems:
            logger.error(f"REFUSING: {p}")

        if args.dry_run:
            for day, lo, hi in windows[:3] + windows[-3:]:
                logger.info(f"  {day}: {_iso(lo)} -> {_iso(hi)}  {int((hi - lo) / STEP) + 1} calls")
            return
        if not ODDS_API_KEY:
            raise SystemExit("ODDS_API_KEY not set")
        if problems:
            raise SystemExit("refusing to start: " + "; ".join(problems))

        mine = shard_windows(windows, args.shard)
        known = {r[0] for r in conn.execute(
            "SELECT game_id FROM games WHERE sport = %s AND season = %s",
            (SPORT, args.season)).fetchall()}
        for day, lo, hi in mine:
            pull_day(conn, day, lo, hi, budget, known, markets)
            if budget.stop:
                break
        logger.success(
            f"shard {args.shard}: spent {budget.spent:,} of {budget.ceiling:,} "
            f"credits{' — STOPPED EARLY: ' + budget.stopped_reason if budget.stop else ''}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
