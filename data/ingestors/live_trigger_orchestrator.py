"""
live_trigger_orchestrator.py — Phase 3 of the live (in-play) betting build.

Consumes pending `live_trigger_events` (produced by live_game_state_poller),
fetches in-play DraftKings odds for the affected games (debounced + capped),
and dispatches the live scorer. One pass is one unit of work — call it from
live_runner.py on a short cadence.

Cadence (this round — game-level FG markets only; props are out of scope):
    inning_change OR score_change  → fetch h2h+totals (debounced LIVE_FG_DEBOUNCE_SEC) → score
    pitching_change / due_up_change → consumed (stamped) but no fetch (no live prop models yet)

Spend controls:
    LIVE_FG_DEBOUNCE_SEC  — at most one odds fetch per game inside this window.
    LIVE_DAILY_CREDIT_CAP — once today's logged credits reach the cap, stop
                            fetching new odds (scoring still runs off existing
                            in_play rows — that's free). 0 = uncapped.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import LIVE_FG_DEBOUNCE_SEC, LIVE_DAILY_CREDIT_CAP
from data.db import get_connection, DBConnection
from data.ingestors.live_odds_ingestor import fetch_in_play_odds
from models.live_scorer import run_live_scorer
from models.scorer import _get_current_bankroll

_ET = ZoneInfo("America/New_York")
_FG_TRIGGERS = ("inning_change", "score_change")

_LIVE_STATE_COLS = ["inning", "inning_half", "outs", "bases_state",
                    "home_score", "away_score", "current_pitcher_id",
                    "current_batter_id", "on_deck_batter_id", "abstract_game_state"]


def _now_iso() -> str:
    return datetime.now(_ET).isoformat()


def _seconds_since(iso_ts: str | None) -> float:
    """Seconds between an ISO timestamp and now, or +inf if unparseable/None."""
    if not iso_ts:
        return float("inf")
    try:
        then = datetime.fromisoformat(iso_ts)
        if then.tzinfo is None:
            then = then.replace(tzinfo=_ET)
        return (datetime.now(_ET) - then).total_seconds()
    except Exception:
        return float("inf")


def _latest_state(conn: DBConnection, game_id: str) -> dict | None:
    row = conn.execute(f"""
        SELECT {', '.join(_LIVE_STATE_COLS)}
        FROM live_game_state
        WHERE game_id = ?
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id,)).fetchone()
    return dict(zip(_LIVE_STATE_COLS, row)) if row else None


def _last_fetch_seconds(conn: DBConnection, game_id: str, target_date: str) -> float:
    row = conn.execute("""
        SELECT MAX(fired_at) FROM live_credit_telemetry
        WHERE game_id = ? AND date = ?
    """, (game_id, target_date)).fetchone()
    return _seconds_since(row[0] if row else None)


def _credits_spent_today(conn: DBConnection, target_date: str) -> int:
    row = conn.execute("""
        SELECT COALESCE(SUM(credits), 0) FROM live_credit_telemetry WHERE date = ?
    """, (target_date,)).fetchone()
    return int(row[0]) if row and row[0] is not None else 0


def process_pending_triggers(conn: DBConnection, target_date: str,
                             bankroll: float, dry_run: bool = False) -> dict:
    """
    Drain pending FG triggers: fetch in-play odds (debounced/capped) and score.
    Returns a summary dict. Stamps dispatched_at on every trigger it consumes.
    """
    triggers = conn.execute("""
        SELECT trigger_id, game_id, trigger_type, fired_at
        FROM live_trigger_events
        WHERE dispatched_at IS NULL
        ORDER BY fired_at
    """).fetchall()
    if not triggers:
        return {"triggers_seen": 0, "games_dispatched": 0, "credits_spent": 0, "picks": 0}

    # Games that need an FG refresh+score this pass (dedupe).
    fg_games = []
    seen = set()
    consumed_ids = []
    for trigger_id, game_id, trigger_type, _fired in triggers:
        consumed_ids.append(trigger_id)
        if trigger_type in _FG_TRIGGERS and game_id not in seen:
            seen.add(game_id)
            fg_games.append(game_id)

    spent_today = _credits_spent_today(conn, target_date)
    capped = LIVE_DAILY_CREDIT_CAP > 0 and spent_today >= LIVE_DAILY_CREDIT_CAP
    if capped:
        logger.warning(f"live cap reached ({spent_today}/{LIVE_DAILY_CREDIT_CAP}) — "
                       f"scoring off existing odds only")

    credits_spent = 0
    pick_count = 0
    games_dispatched = 0

    for game_id in fg_games:
        # Debounce: skip a fresh fetch if we pulled odds recently for this game.
        recent = _last_fetch_seconds(conn, game_id, target_date) < LIVE_FG_DEBOUNCE_SEC
        if not capped and not recent and not dry_run:
            credits = fetch_in_play_odds(game_id)
            if credits:
                conn.execute("""
                    INSERT INTO live_credit_telemetry (date, game_id, market, credits, fired_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (target_date, game_id, "h2h+totals", credits, _now_iso()))
                conn.commit()
                credits_spent += credits
                spent_today += credits
                if LIVE_DAILY_CREDIT_CAP > 0 and spent_today >= LIVE_DAILY_CREDIT_CAP:
                    capped = True

        state = _latest_state(conn, game_id)
        if state and (state.get("abstract_game_state") or "") == "Live":
            picks = run_live_scorer(conn, game_id, state, bankroll, dry_run)
            pick_count += len(picks)
            games_dispatched += 1

    # Stamp every consumed trigger (FG + prop/due-up) so the queue drains.
    if consumed_ids and not dry_run:
        placeholders = ",".join(["?"] * len(consumed_ids))
        conn.execute(f"""
            UPDATE live_trigger_events SET dispatched_at = ?
            WHERE trigger_id IN ({placeholders})
        """, (_now_iso(), *consumed_ids))
        conn.commit()

    return {
        "triggers_seen":   len(triggers),
        "games_dispatched": games_dispatched,
        "credits_spent":   credits_spent,
        "picks":           pick_count,
    }


def run_orchestrator_once(target_date: str = None, dry_run: bool = False) -> dict:
    """Standalone one-pass entrypoint (live_runner.py also calls process_pending_triggers)."""
    if target_date is None:
        target_date = datetime.now(_ET).strftime("%Y-%m-%d")
    conn = get_connection()
    try:
        bankroll = _get_current_bankroll(conn)
        return process_pending_triggers(conn, target_date, bankroll, dry_run)
    finally:
        conn.close()
