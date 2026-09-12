"""
Point-in-time ISSUED forecasts for historical NCAAF games -> game_weather_issued.

The totals model trains on `game_weather` (Open-Meteo reanalysis: what
happened) and is served the forecast `ingest_upcoming` writes a few days out.
This fills the forecast AS IT WAS ISSUED N days before each kickoff, from
historical-forecast-api.open-meteo.com's `*_previous_dayN` series -- the same
source `nfl/data_ingest/weather.py` uses for the wind rule -- so a refit can
train on the kind of number the scorer will see. Issued forecasts exist from
2024-01-18, so only 2024+ can be filled.

ONE CALL PER VENUE PER SEASON, not per game: the API returns an hourly series
over a date range, so a venue's whole season is one request (~160 venues a
season). The kickoff hour comes from `games.commence_time`; the row read is
the forecast for that UTC hour, issued `lead` days earlier.

    python -m scripts.ncaaf_weather_issued_backfill --seasons 2024 2025 --leads 1 3 5
    python -m scripts.ncaaf_weather_issued_backfill --seasons 2025 --leads 3 --dry-run
"""
from __future__ import annotations

import argparse
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import requests
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data.db import get_connection  # noqa: E402

HISTFC_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
ISSUED_FORECAST_START = "2024-01-18"


def _get(params: dict, retries: int = 4) -> dict | None:
    for i in range(retries):
        try:
            r = requests.get(HISTFC_URL, params=params, timeout=120)
            if r.status_code == 429:
                time.sleep(10 * (i + 1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:                                  # noqa: BLE001
            logger.warning(f"open-meteo: {exc} (try {i + 1}/{retries})")
            time.sleep(3 * (i + 1))
    return None


def fetch_venue_season(lat: float, lon: float, start: str, end: str,
                       leads: list[int]) -> dict[str, dict[int, dict]]:
    """-> {'YYYY-MM-DDTHH:00': {lead: {temp_f, wind_mph, precip_mm}}}."""
    hourly = []
    for n in leads:
        hourly += [f"temperature_2m_previous_day{n}", f"wind_speed_10m_previous_day{n}",
                   f"precipitation_previous_day{n}"]
    payload = _get({"latitude": lat, "longitude": lon, "start_date": start,
                    "end_date": end, "hourly": ",".join(hourly),
                    "wind_speed_unit": "mph", "temperature_unit": "fahrenheit",
                    "timezone": "UTC"})
    if not payload or "hourly" not in payload:
        return {}
    h = payload["hourly"]
    out: dict[str, dict[int, dict]] = {}
    for i, t in enumerate(h.get("time", [])):
        per_lead = {}
        for n in leads:
            temp = h.get(f"temperature_2m_previous_day{n}", [None])[i] if i < len(h.get(f"temperature_2m_previous_day{n}", [])) else None
            wind = h.get(f"wind_speed_10m_previous_day{n}", [None])[i] if i < len(h.get(f"wind_speed_10m_previous_day{n}", [])) else None
            prec = h.get(f"precipitation_previous_day{n}", [None])[i] if i < len(h.get(f"precipitation_previous_day{n}", [])) else None
            if temp is None or wind is None:
                continue
            per_lead[n] = {"temp_f": round(float(temp), 1), "wind_mph": round(float(wind), 1),
                           "precip_mm": round(float(prec), 2) if prec is not None else 0.0}
        out[t] = per_lead
    return out


def backfill(seasons: list[int], leads: list[int], dry_run: bool = False) -> dict:
    conn = get_connection()
    written = skipped = 0
    try:
        ph = ",".join(["%s"] * len(seasons))
        rows = conn.execute(f"""
            SELECT g.game_id, g.season, g.game_date, g.commence_time,
                   v.venue_id, v.latitude, v.longitude, v.dome
            FROM games g
            JOIN ncaaf_venues v ON v.venue_id = g.venue_id
            WHERE g.sport = 'NCAAF' AND g.season IN ({ph})
              AND g.home_score IS NOT NULL AND g.commence_time IS NOT NULL
              AND v.latitude IS NOT NULL AND v.longitude IS NOT NULL
              AND g.game_date >= %s
            ORDER BY v.venue_id, g.game_date
        """, (*seasons, ISSUED_FORECAST_START)).fetchall()
        logger.info(f"issued backfill: {len(rows)} games, leads {leads}")

        by_venue: dict[tuple, list] = defaultdict(list)
        for gid, season, gdate, kick, vid, lat, lon, dome in rows:
            by_venue[(vid, int(season))].append((gid, str(gdate)[:10], kick, float(lat), float(lon), bool(dome)))

        now = datetime.now(timezone.utc).isoformat()
        for i, ((vid, season), games) in enumerate(sorted(by_venue.items()), 1):
            lat, lon, dome = games[0][3], games[0][4], games[0][5]
            if dome:
                for gid, gdate, kick, *_ in games:
                    for n in leads:
                        if not dry_run:
                            conn.execute("""
                                INSERT INTO game_weather_issued
                                    (game_id, lead_days, temp_f, wind_mph, precip_mm,
                                     kick_hour_utc, is_dome_game, fetched_at)
                                VALUES (%s, %s, 72.0, 0.0, 0.0, %s, 1, %s)
                                ON CONFLICT (game_id, lead_days) DO NOTHING
                            """, (gid, n, _kick_hour(kick), now))
                        written += 1
                continue
            start, end = min(g[1] for g in games), max(g[1] for g in games)
            series = fetch_venue_season(lat, lon, start, end, leads)
            if not series:
                skipped += len(games) * len(leads)
                logger.warning(f"  venue {vid} {season}: no series ({start}..{end})")
                continue
            for gid, gdate, kick, *_ in games:
                hour = _kick_hour(kick)
                key = f"{_kick_date(kick)}T{hour:02d}:00"
                per_lead = series.get(key) or {}
                for n in leads:
                    wx = per_lead.get(n)
                    if wx is None:
                        skipped += 1
                        continue
                    if not dry_run:
                        conn.execute("""
                            INSERT INTO game_weather_issued
                                (game_id, lead_days, temp_f, wind_mph, precip_mm,
                                 kick_hour_utc, is_dome_game, fetched_at)
                            VALUES (%s, %s, %s, %s, %s, %s, 0, %s)
                            ON CONFLICT (game_id, lead_days) DO NOTHING
                        """, (gid, n, wx["temp_f"], wx["wind_mph"], wx["precip_mm"], hour, now))
                    written += 1
            if i % 20 == 0:
                if not dry_run:
                    conn.commit()
                logger.info(f"  {i}/{len(by_venue)} venue-seasons, {written} rows, {skipped} skipped")
            time.sleep(0.4)
        if not dry_run:
            conn.commit()
        out = {"games": len(rows), "venue_seasons": len(by_venue), "rows": written, "skipped": skipped}
        logger.success(f"issued backfill: {out}")
        return out
    finally:
        conn.close()


def _parse_kick(kick) -> datetime:
    t = str(kick).strip().replace("Z", "+00:00")
    d = datetime.fromisoformat(t)
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)


def _kick_hour(kick) -> int:
    return _parse_kick(kick).hour


def _kick_date(kick) -> str:
    return _parse_kick(kick).strftime("%Y-%m-%d")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seasons", nargs="+", type=int, default=[2024, 2025])
    ap.add_argument("--leads", nargs="+", type=int, default=[1, 3, 5])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    print(backfill(a.seasons, a.leads, dry_run=a.dry_run))
