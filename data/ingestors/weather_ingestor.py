"""
weather_ingestor.py — Game-time weather for MLB stadiums via Open-Meteo.

Fetches temperature, wind speed/direction, and precipitation for each game
and computes a wind_out_component: positive = wind blowing toward CF (favors
offense/overs), negative = blowing in from CF (suppresses scoring).

Data source: Open-Meteo (free, no API key, official meteorological data).
  - Historical: archive-api.open-meteo.com
  - Forecast:   api.open-meteo.com (up to 16 days ahead)

Wind component math:
  wind_out_component = wind_mph * cos(angle between wind direction and "out" direction)
  where "out" = wind blowing from behind home plate toward CF.

Usage:
    python -m data.ingestors.weather_ingestor --backfill 2019 2025
    python -m data.ingestors.weather_ingestor --date 2026-04-12
"""

import argparse
import math
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.db import get_connection

# ── Stadium Reference Data ────────────────────────────────────────────────────
# lat, lon:           stadium coordinates (home plate area)
# hp_to_cf_bearing:  compass bearing from home plate toward center field (0=N, 90=E)
# retractable:        True if roof can be closed (we infer open/closed from conditions)
# fixed_dome:         True if stadium is always fully enclosed (Tropicana)

STADIUMS: dict[str, dict] = {
    "ARI": {"lat": 33.4455,  "lon": -112.0667, "hp_to_cf": 340, "retractable": True,  "fixed_dome": False, "venue": "Chase Field"},
    "ATL": {"lat": 33.8908,  "lon":  -84.4678, "hp_to_cf":  22, "retractable": False, "fixed_dome": False, "venue": "Truist Park"},
    "BAL": {"lat": 39.2839,  "lon":  -76.6215, "hp_to_cf": 315, "retractable": False, "fixed_dome": False, "venue": "Camden Yards"},
    "BOS": {"lat": 42.3467,  "lon":  -71.0972, "hp_to_cf":  60, "retractable": False, "fixed_dome": False, "venue": "Fenway Park"},
    "CHC": {"lat": 41.9484,  "lon":  -87.6553, "hp_to_cf":  90, "retractable": False, "fixed_dome": False, "venue": "Wrigley Field"},
    "CWS": {"lat": 41.8300,  "lon":  -87.6339, "hp_to_cf":   4, "retractable": False, "fixed_dome": False, "venue": "Guaranteed Rate Field"},
    "CIN": {"lat": 39.0975,  "lon":  -84.5064, "hp_to_cf": 348, "retractable": False, "fixed_dome": False, "venue": "Great American Ball Park"},
    "CLE": {"lat": 41.4953,  "lon":  -81.6851, "hp_to_cf": 334, "retractable": False, "fixed_dome": False, "venue": "Progressive Field"},
    "COL": {"lat": 39.7560,  "lon": -104.9942, "hp_to_cf": 347, "retractable": False, "fixed_dome": False, "venue": "Coors Field"},
    "DET": {"lat": 42.3390,  "lon":  -83.0485, "hp_to_cf": 330, "retractable": False, "fixed_dome": False, "venue": "Comerica Park"},
    "HOU": {"lat": 29.7573,  "lon":  -95.3555, "hp_to_cf":  32, "retractable": True,  "fixed_dome": False, "venue": "Minute Maid Park"},
    "KC":  {"lat": 39.0517,  "lon":  -94.4803, "hp_to_cf":   8, "retractable": False, "fixed_dome": False, "venue": "Kauffman Stadium"},
    "LAA": {"lat": 33.8003,  "lon": -117.8827, "hp_to_cf": 230, "retractable": False, "fixed_dome": False, "venue": "Angel Stadium"},
    "LAD": {"lat": 34.0739,  "lon": -118.2400, "hp_to_cf": 338, "retractable": False, "fixed_dome": False, "venue": "Dodger Stadium"},
    "MIA": {"lat": 25.7781,  "lon":  -80.2197, "hp_to_cf":  25, "retractable": True,  "fixed_dome": False, "venue": "loanDepot Park"},
    "MIL": {"lat": 43.0280,  "lon":  -87.9712, "hp_to_cf":  48, "retractable": True,  "fixed_dome": False, "venue": "American Family Field"},
    "MIN": {"lat": 44.9817,  "lon":  -93.2781, "hp_to_cf": 347, "retractable": False, "fixed_dome": False, "venue": "Target Field"},
    "NYM": {"lat": 40.7571,  "lon":  -73.8458, "hp_to_cf": 340, "retractable": False, "fixed_dome": False, "venue": "Citi Field"},
    "NYY": {"lat": 40.8296,  "lon":  -73.9262, "hp_to_cf":   2, "retractable": False, "fixed_dome": False, "venue": "Yankee Stadium"},
    "OAK": {"lat": 37.7516,  "lon": -122.2005, "hp_to_cf":   3, "retractable": False, "fixed_dome": False, "venue": "Oakland Coliseum"},
    "PHI": {"lat": 39.9057,  "lon":  -75.1665, "hp_to_cf":   8, "retractable": False, "fixed_dome": False, "venue": "Citizens Bank Park"},
    "PIT": {"lat": 40.4469,  "lon":  -80.0057, "hp_to_cf": 330, "retractable": False, "fixed_dome": False, "venue": "PNC Park"},
    "SD":  {"lat": 32.7073,  "lon": -117.1566, "hp_to_cf":  13, "retractable": False, "fixed_dome": False, "venue": "Petco Park"},
    "SEA": {"lat": 47.5914,  "lon": -122.3325, "hp_to_cf": 348, "retractable": True,  "fixed_dome": False, "venue": "T-Mobile Park"},
    "SF":  {"lat": 37.7786,  "lon": -122.3893, "hp_to_cf":   0, "retractable": False, "fixed_dome": False, "venue": "Oracle Park"},
    "STL": {"lat": 38.6226,  "lon":  -90.1928, "hp_to_cf":   5, "retractable": False, "fixed_dome": False, "venue": "Busch Stadium"},
    "TB":  {"lat": 27.7683,  "lon":  -82.6534, "hp_to_cf": 350, "retractable": False, "fixed_dome": True,  "venue": "Tropicana Field"},
    "TEX": {"lat": 32.7474,  "lon":  -97.0825, "hp_to_cf": 354, "retractable": True,  "fixed_dome": False, "venue": "Globe Life Field"},
    "TOR": {"lat": 43.6414,  "lon":  -79.3894, "hp_to_cf": 350, "retractable": True,  "fixed_dome": False, "venue": "Rogers Centre"},
    "WSH": {"lat": 38.8730,  "lon":  -77.0074, "hp_to_cf":   5, "retractable": False, "fixed_dome": False, "venue": "Nationals Park"},
    # ── Abbreviation aliases (CSV data uses different codes than STATSAPI) ────
    "WAS": {"lat": 38.8730,  "lon":  -77.0074, "hp_to_cf":   5, "retractable": False, "fixed_dome": False, "venue": "Nationals Park"},       # WSH alias
    "CHW": {"lat": 41.8300,  "lon":  -87.6339, "hp_to_cf":   4, "retractable": False, "fixed_dome": False, "venue": "Guaranteed Rate Field"}, # CWS alias
    "AZ":  {"lat": 33.4455,  "lon": -112.0667, "hp_to_cf": 340, "retractable": True,  "fixed_dome": False, "venue": "Chase Field"},           # ARI alias
    "FLO": {"lat": 25.7781,  "lon":  -80.2197, "hp_to_cf":  25, "retractable": True,  "fixed_dome": False, "venue": "loanDepot Park"},        # Florida Marlins (legacy = MIA)
    # Athletics moved to Sacramento (Sutter Health Park) for 2024+
    "ATH": {"lat": 38.5892,  "lon": -121.5050, "hp_to_cf": 350, "retractable": False, "fixed_dome": False, "venue": "Sutter Health Park"},
}

# Threshold: retractable roof considered closed if temp < 50°F OR precip > 0.3mm
_DOME_CLOSE_TEMP_F  = 50.0
_DOME_CLOSE_PRECIP  = 0.3   # mm per hour

# Open-Meteo endpoints
_HISTORICAL_API = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_API   = "https://api.open-meteo.com/v1/forecast"
_ARCHIVE_CUTOFF_DAYS = 5   # data older than this uses the archive endpoint

# Game start hour in local time — we use 19:00 (7pm) as a proxy for most MLB games.
# Open-Meteo returns UTC; we convert using a rough UTC offset per stadium longitude.
_DEFAULT_GAME_HOUR_LOCAL = 19


def _utc_offset_from_lon(lon: float) -> int:
    """Rough UTC offset from longitude (integer hours). Good enough for hourly weather."""
    if lon < -100:
        return -8   # Pacific
    elif lon < -87:
        return -7   # Mountain / Central overlap — use Mountain as conservative
    elif lon < -75:
        return -5   # Central → Eastern split; use Central for most MLB
    else:
        return -5   # Eastern


def _game_hour_utc(stadium: dict) -> int:
    """UTC hour of approximate game start for this stadium."""
    offset = _utc_offset_from_lon(stadium["lon"])
    return (_DEFAULT_GAME_HOUR_LOCAL - offset) % 24


def _wind_out_component(wind_mph: float, wind_dir_deg: float, hp_to_cf: float) -> float:
    """
    Compute the wind component blowing toward center field.

    wind_dir_deg: meteorological FROM direction (0=from N, 90=from E …)
    hp_to_cf:     compass bearing from home plate toward CF (0=CF is due North)

    Positive result = wind blowing out (tailwind, boosts offense).
    Negative result = wind blowing in (headwind, suppresses scoring).
    """
    # Direction wind must blow FROM to blow "out" toward CF
    out_from_dir = (hp_to_cf + 180.0) % 360.0
    angle_diff   = (wind_dir_deg - out_from_dir + 360.0) % 360.0
    return round(wind_mph * math.cos(math.radians(angle_diff)), 2)


def _is_dome_game(stadium: dict, temp_f: float, precip_mm: float) -> int:
    """Return 1 if weather is neutralised by a roof, 0 otherwise."""
    if stadium["fixed_dome"]:
        return 1
    if stadium["retractable"]:
        if temp_f < _DOME_CLOSE_TEMP_F or precip_mm > _DOME_CLOSE_PRECIP:
            return 1
    return 0


def _celsius_to_f(c: float) -> float:
    return round(c * 9 / 5 + 32, 1)


def _fetch_open_meteo(lat: float, lon: float, game_date: str) -> dict | None:
    """
    Fetch hourly weather for game_date from Open-Meteo.
    Returns a dict with temp_f, wind_mph, wind_dir_deg, precip_mm for game time,
    or None on failure.
    """
    today      = date.today()
    target     = date.fromisoformat(game_date)
    days_old   = (today - target).days

    if days_old > _ARCHIVE_CUTOFF_DAYS:
        base_url = _HISTORICAL_API
        params   = {
            "latitude":   lat,
            "longitude":  lon,
            "start_date": game_date,
            "end_date":   game_date,
            "hourly":     "temperature_2m,windspeed_10m,winddirection_10m,precipitation",
            "windspeed_unit": "mph",
            "timezone":   "UTC",
        }
    else:
        base_url = _FORECAST_API
        params   = {
            "latitude":   lat,
            "longitude":  lon,
            "hourly":     "temperature_2m,windspeed_10m,winddirection_10m,precipitation",
            "windspeed_unit": "mph",
            "timezone":   "UTC",
            "forecast_days": min(days_old + 2, 16),
        }

    try:
        resp = requests.get(base_url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning(f"Open-Meteo request failed for {game_date}: {exc}")
        return None

    hourly = data.get("hourly", {})
    times  = hourly.get("time", [])
    temps  = hourly.get("temperature_2m", [])
    winds  = hourly.get("windspeed_10m", [])
    dirs   = hourly.get("winddirection_10m", [])
    precip = hourly.get("precipitation", [])

    if not times:
        return None

    # Find the hour closest to game time in UTC
    # Build a rough game_hour_utc from the lon-based offset
    # We target the hour string: f"{game_date}T{hour:02d}:00"
    rough_utc_hour = (_DEFAULT_GAME_HOUR_LOCAL - _utc_offset_from_lon(lon)) % 24
    target_time    = f"{game_date}T{rough_utc_hour:02d}:00"

    # Pick closest available hour
    best_idx = 0
    for idx, t in enumerate(times):
        if t <= target_time:
            best_idx = idx

    temp_c     = temps[best_idx]  if best_idx < len(temps)  else None
    wind_mph   = winds[best_idx]  if best_idx < len(winds)  else None
    wind_deg   = dirs[best_idx]   if best_idx < len(dirs)   else None
    precip_mm  = precip[best_idx] if best_idx < len(precip) else None

    if temp_c is None or wind_mph is None:
        return None

    return {
        "temp_f":      _celsius_to_f(temp_c),
        "wind_mph":    round(float(wind_mph), 1),
        "wind_dir_deg": round(float(wind_deg), 1) if wind_deg is not None else None,
        "precip_mm":   round(float(precip_mm), 2) if precip_mm is not None else 0.0,
    }


# ── Main Functions ────────────────────────────────────────────────────────────

def fetch_and_store_weather_for_date(game_date: str, conn=None) -> int:
    """
    Fetch weather for all MLB games on game_date and upsert into game_weather.
    Returns number of rows written.
    """
    close_conn = conn is None
    if conn is None:
        conn = get_connection()

    try:
        games = conn.execute("""
            SELECT game_id, home_team, away_team
            FROM games
            WHERE sport = 'MLB' AND game_date = %s
        """, (game_date,)).fetchall()

        if not games:
            logger.debug(f"No MLB games found for {game_date}")
            return 0

        written = 0
        for game_id, home_team, away_team in games:
            stadium = STADIUMS.get(home_team)
            if not stadium:
                logger.warning(f"No stadium data for {home_team} — skipping weather")
                continue

            wx = _fetch_open_meteo(stadium["lat"], stadium["lon"], game_date)
            if not wx:
                continue

            dome = _is_dome_game(stadium, wx["temp_f"], wx["precip_mm"])

            if dome:
                wind_component = 0.0
            elif wx["wind_dir_deg"] is not None:
                wind_component = _wind_out_component(
                    wx["wind_mph"], wx["wind_dir_deg"], stadium["hp_to_cf"]
                )
            else:
                wind_component = 0.0

            conn.execute("""
                INSERT INTO game_weather (
                    game_id, game_date, home_team, venue,
                    temp_f, wind_mph, wind_dir_deg, wind_out_component,
                    precip_mm, is_dome_game, fetched_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (game_id) DO UPDATE SET
                    temp_f             = EXCLUDED.temp_f,
                    wind_mph           = EXCLUDED.wind_mph,
                    wind_dir_deg       = EXCLUDED.wind_dir_deg,
                    wind_out_component = EXCLUDED.wind_out_component,
                    precip_mm          = EXCLUDED.precip_mm,
                    is_dome_game       = EXCLUDED.is_dome_game,
                    fetched_at         = EXCLUDED.fetched_at
            """, (
                game_id, game_date, home_team, stadium["venue"],
                wx["temp_f"], wx["wind_mph"], wx["wind_dir_deg"], wind_component,
                wx["precip_mm"], dome, datetime.now(tz=timezone.utc).isoformat()
            ))
            written += 1
            time.sleep(0.3)   # be polite to Open-Meteo

        if close_conn:
            conn.commit()
        return written

    finally:
        if close_conn:
            conn.close()


def backfill_weather(start_season: int, end_season: int) -> None:
    """
    Backfill weather for all historical MLB games in [start_season, end_season].
    Skips game_ids already in game_weather.
    """
    conn = get_connection()
    try:
        dates = [r[0] for r in conn.execute("""
            SELECT DISTINCT g.game_date
            FROM games g
            LEFT JOIN game_weather w ON g.game_id = w.game_id
            WHERE g.sport = 'MLB'
              AND g.season >= %s AND g.season <= %s
              AND w.game_id IS NULL
            ORDER BY g.game_date
        """, (start_season, end_season)).fetchall()]

        logger.info(f"Weather backfill: {len(dates)} dates to process "
                    f"({start_season}–{end_season})")

        total = 0
        for i, d in enumerate(dates, 1):
            n = fetch_and_store_weather_for_date(d, conn=conn)
            conn.commit()
            total += n
            if i % 50 == 0:
                logger.info(f"  {d} — {i}/{len(dates)} dates, {total} rows written")

        logger.success(f"Weather backfill complete: {total} rows written across {len(dates)} dates")
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLB weather ingestor")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                        help="Backfill weather for seasons START through END")
    parser.add_argument("--date", help="Fetch weather for a specific date YYYY-MM-DD")
    args = parser.parse_args()

    if args.backfill:
        backfill_weather(args.backfill[0], args.backfill[1])
    elif args.date:
        conn = get_connection()
        n = fetch_and_store_weather_for_date(args.date, conn=conn)
        conn.commit()
        conn.close()
        logger.info(f"Wrote {n} weather rows for {args.date}")
    else:
        # Default: today's games
        today_str = date.today().isoformat()
        conn = get_connection()
        n = fetch_and_store_weather_for_date(today_str, conn=conn)
        conn.commit()
        conn.close()
        logger.info(f"Wrote {n} weather rows for {today_str}")
