"""
Remove the `games` rows a historical odds snapshot created for games that were
never on the board -- and only those.

Session 280 (2026-09-10): `book_timing_snapshot.py` went through the odds
ingestor's `_upsert_games`, which created 11 NCAAF rows for already-played
FCS-visitor games (two with the mascot in the id). None ever had a pick, so
CLAUDE.md 1c's carve-out applies: rows that were never a pick may be deleted.
The snapshot's odds rows for those ids go with them; the odds rows on the 92
real games stay.

Scoped three ways, all required: sport NCAAF, `data_source='live'`, created
inside the snapshot's own write window. A row with a pick is never touched,
whatever the window says. Dry-run by default.

    python -m scripts.ncaaf_search.remove_snapshot_game_rows --from 2026-09-11T03:40Z --to 2026-09-11T03:50Z
    python -m scripts.ncaaf_search.remove_snapshot_game_rows --from ... --to ... --apply
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.db import get_connection  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--from", dest="t0", required=True)
    ap.add_argument("--to", dest="t1", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()

    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.game_date,
                   (SELECT COUNT(*) FROM odds o WHERE o.game_id = g.game_id) AS odds_rows,
                   (SELECT COUNT(*) FROM picks p WHERE p.game_id = g.game_id) AS picks
            FROM games g
            WHERE g.sport = 'NCAAF' AND g.data_source = 'live'
              AND g.created_at::timestamptz BETWEEN %s::timestamptz AND %s::timestamptz
            ORDER BY g.game_id
        """, (a.t0, a.t1)).fetchall()
        doomed = [r[0] for r in rows if r[3] == 0]
        kept = [r[0] for r in rows if r[3] > 0]
        for gid, gd, n_odds, n_picks in rows:
            print(f"  {gid}  odds={n_odds}  picks={n_picks}  {'DELETE' if n_picks == 0 else 'KEEP (has picks)'}")
        print(f"{len(doomed)} to delete, {len(kept)} kept")
        if not a.apply or not doomed:
            print("dry run" if not a.apply else "nothing to do")
            return
        ph = ",".join(["%s"] * len(doomed))
        n_odds = conn.execute(f"DELETE FROM odds WHERE game_id IN ({ph})", tuple(doomed))._cur.rowcount
        n_games = conn.execute(f"DELETE FROM games WHERE game_id IN ({ph})", tuple(doomed))._cur.rowcount
        conn.commit()
        print(f"deleted {n_odds} odds rows and {n_games} games rows")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
