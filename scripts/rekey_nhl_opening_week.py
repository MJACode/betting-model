"""Re-key the NHL games the odds ingestor stored under invented team ids.

The odds feed spells two teams 'Montréal Canadiens' and 'St Louis Blues'; the
name map held 'Montreal' / 'St. Louis', and the fallback turned them into CAN
and BLU (worker log 2026-09-20). Every opening-week game involving either team
was stored as e.g. NHL_2026-09-29_CAN_TOR, which joins to no team stats and
would be written a SECOND time, as ..._MTL_TOR, the moment the name fix
deploys. The same rows also carry the old October season label on 09-29/30.

This moves the odds history; it deletes no snapshot. Those rows are two months of
NHL opener movement. Every table with a `game_id` column is checked, so a table
added later is not silently missed.

    python -m scripts.rekey_nhl_opening_week            # dry run: counts only
    python -m scripts.rekey_nhl_opening_week --apply
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, ".")

from data.db import get_connection
from data.season_labels import nhl_season_label

INVENTED = {"CAN": "MTL", "BLU": "STL"}


def _mapping(conn) -> dict[str, dict]:
    """old game_id -> the corrected row, for every NHL game with an invented id."""
    rows = conn.execute("""
        SELECT game_id, game_date, home_team, away_team
        FROM games
        WHERE sport = 'NHL' AND (home_team IN ('CAN','BLU') OR away_team IN ('CAN','BLU'))
    """).fetchall()
    out = {}
    for game_id, game_date, home, away in rows:
        h, a = INVENTED.get(home, home), INVENTED.get(away, away)
        out[game_id] = {"new_id": f"NHL_{game_date[:10]}_{a}_{h}", "home": h, "away": a}
    return out


def _tables_with_game_id(conn) -> list[str]:
    rows = conn.execute("""
        SELECT c.table_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = 'public' AND c.column_name = 'game_id'
          AND t.table_type = 'BASE TABLE' AND c.table_name <> 'games'
        ORDER BY 1
    """).fetchall()
    return [r[0] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = get_connection(session_mode=bool(args.apply))
    try:
        mapping = _mapping(conn)
        print(f"{len(mapping)} games stored under an invented team id")
        for old, m in sorted(mapping.items()):
            print(f"  {old}  ->  {m['new_id']}")

        # Once the name fix is deployed the ingestor writes the corrected id
        # itself, so a late run finds BOTH rows. Then the history moves under
        # the row that already exists and the invented one goes.
        for m in mapping.values():
            m["exists"] = bool(conn.execute("SELECT 1 FROM games WHERE game_id = ?",
                                            (m["new_id"],)).fetchone())
        print("corrected id already present for:",
              [m["new_id"] for m in mapping.values() if m["exists"]] or "none")

        old_ids = list(mapping)
        touched: dict[str, int] = {}
        if old_ids:
            marks = ",".join("?" for _ in old_ids)
            for table in _tables_with_game_id(conn):
                n = conn.execute(f"SELECT count(*) FROM {table} WHERE game_id IN ({marks})",
                                 tuple(old_ids)).fetchone()[0]
                if n:
                    touched[table] = n
        print("rows holding those ids:", touched or "none outside games")

        relabel = conn.execute("""
            SELECT game_id, game_date, season FROM games
            WHERE sport = 'NHL' AND game_date >= '2026-09-01' AND home_score IS NULL
        """).fetchall()
        wrong = [(g, d, s) for g, d, s in relabel if nhl_season_label(d) != s]
        print(f"{len(wrong)} unplayed games carry the wrong season label")
        for g, d, s in wrong:
            print(f"  {g}: {s} -> {nhl_season_label(d)}")

        if not args.apply:
            print("\ndry run — nothing written. Re-run with --apply.")
            return

        # `odds` carries a per-ROW update trigger that recomputes `latest_odds`
        # for the row's key. Moving 126,000 rows fired it 126,000 times and the
        # first --apply hit the 2-minute statement timeout with nothing written
        # (2026-09-20). For THIS transaction only: triggers off, a longer
        # timeout, and `latest_odds` rebuilt once per (game, market, book) at
        # the end by the same function the trigger calls.
        conn.execute("SET LOCAL session_replication_role = replica")
        conn.execute("SET LOCAL statement_timeout = '20min'")
        moved_keys: set[tuple[str, str, str]] = set()

        game_cols = [r[0] for r in conn.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = 'games'
            ORDER BY ordinal_position""").fetchall()]
        for old, m in mapping.items():
            # Children first would orphan them; parents first would break an FK.
            # Insert the corrected parent, move the children, drop the old parent.
            for mk, bk in conn.execute(
                    "SELECT DISTINCT market, bookmaker FROM odds WHERE game_id = ?",
                    (old,)).fetchall():
                moved_keys.add((m["new_id"], mk, bk))
            # The state table is rebuilt below, never moved by hand.
            conn.execute("DELETE FROM latest_odds WHERE game_id = ?", (old,))
            if m["exists"]:
                for table in touched:
                    if table != "latest_odds":
                        conn.execute(f"UPDATE {table} SET game_id = ? WHERE game_id = ?",
                                     (m["new_id"], old))
                conn.execute("DELETE FROM games WHERE game_id = ?", (old,))
                continue
            swap = {"game_id": m["new_id"], "home_team": m["home"], "away_team": m["away"]}
            select = ", ".join("?" if c in swap else c for c in game_cols)
            conn.execute(
                f"INSERT INTO games ({', '.join(game_cols)}) "
                f"SELECT {select} FROM games WHERE game_id = ?",
                tuple(swap[c] for c in game_cols if c in swap) + (old,))
            for table in touched:
                if table != "latest_odds":
                    conn.execute(f"UPDATE {table} SET game_id = ? WHERE game_id = ?",
                                 (m["new_id"], old))
            conn.execute("DELETE FROM games WHERE game_id = ?", (old,))
        for new_id, mk, bk in sorted(moved_keys):
            conn.execute("SELECT latest_odds_recompute(?, ?, ?)", (new_id, mk, bk))
        print(f"latest_odds rebuilt for {len(moved_keys)} (game, market, book) keys")
        for g, d, s in wrong:
            new_id = mapping.get(g, {}).get("new_id", g)
            conn.execute("UPDATE games SET season = ?, updated_at = NOW()::TEXT "
                         "WHERE game_id = ?", (nhl_season_label(d), new_id))
        conn.commit()
        print("\napplied.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
