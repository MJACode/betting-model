"""
live_odds_ingestor.py — Phase 3 of the live (in-play) betting build.

In-play counterpart to odds_ingestor.py. Fetches current DraftKings game-level
lines (h2h + totals) for ONE in-progress game via The Odds API per-event
endpoint and writes them to the `odds` table with snapshot_type='in_play'.
Called by the trigger orchestrator when an FG-tier trigger fires.

The per-event endpoint returns whatever lines the book currently offers —
pre-game or live. Pre-game scoring/settlement queries filter
snapshot_type IN ('open','close'), so 'in_play' rows never pollute them.

COST GATE: live in-play odds volume needs The Odds API Pro tier (~$300/mo).
On the Starter tier the per-event endpoint returns 404/422 for live games →
_get_event_odds returns None → 0 rows written → the live scorer writes no pick
(identical to the F5 "no real DK odds → skip" path). This module therefore
ships and runs on Starter, and "turns on" on Pro with zero code change.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.db import get_connection, DBConnection
from data.ingestors.odds_ingestor import (
    SPORT_KEYS, _list_events, _get_event_odds, _process_events, _insert_odds,
    _normalize_team, _build_game_id,
)

_ET = ZoneInfo("America/New_York")
LIVE_FG_MARKETS = ("h2h", "totals")


def _event_to_game_id(ev: dict) -> str | None:
    """Compute our canonical MLB game_id from an Odds API event dict."""
    commence = ev.get("commence_time", "")
    try:
        dt = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        game_date = dt.astimezone(_ET).strftime("%Y-%m-%d")
    except Exception:
        return None
    home = _normalize_team(ev.get("home_team", ""), "MLB")
    away = _normalize_team(ev.get("away_team", ""), "MLB")
    if not home or not away:
        return None
    return _build_game_id("MLB", game_date, away, home)


def fetch_in_play_odds(game_id: str,
                       markets: tuple[str, ...] = LIVE_FG_MARKETS) -> int:
    """
    Fetch live DK h2h+totals for one game and store them as snapshot_type='in_play'.
    Returns the number of Odds API credits consumed (≈ len(markets) on a hit, 0
    when the book offers no live lines — the graceful-degradation path).
    """
    sport_key = SPORT_KEYS["MLB"]
    try:
        events = _list_events(sport_key)
    except Exception as exc:                       # noqa: BLE001
        logger.warning(f"live odds: events list failed: {exc}")
        return 0

    match = next((ev for ev in events if _event_to_game_id(ev) == game_id), None)
    if not match or not match.get("id"):
        logger.debug(f"live odds: no Odds API event matches {game_id}")
        return 0

    try:
        ev_odds = _get_event_odds(sport_key, match["id"], list(markets))
    except Exception as exc:                        # noqa: BLE001
        logger.warning(f"live odds: per-event fetch failed for {game_id}: {exc}")
        return 0
    if not ev_odds:
        # 404/422 — book not offering live lines for this event (e.g. Starter tier).
        return 0

    snapshot_at = datetime.now(_ET).isoformat()
    _, odds_rows = _process_events([ev_odds], "MLB",
                                   snapshot_type="in_play", snapshot_at=snapshot_at)
    odds_rows = [r for r in odds_rows if r.get("market") in markets]
    if not odds_rows:
        return len(markets)   # call was made (credits spent) but no usable rows

    conn = get_connection()
    try:
        n = _insert_odds(conn, odds_rows)
        conn.commit()
    finally:
        conn.close()
    logger.info(f"live odds: {game_id} → {n} in_play rows ({', '.join(markets)})")
    return len(markets)


def live_odds_lookup(conn: DBConnection, game_id: str, market: str) -> dict | None:
    """Latest DraftKings in-play odds snapshot for a game+market, or None."""
    cols = ["home_price", "away_price", "draw_price",
            "spread_home", "total_line", "over_price", "under_price"]
    row = conn.execute("""
        SELECT home_price, away_price, draw_price,
               spread_home, total_line, over_price, under_price
        FROM odds
        WHERE game_id = ? AND market = ?
          AND bookmaker = 'draftkings'
          AND snapshot_type = 'in_play'
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, market)).fetchone()
    return dict(zip(cols, row)) if row else None
