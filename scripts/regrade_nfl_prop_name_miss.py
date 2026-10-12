"""Re-settle NFL prop picks that settled NO_ACTION only because the stat log
spells the player's first name differently (mike, 2026-10-12: "yes").

    python -m scripts.regrade_nfl_prop_name_miss --pick-ids 2329088 2371024
    python -m scripts.regrade_nfl_prop_name_miss --pick-ids ... --apply

The two picks this was written for, both 2026-09-17 DET@BUF, both NO_ACTION:
    2329088  Joshua Palmer Under 1.5 Rec (MGM)            -185
    2371024  Joshua Palmer Under 11.5 Rec Yds (betrivers)  -114
nfl_player_game_log has him as "Josh Palmer": 1 reception, 43 yards.

The settlement itself is NOT re-implemented here. Each named pick is reset to
unsettled and tracking.paper_tracker._settle_prop_picks runs for its date, so
the grade comes from the same code path as every other prop (with the
first-initial + surname fallback, tracking.paper_tracker._nfl_name_fallback).
Refuses a pick that is not an NFL prop BET settled NO_ACTION, and refuses a
date with any other unsettled prop BET, so nothing else is settled by accident.
Dry run by default: it prints what the settler WOULD write and rolls back.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db import get_connection
from tracking import paper_tracker as pt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick-ids", nargs="+", type=int, required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    conn = get_connection()
    rows = conn.execute("""
        SELECT pick_id, game_date, model_id, signal_type, result, pick_label
        FROM picks WHERE pick_id = ANY(%s)""", (a.pick_ids,)).fetchall()
    if len(rows) != len(a.pick_ids):
        raise SystemExit(f"found {len(rows)} of {len(a.pick_ids)} picks")
    dates = set()
    for pid, gd, mid, sig, res, label in rows:
        if not (str(mid).startswith("nfl_prop_") and sig == "BET" and res == "NO_ACTION"):
            raise SystemExit(f"refusing {pid} {label}: {mid} {sig} {res}")
        dates.add(str(gd))
    for d in sorted(dates):
        other = conn.execute("""
            SELECT count(*) FROM picks WHERE game_date = %s AND result IS NULL
              AND signal_type = 'BET' AND model_id LIKE 'nfl_prop_%%'""", (d,)).fetchone()[0]
        if other:
            raise SystemExit(f"{d} already has {other} unsettled NFL prop BETs; refusing")
    conn.execute("""UPDATE picks SET result = NULL, profit_flat = NULL,
                    profit_kelly = NULL, settled_at = NULL
                    WHERE pick_id = ANY(%s)""", (a.pick_ids,))
    settled_at = datetime.now(timezone.utc).isoformat()
    for d in sorted(dates):
        print(d, pt._settle_prop_picks(conn, d, settled_at))
    after = conn.execute("""SELECT pick_id, pick_label, result, profit_flat
                            FROM picks WHERE pick_id = ANY(%s) ORDER BY pick_id""",
                         (a.pick_ids,)).fetchall()
    for r in after:
        print(r)
    if a.apply:
        conn.commit()
        print("committed")
    else:
        conn.rollback()
        print("dry run: rolled back (pass --apply to write)")
    conn.close()


if __name__ == "__main__":
    main()
