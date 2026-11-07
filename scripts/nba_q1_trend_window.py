"""The NBA first-quarter spread window: nba_q1_trend's fetch, decision and close.

The fetch and the decision about an hour before each tip, the closing snapshot 12-25 minutes before it: the first-half
total's window (scripts/nba_first_half_total_luck_window.py), its lead constants imported. The graded bets were
decided on the per-game purchase 45-75 minutes before tip (models/nba_q1_trend.py). No other job fetches
first-quarter spreads.

ONE JOB, ONE PLANNING READ: this model's ticks run inside the NBA pre-game window job (scheduler
.run_nba_total_luck_window, every minute), planned by the same single read as the other NBA game models
(scripts/nba_pregame_window.py).

WHAT A TICK DOES FOR THIS MODEL:
  1. plan(): the unstarted regular-season games tipping FETCH_LEAD_MIN (45-56) minutes from now that the card has not
     decided, and the games holding an nba_q1_trend BET whose closing snapshot is due and not yet taken. Reads only.
  2. --fetch G...: one spreads_q1 call per named game, stored (data/ingestors/nba_first_quarter_odds.py). Exit 1 when
     a call failed, not when the books offered nothing.
  3. The card (step nba-q1-trend) decides on that fetch.
  4. --close G...: the closing snapshot, filed 'close', for closing-line value only (the card reads 'open' only).

    python -m scripts.nba_q1_trend_window                 # print what a tick would do
    python -m scripts.nba_q1_trend_window --fetch G1 G2   # decision fetch
    python -m scripts.nba_q1_trend_window --close G1      # closing snapshot
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_q1_trend as q1  # noqa: E402
import scripts.nba_q1_trend_card as card  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
from data.db import get_connection  # noqa: E402
from scripts.nba_team_total_luck_window import CLOSE_LEAD_MIN, Plan, close_due  # noqa: E402,F401
from scripts.nba_total_luck_window import has_teams  # noqa: E402

PLAN_HORIZON_MIN = max(q1.FETCH_LEAD_MIN[1], CLOSE_LEAD_MIN[1])


def plan(conn, now: datetime, games: dict[str, dict] | None = None) -> Plan:
    """What this tick has to do for nba_q1_trend, from what is stored. Reads only."""
    if games is None:
        games = tlcard.slate(conn, now, horizon_min=PLAN_HORIZON_MIN)
    games = {g: v for g, v in games.items() if has_teams(v)}
    lo, hi = q1.FETCH_LEAD_MIN
    near = sorted(g for g, v in games.items() if lo <= q1.lead_minutes(v["tip"], now) <= hi)
    done = card.decided_games(conn, near) if near else set()
    closing = sorted(g for g, v in games.items() if close_due(v["tip"], now))
    owed: list[str] = []
    if closing:
        from data.ingestors.nba_first_quarter_odds import closes_taken
        bet = card.games_with_a_bet(conn, closing)
        taken = closes_taken(conn, sorted(bet)) if bet else set()
        owed = sorted(bet - taken)
    return Plan(decide=[g for g in near if g not in done], close=owed)


def plan_tick(now: datetime | None = None) -> Plan:
    conn = get_connection()
    try:
        return plan(conn, now or datetime.now(timezone.utc))
    finally:
        conn.close()


def fetch(game_ids: list[str], snapshot_type: str = "open") -> dict:
    from data.ingestors.nba_first_quarter_odds import fetch_first_quarter
    return fetch_first_quarter(game_ids, snapshot_type)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--fetch", nargs="+", metavar="GAME_ID",
                    help="fetch and store the first-quarter spreads of exactly these games")
    ap.add_argument("--close", nargs="+", metavar="GAME_ID",
                    help="fetch and store these bet games' closing first-quarter spreads")
    a = ap.parse_args()
    if a.fetch or a.close:
        kind, ids = ("open", a.fetch) if a.fetch else ("close", a.close)
        result = fetch(ids, kind)
        logger.info(f"NBA first-quarter window {kind} fetch: {result}")
        if result.get("failed"):
            logger.error(f"NBA first-quarter window: the {kind} call failed for {result['failed']}")
            sys.exit(1)
        return
    print(plan_tick())


if __name__ == "__main__":
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nba-q1-trend-window")
    except Exception:  # noqa: BLE001
        pass
    main()
