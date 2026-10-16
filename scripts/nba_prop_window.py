"""The NBA prop window job: put a look inside every game's decision window.

WHY. nba_prop_market decides a game once, 45-57 minutes before tip
(models/nba_prop_market.DECISION_WINDOW_MIN). The refresh passes run hourly at
:17 until 5pm ET and every ten minutes from 6pm, so no pass ever landed 45-57
minutes before a tip at or before 6:00pm ET: 177 of 1,206 regular-season games
in 2026-27 could never be decided. mike, 2026-10-16: "run the fucking thing
more often ... we're not leaving our games."

WHAT A TICK DOES (scheduler.run_nba_prop_window, every five minutes, 24x7):
  1. plan(): the unstarted regular-season NBA games tipping 40-62 minutes from
     now (LOOK_AHEAD_MIN) that are not decided yet, and the bet games whose
     closing snapshot is due (12-25 minutes before tip, not yet taken). One
     database read; no API call.
  2. Nothing in either list: the tick returns. It spends nothing.
  3. Otherwise: fetch props for EXACTLY the games to decide
     (`python -m scripts.nba_prop_window --fetch <game ids>`, the same
     ingestor as the refresh pass's nba-prop-odds, restricted with
     only_game_ids), then the card (step nba-prop-market), then the closing
     snapshot (step nba-prop-close), then publish.

LOOK_AHEAD_MIN is a little wider than the decision window on both ends, so the
fetch of a game is never the reason it misses its window: a tick whose fetch
lands just outside 45-57 is simply not a decision, and the next tick, five
minutes later, tries again. The card, not this job, applies the window.

The refresh pass keeps its own NBA prop fetch (every game, seven days ahead),
card and close steps. This job adds looks; it removes none.

    python -m scripts.nba_prop_window                 # print what a tick would do
    python -m scripts.nba_prop_window --fetch G1 G2   # fetch props for these games
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.ingestors.nba_prop_close_ingestor as close_ing  # noqa: E402
import models.nba_prop_market as mk  # noqa: E402
import scripts.nba_prop_market_card as card  # noqa: E402
import scripts.nba_prop_projection_card as projection_card  # noqa: E402
from data.db import get_connection  # noqa: E402

_ET = ZoneInfo("America/New_York")

# Minutes before tip in which a game is fetched for a decision, both ends
# inclusive. Five minutes wider than DECISION_WINDOW_MIN (45, 57) at each end.
LOOK_AHEAD_MIN = (40, 62)


@dataclass
class Plan:
    decide: list[str] = field(default_factory=list)    # games to fetch and decide
    close: list[str] = field(default_factory=list)     # bet games owed a close
    project: list[str] = field(default_factory=list)   # games due the projection model's frame


def plan(conn, now: datetime) -> Plan:
    """What this tick has to do, from what is stored. No API call."""
    card.ensure_decisions_table(conn)
    games = card.slate(conn, now, horizon_min=LOOK_AHEAD_MIN[1])
    near = sorted(g for g, v in games.items()
                  if mk.minutes_to_tip(v["tip"], now) >= LOOK_AHEAD_MIN[0])
    if near:
        # a game is done only when BOTH NBA prop models have decided it
        rule_done = card.decided_games(conn, near) | card.games_with_a_bet(conn, near)
        proj_done = projection_card.decided_games(conn, near)
        near = [g for g in near if not (g in rule_done and g in proj_done)]
    bet = close_ing.bet_games(conn, now)
    taken = close_ing.closes_taken(conn, sorted(bet)) if bet else set()
    owed = sorted(g for g, v in bet.items()
                  if close_ing.due(v["tip"], now, has_bet=True, close_taken=g in taken))
    return Plan(decide=near, close=owed, project=projection_card.to_project(conn, now))


def plan_tick(now: datetime | None = None) -> Plan:
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc))
    finally:
        conn.close()


def fetch(game_ids: list[str], now: datetime | None = None) -> dict:
    """Props for exactly `game_ids`: the refresh pass's NBA fetch, restricted.

    days_ahead=1 so a game whose ET date is tomorrow (a tick just before
    midnight) is still in the feed's event list.
    """
    from data.ingestors.prop_odds_ingestor import run_prop_odds_ingestor
    now = now or datetime.now(timezone.utc)
    return run_prop_odds_ingestor(target_date=now.astimezone(_ET).date().isoformat(),
                                  snapshot_type="open", sport="NBA", days_ahead=1,
                                  only_game_ids=list(game_ids))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", nargs="+", metavar="GAME_ID",
                    help="fetch props for exactly these games")
    a = ap.parse_args()
    if a.fetch:
        result = fetch(a.fetch)
        logger.info(f"NBA prop window fetch: {result}")
        return
    print(plan_tick())


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/): the fetch is a paid
    # Odds API call. Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-prop-window")
    except Exception:  # noqa: BLE001
        pass

    main()
