"""The NBA home team-total window: nba_team_total_luck's fetch, decision, close.

The fetch and the decision about an hour before each tip, the closing snapshot
12-25 minutes before it.

WHY. The graded bets were decided 54.3 to 64.4 minutes before tip (median
54.4), on a per-event team-total purchase (models/nba_team_total_luck.py). No
other job fetches team totals: the refresh pass and the full-game totals
window call the bulk endpoint, which never returns them.

ONE JOB, ONE PLANNING READ. This model's ticks run inside the NBA totals window
job (scheduler.run_nba_total_luck_window, every minute, 24x7), planned by the
same single read as nba_total_luck's (scripts/nba_pregame_window.py). A second
every-minute job would open a database connection on every tick for its
heartbeat alone (scheduler._with_heartbeat -> tracking/job_heartbeat.beat),
whatever its plan read.

WHAT A TICK DOES FOR THIS MODEL:
  1. plan(): the unstarted regular-season games tipping FETCH_LEAD_MIN (45-56)
     minutes from now that the card has not decided, and the games holding a
     nba_team_total_luck BET whose closing snapshot is due (CLOSE_LEAD_MIN,
     12-25 minutes out) and not yet taken. Reads only; no API call, no table
     created.
  2. --fetch G...: one team_totals call per named game, stored
     (data/ingestors/nba_team_total_odds.py). Exit 1 when a call failed, not
     when the books offered nothing.
  3. The card (step nba-team-total-luck) decides on that fetch.
  4. --close G...: the closing snapshot, filed 'close', for closing-line value
     only (the card reads 'open' only). The precedent is
     data/ingestors/nba_prop_close_ingestor.py: CLV is a bar from night one.
     Closing-line value reads a team total's close from 'close' rows only
     (tracking/paper_tracker._closing_odds), so without this snapshot the pick
     is not measured.

The first tick in the window, about 56 minutes out, decides; each later tick
down to 45 minutes is a backup for one that was skipped or failed.

    python -m scripts.nba_team_total_luck_window                 # print what a tick would do
    python -m scripts.nba_team_total_luck_window --fetch G1 G2   # decision fetch
    python -m scripts.nba_team_total_luck_window --close G1      # closing snapshot
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_team_total_luck as tt  # noqa: E402
import scripts.nba_team_total_luck_card as card  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
from data.db import get_connection  # noqa: E402

# Minutes before tip in which a bet game's closing snapshot is taken: one call,
# [tip - 25, tip - 12). Twelve is the inside edge because the tip is the
# scheduled start, and a quote taken after the real tip is an in-play price
# (the NBA prop close's own window, config.NBA_PROP_CLOSE_*_MIN).
CLOSE_LEAD_MIN = (12.0, 25.0)
# How far ahead the plan reads the slate: the top of the fetch window.
PLAN_HORIZON_MIN = max(tt.FETCH_LEAD_MIN[1], CLOSE_LEAD_MIN[1])
# The teams a game must have to be planned. The schedule holds NBA Cup
# knockout placeholders before their teams are known (games rows such as
# NBA_2026-12-04_nan_nan, home and away 'NaN', tipping at midnight Eastern,
# listed 'regular'; read 2026-10-20): no event in the feed is that game, so
# planning one would fail its call on every tick of its window.
TEAMS = frozenset(tt.config.NBA_ODDS_API_MAP.values())


def _matchup(g: dict) -> bool:
    return g.get("home") in TEAMS and g.get("away") in TEAMS


@dataclass
class Plan:
    decide: list[str] = field(default_factory=list)   # games to fetch and decide
    close: list[str] = field(default_factory=list)    # bet games owed their close


def close_due(tip: datetime, now: datetime) -> bool:
    lead = tt.lead_minutes(tip, now)
    return CLOSE_LEAD_MIN[0] < lead <= CLOSE_LEAD_MIN[1]


def plan(conn, now: datetime, games: dict[str, dict] | None = None) -> Plan:
    """What this tick has to do for nba_team_total_luck, from what is stored.

    `games` is the slate already read this tick (scripts/nba_pregame_window,
    which reads it once for both NBA totals models); without it, the plan
    reads its own. Reads only."""
    if games is None:
        games = tlcard.slate(conn, now, horizon_min=PLAN_HORIZON_MIN)
    games = {g: v for g, v in games.items() if _matchup(v)}
    lo, hi = tt.FETCH_LEAD_MIN
    near = sorted(g for g, v in games.items() if lo <= tt.lead_minutes(v["tip"], now) <= hi)
    done = card.decided_games(conn, near) if near else set()
    closing = sorted(g for g, v in games.items() if close_due(v["tip"], now))
    owed: list[str] = []
    if closing:
        from data.ingestors.nba_team_total_odds import closes_taken
        bet = card.games_with_a_bet(conn, closing)
        taken = closes_taken(conn, sorted(bet)) if bet else set()
        owed = sorted(bet - taken)
    return Plan(decide=[g for g in near if g not in done], close=owed)


def plan_tick(now: datetime | None = None) -> Plan:
    """This model's plan on its own connection: the command line's. The
    scheduler plans through scripts/nba_pregame_window.plan_tick instead."""
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc))
    finally:
        conn.close()


def fetch(game_ids: list[str], snapshot_type: str = "open") -> dict:
    from data.ingestors.nba_team_total_odds import fetch_team_totals
    return fetch_team_totals(game_ids, snapshot_type)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", nargs="+", metavar="GAME_ID",
                    help="fetch and store the team totals of exactly these games")
    ap.add_argument("--close", nargs="+", metavar="GAME_ID",
                    help="fetch and store these bet games' closing team totals")
    a = ap.parse_args()
    if a.fetch or a.close:
        kind, ids = ("open", a.fetch) if a.fetch else ("close", a.close)
        result = fetch(ids, kind)
        logger.info(f"NBA team total window {kind} fetch: {result}")
        if result.get("failed"):
            # A failed call is logged and the run goes on to the next game; a
            # run with one must say so, so the job's heartbeat records an
            # error. A game whose books offered no team total is not one.
            logger.error(f"NBA team total window: the {kind} call failed for "
                         f"{result['failed']}")
            sys.exit(1)
        return
    print(plan_tick())


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/): the fetch is a paid
    # Odds API call. Best-effort and silent.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-team-total-luck-window")
    except Exception:  # noqa: BLE001
        pass

    main()
