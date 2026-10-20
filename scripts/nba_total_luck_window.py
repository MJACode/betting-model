"""The NBA totals window job: a fetch and a decision 60-66 minutes before tip.

WHY. nba_total_luck decides each game once, on a fetch 60-180 minutes before
tip (decision point C), and the lab's fetch sat at 60 minutes. Until
2026-10-17 the card rode the refresh pass and decided only on the one pass 60
minutes out. A refresh pass that runs past ten minutes makes the scheduler skip
the next tick (max_instances=1), and the game whose deciding tick was skipped
was never priced: 27 of the 504 evening ticks over 2026-10-03..16 never started
(production pipeline_runs, read 2026-10-17), and 8 of those were on the hour or
the half hour, the ticks that decide 7:30, 8:30, 9:00 and 10:00 pm tips.

WHAT A TICK DOES (scheduler.run_nba_total_luck_window, every minute, 24x7):
  1. plan(): the unstarted regular-season NBA games tipping 61-66 minutes from
     now (LOOK_AHEAD_MIN) that the card has not decided. One database read;
     no API call.
  2. Nothing due: the tick returns. It spends nothing.
  3. Otherwise: fetch the NBA board (`python -m scripts.nba_total_luck_window
     --fetch`: the refresh pass's own NBA odds fetch, every game and market,
     'open'), then the card (step nba-total-luck), then publish.

The card decides on a fetch that landed 60-66 minutes before tip
(models.nba_total_luck.DECISION_LEAD_MIN). This job asks a minute above the
bottom, so a fetch that takes up to a minute to land still counts. The first
tick in the window decides; if it is skipped or fails, up to five more follow,
each a minute later.

    python -m scripts.nba_total_luck_window            # print what a tick would do
    python -m scripts.nba_total_luck_window --fetch    # fetch the NBA board
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_total_luck as tl  # noqa: E402
import scripts.nba_total_luck_card as card  # noqa: E402
from data.db import get_connection  # noqa: E402

_ET = ZoneInfo("America/New_York")

# Minutes before tip, both ends inclusive, at which a tick fetches and decides.
# Inside DECISION_LEAD_MIN: a minute above its bottom (a fetch lands seconds
# after it is asked for) and not above its top.
LOOK_AHEAD_MIN = (61.0, 66.0)


def plan(conn, now: datetime, games: dict[str, dict] | None = None) -> list[str]:
    """The undecided games this tick must fetch and decide. Reads only: it
    creates no table (card.decided_games reads none that does not exist).

    `games` is a slate already read this tick, reaching at least
    LOOK_AHEAD_MIN[1] (scripts/nba_pregame_window, which plans this model and
    nba_team_total_luck on one read); without it, the plan reads its own."""
    if games is None:
        games = card.slate(conn, now, horizon_min=LOOK_AHEAD_MIN[1])
    near = sorted(g for g, v in games.items()
                  if LOOK_AHEAD_MIN[0] <= tl.lead_minutes(v["tip"], now) <= LOOK_AHEAD_MIN[1])
    if not near:
        return []
    done = card.decided_games(conn, near)
    return [g for g in near if g not in done]


def plan_tick(now: datetime | None = None) -> list[str]:
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc))
    finally:
        conn.close()


def fetch(now: datetime | None = None) -> dict:
    """The NBA board, stored: the refresh pass's NBA odds fetch (every game,
    h2h, spreads and totals at every line-shop book), on demand."""
    from data.ingestors.odds_ingestor import run_odds_ingestor
    now = now or datetime.now(timezone.utc)
    return run_odds_ingestor(sport="NBA", snapshot_type="open",
                             target_date=now.astimezone(_ET).date().isoformat())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", action="store_true", help="fetch and store the NBA board")
    a = ap.parse_args()
    if a.fetch:
        result = fetch()
        logger.info(f"NBA totals window fetch: {result}")
        if not result.get("odds_rows"):
            # The ingestor logs a failed call and returns; a tick that stored
            # nothing must say so, so the job's heartbeat records an error.
            logger.error("NBA totals window fetch stored no odds rows")
            sys.exit(1)
        return
    print(plan_tick())


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/): the fetch is a paid
    # Odds API call. Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-total-luck-window")
    except Exception:  # noqa: BLE001
        pass

    main()
