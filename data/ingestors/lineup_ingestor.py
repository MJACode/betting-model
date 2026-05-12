"""
lineup_ingestor.py — Fetch confirmed MLB batting lineups from MLB Stats API.

Writes 9 rows per team per game to lineup_slots once lineups are posted.
Lineups typically appear 60-90 minutes before first pitch.

Uses the MLB live feed endpoint to check if a lineup has been announced.
Bat hand (L/R/S) is fetched via bulk people endpoint.

Run order in daily pipeline: after prop_odds, before scoring.
Mid-day refreshes also run this — lineups for early games post by 11am,
late games may not post until 2-3pm ET.

Usage:
    python -m data.ingestors.lineup_ingestor                      # today
    python -m data.ingestors.lineup_ingestor --date 2026-05-12    # specific date
"""

import argparse
import time
from datetime import date, datetime, timezone

import requests
import statsapi
from loguru import logger

from data.db import get_connection, DBConnection
from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS

# MLB Stats API base URLs
_MLB_API     = "https://statsapi.mlb.com/api/v1"
_MLB_API_V11 = "https://statsapi.mlb.com/api/v1.1"

# Numeric position code → abbreviation (MLB convention)
_POSITION_MAP = {
    "1":  "P",   "2":  "C",   "3":  "1B",  "4":  "2B",
    "5":  "3B",  "6":  "SS",  "7":  "LF",  "8":  "CF",
    "9":  "RF",  "10": "DH",  "11": "PH",  "12": "PR",
}


# ── MLB API helpers ───────────────────────────────────────────────────────────

def _fetch_lineup(mlbam_game_id: int) -> dict[str, list[tuple]]:
    """
    Fetch batting lineup from the MLB live feed for one game.

    Returns {side: [(player_id, full_name, batting_order, position), ...]}
    where side is 'home' or 'away'. Only includes sides whose lineups have
    been announced (battingOrder list is non-empty in the feed).
    """
    url = f"{_MLB_API_V11}/game/{mlbam_game_id}/feed/live"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(f"  Live feed error for game {mlbam_game_id}: {exc}")
        return {}

    teams = (
        data.get("liveData", {})
            .get("boxscore", {})
            .get("teams", {})
    )

    result: dict[str, list[tuple]] = {}
    for side in ("home", "away"):
        team_data     = teams.get(side, {})
        batting_order = team_data.get("battingOrder", [])
        if not batting_order:
            continue                         # lineup not yet posted for this side

        players = team_data.get("players", {})
        lineup  = []
        for pid in batting_order:
            p         = players.get(f"ID{pid}", {})
            order_raw = p.get("battingOrder", "")
            order     = int(order_raw) // 100 if order_raw else None
            pos_code  = p.get("position", {}).get("code", "")
            pos       = _POSITION_MAP.get(pos_code, pos_code)
            name      = p.get("person", {}).get("fullName", "")
            lineup.append((str(pid), name, order, pos))

        if lineup:
            result[side] = lineup

    return result


def _fetch_bat_hands(player_ids: list[str]) -> dict[str, str]:
    """
    Fetch batting hand for a list of MLBAM player IDs via bulk people endpoint.
    Returns {player_id: 'L' | 'R' | 'S'}.
    Batches at 50 IDs per request to stay within URL length limits.
    """
    hands: dict[str, str] = {}
    for i in range(0, len(player_ids), 50):
        batch = player_ids[i : i + 50]
        try:
            resp = requests.get(
                f"{_MLB_API}/people",
                params={"personIds": ",".join(batch)},
                timeout=10,
            )
            resp.raise_for_status()
            for person in resp.json().get("people", []):
                pid   = str(person["id"])
                code  = person.get("batSide", {}).get("code", "")
                hands[pid] = code
        except Exception as exc:
            logger.warning(f"  People endpoint error (batch {i}): {exc}")
        time.sleep(0.2)     # be polite to the API

    return hands


# ── Main ingest function ──────────────────────────────────────────────────────

def ingest_lineups_for_date(target_date: str = None) -> dict:
    """
    Fetch and store all confirmed MLB batting lineups for a given date.

    For each game scheduled on target_date:
      - Checks the MLB live feed for a posted batting order
      - If found, deletes any existing lineup_slots rows for that team + game
        and writes fresh rows (idempotent — safe to re-run as lineups update)
      - Skips sides whose lineups haven't been announced yet

    Returns a summary dict with counts.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    snapshot_at = datetime.now(timezone.utc).isoformat()

    logger.info(f"Lineup ingest — {target_date}")

    # ── 1. Get MLB schedule for the date ──────────────────────────────────────
    try:
        games = statsapi.schedule(date=target_date, sportId=1)
    except Exception as exc:
        logger.error(f"statsapi.schedule failed: {exc}")
        return {"date": target_date, "games": 0, "lineups_written": 0}

    if not games:
        logger.info(f"  No MLB games on {target_date}")
        return {"date": target_date, "games": 0, "lineups_written": 0}

    total_rows        = 0
    games_with_lineup = 0

    conn = get_connection()
    try:
        for g in games:
            mlbam_id    = g["game_id"]
            away_id     = g["away_id"]
            home_id     = g["home_id"]

            away_abbrev = STATSAPI_TEAM_IDS.get(away_id)
            home_abbrev = STATSAPI_TEAM_IDS.get(home_id)
            if not away_abbrev or not home_abbrev:
                logger.warning(f"  Unknown team IDs: away={away_id}, home={home_id} — skipping")
                continue

            game_id = f"MLB_{target_date}_{away_abbrev}_{home_abbrev}"

            # Confirm game exists in our DB (skip if not yet ingested by odds ingestor)
            row = conn.execute(
                "SELECT 1 FROM games WHERE game_id = %s", (game_id,)
            ).fetchone()
            if not row:
                logger.debug(f"  {game_id} not in games table — skipping")
                continue

            # ── 2. Fetch lineup from MLB live feed ────────────────────────────
            lineup_data = _fetch_lineup(mlbam_id)
            if not lineup_data:
                logger.debug(f"  {game_id}: no lineups posted yet")
                continue

            # ── 3. Bulk-fetch bat hands for all players in this game ──────────
            all_pids  = [pid for players in lineup_data.values() for pid, _, _, _ in players]
            bat_hands = _fetch_bat_hands(all_pids)

            # ── 4. Write lineup rows ──────────────────────────────────────────
            side_to_team  = {"home": home_abbrev, "away": away_abbrev}
            sides_written = 0

            for side, players in lineup_data.items():
                team = side_to_team[side]

                # Delete stale rows so re-runs stay clean
                conn.execute(
                    "DELETE FROM lineup_slots WHERE game_id = %s AND team = %s",
                    (game_id, team),
                )

                slot_rows = [
                    {
                        "game_id":       game_id,
                        "game_date":     target_date,
                        "team":          team,
                        "player_id":     pid,
                        "player_name":   name,
                        "batting_order": order,
                        "position":      pos,
                        "hand":          bat_hands.get(pid, ""),
                        "is_confirmed":  True,
                        "snapshot_at":   snapshot_at,
                    }
                    for pid, name, order, pos in players
                ]

                conn.executemany(
                    """
                    INSERT INTO lineup_slots (
                        game_id, game_date, team, player_id, player_name,
                        batting_order, position, hand, is_confirmed, snapshot_at
                    ) VALUES (
                        %(game_id)s, %(game_date)s, %(team)s, %(player_id)s, %(player_name)s,
                        %(batting_order)s, %(position)s, %(hand)s, %(is_confirmed)s, %(snapshot_at)s
                    )
                    """,
                    slot_rows,
                )
                total_rows += len(slot_rows)
                sides_written += 1
                logger.info(f"  {game_id} [{team}]: {len(slot_rows)} batters written")

            if sides_written:
                games_with_lineup += 1

        conn.commit()
    finally:
        conn.close()

    logger.success(
        f"Lineup ingest complete: {games_with_lineup}/{len(games)} games with lineups, "
        f"{total_rows} rows written"
    )
    return {
        "date":               target_date,
        "games":              len(games),
        "games_with_lineup":  games_with_lineup,
        "lineups_written":    total_rows,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest MLB batting lineups")
    parser.add_argument(
        "--date", default=None,
        help="Date to ingest (YYYY-MM-DD, default: today)"
    )
    args = parser.parse_args()
    ingest_lineups_for_date(args.date)
