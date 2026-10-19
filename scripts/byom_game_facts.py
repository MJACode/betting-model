"""Build NFL byom_game_facts from the lines already in the database.

Dry run unless --apply. Does not declare a worker job, so a merge does not
run this against production.

    python -m scripts.byom_game_facts
    python -m scripts.byom_game_facts --season 2024
    python -m scripts.byom_game_facts --season 2024 --apply
"""
from __future__ import annotations

import argparse
import json

from byom.constants import DK_HISTORY_START_SEASON


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, action="append",
                        help="one season; repeatable. Default: every season "
                             f"from {DK_HISTORY_START_SEASON} on")
    parser.add_argument("--apply", action="store_true",
                        help="write byom_game_facts. Without this, print only")
    args = parser.parse_args(argv)
    for season in args.season or []:
        if season < DK_HISTORY_START_SEASON:
            raise SystemExit(
                f"{season} is before DraftKings history "
                f"({DK_HISTORY_START_SEASON}); nothing to build")

    from data.db import get_connection
    from byom.load import build_seasons

    conn = get_connection()
    try:
        result = build_seasons(conn, args.season, apply=args.apply)
    finally:
        conn.close()
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
