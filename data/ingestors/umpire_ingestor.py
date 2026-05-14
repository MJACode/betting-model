"""
umpire_ingestor.py — Fetch MLB home-plate umpire assignments from MLB Stats API.

Stores one row per game in the `umpires` table:
    game_id, game_date, umpire_name, umpire_source='mlb_stats_api'

k_per_game and k_plus_minus are left NULL here; the feature engine computes
them on-the-fly from player_game_log so the stats stay ASOF-correct and always
current without requiring a separate pre-compute step.

Usage:
    python -m data.ingestors.umpire_ingestor --backfill 2019 2025
    python -m data.ingestors.umpire_ingestor --date 2026-05-13   # today or specific date
    python -m data.ingestors.umpire_ingestor                      # defaults to today
"""

import argparse
import time
from datetime import date, timedelta
from pathlib import Path
import sys

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.db import get_connection

# MLB Stats API team_id → 3-letter abbreviation (same map used elsewhere)
_TEAM_IDS: dict[int, str] = {
    109: "ARI", 144: "ATL", 110: "BAL", 111: "BOS", 112: "CHC",
    145: "CWS", 113: "CIN", 114: "CLE", 115: "COL", 116: "DET",
    117: "HOU", 118: "KC",  108: "LAA", 119: "LAD", 146: "MIA",
    158: "MIL", 142: "MIN", 121: "NYM", 147: "NYY", 133: "OAK",
    143: "PHI", 134: "PIT", 135: "SD",  136: "SEA", 137: "SF",
    138: "STL", 139: "TB",  140: "TEX", 141: "TOR", 120: "WSH",
}

_SCHEDULE_URL = (
    "https://statsapi.mlb.com/api/v1/schedule"
    "?sportId=1&date={date}&hydrate=officials"
)


def _fetch_umpires_for_date(game_date: str) -> list[dict]:
    """
    Call MLB Stats API and return a list of dicts:
        {game_id, game_date, umpire_name, umpire_source}

    Returns empty list on API error or if no completed games with officials found.
    """
    try:
        resp = requests.get(_SCHEDULE_URL.format(date=game_date), timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(f"umpire fetch failed for {game_date}: {exc}")
        return []

    results = []
    for day in data.get("dates", []):
        for game in day.get("games", []):
            home_id = game.get("teams", {}).get("home", {}).get("team", {}).get("id")
            away_id = game.get("teams", {}).get("away", {}).get("team", {}).get("id")
            home_abbr = _TEAM_IDS.get(home_id)
            away_abbr = _TEAM_IDS.get(away_id)
            if not home_abbr or not away_abbr:
                continue

            hp_umpire = None
            for official in game.get("officials", []):
                if official.get("officialType") == "Home Plate":
                    hp_umpire = official.get("official", {}).get("fullName")
                    break

            if hp_umpire is None:
                continue  # no HP umpire announced yet — skip

            game_id = f"MLB_{game_date}_{away_abbr}_{home_abbr}"
            results.append({
                "game_id":       game_id,
                "game_date":     game_date,
                "umpire_name":   hp_umpire,
                "umpire_source": "mlb_stats_api",
            })

    return results


def ingest_umpires_for_date(game_date: str) -> int:
    """
    Fetch HP umpire assignments for game_date and upsert into the umpires table.
    Idempotent — existing rows are updated if umpire_name changes (e.g. substitution).

    Returns the number of rows written.
    """
    records = _fetch_umpires_for_date(game_date)
    if not records:
        logger.debug(f"No umpire assignments found for {game_date}")
        return 0

    conn = get_connection()
    try:
        written = 0
        for r in records:
            # Use WHERE EXISTS so spring-training / All-Star games that aren't
            # in our games table are silently skipped (avoids FK violation).
            conn.execute("""
                INSERT INTO umpires (game_id, game_date, umpire_name, umpire_source)
                SELECT %s, %s, %s, %s
                WHERE EXISTS (SELECT 1 FROM games WHERE game_id = %s)
                ON CONFLICT (game_id) DO UPDATE
                    SET umpire_name   = EXCLUDED.umpire_name,
                        umpire_source = EXCLUDED.umpire_source
            """, (r["game_id"], r["game_date"], r["umpire_name"], r["umpire_source"],
                  r["game_id"]))
            written += 1

        conn.commit()
        logger.info(f"Umpires: {written} rows written for {game_date}")
        return written

    except Exception as exc:
        conn.rollback()
        logger.error(f"umpire upsert failed for {game_date}: {exc}")
        raise
    finally:
        conn.close()


def backfill_umpires(start_year: int, end_year: int) -> int:
    """
    Backfill HP umpire assignments for all dates in the games table between
    start_year and end_year (inclusive).

    Only fetches dates not already fully populated in the umpires table.
    Skips API calls for dates where all games already have umpire data.
    """
    conn = get_connection()

    # Get all distinct game dates in the requested year range that exist in games
    all_dates = conn.execute("""
        SELECT DISTINCT game_date
        FROM games
        WHERE sport = 'MLB'
          AND EXTRACT(YEAR FROM game_date::DATE) BETWEEN %s AND %s
        ORDER BY game_date
    """, (start_year, end_year)).fetchall()

    # Dates already fully covered in umpires table
    done_dates = conn.execute("""
        SELECT DISTINCT game_date FROM umpires
    """).fetchall()
    conn.close()

    done_set = {r[0] for r in done_dates}
    pending  = [r[0] for r in all_dates if r[0] not in done_set]

    logger.info(
        f"Umpire backfill {start_year}-{end_year}: "
        f"{len(all_dates)} total dates, {len(done_set)} already done, "
        f"{len(pending)} to fetch"
    )

    total_written = 0
    for i, game_date in enumerate(pending, 1):
        written = ingest_umpires_for_date(game_date)
        total_written += written
        if i % 50 == 0:
            logger.info(f"  Progress: {i}/{len(pending)} dates processed")
        # Polite pause — MLB Stats API has no documented rate limit but
        # rapid-fire requests occasionally trigger 429s on bulk backfills.
        time.sleep(0.15)

    logger.success(
        f"Umpire backfill complete: {total_written} assignments written "
        f"across {len(pending)} dates"
    )
    return total_written


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest MLB HP umpire assignments")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill years START through END (e.g. --backfill 2019 2025)")
    parser.add_argument("--date", help="Ingest a specific date YYYY-MM-DD")
    args = parser.parse_args()

    if args.backfill:
        backfill_umpires(args.backfill[0], args.backfill[1])
    elif args.date:
        ingest_umpires_for_date(args.date)
    else:
        today = date.today().isoformat()
        ingest_umpires_for_date(today)
