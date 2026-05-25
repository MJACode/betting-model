"""
live_game_state_poller.py — Phase 1 of the live (in-play) betting build.

Polls the MLB Stats API live feed for every in-progress game on the given date,
writes a snapshot to `live_game_state`, and emits trigger rows to
`live_trigger_events` whenever a meaningful change is detected:

    inning_change     — currentInning or inning_half changed
    score_change      — home_score or away_score changed
    pitching_change   — current_pitcher_id changed
    due_up_change     — current_batter_id changed (next PA started)

Triggers are consumed by the trigger orchestrator (Phase 3 — not yet built).
This module never calls The Odds API and consumes zero Odds API credits.

Runtime modes
-------------
    # Continuous loop — poll every LIVE_POLL_INTERVAL_SEC until no games are live
    python -m data.ingestors.live_game_state_poller

    # Single pass (use from cron / external scheduler)
    python -m data.ingestors.live_game_state_poller --once

    # Single specific game (handy when manually verifying triggers)
    python -m data.ingestors.live_game_state_poller --game-id MLB_2026-05-25_NYY_BOS --once

    # Dry-run: detect and log triggers but write nothing to DB
    python -m data.ingestors.live_game_state_poller --dry-run

Schedule note
-------------
Long-lived `while True:` loops do not fit GitHub Actions (5 min cron minimum,
unreliable). Run via a background worker (Render/Fly.io ~$7/mo) or invoke
`--once` from an external 15-second scheduler. Phase 3 hardens this.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

import requests
import statsapi
from loguru import logger

from config import LIVE_POLL_INTERVAL_SEC, LIVE_PREGAME_BUFFER_MIN
from data.db import get_connection, DBConnection
from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS

_MLB_API_V11 = "https://statsapi.mlb.com/api/v1.1"


# ── MLB live feed helpers ─────────────────────────────────────────────────────

def _fetch_live_feed(mlbam_game_id: int) -> Optional[dict]:
    """Return the full /game/{id}/feed/live payload, or None on error."""
    url = f"{_MLB_API_V11}/game/{mlbam_game_id}/feed/live"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning(f"  Live feed error for game {mlbam_game_id}: {exc}")
        return None


def _bases_state(linescore: dict) -> str:
    """Encode runners as 3-char binary string: 1B-2B-3B. '101' = 1B+3B."""
    offense = linescore.get("offense") or {}
    return "".join(
        "1" if offense.get(base) else "0"
        for base in ("first", "second", "third")
    )


def _extract_state(feed: dict) -> dict:
    """Flatten the parts of the live feed we care about into a plain dict."""
    game_data    = feed.get("gameData", {}) or {}
    live_data    = feed.get("liveData", {}) or {}
    linescore    = live_data.get("linescore", {}) or {}
    plays        = live_data.get("plays", {}) or {}
    current_play = plays.get("currentPlay") or {}
    matchup      = current_play.get("matchup") or {}
    offense      = linescore.get("offense") or {}
    teams        = linescore.get("teams") or {}

    abstract_state = (game_data.get("status") or {}).get("abstractGameState")

    pitcher_id = None
    batter_id  = None
    on_deck_id = None
    if matchup:
        pitcher_id = (matchup.get("pitcher") or {}).get("id")
        batter_id  = (matchup.get("batter") or {}).get("id")
    # `offense.batter` is the live current batter (more current than play matchup)
    if offense.get("batter"):
        batter_id = offense["batter"].get("id", batter_id)
    if offense.get("onDeck"):
        on_deck_id = offense["onDeck"].get("id")

    return {
        "inning":              linescore.get("currentInning"),
        "inning_half":         (linescore.get("inningHalf") or "").lower() or None,
        "outs":                linescore.get("outs"),
        "bases_state":         _bases_state(linescore),
        "home_score":          (teams.get("home") or {}).get("runs"),
        "away_score":          (teams.get("away") or {}).get("runs"),
        "current_pitcher_id":  str(pitcher_id) if pitcher_id is not None else None,
        "current_batter_id":   str(batter_id) if batter_id is not None else None,
        "on_deck_batter_id":   str(on_deck_id) if on_deck_id is not None else None,
        "abstract_game_state": abstract_state,
    }


def _raw_state_debug(feed: dict) -> dict:
    """Tiny JSON blob worth keeping for debugging — strip pitch-level detail."""
    linescore = (feed.get("liveData") or {}).get("linescore", {}) or {}
    return {
        "currentInning":   linescore.get("currentInning"),
        "inningHalf":      linescore.get("inningHalf"),
        "outs":            linescore.get("outs"),
        "balls":           linescore.get("balls"),
        "strikes":         linescore.get("strikes"),
    }


# ── Trigger detection ─────────────────────────────────────────────────────────

_TRIGGER_FIELDS = {
    "inning_change":    ("inning", "inning_half"),
    "score_change":     ("home_score", "away_score"),
    "pitching_change":  ("current_pitcher_id",),
    "due_up_change":    ("current_batter_id",),
}


def _detect_triggers(prev: Optional[dict], curr: dict) -> list[tuple[str, str]]:
    """
    Compare two consecutive states and return [(trigger_type, detail), ...].
    On the very first snapshot (prev is None) we fire no triggers — we have
    nothing to compare against.
    """
    if prev is None:
        return []

    fired = []
    for trigger_type, fields in _TRIGGER_FIELDS.items():
        changed = [f for f in fields if prev.get(f) != curr.get(f)]
        if not changed:
            continue
        detail_parts = [
            f"{f}: {prev.get(f)} → {curr.get(f)}" for f in changed
        ]
        fired.append((trigger_type, "; ".join(detail_parts)))
    return fired


# ── DB helpers ────────────────────────────────────────────────────────────────

def _load_last_state(conn: DBConnection, game_id: str) -> Optional[dict]:
    row = conn.execute(
        """
        SELECT inning, inning_half, outs, bases_state,
               home_score, away_score,
               current_pitcher_id, current_batter_id, on_deck_batter_id,
               abstract_game_state
        FROM live_game_state
        WHERE game_id = %s
        ORDER BY snapshot_at DESC
        LIMIT 1
        """,
        (game_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "inning":              row[0],
        "inning_half":         row[1],
        "outs":                row[2],
        "bases_state":         row[3],
        "home_score":          row[4],
        "away_score":          row[5],
        "current_pitcher_id":  row[6],
        "current_batter_id":   row[7],
        "on_deck_batter_id":   row[8],
        "abstract_game_state": row[9],
    }


def _insert_state(
    conn: DBConnection,
    game_id: str,
    snapshot_at: str,
    state: dict,
    raw_state: dict,
) -> Optional[int]:
    """Insert a snapshot and return the new state_id (Postgres RETURNING)."""
    row = conn.execute(
        """
        INSERT INTO live_game_state (
            game_id, snapshot_at,
            inning, inning_half, outs, bases_state,
            home_score, away_score,
            current_pitcher_id, current_batter_id, on_deck_batter_id,
            abstract_game_state, raw_state
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        ) RETURNING state_id
        """,
        (
            game_id, snapshot_at,
            state["inning"], state["inning_half"], state["outs"], state["bases_state"],
            state["home_score"], state["away_score"],
            state["current_pitcher_id"], state["current_batter_id"], state["on_deck_batter_id"],
            state["abstract_game_state"], json.dumps(raw_state),
        ),
    ).fetchone()
    return row[0] if row else None


def _insert_triggers(
    conn: DBConnection,
    game_id: str,
    fired_at: str,
    new_state_id: Optional[int],
    triggers: list[tuple[str, str]],
) -> None:
    if not triggers or new_state_id is None:
        return
    rows = [
        {
            "game_id":      game_id,
            "fired_at":     fired_at,
            "trigger_type": trigger_type,
            "detail":       detail,
            "new_state_id": new_state_id,
        }
        for trigger_type, detail in triggers
    ]
    conn.executemany(
        """
        INSERT INTO live_trigger_events (
            game_id, fired_at, trigger_type, detail, new_state_id
        ) VALUES (
            %(game_id)s, %(fired_at)s, %(trigger_type)s, %(detail)s, %(new_state_id)s
        )
        """,
        rows,
    )


# ── Game discovery ────────────────────────────────────────────────────────────

def _game_id_from_statsapi(g: dict, target_date: str) -> Optional[str]:
    away = STATSAPI_TEAM_IDS.get(g["away_id"])
    home = STATSAPI_TEAM_IDS.get(g["home_id"])
    if not away or not home:
        return None
    return f"MLB_{target_date}_{away}_{home}"


def _is_active_or_starting_soon(g: dict) -> bool:
    """
    A game counts as 'active' if it is currently In Progress, or it is scheduled
    to start within LIVE_PREGAME_BUFFER_MIN. We keep polling Final games for one
    more cycle so the final state is captured, then drop them.
    """
    status = (g.get("status") or "").lower()
    abstract = (g.get("abstract_game_state") or "").lower()
    if abstract == "live" or "in progress" in status:
        return True
    if abstract == "final" or "final" in status or "game over" in status:
        return False
    # Pre-game — only include if first pitch is soon
    raw_time = g.get("game_datetime")
    if not raw_time:
        return False
    try:
        first_pitch = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
    except Exception:
        return False
    now = datetime.now(timezone.utc)
    return now >= first_pitch - timedelta(minutes=LIVE_PREGAME_BUFFER_MIN)


def _discover_active_games(target_date: str, only_game_id: Optional[str] = None) -> list[dict]:
    """Return list of {game_id, mlbam_id} for games we should poll right now."""
    try:
        schedule = statsapi.schedule(date=target_date, sportId=1)
    except Exception as exc:
        logger.error(f"statsapi.schedule failed: {exc}")
        return []

    out = []
    for g in schedule:
        game_id = _game_id_from_statsapi(g, target_date)
        if not game_id:
            continue
        if only_game_id and game_id != only_game_id:
            continue
        if not _is_active_or_starting_soon(g):
            continue
        out.append({"game_id": game_id, "mlbam_id": g["game_id"]})
    return out


# ── Core poll cycle ───────────────────────────────────────────────────────────

def _poll_one_game(
    conn: DBConnection,
    game_id: str,
    mlbam_id: int,
    dry_run: bool,
) -> dict:
    """Poll a single game once. Returns counts for telemetry."""
    feed = _fetch_live_feed(mlbam_id)
    if not feed:
        return {"snapshots": 0, "triggers": 0, "final": False}

    curr_state = _extract_state(feed)

    # If the game hasn't actually started yet (Preview), skip — no useful state.
    if curr_state["abstract_game_state"] not in ("Live", "Final"):
        logger.debug(f"  {game_id}: still Preview, skipping")
        return {"snapshots": 0, "triggers": 0, "final": False}

    snapshot_at  = datetime.now(timezone.utc).isoformat()
    prev_state   = _load_last_state(conn, game_id)
    triggers     = _detect_triggers(prev_state, curr_state)
    is_final     = curr_state["abstract_game_state"] == "Final"

    if dry_run:
        logger.info(
            f"  [DRY] {game_id} inning={curr_state['inning']}{curr_state['inning_half']} "
            f"score={curr_state['away_score']}-{curr_state['home_score']} "
            f"outs={curr_state['outs']} bases={curr_state['bases_state']} "
            f"triggers={[t[0] for t in triggers]}"
        )
        return {"snapshots": 1, "triggers": len(triggers), "final": is_final}

    new_state_id = _insert_state(conn, game_id, snapshot_at, curr_state, _raw_state_debug(feed))
    _insert_triggers(conn, game_id, snapshot_at, new_state_id, triggers)
    conn.commit()

    if triggers:
        logger.info(
            f"  {game_id} inning={curr_state['inning']}{curr_state['inning_half']} "
            f"score={curr_state['away_score']}-{curr_state['home_score']} "
            f"→ {len(triggers)} trigger(s): {[t[0] for t in triggers]}"
        )
    return {"snapshots": 1, "triggers": len(triggers), "final": is_final}


def poll_once(
    target_date: Optional[str] = None,
    only_game_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    """One pass over every active game. Safe to call repeatedly from cron."""
    if target_date is None:
        target_date = date.today().isoformat()

    games = _discover_active_games(target_date, only_game_id=only_game_id)
    if not games:
        logger.info(f"Live poller: no active games on {target_date}")
        return {"date": target_date, "active_games": 0, "snapshots": 0, "triggers": 0}

    logger.info(f"Live poller: {len(games)} active game(s) on {target_date}")

    totals = {"snapshots": 0, "triggers": 0, "final_seen": 0}
    conn = get_connection() if not dry_run else None
    fake_conn = _NoOpConn() if dry_run else conn

    try:
        for g in games:
            counts = _poll_one_game(fake_conn, g["game_id"], g["mlbam_id"], dry_run)
            totals["snapshots"]  += counts["snapshots"]
            totals["triggers"]   += counts["triggers"]
            totals["final_seen"] += int(counts["final"])
    finally:
        if conn is not None:
            conn.close()

    return {
        "date":         target_date,
        "active_games": len(games),
        **totals,
    }


def poll_forever(
    target_date: Optional[str] = None,
    only_game_id: Optional[str] = None,
    dry_run: bool = False,
    max_idle_passes: int = 4,
) -> None:
    """
    Loop until no active games remain for `max_idle_passes` consecutive cycles
    (gives Final games a few cycles to settle).
    """
    idle = 0
    while True:
        summary = poll_once(target_date=target_date, only_game_id=only_game_id, dry_run=dry_run)
        if summary["active_games"] == 0:
            idle += 1
            if idle >= max_idle_passes:
                logger.success(f"Live poller: idle for {idle} cycles, exiting.")
                return
        else:
            idle = 0
        time.sleep(LIVE_POLL_INTERVAL_SEC)


# ── Misc ──────────────────────────────────────────────────────────────────────

class _NoOpConn:
    """Stand-in connection used in --dry-run so we never touch the DB."""
    def execute(self, *_a, **_kw):
        class _Empty:
            def fetchone(self): return None
            def fetchall(self): return []
        return _Empty()
    def executemany(self, *_a, **_kw): pass
    def commit(self): pass
    def close(self): pass


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Poll MLB live feed and emit triggers")
    parser.add_argument("--date",    default=None, help="Date to poll (YYYY-MM-DD, default: today)")
    parser.add_argument("--game-id", default=None, help="Restrict to one game_id (e.g. MLB_2026-05-25_NYY_BOS)")
    parser.add_argument("--once",    action="store_true", help="Single pass instead of continuous loop")
    parser.add_argument("--dry-run", action="store_true", help="Detect triggers but write nothing")
    args = parser.parse_args()

    if args.once:
        poll_once(target_date=args.date, only_game_id=args.game_id, dry_run=args.dry_run)
    else:
        poll_forever(target_date=args.date, only_game_id=args.game_id, dry_run=args.dry_run)
