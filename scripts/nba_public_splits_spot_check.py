"""
Spot-check stored NBA public splits against what Action Network serves now.

Action Network's public-betting page renders a past date in the browser from
the same scoreboard JSON the ingestor reads (the page's server render ignores
?date=, and the old per-game pages answer HTTP 410), so the source a reader
sees for a past game IS that JSON. This re-fetches it fresh -- no cache -- for
the given games and prints stored vs served, per endpoint, market and side.

Read-only; free endpoints only.

    python -m scripts.nba_public_splits_spot_check NBA_2024-01-15_HOU_PHI ...
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def main(game_ids: list[str]) -> int:
    from data.db import get_connection
    from data.ingestors import nba_public_splits_ingestor as ing

    conn = get_connection()
    index, _ = ing.load_games_index(conn, (2021, 2027))
    known = ing._known_abbrs()
    mismatches = 0
    for gid in game_ids:
        stored = conn.execute(
            "SELECT endpoint, market, side, line_value, odds, tickets_pct, "
            "money_pct, an_game_id, game_date, home_team, away_team "
            "FROM nba_public_splits WHERE game_id = %s AND capture_kind = %s "
            "ORDER BY endpoint, market, side", (gid, ing.ARCHIVE)).fetchall()
        if not stored:
            print(f"{gid}: nothing stored")
            mismatches += 1
            continue
        an_id, day = stored[0][7], stored[0][8]
        print(f"\n{gid}  (Action Network game {an_id}, {stored[0][10]} at {stored[0][9]})")
        for endpoint in ("v1", "v2"):
            data = ing.fetch_scoreboard(endpoint, day, cache_dir=None)
            game = next((g for g in data.get("games") or [] if g.get("id") == an_id), None)
            served = {}
            if game:
                rows, _ = ing.build_rows(game, endpoint, index, known,
                                         capture_kind=ing.ARCHIVE, fetched_at="now")
                served = {(r["market"], r["side"]): r for r in rows}
            for ep, market, side, line, odds, tix, money, *_ in stored:
                if ep != endpoint:
                    continue
                s = served.get((market, side))
                got = (s["line_value"], s["odds"], s["tickets_pct"], s["money_pct"]) if s else None
                want = (None if line is None else float(line), odds,
                        None if tix is None else float(tix),
                        None if money is None else float(money))
                norm = None if got is None else (
                    None if got[0] is None else float(got[0]), got[1],
                    None if got[2] is None else float(got[2]),
                    None if got[3] is None else float(got[3]))
                ok = norm == want
                mismatches += not ok
                print(f"  {endpoint} {market:8s} {side:6s} stored line={want[0]} "
                      f"price={want[1]} tickets={want[2]} money={want[3]}  | "
                      f"served now {norm}  {'SAME' if ok else 'DIFFERENT'}")
    conn.close()
    print(f"\nmismatches: {mismatches}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
