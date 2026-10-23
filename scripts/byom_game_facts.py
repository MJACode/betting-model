"""Build byom_game_facts from the lines already in the database.

Dry run unless --apply. Does not declare a worker job, and does not
enable byom_refresh, so a merge does not run this against production.
--sport all is the backfill path. It still writes nothing without --apply.
The printed JSON counts spread and total sides priced via same_point,
via cross_point, and left as line_no_price. A null sport is NFL.

    python -m scripts.byom_game_facts
    python -m scripts.byom_game_facts --season 2024
    python -m scripts.byom_game_facts --sport NBA --season 2026
    python -m scripts.byom_game_facts --sport all
    python -m scripts.byom_game_facts --sport all --apply
"""
from __future__ import annotations

import argparse
import json

from byom.constants import DK_HISTORY_START_SEASON


def sports_requested(values: list[str] | None) -> list[str] | None:
    """Sport codes to build. None means every sport in games.

    The default is NFL. `all` is the backfill across sports.
    """
    raw = values or ["NFL"]
    if any(str(item).strip().lower() == "all" for item in raw):
        return None
    sports = []
    for item in raw:
        sport = str(item).strip().upper()
        if sport:
            sports.append(sport)
    return sports


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, action="append",
                        help="one season; repeatable. Default: every season "
                             "that sport has in games")
    parser.add_argument("--sport", action="append",
                        help="one sport; repeatable. Default: NFL. "
                             "`all` builds every sport in games")
    parser.add_argument("--apply", action="store_true",
                        help="write byom_game_facts. Without this, print only")
    args = parser.parse_args(argv)
    sports = sports_requested(args.sport)
    if sports is not None and "NFL" in sports:
        for season in args.season or []:
            if season < DK_HISTORY_START_SEASON:
                raise SystemExit(
                    f"{season} is before DraftKings history "
                    f"({DK_HISTORY_START_SEASON}); nothing to build")

    from data.db import get_connection
    from byom.load import build_seasons, sports_in_games

    conn = get_connection()
    try:
        chosen = sports_in_games(conn) if sports is None else sports
        result = [
            build_seasons(conn, args.season, apply=args.apply, sport=sport)
            for sport in chosen
        ]
    finally:
        conn.close()
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
