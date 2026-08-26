"""
NCAAF weather backfill — Open-Meteo historical weather for NCAAF games.

Uses ncaaf_venues (lat/lon) for coordinates and the dome flag. Writes to the
existing game_weather table (same schema as MLB weather). For NCAAF we skip
wind_out_component (no field orientation) and write raw wind_mph instead.

Open-Meteo's archive API supports date ranges, so we batch by venue+date to
reduce API calls. Rate-limited to ~0.3s per call to stay under their free tier.

Usage:
    python -m scripts.ncaaf_weather_backfill --seasons 2025
    python -m scripts.ncaaf_weather_backfill --seasons 2014 2025
"""

import argparse
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection

_HISTORICAL_API = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_API = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_CUTOFF_DAYS = 5

# CFB games kick off around 12pm-8pm local time. We target 3pm local (15:00)
# as the median and convert to UTC using longitude.
_DEFAULT_GAME_HOUR_LOCAL = 15


def _utc_offset_from_lon(lon: float) -> int:
    """Rough UTC offset from longitude (continental US only)."""
    return round(lon / 15.0)


def _celsius_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)


def _fetch_weather(lat: float, lon: float, game_date: str) -> dict | None:
    """Fetch hourly weather from Open-Meteo for a single date."""
    today = date.today()
    target = date.fromisoformat(game_date)
    days_old = (today - target).days

    if days_old > _ARCHIVE_CUTOFF_DAYS:
        base_url = _HISTORICAL_API
        params = {
            "latitude": lat, "longitude": lon,
            "start_date": game_date, "end_date": game_date,
            "hourly": "temperature_2m,windspeed_10m,precipitation",
            "windspeed_unit": "mph", "timezone": "UTC",
        }
    else:
        base_url = _FORECAST_API
        params = {
            "latitude": lat, "longitude": lon,
            "hourly": "temperature_2m,windspeed_10m,precipitation",
            "windspeed_unit": "mph", "timezone": "UTC",
            # days_old is NEGATIVE for future games: a game 3 days ahead gives
            # (today - target).days = -3, and the old expression min(days_old+2, 16)
            # produced forecast_days = -1, which Open-Meteo rejects. Cover the
            # horizon out to the game date plus one day, capped at the API max.
            "forecast_days": min(max(-days_old + 2, 2), 16),
        }

    try:
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(f"Open-Meteo failed for {game_date} ({lat},{lon}): {exc}")
        return None

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    temps = hourly.get("temperature_2m", [])
    winds = hourly.get("windspeed_10m", [])
    precip = hourly.get("precipitation", [])

    if not times:
        return None

    # Target game-time hour in UTC
    rough_utc_hour = (_DEFAULT_GAME_HOUR_LOCAL - _utc_offset_from_lon(lon)) % 24
    target_time = f"{game_date}T{rough_utc_hour:02d}:00"

    best_idx = 0
    for idx, t in enumerate(times):
        if t <= target_time:
            best_idx = idx

    temp_c = temps[best_idx] if best_idx < len(temps) else None
    wind_mph = winds[best_idx] if best_idx < len(winds) else None
    precip_mm = precip[best_idx] if best_idx < len(precip) else None

    if temp_c is None or wind_mph is None:
        return None

    return {
        "temp_f": _celsius_to_f(temp_c),
        "wind_mph": round(float(wind_mph), 1),
        "precip_mm": round(float(precip_mm), 2) if precip_mm is not None else 0.0,
    }


def backfill(start_season: int, end_season: int) -> None:
    conn = get_connection()
    try:
        # All completed NCAAF games with venue coords, not yet in game_weather
        rows = conn.execute("""
            SELECT g.game_id, g.game_date, g.home_team, v.latitude, v.longitude,
                   v.dome, v.name AS venue_name
            FROM games g
            JOIN ncaaf_venues v ON v.venue_id = g.venue_id
            LEFT JOIN game_weather gw ON gw.game_id = g.game_id
            WHERE g.sport = 'NCAAF'
              AND g.season >= %s AND g.season <= %s
              AND g.home_score IS NOT NULL
              AND v.latitude IS NOT NULL AND v.longitude IS NOT NULL
              AND gw.game_id IS NULL
            ORDER BY g.game_date
        """, (start_season, end_season)).fetchall()

        logger.info(f"NCAAF weather backfill: {len(rows)} games to process "
                    f"({start_season}-{end_season})")

        written = 0
        for i, (game_id, game_date, home_team, lat, lon, dome, venue) in enumerate(rows, 1):
            is_dome = bool(dome)

            if is_dome:
                # Dome games: fixed comfortable conditions, no API call needed
                conn.execute("""
                    INSERT INTO game_weather (
                        game_id, game_date, home_team, venue,
                        temp_f, wind_mph, wind_dir_deg, wind_out_component,
                        precip_mm, is_dome_game, fetched_at
                    ) VALUES (%s, %s, %s, %s, 72.0, 0.0, NULL, 0.0, 0.0, 1, %s)
                    ON CONFLICT (game_id) DO NOTHING
                """, (game_id, game_date, home_team, venue or "Unknown",
                      datetime.now(tz=timezone.utc).isoformat()))
                written += 1
            else:
                wx = _fetch_weather(lat, lon, game_date)
                if wx is None:
                    continue

                conn.execute("""
                    INSERT INTO game_weather (
                        game_id, game_date, home_team, venue,
                        temp_f, wind_mph, wind_dir_deg, wind_out_component,
                        precip_mm, is_dome_game, fetched_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, NULL, 0.0, %s, 0, %s)
                    ON CONFLICT (game_id) DO NOTHING
                """, (game_id, game_date, home_team, venue or "Unknown",
                      wx["temp_f"], wx["wind_mph"], wx["precip_mm"],
                      datetime.now(tz=timezone.utc).isoformat()))
                written += 1
                time.sleep(0.3)

            if i % 100 == 0:
                conn.commit()
                logger.info(f"  {i}/{len(rows)} games processed, {written} written")

        conn.commit()
        logger.success(f"NCAAF weather backfill complete: {written}/{len(rows)} rows written")
    finally:
        conn.close()


def ingest_upcoming(days_ahead: int = 7) -> int:
    """
    Forecast weather for UPCOMING NCAAF games -- the serve-time counterpart of
    the historical backfill. Without this, the totals model (which trains on
    wx_temp_f / wx_wind_mph / wx_precip_mm) scores every live game with NaN
    weather: train/serve skew on its own repair feature.

    Unlike the backfill this UPSERTS (DO UPDATE), so a day-6 forecast is
    replaced by the sharper day-1 forecast on later runs. Wired into the daily
    pipeline as `--step ncaaf-weather`; each run refreshes every game inside
    the window, ~60-80 Open-Meteo calls on a full Saturday slate, free tier.
    """
    today = date.today()
    hi = (today + __import__("datetime").timedelta(days=days_ahead)).isoformat()
    conn = get_connection()
    written = 0
    try:
        # Odds-created games carry venue_id = NULL (the odds ingestor knows no
        # venues; CFBD's schedule ingest fills them later). Rather than skip
        # those -- which on launch week is EVERY upcoming game -- fall back to
        # the HOME TEAM's modal historical venue. For a true home game that is
        # exactly right; for the occasional neutral-site opener it is the wrong
        # stadium but still that region's weather, which beats NaN.
        rows = conn.execute("""
            WITH modal_venue AS (
                SELECT DISTINCT ON (g.home_team) g.home_team AS team, g.venue_id
                FROM games g
                WHERE g.sport = 'NCAAF' AND g.venue_id IS NOT NULL
                GROUP BY g.home_team, g.venue_id
                ORDER BY g.home_team, COUNT(*) DESC
            )
            SELECT g.game_id, g.game_date, g.home_team, v.latitude, v.longitude,
                   v.dome, v.name
            FROM games g
            LEFT JOIN modal_venue mv ON mv.team = g.home_team
            JOIN ncaaf_venues v ON v.venue_id = COALESCE(g.venue_id, mv.venue_id)
            WHERE g.sport = 'NCAAF'
              AND g.home_score IS NULL
              AND g.game_date >= %s AND g.game_date <= %s
              AND v.latitude IS NOT NULL AND v.longitude IS NOT NULL
            ORDER BY g.game_date
        """, (today.isoformat(), hi)).fetchall()
        logger.info(f"NCAAF upcoming weather: {len(rows)} games through {hi}")

        now = datetime.now(tz=timezone.utc).isoformat()
        for game_id, game_date, home_team, lat, lon, dome, venue in rows:
            if bool(dome):
                vals = {"temp_f": 72.0, "wind_mph": 0.0, "precip_mm": 0.0, "is_dome": 1}
            else:
                wx = _fetch_weather(lat, lon, str(game_date)[:10])
                if wx is None:
                    continue
                vals = {**wx, "is_dome": 0}
                time.sleep(0.3)
            conn.execute("""
                INSERT INTO game_weather (
                    game_id, game_date, home_team, venue,
                    temp_f, wind_mph, wind_dir_deg, wind_out_component,
                    precip_mm, is_dome_game, fetched_at
                ) VALUES (%s, %s, %s, %s, %s, %s, NULL, 0.0, %s, %s, %s)
                ON CONFLICT (game_id) DO UPDATE SET
                    temp_f = EXCLUDED.temp_f,
                    wind_mph = EXCLUDED.wind_mph,
                    precip_mm = EXCLUDED.precip_mm,
                    is_dome_game = EXCLUDED.is_dome_game,
                    fetched_at = EXCLUDED.fetched_at
            """, (game_id, str(game_date)[:10], home_team, venue or "Unknown",
                  vals["temp_f"], vals["wind_mph"], vals["precip_mm"],
                  vals["is_dome"], now))
            written += 1
        conn.commit()
        logger.success(f"NCAAF upcoming weather: {written}/{len(rows)} rows upserted")
    finally:
        conn.close()
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="NCAAF weather backfill via Open-Meteo")
    ap.add_argument("--upcoming", type=int, metavar="DAYS", default=None,
                    help="Forecast mode: upsert weather for NCAAF games in the "
                         "next DAYS days (the daily-pipeline entry point)")
    ap.add_argument("--seasons", nargs="+", type=int, required=False,
                    help="Season(s) to backfill. One value = single season, "
                         "two values = range (inclusive)")
    args = ap.parse_args()
    if args.upcoming is not None:
        ingest_upcoming(args.upcoming)
        sys.exit(0)
    if not args.seasons:
        ap.error("--seasons is required unless --upcoming is given")
    seasons = args.seasons
    if len(seasons) == 1:
        backfill(seasons[0], seasons[0])
    elif len(seasons) == 2:
        backfill(seasons[0], seasons[1])
    else:
        ap.error("Provide 1 or 2 season values")
