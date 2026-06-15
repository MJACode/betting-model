"""
live_odds_ingestor.py — Phase 3 of the live (in-play) betting build.

Fetches in-play DraftKings odds and writes them to the existing `odds` table
with snapshot_type='in_play'. Called by live_trigger_orchestrator when an
FG-tier trigger (inning_change / score_change) fires.

Cost model (The Odds API): the bulk /sports/{key}/odds endpoint covers EVERY
live + upcoming event in ONE request, costed at #markets × #regions credits —
so a full-game ML/RL/O/U refresh is 3 credits no matter how many games are
in progress. Every fetch is recorded in `live_credit_telemetry`, which the
orchestrator reads to enforce LIVE_DAILY_CREDIT_CAP.

Isolation from the pre-game pipeline:
  - rows are tagged snapshot_type='in_play'
  - the pre-game scorer's `_get_dk_odds`, the training bulk odds lookup, and
    CLV close capture all EXCLUDE 'in_play' rows, so in-play prices can never
    leak into pre-game scoring, training features, or closing-line math.

F5 and player-prop in-play fetches are deliberately NOT implemented yet —
they are the credit cost drivers (per-event endpoint, per game) and there are
no live F5/prop models to consume them. See the Phase 3 TODOs in
live_trigger_orchestrator.py.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import ODDS_API_REGIONS
from data.db import get_connection, DBConnection
from data.ingestors.odds_ingestor import (
    MARKETS,
    SPORT_KEYS,
    _get_odds,
    _insert_odds,
    _process_events,
)

# Full-game markets fetched in-play. Bulk endpoint cost = len × regions.
LIVE_FG_MARKETS = list(MARKETS)          # ["h2h", "spreads", "totals"]


def _credit_cost(markets: list[str]) -> int:
    n_regions = len([r for r in ODDS_API_REGIONS.split(",") if r])
    return max(len(markets) * max(n_regions, 1), 1)


def record_credits(conn: DBConnection, purpose: str, credits: int,
                   game_id: Optional[str] = None,
                   fired_at: Optional[str] = None) -> None:
    """Append one telemetry row (drives the orchestrator's daily credit cap)."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""
        INSERT INTO live_credit_telemetry (date, game_id, market, credits, fired_at)
        VALUES (%s, %s, %s, %s, %s)
    """, (now[:10], game_id, purpose, credits, fired_at or now))


def credits_used_today(conn: DBConnection, today: Optional[str] = None) -> int:
    today = today or datetime.now(timezone.utc).isoformat()[:10]
    row = conn.execute("""
        SELECT COALESCE(SUM(credits), 0) FROM live_credit_telemetry
        WHERE date = %s
    """, (today,)).fetchone()
    return int(row[0]) if row else 0


def fetch_in_play_odds(conn: DBConnection,
                       sport: str = "MLB",
                       game_ids: Optional[set[str]] = None,
                       dry_run: bool = False) -> dict:
    """
    One bulk in-play odds fetch for `sport`. Writes snapshot_type='in_play'
    rows for the games in `game_ids` (None = all events returned).

    Returns {"odds_rows": n, "credits": n}.
    """
    sport_key = SPORT_KEYS[sport]
    snapshot_at = datetime.now(timezone.utc).isoformat()

    events = _get_odds(sport_key, LIVE_FG_MARKETS)
    credits = _credit_cost(LIVE_FG_MARKETS)

    # The bulk feed also returns upcoming (pre-game) events; keep only the
    # games the orchestrator asked for (the ones currently live).
    _, odds_rows = _process_events(events, sport, "in_play", snapshot_at)
    if game_ids is not None:
        odds_rows = [r for r in odds_rows if r["game_id"] in game_ids]

    if dry_run:
        logger.info(f"[DRY] in-play fetch: {len(odds_rows)} odds rows "
                    f"({credits} credits, not recorded)")
        return {"odds_rows": len(odds_rows), "credits": credits}

    if odds_rows:
        _insert_odds(conn, odds_rows)
    record_credits(conn, purpose=f"fg_bulk:{','.join(LIVE_FG_MARKETS)}",
                   credits=credits)
    conn.commit()

    logger.info(f"In-play odds: {len(odds_rows)} rows for "
                f"{len({r['game_id'] for r in odds_rows})} game(s) "
                f"[{credits} credits]")
    return {"odds_rows": len(odds_rows), "credits": credits}


# ── CLI (manual spot-checks) ──────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch in-play DK odds once")
    parser.add_argument("--sport",   default="MLB", choices=list(SPORT_KEYS.keys()))
    parser.add_argument("--game-id", default=None, help="Restrict to one game_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = get_connection()
    try:
        ids = {args.game_id} if args.game_id else None
        summary = fetch_in_play_odds(conn, sport=args.sport, game_ids=ids,
                                     dry_run=args.dry_run)
        logger.success(f"Done: {summary}")
    finally:
        conn.close()
