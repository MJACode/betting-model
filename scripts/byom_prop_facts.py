"""Build NFL byom_prop_facts from player_prop_odds and nfl_player_game_log.

Dry run unless --apply. No --season builds every NFL season from 2023
whose game_date is on or after 2023-09-01. The printed JSON is one
entry per season: facts, written, and canonical_keys.

Apply data/migrations/byom_prop_facts_dk_prices_2026_10_28.sql before
--apply. The declared job byom-nfl-prop-facts is the same no-season
write, enqueued once.

    python -m scripts.byom_prop_facts
    python -m scripts.byom_prop_facts --apply
    python -m scripts.byom_prop_facts --season 2024
    python -m scripts.byom_prop_facts --season 2024 --apply
"""
from __future__ import annotations

import argparse
import json

from byom.constants import PROP_HISTORY_START_SEASON


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, action="append")
    parser.add_argument("--apply", action="store_true",
                        help="write byom_prop_facts. Without this, print only")
    args = parser.parse_args(argv)
    for season in args.season or []:
        if season < PROP_HISTORY_START_SEASON:
            raise SystemExit(
                f"{season} is before player_prop_odds history "
                f"({PROP_HISTORY_START_SEASON}); nothing to build")

    from data.db import get_connection
    from byom.prop_load import build_seasons

    conn = get_connection()
    try:
        result = build_seasons(conn, args.season, apply=args.apply)
    finally:
        conn.close()
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
