#!/usr/bin/env python3
"""
Record whether a pick was actually placeable at the book, at its number.

    python -m scripts.mark_placeable --pick-id 2691365 --no  --by mike --note "gone by 5:35pm"
    python -m scripts.mark_placeable --pick-id 2691366 --yes --by mike
    python -m scripts.mark_placeable --report            # fresh-number picks and their answers

WHY (mike, 2026-09-22). The opener fires on a soft book's number that differs
from Pinnacle's. When that number appeared seconds ago it is either a book
error -- the best bet the model can find, if it can be placed -- or a feed
ghost nobody could bet. The feed cannot tell them apart and neither can the
backtest (docs/sessions/2026-09.md, 2026-09-22). The person who tries to place
it can. This is where that answer is kept, one row per pick, so the question
is settled by the record.

Writes `pick_placement_checks` (data/migrations/pick_placement_checks_2026_09_22.sql).
Upsert: re-running with a different answer replaces the earlier one. The pick
itself is never touched.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

FRESH_RE = r"· NEW \d+m|· age unknown"


def mark(conn, pick_id: int, placeable: bool, by: str, note: str | None) -> dict:
    row = conn.execute(
        "SELECT pick_id, model_id, pick_label, created_at FROM picks WHERE pick_id = %s",
        (pick_id,)).fetchone()
    if not row:
        raise SystemExit(f"no pick {pick_id}")
    conn.execute("""
        INSERT INTO pick_placement_checks (pick_id, placeable, checked_by, note)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (pick_id) DO UPDATE
        SET placeable = EXCLUDED.placeable, checked_by = EXCLUDED.checked_by,
            note = EXCLUDED.note, checked_at = now()
    """, (pick_id, placeable, by, note))
    conn.commit()
    return {"pick_id": row[0], "model_id": row[1], "pick_label": row[2],
            "created_at": row[3], "placeable": placeable}


def report(conn) -> list[dict]:
    """Every pick whose label says the number was fresh, with its answer."""
    rows = conn.execute(f"""
        SELECT p.pick_id, p.model_id, p.pick_label, p.created_at, p.result,
               c.placeable, c.checked_by, c.note
        FROM picks p LEFT JOIN pick_placement_checks c USING (pick_id)
        WHERE p.pick_label ~ %s
        ORDER BY p.created_at
    """, (FRESH_RE,)).fetchall()
    return [dict(pick_id=r[0], model_id=r[1], pick_label=r[2], created_at=r[3],
                 result=r[4], placeable=r[5], checked_by=r[6], note=r[7]) for r in rows]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-id", type=int)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--yes", action="store_true", help="the bet could be placed at that number")
    g.add_argument("--no", action="store_true", help="the number was not on the board")
    ap.add_argument("--by", default=None, help="who checked (mike / matt)")
    ap.add_argument("--note", default=None)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    from data.db import get_connection
    conn = get_connection()
    try:
        if a.report:
            rows = report(conn)
            if not rows:
                print("no fresh-number picks yet")
                return 0
            for r in rows:
                ans = "?" if r["placeable"] is None else ("PLACEABLE" if r["placeable"] else "NOT placeable")
                print(f"{r['pick_id']}  {r['created_at']}  {r['result'] or 'open':9s} {ans:14s} {r['pick_label']}"
                      + (f"  [{r['checked_by']}: {r['note']}]" if r["note"] else ""))
            n = sum(1 for r in rows if r["placeable"] is not None)
            y = sum(1 for r in rows if r["placeable"])
            print(f"\n{len(rows)} fresh-number pick(s), {n} checked, {y} placeable")
            return 0
        if not a.pick_id or not (a.yes or a.no) or not a.by:
            ap.error("--pick-id, one of --yes/--no, and --by are required")
        out = mark(conn, a.pick_id, a.yes, a.by, a.note)
        print(f"{out['pick_id']}  {out['pick_label']}  -> "
              f"{'PLACEABLE' if out['placeable'] else 'NOT placeable'} (by {a.by})")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
