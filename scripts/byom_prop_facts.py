"""Build byom_prop_facts from player_prop_odds and the sport's game log.

Dry run unless --apply. No --season builds every season of that sport
from 2023 whose game_date is on or after 2023-09-01. The printed JSON
is one entry per season: facts, written, and canonical_keys. Default
sport is NFL. NBA reads nba_player_game_log and the fourteen markets.

Apply data/migrations/byom_prop_facts_dk_prices_2026_10_28.sql before
--apply. NBA also needs
data/migrations/byom_nba_props_2026_10_29.sql so week may be null.
The declared job byom-nfl-prop-facts is the NFL no-season write,
enqueued once. NBA is not declared. Run it here.

    python -m scripts.byom_prop_facts
    python -m scripts.byom_prop_facts --apply
    python -m scripts.byom_prop_facts --season 2024
    python -m scripts.byom_prop_facts --sport NBA
    python -m scripts.byom_prop_facts --sport NBA --season 2027 --apply
"""
from __future__ import annotations

import argparse
import json

from byom.constants import PROP_HISTORY_START_SEASON


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", type=int, action="append")
    parser.add_argument("--sport", default="NFL",
                        help="NFL or NBA. Default NFL")
    parser.add_argument("--apply", action="store_true",
                        help="write byom_prop_facts. Without this, print only")
    args = parser.parse_args(argv)
    sport = str(args.sport or "NFL").strip().upper()
    if sport not in ("NFL", "NBA"):
        raise SystemExit(f"sport must be NFL or NBA, got {sport}")
    for season in args.season or []:
        if season < PROP_HISTORY_START_SEASON:
            raise SystemExit(
                f"{season} is before player_prop_odds history "
                f"({PROP_HISTORY_START_SEASON}); nothing to build")

    from data.db import get_connection
    from byom.prop_load import build_seasons

    conn = get_connection()
    try:
        result = build_seasons(conn, args.season, apply=args.apply, sport=sport)
    finally:
        conn.close()
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
