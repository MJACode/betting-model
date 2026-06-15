"""
live_trigger_orchestrator.py — Phase 3 of the live (in-play) betting build.

Consumes `live_trigger_events` rows (produced by live_game_state_poller) and
decides when to spend Odds API credits and re-score:

    Trigger type                      | Action
    ----------------------------------+------------------------------------------
    inning_change / score_change      | bulk in-play FG odds fetch (debounced
                                      | LIVE_FG_DEBOUNCE_SEC) → run_live_scorer
                                      | for the triggering games
    pitching_change / due_up_change   | consumed with no action — there are no
                                      | live prop/F5 models yet (deferred; these
                                      | are the per-event credit cost drivers)

Credit safety: every fetch is logged to `live_credit_telemetry`; when
LIVE_DAILY_CREDIT_CAP > 0 and today's burn would exceed it, dispatching stops
(triggers are still stamped so the queue never grows unbounded).

Runtime modes
-------------
    # One pass: consume pending triggers, then exit (cron-friendly)
    python -m data.ingestors.live_trigger_orchestrator --once

    # Full live loop: poll game state + consume triggers every
    # LIVE_POLL_INTERVAL_SEC until no games are live (run on Matt's machine
    # or a background worker — NOT GitHub Actions)
    python -m data.ingestors.live_trigger_orchestrator --loop

    # Observe without writing odds/picks
    python -m data.ingestors.live_trigger_orchestrator --once --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    LIVE_DAILY_CREDIT_CAP,
    LIVE_FG_DEBOUNCE_SEC,
    LIVE_POLL_INTERVAL_SEC,
)
from data.db import get_connection, DBConnection
from data.ingestors.live_odds_ingestor import (
    LIVE_FG_MARKETS,
    _credit_cost,
    credits_used_today,
    fetch_in_play_odds,
)

# Trigger types that justify a full-game odds refresh.
FG_TRIGGER_TYPES = {"inning_change", "score_change"}
# Consumed silently until live prop/F5 models exist.
NOOP_TRIGGER_TYPES = {"pitching_change", "due_up_change"}


# ── Pure decision helpers (unit-tested) ───────────────────────────────────────

def split_triggers(pending: list[dict]) -> tuple[set[str], list[int]]:
    """
    Partition pending trigger rows into (fg_game_ids, all_trigger_ids).
    Unknown trigger types are treated as no-ops (consumed, no fetch).
    """
    fg_games: set[str] = set()
    ids: list[int] = []
    for t in pending:
        ids.append(t["trigger_id"])
        if t["trigger_type"] in FG_TRIGGER_TYPES:
            fg_games.add(t["game_id"])
    return fg_games, ids


def should_fetch(last_fetch_age_sec: Optional[float],
                 debounce_sec: int = LIVE_FG_DEBOUNCE_SEC) -> bool:
    """Debounce: at most one FG fetch per debounce window (None = never fetched)."""
    return last_fetch_age_sec is None or last_fetch_age_sec >= debounce_sec


def under_credit_cap(used_today: int, next_cost: int,
                     cap: int = LIVE_DAILY_CREDIT_CAP) -> bool:
    """cap <= 0 means uncapped."""
    return cap <= 0 or (used_today + next_cost) <= cap


# ── DB helpers ────────────────────────────────────────────────────────────────

def _pending_triggers(conn: DBConnection) -> list[dict]:
    rows = conn.execute("""
        SELECT trigger_id, game_id, trigger_type, fired_at
        FROM live_trigger_events
        WHERE dispatched_at IS NULL
        ORDER BY fired_at
    """).fetchall()
    return [dict(zip(["trigger_id", "game_id", "trigger_type", "fired_at"], r))
            for r in rows]


def _last_fg_fetch_age(conn: DBConnection) -> Optional[float]:
    """Seconds since the most recent in-play FG fetch (telemetry-based)."""
    row = conn.execute("""
        SELECT MAX(fired_at) FROM live_credit_telemetry
        WHERE market LIKE 'fg_bulk%%'
    """).fetchone()
    if not row or not row[0]:
        return None
    try:
        ts = datetime.fromisoformat(str(row[0]).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


def _stamp_dispatched(conn: DBConnection, trigger_ids: list[int]) -> None:
    if not trigger_ids:
        return
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join(["%s"] * len(trigger_ids))
    conn.execute(f"""
        UPDATE live_trigger_events SET dispatched_at = %s
        WHERE trigger_id IN ({placeholders})
    """, [now] + trigger_ids)


# ── Core ──────────────────────────────────────────────────────────────────────

def consume_triggers_once(dry_run: bool = False) -> dict:
    """
    One orchestration pass. Returns a telemetry summary dict.
    Safe to call from cron or from the --loop runner.
    """
    conn = get_connection()
    summary = {"pending": 0, "fg_games": 0, "fetched": False,
               "credits": 0, "picks": 0, "capped": False}
    try:
        pending = _pending_triggers(conn)
        summary["pending"] = len(pending)
        if not pending:
            return summary

        fg_games, all_ids = split_triggers(pending)
        summary["fg_games"] = len(fg_games)

        if fg_games:
            next_cost = _credit_cost(LIVE_FG_MARKETS)
            used = credits_used_today(conn)
            if not under_credit_cap(used, next_cost):
                summary["capped"] = True
                logger.warning(
                    f"Live credit cap hit ({used} used, cap "
                    f"{LIVE_DAILY_CREDIT_CAP}) — skipping fetch, "
                    f"consuming {len(all_ids)} trigger(s)")
            elif not should_fetch(_last_fg_fetch_age(conn)):
                logger.debug(f"FG fetch debounced "
                             f"({LIVE_FG_DEBOUNCE_SEC}s window) — "
                             f"triggers consumed, no fetch")
            else:
                fetch = fetch_in_play_odds(conn, sport="MLB",
                                           game_ids=fg_games, dry_run=dry_run)
                summary["fetched"] = True
                summary["credits"] = fetch["credits"]

                # Re-score the triggering games against the fresh lines.
                from models.live_scorer import run_live_scorer
                score = run_live_scorer(game_ids=fg_games, dry_run=dry_run)
                summary["picks"] = score.get("picks", 0)

        if not dry_run:
            _stamp_dispatched(conn, all_ids)
            conn.commit()
        return summary
    finally:
        conn.close()


def run_live_loop(target_date: Optional[str] = None,
                  dry_run: bool = False,
                  max_idle_passes: int = 4) -> None:
    """
    The single live-betting process: poll game state, then consume triggers,
    every LIVE_POLL_INTERVAL_SEC. Exits after `max_idle_passes` consecutive
    passes with no active games (slate over).
    """
    from data.ingestors.live_game_state_poller import poll_once

    logger.info(f"Live loop starting (interval {LIVE_POLL_INTERVAL_SEC}s, "
                f"FG debounce {LIVE_FG_DEBOUNCE_SEC}s, credit cap "
                f"{LIVE_DAILY_CREDIT_CAP or 'none'})")
    idle = 0
    while True:
        poll = poll_once(target_date=target_date, dry_run=dry_run)
        consume = consume_triggers_once(dry_run=dry_run)
        if consume["fetched"] or consume["picks"]:
            logger.info(f"Loop pass: {poll.get('active_games', 0)} active, "
                        f"{consume['fg_games']} triggered, "
                        f"{consume['picks']} live pick(s)")

        if poll.get("active_games", 0) == 0:
            idle += 1
            if idle >= max_idle_passes:
                logger.success(f"Live loop: idle for {idle} passes, exiting.")
                return
        else:
            idle = 0
        time.sleep(LIVE_POLL_INTERVAL_SEC)


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Consume live triggers → in-play odds → live picks")
    parser.add_argument("--once",    action="store_true",
                        help="Single orchestration pass (no polling)")
    parser.add_argument("--loop",    action="store_true",
                        help="Poll + orchestrate until the slate ends")
    parser.add_argument("--date",    default=None,
                        help="Date for --loop polling (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.loop:
        run_live_loop(target_date=args.date, dry_run=args.dry_run)
    elif args.once:
        summary = consume_triggers_once(dry_run=args.dry_run)
        logger.success(f"Orchestrator pass: {summary}")
    else:
        parser.print_help()
