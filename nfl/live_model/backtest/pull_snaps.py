"""
Credit-budgeted puller for historical IN-PLAY odds snapshots.

    python -m live_model.backtest.pull_snaps --seasons 2023 2024 --budget 3000
    python -m live_model.backtest.pull_snaps --seasons 2023 --dry-run

THE BUDGET IS THE POINT. Historical snapshots cost 10 credits per market per
region per call, and there are 12 snapshots per hour of game time. Pulling
every market for every game of three seasons is a six figure spend. So:

  * `--budget` is a hard stop, checked BEFORE each call, and the default comes
    from config rather than from optimism.
  * Scope is deliberately narrow: `us` only, and only the markets the harness
    can actually adjudicate. Adding a market multiplies the whole spend.
  * Everything is cached by the existing data_ingest.odds_api cache, keyed by
    (date, regions, markets), so a re-run costs zero and an interrupted run
    resumes for free.
  * `--dry-run` prints the exact spend before a single credit moves.

Scope defaults follow the build spec: totals, totals_h2, spreads_h2 and
team_totals, plus the two highest-volume prop markets. Those are the lanes the
harness is meant to answer, and nothing else earns its cost until one of them
shows a pulse.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from data_ingest.odds_api import OddsAPIClient, ledger_status   # noqa: E402
from ..config import BACKTEST_CREDIT_BUDGET, PBP_DIR            # noqa: E402

# Scoped hard. Each extra market multiplies the entire spend by (n+1)/n.
SCOPE_MARKETS = ("totals", "totals_h2", "spreads_h2", "team_totals")
SCOPE_PROPS = ("player_pass_yds", "player_rush_yds")
SCOPE_REGIONS = "us"

SNAP_MINUTES = 5            # the API's historical granularity
GAME_HOURS = 3.5            # a game plus warmup, in wall clock


def game_windows(seasons) -> pd.DataFrame:
    """
    Kickoff times per game, from the pbp files.

    Read off the play-by-play rather than a schedule file so the windows can
    never disagree with the states the harness replays against them.
    """
    rows = []
    for season in seasons:
        path = PBP_DIR / f"play_by_play_{season}.parquet"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing; pull the pbp parquets first")
        df = pd.read_parquet(path, columns=["game_id", "season", "week",
                                            "game_date", "start_time"])
        g = df.groupby("game_id").first().reset_index()
        rows.append(g)
    return pd.concat(rows, ignore_index=True)


# A full game window at the spec's market scope costs 322,560 credits for
# 2023-2025, which is not a budget, it is a rounding error away from the entire
# annual quota. So the puller supports two windows and defaults to neither: the
# caller has to say which, after reading the printed cost.
HALFTIME_OFFSET_MIN = 85        # kickoff to roughly the start of halftime
HALFTIME_SPAN_MIN = 25          # covers the whole break plus timing slop


def snapshot_times(kickoff: datetime, hours: float = GAME_HOURS,
                   window: str = "game") -> list[datetime]:
    """
    Snapshot timestamps for one game, on the API's 5 minute grid.

    `window="halftime"` covers only the break, which is where the highest
    value lane lives and is roughly a tenth of the cost. Halftimes across a
    slate overlap heavily, and the historical endpoint returns the whole slate
    per timestamp, so ten simultaneous games share their snapshots.
    """
    if window == "halftime":
        start = kickoff + timedelta(minutes=HALFTIME_OFFSET_MIN)
        n = int(HALFTIME_SPAN_MIN / SNAP_MINUTES) + 1
        return [start + timedelta(minutes=SNAP_MINUTES * i) for i in range(n)]
    n = int(hours * 60 / SNAP_MINUTES)
    return [kickoff + timedelta(minutes=SNAP_MINUTES * i) for i in range(n)]


def plan(seasons, include_props: bool = False, window: str = "game",
         markets: tuple | None = None) -> dict:
    """
    Cost the pull WITHOUT spending anything.

    Distinct timestamps matter, not distinct games: the historical endpoint
    returns the whole slate for a timestamp, so ten simultaneous 1pm games cost
    one call between them. That is why a full Sunday is affordable and a
    per-game pull would not be.
    """
    games = game_windows(seasons)
    stamps: set[str] = set()
    for _, row in games.iterrows():
        ko = _kickoff(row)
        if ko is None:
            continue
        for t in snapshot_times(ko, window=window):
            stamps.add(t.strftime("%Y-%m-%dT%H:%M:00Z"))

    markets = list(markets) if markets else (
        list(SCOPE_MARKETS) + (list(SCOPE_PROPS) if include_props else []))
    per_call = 10 * len(markets) * len(SCOPE_REGIONS.split(","))
    return {
        "games": int(len(games)),
        "window": window,
        "snapshots": len(stamps),
        "markets": markets,
        "credits_per_call": per_call,
        "total_credits": len(stamps) * per_call,
        "stamps": sorted(stamps),
    }


def _kickoff(row) -> datetime | None:
    date = row.get("game_date")
    start = row.get("start_time")
    if isinstance(start, str) and start:
        try:
            ts = datetime.fromisoformat(start.replace("Z", "+00:00"))
            return ts.astimezone(timezone.utc)
        except ValueError:
            pass
    if date is None or (isinstance(date, float) and pd.isna(date)):
        return None
    try:
        d = pd.to_datetime(date).to_pydatetime()
    except (ValueError, TypeError):
        return None
    # Without a start time, assume a 1pm Eastern kickoff. Only used to place
    # the snapshot window; the harness aligns on real timestamps afterwards.
    return d.replace(hour=18, minute=0, tzinfo=timezone.utc)


def pull(seasons, budget: int, include_props: bool = False,
         api_key: str | None = None, window: str = "game",
         markets: tuple | None = None) -> dict:
    import os
    key = api_key or os.getenv("THE_ODDS_API_KEY") or os.getenv("ODDS_API_KEY")
    if not key:
        raise SystemExit("Set THE_ODDS_API_KEY before pulling snapshots.")

    p = plan(seasons, include_props, window=window, markets=markets)
    markets_param = ",".join(p["markets"])
    client = OddsAPIClient(key)

    spent = 0
    fetched = cached = 0
    for stamp in p["stamps"]:
        if spent + p["credits_per_call"] > budget:
            print(f"budget reached at {stamp}: spent {spent} of {budget}")
            break
        res = client.historical_odds(stamp, regions=SCOPE_REGIONS,
                                     markets=markets_param)
        if res.from_cache:
            cached += 1
        else:
            fetched += 1
            spent += res.cost
    return {"spent": spent, "fetched": fetched, "cached": cached,
            "planned": p["total_credits"], "ledger": ledger_status()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", type=int, nargs="+", default=[2023, 2024, 2025])
    ap.add_argument("--budget", type=int, default=BACKTEST_CREDIT_BUDGET)
    ap.add_argument("--props", action="store_true",
                    help="include the two scoped prop markets (multiplies spend)")
    ap.add_argument("--window", choices=("game", "halftime"), default="halftime",
                    help="halftime covers only the break: the highest value "
                         "lane at roughly a tenth of the cost")
    ap.add_argument("--markets", nargs="+", default=None,
                    help="override the market scope; each extra market "
                         "multiplies the entire spend")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    markets = tuple(args.markets) if args.markets else None
    p = plan(args.seasons, args.props, window=args.window, markets=markets)
    print(f"seasons {args.seasons}  window {args.window}")
    print(f"  games              {p['games']:,}")
    print(f"  distinct snapshots {p['snapshots']:,}")
    print(f"  markets            {', '.join(p['markets'])}")
    print(f"  credits per call   {p['credits_per_call']}")
    print(f"  TOTAL CREDITS      {p['total_credits']:,}")
    print(f"  budget             {args.budget:,}")
    if p["total_credits"] > args.budget:
        covered = args.budget // max(p["credits_per_call"], 1)
        print(f"  budget covers {covered:,} of {p['snapshots']:,} snapshots "
              f"({100 * covered / max(p['snapshots'], 1):.0f}%)")

    if args.dry_run:
        print("\ndry run: nothing spent")
        return
    print(pull(args.seasons, args.budget, args.props, window=args.window,
               markets=markets))


if __name__ == "__main__":
    main()
