"""
Persist the in-play prices a live loop actually decided on.

WHY THIS EXISTS. When a published live number was questioned — "I opened DK and
it was 10.5, not 9.5" — the MLB pick was auditable (its loop writes every
in-play snapshot to `odds`) and the NCAAF one was not: that loop reads
DraftKings' in-play feed, prices against it, and throws it away. A price we
published but cannot show is a price we cannot defend, and the fix cannot be
per-sport: the same question will be asked of NFL the first time it posts a live
number.

So this is deliberately sport-agnostic. It takes whatever shape a loop already
has in hand and writes `odds` rows with snapshot_type='in_play' — the same rows,
same table, same isolation the MLB path uses, so every downstream reader (the
pre-game/in-play split, the all-books views, CLV) behaves identically for every
sport.

Non-fatal by construction: an audit trail must never be able to stop a bet being
priced. Every failure is logged and swallowed.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Iterable, Optional

log = logging.getLogger(__name__)

_COLS = ("home_price", "away_price", "draw_price", "spread_home", "total_line",
         "over_price", "under_price", "home_link", "away_link", "draw_link",
         "over_link", "under_link", "home_sid", "away_sid", "draw_sid",
         "over_sid", "under_sid")


def build_row(game_id: str, sport: str, market: str, bookmaker: str,
              snapshot_at: str, **values) -> dict:
    """One `odds` row, with every column the insert names present.

    executemany binds by NAME, so a missing key raises rather than defaulting —
    filling the full column set here is what lets a caller pass only the two or
    three fields its market actually has."""
    row = {"game_id": game_id, "sport": sport, "market": market,
           "bookmaker": bookmaker, "snapshot_type": "in_play",
           "snapshot_at": snapshot_at}
    for c in _COLS:
        row[c] = values.get(c)
    return row


def rows_from_quote(game_id: str, sport: str, quote: dict, bookmaker: str,
                    snapshot_at: str) -> list[dict]:
    """Rows for one game from the {h2h: {...}, total: {...}} shape both the
    NCAAF and NFL live feeds parse into.

    A market with no prices yields no row — an empty row would read as "the book
    had no line" when in fact we never asked."""
    out = []
    h2h = quote.get("h2h") or {}
    if h2h.get("home") is not None or h2h.get("away") is not None:
        out.append(build_row(game_id, sport, "h2h", bookmaker, snapshot_at,
                             home_price=h2h.get("home"),
                             away_price=h2h.get("away")))
    total = quote.get("total") or {}
    if total.get("line") is not None and (total.get("over") is not None
                                          or total.get("under") is not None):
        out.append(build_row(game_id, sport, "totals", bookmaker, snapshot_at,
                             total_line=total.get("line"),
                             over_price=total.get("over"),
                             under_price=total.get("under")))
    spread = quote.get("spread") or {}
    if spread.get("line") is not None:
        out.append(build_row(game_id, sport, "spreads", bookmaker, snapshot_at,
                             spread_home=spread.get("line"),
                             home_price=spread.get("home"),
                             away_price=spread.get("away")))
    return out


def record_live_prices(conn, rows: Iterable[dict],
                       known_game_ids: Optional[set[str]] = None) -> int:
    """Append in-play rows. Returns how many were written.

    `known_game_ids` is not optional in spirit: `odds.game_id` is a foreign key,
    and the bulk in-play feeds carry games with no `games` row (tomorrow's
    slate, other divisions). Writing one of those raises a FK violation that
    aborts the transaction — which is exactly how the MLB floor fetch took the
    live loop down the day it shipped. Pass the games you are pricing."""
    rows = [r for r in rows
            if known_game_ids is None or r["game_id"] in known_game_ids]
    if not rows:
        return 0
    try:
        from data.ingestors.odds_ingestor import _insert_odds
        _insert_odds(conn, rows)
        conn.commit()
        return len(rows)
    except Exception as exc:                         # noqa: BLE001
        log.warning("live price log failed (non-fatal): %s", exc)
        try:
            conn.rollback()
        except Exception:                            # noqa: BLE001
            pass
        return 0


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
