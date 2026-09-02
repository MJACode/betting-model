"""
Persist the in-play prices the NFL live model decides on.

WHY THIS IS PLATFORM-SIDE AND NOT INSIDE `nfl/`. The §28 package is deliberately
self-contained — it has its own feeds, its own recorder, and no database. The
platform's bridge to it has always lived here (`nfl_wind_publisher` writes its
picks and its line snapshots), so the audit trail follows the same seam: the
worker hands over the quotes it already fetched, and every piece of DB knowledge
— team-name resolution, the games index, the foreign key — stays on this side.
`nfl/` keeps running standalone with no platform installed, because the call is
a soft import there.

WHY IT EXISTS AT ALL. A live price we published but cannot show later is a price
we cannot defend. MLB and NCAAF both write their in-play snapshots to `odds`;
NFL was the last live lane that did not, and it is about to post its first live
number in Week 1. Wiring it now means the first time someone asks "the book says
51, why did you post 46.5" the answer is a query rather than an argument.

Zero extra credits: the anchor fetch has already been paid for by the time this
is called.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import LINE_SHOP_BOOKMAKERS
from data.db import get_connection
from data.ingestors.live_price_log import (
    now_iso, quote_from_nfl_quotes, record_live_prices, rows_from_quote)

# How far either side of now a `games` row may sit and still be "the game these
# quotes are about". Generous on purpose: an NFL game runs past three hours and
# the anchor is a slate-wide board, so the risk being managed is matching the
# WRONG week's meeting of the same two teams, not missing today's.
_WINDOW = timedelta(hours=8)


def _abbrev(name):
    """Odds API team name -> the abbrev `games` stores. Unknown names return
    None and are skipped: a guessed mapping writes prices onto the wrong game,
    which is worse than no audit row."""
    if not name:
        return None
    try:
        from nfl.data_ingest.parse import TEAM_MAP
    except Exception:                                    # noqa: BLE001
        return None
    return TEAM_MAP.get(name) or TEAM_MAP.get(str(name).strip())


def game_index(conn, now: datetime | None = None) -> dict:
    """{(home_abbrev, away_abbrev): game_id} for NFL games in the window."""
    now = now or datetime.now(timezone.utc)
    lo, hi = (now - _WINDOW).isoformat(), (now + _WINDOW).isoformat()
    rows = conn.execute("""
        SELECT game_id, home_team, away_team FROM games
        WHERE sport = 'NFL' AND commence_time IS NOT NULL
          AND commence_time::timestamptz BETWEEN %s::timestamptz AND %s::timestamptz
    """, (lo, hi)).fetchall()
    return {(r[1], r[2]): r[0] for r in rows}


def rows_for_quotes(quotes, index: dict, snapshot_at: str) -> list[dict]:
    """Anchor quotes -> `odds` rows, one per (game, market, book)."""
    out = []
    by_game: dict[tuple, list] = {}
    for q in quotes or []:
        key = (_abbrev(getattr(q, "home_team", None)),
               _abbrev(getattr(q, "away_team", None)))
        if key not in index:
            continue
        by_game.setdefault(key, []).append(q)
    for key, qs in by_game.items():
        books = {getattr(q, "bookmaker", None) for q in qs}
        for book in sorted(b for b in books if b in LINE_SHOP_BOOKMAKERS):
            quote = quote_from_nfl_quotes(qs, book)
            out.extend(rows_from_quote(index[key], "NFL", quote, book,
                                       snapshot_at))
    return out


def record_nfl_anchor_prices(quotes) -> int:
    """Entry point for the live worker. Never raises: an audit trail must not be
    able to stop a bet being priced."""
    if not quotes:
        return 0
    conn = None
    try:
        conn = get_connection()
        index = game_index(conn)
        if not index:
            return 0
        rows = rows_for_quotes(quotes, index, now_iso())
        return record_live_prices(conn, rows,
                                  known_game_ids=set(index.values()))
    except Exception as exc:                             # noqa: BLE001
        logger.warning(f"NFL live price log failed (non-fatal): {exc}")
        return 0
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:                            # noqa: BLE001
                pass
