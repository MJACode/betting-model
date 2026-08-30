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
    had no line" when in fact we never asked.

    `snapshot_at` is the BOOK'S last_update where the market carries one, and
    only falls back to the caller's clock where it does not. This matches what
    the pre-game ingestor already stores, and it is what makes the log answer
    the question actually asked of it: not "when did we look" but "when did
    DraftKings last publish this". A log stamped with our clock shows a frozen
    price refreshing every five seconds, which is precisely the illusion that
    let a four-minute-old Florida State total get bet on 2026-08-29."""
    out = []
    h2h = quote.get("h2h") or {}
    if h2h.get("home") is not None or h2h.get("away") is not None:
        out.append(build_row(game_id, sport, "h2h", bookmaker,
                             h2h.get("ts") or snapshot_at,
                             home_price=h2h.get("home"),
                             away_price=h2h.get("away")))
    total = quote.get("total") or {}
    if total.get("line") is not None and (total.get("over") is not None
                                          or total.get("under") is not None):
        out.append(build_row(game_id, sport, "totals", bookmaker,
                             total.get("ts") or snapshot_at,
                             total_line=total.get("line"),
                             over_price=total.get("over"),
                             under_price=total.get("under")))
    spread = quote.get("spread") or {}
    if spread.get("line") is not None:
        out.append(build_row(game_id, sport, "spreads", bookmaker,
                             spread.get("ts") or snapshot_at,
                             spread_home=spread.get("line"),
                             home_price=spread.get("home"),
                             away_price=spread.get("away")))
    return out


def quote_from_nfl_quotes(quotes, bookmaker: str) -> dict:
    """Fold the NFL live model's flat `Quote` rows into the {h2h, total,
    spread} shape this module already writes.

    The NFL feed parses one row per OUTCOME (side, price, line, ts) while the
    NCAAF feed parses one record per event. Rather than teach the writer two
    shapes, the flat rows are folded here — so NFL live prices land in exactly
    the same `odds` rows, with the same in-play isolation, as every other
    sport. Only `bookmaker` is kept; the log records what we priced against,
    and the live model prices against one book."""
    rec: dict = {"h2h": {}, "total": {}, "spread": {}}
    for q in quotes or []:
        if getattr(q, "bookmaker", None) != bookmaker:
            continue
        market, side = getattr(q, "market", None), getattr(q, "side", None)
        price, line = getattr(q, "price", None), getattr(q, "line", None)
        ts = getattr(q, "ts", None)
        ts = ts.isoformat() if hasattr(ts, "isoformat") else ts
        if market == "h2h" and side in ("home", "away"):
            rec["h2h"][side] = price
            rec["h2h"]["ts"] = ts
        elif market == "totals" and side in ("over", "under"):
            rec["total"][side] = price
            rec["total"]["line"] = line
            rec["total"]["ts"] = ts
        elif market == "spreads" and side == "home":
            rec["spread"]["home"] = price
            rec["spread"]["line"] = line
            rec["spread"]["ts"] = ts
        elif market == "spreads" and side == "away":
            rec["spread"]["away"] = price
            rec["spread"].setdefault("ts", ts)
    return {k: (v or None) for k, v in rec.items()}


# One entry per (game, market, book publish) already written by this process.
# Polling runs an order of magnitude faster than a book republishes — 5s against
# a measured 47s median — so without this the log stores ~10 identical rows per
# publish and stops being readable as a price history. Bounded because a long
# Saturday would otherwise grow it without limit; a restart costs one duplicate
# row per market, which is cheaper than unbounded memory.
_WRITTEN: set[tuple] = set()
_WRITTEN_CAP = 20000


def _publish_key(row: dict) -> tuple:
    return (row["game_id"], row["market"], row["bookmaker"], row["snapshot_at"])


def _mark_written(rows: list[dict]) -> None:
    """Recorded only AFTER the insert commits. Marking on the way in would drop
    a publish permanently the one time the write fails."""
    if len(_WRITTEN) >= _WRITTEN_CAP:
        _WRITTEN.clear()
    _WRITTEN.update(_publish_key(r) for r in rows)


def record_live_prices(conn, rows: Iterable[dict],
                       known_game_ids: Optional[set[str]] = None) -> int:
    """Append in-play rows, one per book publish. Returns how many were written.

    `known_game_ids` is not optional in spirit: `odds.game_id` is a foreign key,
    and the bulk in-play feeds carry games with no `games` row (tomorrow's
    slate, other divisions). Writing one of those raises a FK violation that
    aborts the transaction — which is exactly how the MLB floor fetch took the
    live loop down the day it shipped. Pass the games you are pricing."""
    seen: set[tuple] = set()
    fresh = []
    for r in rows:
        if known_game_ids is not None and r["game_id"] not in known_game_ids:
            continue
        key = _publish_key(r)
        if key in _WRITTEN or key in seen:
            continue
        seen.add(key)
        fresh.append(r)
    rows = fresh
    if not rows:
        return 0
    try:
        from data.ingestors.odds_ingestor import _insert_odds
        _insert_odds(conn, rows)
        conn.commit()
        _mark_written(rows)
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
