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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import (
    LIVE_DAILY_CREDIT_CAP,
    LIVE_FG_DEBOUNCE_SEC,
    LIVE_STATE_MAX_AGE_SEC,
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

def _live_game_ids(conn: DBConnection) -> set[str]:
    """Games whose newest state snapshot is fresh AND says the game is live.

    Gates the floor fetch: without it the loop would keep buying odds every
    60s all day with nothing in progress."""
    cutoff = (datetime.now(timezone.utc)
              - timedelta(seconds=LIVE_STATE_MAX_AGE_SEC)).isoformat()
    rows = conn.execute("""
        SELECT DISTINCT ON (game_id) game_id, abstract_game_state
        FROM live_game_state
        WHERE snapshot_at >= %s
        ORDER BY game_id, snapshot_at DESC
    """, (cutoff,)).fetchall()
    return {r[0] for r in rows if r[1] == "Live"}


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
        fg_games, all_ids = split_triggers(pending)
        summary["fg_games"] = len(fg_games)

        # A FLOOR fetch, not only a triggered one.
        #
        # This used to `return` right here when no trigger was pending, so the
        # in-play line refreshed ONLY on an inning or score change. Measured on
        # 2026-08-29: DraftKings in-play snapshots landed on average every 269
        # SECONDS, with gaps up to 17 minutes -- against a LIVE_ODDS_MAX_AGE_SEC
        # of 300, so the loop was routinely allowed to price a live total that
        # was minutes old and bet it at a number the book had already left.
        # (CWS@MIN: published Over 9.5 -124, which was DK's real price at
        # 18:29:36; by 18:35 DK was on 10.5. The line was genuine, and stale.)
        #
        # The events we triggered on were a strict subset of the events that
        # move the line: a live total moves on every baserunner, not only on
        # runs and half-innings. A floor is the honest fix. The bulk endpoint
        # costs 3 credits however many games are live, so a 60s floor over a
        # 10-hour slate is ~1,800 credits against a 4.3M balance.
        live_now = _live_game_ids(conn)
        floor_due = bool(live_now) and should_fetch(_last_fg_fetch_age(conn))
        if not pending and not floor_due:
            return summary

        if fg_games or floor_due:
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
                # On a floor pass there is no triggering game, so score every
                # live one -- which is also what we want: a line that moved
                # without an inning or score change is exactly the case the
                # trigger set could not see.
                #
                # NEVER None. game_ids=None means "keep every event the bulk
                # feed returned", and that feed carries TOMORROW's games, which
                # have no `games` row yet -- so the insert dies on the odds FK
                # and takes the whole loop down (seen in production the first
                # pass after the floor shipped: MLB_2026-08-30_MIA_WSH). The
                # union is always non-empty here: the trigger branch requires
                # fg_games, the floor branch requires live_now.
                target = fg_games | live_now
                fetch = fetch_in_play_odds(conn, sport="MLB",
                                           game_ids=target, dry_run=dry_run)
                summary["fetched"] = True
                summary["credits"] = fetch["credits"]

                from models.live_scorer import run_live_scorer
                score = run_live_scorer(game_ids=target, dry_run=dry_run)
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
