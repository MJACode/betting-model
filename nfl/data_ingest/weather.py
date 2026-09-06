"""
Stadium wind from Open-Meteo.

Three endpoints, three different jobs. Getting these confused is the single
easiest way to leak future information into a backtest.

  ARCHIVE   archive-api.open-meteo.com
            ERA5 reanalysis. The best available estimate of what the wind
            ACTUALLY was. Truth for validation. Never a feature.

  FORECAST  historical-forecast-api.open-meteo.com, plain `wind_speed_10m`
            The assembled best-estimate series, initialised from the most
            recent model run. Effectively analysis, ~0-24h lead.
            DO NOT use this as a "forecast at cutoff". It is near-truth.

  ISSUED    historical-forecast-api.open-meteo.com, `wind_speed_10m_previous_dayN`
            The forecast for this timestamp as actually issued N days earlier.
            This is the only leakage-free historical forecast available.
            VERIFIED COVERAGE: null before 2024-01-18, complete from 2024-02.

  LIVE      api.open-meteo.com/v1/forecast
            Forward-looking forecast for upcoming games. What production uses.

`previous-runs-api.open-meteo.com` is NOT reachable from the project sandbox
(proxy refuses the connection). Do not build against it.

Units: Open-Meteo defaults to km/h at 10m. We request mph explicitly everywhere.

CALIBRATION WARNING
-------------------
Open-Meteo wind and the nflverse `wind` column are NOT the same measurement.
Measured on 1,794 outdoor games 2016-2025: correlation 0.688, sd of the
difference 3.87 mph, agreement on the >=12 flag only 85.8%.

The frozen betting rule was fitted on nflverse `wind`. Applying a threshold of
12 to an Open-Meteo number is therefore not the same rule. Use
`ERA5_EQUIVALENT_THRESHOLD` below, which is rate-matched, and see
scripts/validate_wind_forecast.py for the derivation.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pandas as pd
import requests

CACHE = Path(os.environ.get("WX_CACHE", "data/weather_cache"))
CACHE.mkdir(parents=True, exist_ok=True)

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTFC_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
LIVE_URL = "https://api.open-meteo.com/v1/forecast"

# First date on which wind_speed_10m_previous_dayN returns non-null. Verified
# month by month against a Buffalo grid point; see validate_wind_forecast.py.
ISSUED_FORECAST_START = "2024-01-18"

# Rule thresholds. The published rule is `nflverse wind >= 12`. On an
# Open-Meteo/ERA5 scale the fire-rate-matched equivalent is 11.40; 11 is
# preferred in deployment because forecasts shrink high wind toward
# climatology (see FORECAST_BIAS below) and 11 recovers the lost volume at a
# cost of ~0.4pp of win rate.
NFLVERSE_THRESHOLD = 12.0
ERA5_EQUIVALENT_THRESHOLD = 11.40
DEPLOY_THRESHOLD = 11.0

# E[true wind | forecast] - forecast, in mph, keyed by lead and by the
# FORECAST bucket. Measured on 298,944 hourly forecast/ERA5 pairs, 2024-25.
#
# Note the sign. Conditioning on a HIGH forecast, true wind regresses DOWN,
# because an extreme forecast is partly extreme noise. At lead 3 a forecast of
# 12-14 mph corresponds to 10.7 mph actual. The opposite table, E[fc - truth |
# truth], has the reverse sign and is the wrong one to apply live: you never
# observe the truth at bet time. Getting this backwards inflates wind and fires
# the rule on far too many games.
EXPECTED_TRUE_WIND_ADJ = {
    1: {(0, 4): 0.82, (4, 8): -0.17, (8, 10): -0.73, (10, 12): -1.13, (12, 14): -1.46,
        (14, 16): -1.85, (16, 18): -2.14, (18, 22): -2.61, (22, 99): -3.87},
    3: {(0, 4): 0.91, (4, 8): -0.23, (8, 10): -1.15, (10, 12): -1.71, (12, 14): -2.14,
        (14, 16): -2.55, (16, 18): -2.93, (18, 22): -3.64, (22, 99): -5.10},
    5: {(0, 4): 1.42, (4, 8): -0.00, (8, 10): -1.29, (10, 12): -2.20, (12, 14): -2.93,
        (14, 16): -3.78, (16, 18): -4.24, (18, 22): -4.98, (22, 99): -6.47},
}

# lat, lon per nflverse stadium_id. Domes included so coverage checks do not
# silently drop a relocated game.
STADIUM_COORDS = {
    "NYC01": (40.8135, -74.0745), "LAX01": (33.9535, -118.3392),
    "BUF00": (42.7738, -78.7870), "PHI00": (39.9008, -75.1675),
    "BOS00": (42.0909, -71.2643), "HOU00": (29.6847, -95.4107),
    "BAL00": (39.2780, -76.6227), "NOR00": (29.9511, -90.0812),
    "DET00": (42.3400, -83.0456), "GNB00": (44.5013, -88.0622),
    "DAL00": (32.7473, -97.0945), "TAM00": (27.9759, -82.5033),
    "SFO01": (37.4030, -121.9700), "MIN01": (44.9736, -93.2575),
    "NAS00": (36.1665, -86.7713), "CHI98": (41.8623, -87.6167),
    "IND00": (39.7601, -86.1639), "MIA00": (25.9580, -80.2389),
    "WAS00": (38.9077, -76.8645), "CLE00": (41.5061, -81.6995),
    "CAR00": (35.2258, -80.8528), "ATL97": (33.7554, -84.4009),
    "PHO00": (33.5276, -112.2626), "JAX00": (30.3239, -81.6373),
    "DEN00": (39.7439, -105.0201), "VEG00": (36.0909, -115.1833),
    "PIT00": (40.4468, -80.0158), "KAN00": (39.0489, -94.4839),
    "SEA00": (47.5952, -122.3316), "CIN00": (39.0955, -84.5161),
    "LAX99": (34.0141, -118.2879), "LAX97": (33.8644, -118.2611),
    "OAK00": (37.7516, -122.2005), "ATL00": (33.7576, -84.4009),
    "SDG00": (32.7831, -117.1196), "LON00": (51.5560, -0.2795),
    "LON01": (51.4560, -0.3416), "LON02": (51.6043, -0.0665),
    "MEX00": (19.3029, -99.1505), "GER00": (48.2188, 11.6247),
    "FRA00": (50.0686, 8.6455), "SAO00": (-23.5453, -46.4742),
    "MAD00": (40.4531, -3.6883),
}

# Roof values that mean weather cannot affect the game.
INDOOR_ROOFS = {"dome", "closed"}

# Venues whose roof OPENS AND CLOSES, so the roof value is a per-game
# observation rather than a property of the stadium. Derived from games.csv
# rather than from memory: these are exactly the stadium_ids whose history
# contains an 'open' or a 'closed' row, and no others.
#
#   ATL97 Mercedes-Benz      open 18 / closed 56    (76% closed)
#   DAL00 AT&T               open  9 / closed 136   (94% closed)
#   HOU00 NRG                open 46 / closed 159   (78% closed)
#   IND00 Lucas Oil          open 34 / closed 119   (78% closed)
#   PHO00 State Farm         open 21 / closed 151   (88% closed)
#
# WHY THIS EXISTS. nflverse records the roof state of a game that has been
# PLAYED, so a future game has none -- and every one of the 43 blank-roof rows
# in the 2026 schedule is one of these five venues. `~roof.isin(INDOOR_ROOFS)`
# reads a blank as OUTDOOR, so the wind model was pricing an open-air forecast
# for stadiums that are closed three-quarters of the time or more. Two of the
# five Week 1 picks live on 2026-09-06 were on that basis (NRG and Lucas Oil).
#
# A wind under on a game played under a closed roof has no premise at all, so a
# blank here is NOT eligible until the state is known. That loses nothing: if
# the roof is in fact open, the state lands before kickoff and the game
# re-qualifies inside the firing window.
RETRACTABLE_STADIUMS = {"ATL97", "DAL00", "HOU00", "IND00", "PHO00"}


def open_air_mask(games) -> "pd.Series":
    """Boolean mask: games the weather can actually reach.

    Use this instead of `~games.roof.isin(INDOOR_ROOFS)`, which silently treats
    an unknown roof state as open air. See RETRACTABLE_STADIUMS.
    """
    roof = games.roof.fillna("").astype(str).str.strip()
    known = roof != ""
    retractable = games.stadium_id.isin(RETRACTABLE_STADIUMS)
    return ~roof.isin(INDOOR_ROOFS) & (known | ~retractable)


class OpenMeteoError(RuntimeError):
    pass


def _get(url: str, params: dict, key: str | None, retries: int = 5, timeout: int = 120) -> dict:
    """Cached GET. `key=None` disables caching, which is correct for live calls."""
    cp = CACHE / f"{key}.json" if key else None
    if cp is not None and cp.exists():
        try:
            return json.loads(cp.read_text())
        except (json.JSONDecodeError, OSError):
            cp.unlink(missing_ok=True)

    last = None
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, timeout=timeout)
            if r.status_code == 200:
                d = r.json()
                if cp is not None:
                    tmp = cp.with_suffix(".tmp")
                    tmp.write_text(json.dumps(d))
                    os.replace(tmp, cp)
                return d
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"{r.status_code}: {r.text[:200]}"
                time.sleep(4 * (attempt + 1))
                continue
            raise OpenMeteoError(f"{r.status_code}: {r.text[:300]}")
        except requests.RequestException as e:
            last = str(e)
            time.sleep(4 * (attempt + 1))
    raise OpenMeteoError(f"failed after {retries} retries: {last}")


def _frame(payload: dict, sid: str, rename: dict) -> pd.DataFrame:
    h = payload.get("hourly")
    if not h:
        return pd.DataFrame()
    out = pd.DataFrame({"stadium_id": sid, "ts": pd.to_datetime(h["time"], utc=True)})
    for src, dst in rename.items():
        out[dst] = h.get(src)
    return out


def fetch_era5(sid: str, start: str, end: str) -> pd.DataFrame:
    """ERA5 reanalysis. Truth for validation only. Never a live feature."""
    lat, lon = STADIUM_COORDS[sid]
    p = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
         "hourly": "wind_speed_10m,wind_gusts_10m,temperature_2m,precipitation",
         "wind_speed_unit": "mph", "temperature_unit": "fahrenheit", "timezone": "UTC"}
    d = _get(ARCHIVE_URL, p, f"era5_{sid}_{start}_{end}")
    return _frame(d, sid, {"wind_speed_10m": "era5_wind", "wind_gusts_10m": "era5_gust",
                           "temperature_2m": "era5_temp", "precipitation": "era5_precip"})


def fetch_issued_forecasts(sid: str, start: str, end: str,
                           leads=(1, 2, 3, 4, 5, 6, 7)) -> pd.DataFrame:
    """
    Archived forecasts AS ISSUED N days before each timestamp. Leakage-free.
    Raises if the window predates ISSUED_FORECAST_START.
    """
    if end < ISSUED_FORECAST_START:
        raise OpenMeteoError(
            f"issued forecasts start {ISSUED_FORECAST_START}; requested window ends {end}. "
            "Before that date only the assembled near-analysis series exists, which leaks."
        )
    lat, lon = STADIUM_COORDS[sid]
    hourly = ["wind_speed_10m"] + [f"wind_speed_10m_previous_day{i}" for i in leads] + \
             ["temperature_2m", "precipitation"]
    p = {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
         "hourly": ",".join(hourly), "wind_speed_unit": "mph",
         "temperature_unit": "fahrenheit", "timezone": "UTC"}
    d = _get(HISTFC_URL, p, f"issued_{sid}_{start}_{end}")
    rename = {"wind_speed_10m": "om_analysis", "temperature_2m": "om_temp",
              "precipitation": "om_precip"}
    rename.update({f"wind_speed_10m_previous_day{i}": f"fc_d{i}" for i in leads})
    return _frame(d, sid, rename)


def fetch_live_forecast(sid: str, days: int = 8) -> pd.DataFrame:
    """
    Forward-looking forecast for upcoming games. This is what production uses.
    Never cached: a stale forecast is worse than no forecast.
    """
    lat, lon = STADIUM_COORDS[sid]
    p = {"latitude": lat, "longitude": lon, "forecast_days": min(days, 16),
         "hourly": "wind_speed_10m,wind_gusts_10m,temperature_2m,precipitation,precipitation_probability",
         "wind_speed_unit": "mph", "temperature_unit": "fahrenheit", "timezone": "UTC"}
    try:
        d = _get(LIVE_URL, p, None)
    except OpenMeteoError as e:
        if "403" in str(e) or "Tunnel connection failed" in str(e):
            raise OpenMeteoError(
                f"{LIVE_URL} is unreachable from this environment (proxy returned 403). "
                "archive-api and historical-forecast-api ARE reachable, so backtests and "
                "replays work; only the live card needs this host. Run the live card from a "
                "machine with open egress, or allowlist api.open-meteo.com."
            ) from e
        raise
    return _frame(d, sid, {"wind_speed_10m": "wind", "wind_gusts_10m": "gust",
                           "temperature_2m": "temp", "precipitation": "precip",
                           "precipitation_probability": "precip_prob"})


def expected_true_wind(forecast, lead_days: int = 3) -> pd.Series:
    """
    E[true wind | forecast]. A DIAGNOSTIC for the bet card, not a selection input.

    Do not threshold on this. The rule was validated by applying the threshold
    to the RAW forecast, and because the adjustment is monotone in the forecast,
    thresholding the adjusted value is just the raw rule at a different cutoff.
    Substituting it silently would change the selection and invalidate the
    calibrated probabilities in models/wind_totals.py. Change the threshold
    instead, and re-run the validation if you do.
    """
    lead = min(EXPECTED_TRUE_WIND_ADJ, key=lambda k: abs(k - lead_days))
    w = pd.Series(forecast).astype(float)
    out = w.copy()
    for (lo, hi), adj in EXPECTED_TRUE_WIND_ADJ[lead].items():
        out = out.where(~w.between(lo, hi, inclusive="left"), w + adj)
    return out


def wind_at_kickoff(hourly: pd.DataFrame, games: pd.DataFrame, col: str,
                    window_hours: int = 0) -> pd.Series:
    """
    Value of `col` at kickoff hour, or the mean over the first `window_hours`.

    Kickoff hour is the better predictor: it correlates 0.771 with nflverse
    observed wind versus 0.730 for the 4-hour mean, and the rule scores 59.32%
    on it versus 57.88% on the window mean. Default is therefore kickoff hour.

    `games` needs columns game_id, stadium_id, kick_utc (tz-aware UTC).
    """
    g = games[["game_id", "stadium_id", "kick_utc"]].copy()
    g["hr"] = pd.to_datetime(g.kick_utc, utc=True).dt.floor("h")
    offsets = range(window_hours + 1) if window_hours else [0]
    parts = []
    for off in offsets:
        t = g.copy()
        t["hr"] = t.hr + pd.Timedelta(hours=off)
        parts.append(t.merge(hourly, left_on=["stadium_id", "hr"],
                             right_on=["stadium_id", "ts"], how="left")[["game_id", col]])
    return pd.concat(parts).groupby("game_id")[col].mean()


def coverage_check(games: pd.DataFrame) -> dict:
    """Fail loudly on an unmapped stadium rather than silently dropping a game."""
    outdoor = games[open_air_mask(games)]
    missing = sorted(set(outdoor.stadium_id.dropna()) - set(STADIUM_COORDS))
    return {"outdoor_games": len(outdoor),
            "stadiums": outdoor.stadium_id.nunique(),
            "missing_coords": missing}
