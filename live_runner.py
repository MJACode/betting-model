"""
live_runner.py — one-pass driver for the live (in-play) betting loop.

A single pass does:
    1. poll_once       — refresh live_game_state + emit triggers (free MLB feed)
    2. process_pending_triggers — fetch in-play odds (debounced/capped) + score

This is the unit a short-cadence scheduler calls. Two runtime modes:

    # Single pass — for an external 15-60s scheduler, or run_pipeline --step live
    python live_runner.py --once

    # Persistent loop — what a small worker (Render/Fly ~$7/mo) runs as its
    # process command. Polls every LIVE_POLL_INTERVAL_SEC until no live games
    # remain for a few consecutive idle passes.
    python live_runner.py --loop

The tight loop does NOT fit GitHub Actions cron (5-min minimum, unreliable).
A `*/5` Actions cron calling `--step live` is the degraded day-1 fallback; an
always-on worker running `--loop` is the recommended host.
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from loguru import logger

from config import LIVE_POLL_INTERVAL_SEC
from data.db import get_connection
from data.ingestors.live_game_state_poller import poll_once
from data.ingestors.live_trigger_orchestrator import process_pending_triggers
from models.scorer import _get_current_bankroll

_ET = ZoneInfo("America/New_York")


def run_live_once(target_date: str = None, dry_run: bool = False) -> dict:
    """One full pass: poll game state, then dispatch odds + scoring on triggers."""
    if target_date is None:
        target_date = datetime.now(_ET).strftime("%Y-%m-%d")

    poll = poll_once(target_date=target_date, dry_run=dry_run)

    conn = get_connection()
    try:
        bankroll = _get_current_bankroll(conn)
        dispatch = process_pending_triggers(conn, target_date, bankroll, dry_run)
    finally:
        conn.close()

    summary = {
        "date":            target_date,
        "active_games":    poll.get("active_games", 0),
        "snapshots":       poll.get("snapshots", 0),
        "triggers":        poll.get("triggers", 0),
        **dispatch,
    }
    logger.info(f"live pass: {summary}")
    return summary


def run_live_loop(target_date: str = None, dry_run: bool = False,
                  max_idle_passes: int = 4) -> None:
    """Loop run_live_once until no active games for max_idle_passes cycles."""
    idle = 0
    while True:
        summary = run_live_once(target_date=target_date, dry_run=dry_run)
        if summary.get("active_games", 0) == 0:
            idle += 1
            if idle >= max_idle_passes:
                logger.info("No active games — live loop exiting.")
                return
        else:
            idle = 0
        time.sleep(LIVE_POLL_INTERVAL_SEC)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Live (in-play) betting runner")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously every LIVE_POLL_INTERVAL_SEC")
    parser.add_argument("--once", action="store_true",
                        help="Run a single pass (default)")
    parser.add_argument("--date", help="Target date YYYY-MM-DD (default: today ET)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Detect/score but write nothing to the DB")
    args = parser.parse_args()

    if args.loop:
        run_live_loop(target_date=args.date, dry_run=args.dry_run)
    else:
        run_live_once(target_date=args.date, dry_run=args.dry_run)
