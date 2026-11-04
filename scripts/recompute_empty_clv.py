#!/usr/bin/env python3
"""Recompute CLV for picks stamped measured with an empty close.

A row is in scope when ``clv_method`` is ``standard_v2`` and every closing
field is null: ``closing_dk_odds``, ``closing_line``, ``clv_pct``, ``clv_pp``,
``line_clv_pts``, ``market_clv_pct``, ``market_clv_pp``, ``pinnacle_close_odds``,
``clv_close_book``. The bet book and the captured-at stamp may be set. Those
rows were marked done without a close, so the capture will not revisit them.

Dry run is the default and writes nothing. ``--apply`` clears that stamp and
runs the capture for each game date in scope. ``--date YYYY-MM-DD`` and
``--sport`` (the game-id prefix: NCAAB, NBA) narrow it.

    python -m scripts.recompute_empty_clv
    python -m scripts.recompute_empty_clv --date 2026-11-03 --sport NCAAB
    python -m scripts.recompute_empty_clv --date 2026-11-03 --sport NCAAB --apply

This does not change a grade, a stake, or the record. It only refills closing
line value. Do not point it at production from a session that has not been
asked to write there.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from tracking.clv_math import CLV_METHOD_STANDARD

# Every closing field empty. clv_bet_book may still name the book we took.
_EMPTY = """
    p.clv_method = %s
    AND p.closing_dk_odds IS NULL
    AND p.closing_line IS NULL
    AND p.clv_pct IS NULL
    AND p.clv_pp IS NULL
    AND p.line_clv_pts IS NULL
    AND p.market_clv_pct IS NULL
    AND p.market_clv_pp IS NULL
    AND p.pinnacle_close_odds IS NULL
    AND p.clv_close_book IS NULL
"""

_SELECT = """
    SELECT p.pick_id, p.game_date, p.game_id, p.model_id
    FROM picks p
    WHERE
""" + _EMPTY

_CLEAR = """
    UPDATE picks p
    SET clv_method = NULL,
        clv_bet_book = NULL,
        clv_captured_at = NULL
    WHERE p.pick_id = ANY(%s)
      AND
""" + _EMPTY


def _filters(game_date: str | None, sport: str | None) -> tuple[str, list]:
    extra, params = "", []
    if game_date:
        extra += " AND p.game_date = %s"
        params.append(game_date)
    if sport:
        extra += " AND split_part(p.game_id, '_', 1) = %s"
        params.append(sport.strip().upper())
    return extra, params


def empty_close_picks(conn, game_date: str | None = None, sport: str | None = None):
    """Rows stamped standard_v2 with an empty close, oldest date first."""
    extra, params = _filters(game_date, sport)
    return conn.execute(
        _SELECT + extra + " ORDER BY p.game_date, p.pick_id",
        (CLV_METHOD_STANDARD, *params),
    ).fetchall()


def recompute_empty_clv(conn, *, apply: bool = False, game_date: str | None = None,
                        sport: str | None = None, captured_at: str | None = None,
                        capture=None) -> dict:
    """Dry-run by default. ``apply`` clears the empty stamp and recaptures.

    ``capture`` defaults to ``tracking.paper_tracker._capture_clv``. Tests pass
    their own. Nothing is committed here.
    """
    rows = empty_close_picks(conn, game_date, sport)
    ids = [r[0] for r in rows]
    dates = list(dict.fromkeys(str(r[1])[:10] for r in rows))
    summary = {
        "apply": bool(apply),
        "count": len(rows),
        "pick_ids": ids,
        "dates": dates,
        "captured": 0,
    }
    if not apply or not rows:
        return summary
    # The id list is already the date and sport scope. The empty-close
    # predicate is repeated so a row that gained a close between the read
    # and the write is left alone.
    conn.execute(
        "UPDATE picks p SET clv_method = NULL, clv_bet_book = NULL, "
        "clv_captured_at = NULL WHERE p.pick_id = ANY(%s) AND " + _EMPTY,
        (ids, CLV_METHOD_STANDARD),
    )
    if capture is None:
        from tracking.paper_tracker import _capture_clv
        capture = _capture_clv
    stamp = captured_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    captured = 0
    for day in dates:
        captured += capture(conn, day, stamp) or 0
    summary["captured"] = captured
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true",
                    help="clear the empty stamp and recapture (default is a dry run)")
    ap.add_argument("--date", help="game_date YYYY-MM-DD")
    ap.add_argument("--sport", help="game-id prefix, for example NCAAB")
    args = ap.parse_args(argv)

    from data.db import get_connection
    conn = get_connection()
    try:
        summary = recompute_empty_clv(
            conn, apply=args.apply, game_date=args.date, sport=args.sport)
        if args.apply:
            conn.commit()
        else:
            conn.rollback()
    finally:
        conn.close()
    verb = "rewrote" if summary["apply"] else "would rewrite"
    print(f"{verb} {summary['count']} pick(s) on {len(summary['dates'])} date(s)")
    if summary["pick_ids"]:
        print("pick_ids:", ", ".join(str(i) for i in summary["pick_ids"]))
    if summary["apply"]:
        print(f"capture updated {summary['captured']} pick(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
