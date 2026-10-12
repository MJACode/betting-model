"""
Free weather inputs for scripts/nfl_edge_weather.py (NFL edge search).

No database, no Odds API, nothing paid. Three free public sources, every
response saved under the cache dir (scripts/nfl_edge_lib.CACHE) so a re-run
reads the file and never re-requests it:

  1. nflverse play-by-play 1999-2015 (GitHub releases), ONLY the per-game
     `weather` text plus roof/temp/wind. The 15-20 MB raw file is read for
     those columns and deleted; 2016-2025 come from the pbp files already in
     the cache. -> pbp_weather_1999_2025.parquet
  2. ERA5 reanalysis (archive-api.open-meteo.com) at each stadium for the UTC
     day(s) holding the kickoff hour and the three hours after it: hourly
     precipitation (mm, sum over the PRECEDING hour, Open-Meteo convention),
     10 m wind (mph), 2 m temperature (F). This is TRUTH, the same series the
     repo's rain lead was measured on (nfl/scripts/edge_hunt.py
     sec_tot_precip), never a bettable feature. -> era5_kick_1999_2025.parquet
  3. Issued forecasts 2024-25 (historical-forecast-api.open-meteo.com, the
     endpoint nfl/data_ingest/weather.py uses): precipitation_previous_day1..3,
     temperature_2m_previous_day1/3, wind_speed_10m_previous_day1/3, i.e. the
     value for that hour AS FORECAST 24/48/72 h earlier. Leakage-free.
     -> issued_wx_2024_2025.parquet

Request volume. Open-Meteo's free tier counts one call per location for a
window of <= 2 weeks and <= 10 variables. Locations sharing a UTC window are
batched into one HTTP request (comma-separated coordinates). Pacing stays
under 450 calls/minute and 4,500 calls/hour; a 429 for the daily limit stops
the Open-Meteo part cleanly and the consolidation writes what exists, with the
missing count printed. Groups run in priority order:
  A ERA5 outdoor 1999-2015 (the hold-out)   B ERA5 outdoor 2016-2025 (reproduce)
  C issued 2024-25, outdoor and dome         E ERA5 dome 2000-2015 (placebo)
  D ERA5 dome 2016-2025 (placebo)

Coordinates. STADIUM_COORDS is copied literally from nfl/data_ingest/weather.py
(2026-10-11). Thirteen 1999-2015 venues it lacks were added; each was checked
against the Open-Meteo geocoding API's city centroid on 2026-10-11 and every
one sits within 0.07 deg of it (ERA5's grid is 0.25 deg). Seven predecessor
venues sit beside their successor (same site or adjacent lot) and reuse its
coordinates: BOS99 Foxboro, CIN99 Cinergy, DEN99 Mile High, NYC00 Giants
Stadium, PHI99 Veterans, PIT99 Three Rivers, IND99 RCA Dome.

    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_weather_fetch
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import deque
from pathlib import Path

import pandas as pd
import requests

from scripts.nfl_edge_lib import CACHE

# --- coordinates -----------------------------------------------------------
STADIUM_COORDS = {  # copied from nfl/data_ingest/weather.py
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
STADIUM_COORDS.update({  # added here, geocode-checked (see docstring)
    "DAL99": (32.8400, -96.9110), "PHO99": (33.4264, -111.9325),
    "SFO00": (37.7136, -122.3863), "SEA99": (47.6503, -122.3016),
    "MIN98": (44.9765, -93.2245), "BRG00": (30.4120, -91.1838),
    "CHI99": (40.0992, -88.2360), "MIN00": (44.9739, -93.2581),
    "DET99": (42.6459, -83.2550), "SEA98": (47.5952, -122.3316),
    "SAN00": (29.4170, -98.4789), "STL00": (38.6328, -90.1885),
    "BUF01": (43.6414, -79.3894),
})
for _old, _new in {"BOS99": "BOS00", "CIN99": "CIN00", "DEN99": "DEN00", "NYC00": "NYC01",
                   "PHI99": "PHI00", "PIT99": "PIT00", "IND99": "IND00"}.items():
    STADIUM_COORDS[_old] = STADIUM_COORDS[_new]

INDOOR_ROOFS = {"dome", "closed"}
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTFC_URL = "https://historical-forecast-api.open-meteo.com/v1/forecast"
PBP_URL = "https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{s}.parquet"

RAW = CACHE / "wx_fetch"
ERA5_VARS = ["precipitation", "wind_speed_10m", "temperature_2m"]
ISSUED_VARS = ["precipitation", "temperature_2m",
               "precipitation_previous_day1", "precipitation_previous_day2",
               "precipitation_previous_day3", "temperature_2m_previous_day1",
               "temperature_2m_previous_day3", "wind_speed_10m_previous_day1",
               "wind_speed_10m_previous_day3"]


def log(*a):
    print(*a, flush=True)


# --- games -----------------------------------------------------------------
def game_hours() -> pd.DataFrame:
    """Played games 1999-2025 with the kickoff hour in UTC, built exactly as
    edge_hunt.sec_tot_precip builds it (ET wall clock, floor to the hour)."""
    from zoneinfo import ZoneInfo
    g = pd.read_parquet(CACHE / "nflverse_games.parquet",
                        columns=["game_id", "season", "gameday", "gametime", "roof",
                                 "stadium_id", "result"])
    g = g[g.season.between(1999, 2025) & g.result.notna()].copy()
    # nflverse has no gametime for 1999. The pbp `start_time` (ET wall clock,
    # e.g. "9/11/05, 16:18:49") fills it; anything still missing is 13:00 ET.
    pw = CACHE / "pbp_weather_1999_2025.parquet"
    if pw.exists():
        st = pd.read_parquet(pw, columns=["game_id", "start_time"])
        st["st"] = pd.to_datetime(st.start_time, format="%m/%d/%y, %H:%M:%S",
                                  errors="coerce").dt.strftime("%H:%M")
        g = g.merge(st[["game_id", "st"]], on="game_id", how="left")
        fill = g.gametime.isna() & g.st.notna()
        log(f"  gametime missing {g.gametime.isna().sum()}, filled from pbp start_time {fill.sum()}")
        g.loc[fill, "gametime"] = g.loc[fill, "st"]
    miss_t = g.gametime.isna().sum()
    if miss_t:
        log(f"  {miss_t} games with no gametime: 13:00 ET assumed")
    dt = pd.to_datetime(g.gameday + " " + g.gametime.fillna("13:00"), errors="coerce")
    g["kick_utc"] = dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                      nonexistent="shift_forward").dt.tz_convert("UTC")
    g["hr"] = g.kick_utc.dt.floor("h")
    g["w0"] = g.hr.dt.strftime("%Y-%m-%d")
    # every window is the kickoff's UTC day plus the next (one call, <= 2 weeks),
    # so all games on one UTC date batch into one request and kickoff+3h fits.
    g["w1"] = (g.hr + pd.Timedelta(days=1)).dt.strftime("%Y-%m-%d")
    g["indoor"] = g.roof.isin(INDOOR_ROOFS)
    nocoord = sorted(set(g.stadium_id) - set(STADIUM_COORDS))
    if nocoord:
        log(f"  stadiums without coordinates (dropped): {nocoord}")
    return g[g.stadium_id.isin(STADIUM_COORDS)]


# --- pbp weather text ------------------------------------------------------
def pbp_weather() -> None:
    out = CACHE / "pbp_weather_1999_2025.parquet"
    if out.exists():
        log(f"pbp weather: {out.name} exists")
        return
    part = CACHE / "pbp_weather_parts"
    part.mkdir(exist_ok=True)
    cols = ["game_id", "weather", "roof", "temp", "wind", "start_time"]
    for s in range(1999, 2026):
        pf = part / f"{s}.parquet"
        if pf.exists():
            continue
        src = CACHE / f"pbp_{s}.parquet"
        tmp = None
        if not src.exists():
            tmp = CACHE / "pbp_raw" / f"play_by_play_{s}.parquet"
            tmp.parent.mkdir(exist_ok=True)
            if not tmp.exists():
                r = requests.get(PBP_URL.format(s=s), timeout=300)
                r.raise_for_status()
                tmp.write_bytes(r.content)
                log(f"  pbp {s}: downloaded {len(r.content)/1e6:.1f} MB")
            src = tmp
        p = pd.read_parquet(src, columns=cols)
        w = (p.sort_values("weather", na_position="last")
             .drop_duplicates("game_id").assign(season=s)
             .assign(n_weather_values=p.groupby("game_id").weather.transform("nunique")))
        w.to_parquet(pf, index=False)
        if tmp is not None:
            tmp.unlink()
        log(f"  pbp {s}: {len(w)} games, {w.weather.notna().sum()} with weather text")
    d = pd.concat([pd.read_parquet(part / f"{s}.parquet") for s in range(1999, 2026)],
                  ignore_index=True)
    d.to_parquet(out, index=False)
    log(f"pbp weather: wrote {out.name} ({len(d)} games)")


# --- Open-Meteo, paced -----------------------------------------------------
class DailyLimit(Exception):
    pass


class Pacer:
    def __init__(self, per_min=450, per_hour=4500):
        self.q = deque()
        self.per_min, self.per_hour = per_min, per_hour
        self.total = 0

    def seed(self, raw: Path):
        """Count calls already made in the last hour (cached files' mtimes), so a
        restarted run does not overshoot the hourly limit."""
        now = time.time()
        for fp in raw.glob("*.json"):
            t = fp.stat().st_mtime
            if now - t < 3600:
                try:
                    n = len(json.loads(fp.read_text(encoding="utf-8"))["stadiums"])
                except (json.JSONDecodeError, KeyError, OSError):
                    continue
                self.q.append((t, n))
        self.q = deque(sorted(self.q))
        log(f"  pacer seeded with {sum(c for _, c in self.q)} calls from the last hour")

    def wait(self, n):
        while True:
            now = time.time()
            while self.q and now - self.q[0][0] > 3600:
                self.q.popleft()
            m = sum(c for t, c in self.q if now - t <= 60)
            h = sum(c for t, c in self.q)
            if m + n <= self.per_min and h + n <= self.per_hour:
                self.q.append((now, n))
                self.total += n
                return
            time.sleep(5)


def om_get(url, params, pacer, n_loc):
    for attempt in range(8):
        pacer.wait(n_loc)
        try:
            r = requests.get(url, params=params, timeout=180)
        except requests.RequestException as e:
            log(f"    network error {e}; retry")
            time.sleep(10 * (attempt + 1))
            continue
        if r.status_code == 200:
            try:
                return r.json()
            except ValueError as e:             # truncated body: retry, it was counted
                log(f"    bad JSON ({e}); retry")
                time.sleep(10 * (attempt + 1))
                continue
        txt = r.text[:300]
        if r.status_code == 429:
            low = txt.lower()
            if "daily" in low:
                raise DailyLimit(txt)
            wait = 3700 - (time.time() % 3600) if "hourly" in low else 70
            log(f"    429 ({txt}); sleeping {wait:.0f}s")
            time.sleep(wait)
            continue
        if r.status_code in (500, 502, 503, 504):
            time.sleep(10 * (attempt + 1))
            continue
        raise RuntimeError(f"{r.status_code}: {txt}")
    raise RuntimeError("retries exhausted")


def run_group(name, url, variables, frame, pacer, max_loc=20, extra=None):
    """frame: rows (stadium_id, w0, w1). One cached JSON per request."""
    jobs = (frame.drop_duplicates(["stadium_id", "w0", "w1"])
            .groupby(["w0", "w1"]).stadium_id.apply(sorted).reset_index())
    done = fetched = 0
    for _, j in jobs.iterrows():
        sids = j.stadium_id
        for k in range(0, len(sids), max_loc):
            chunk = sids[k:k + max_loc]
            h = hashlib.md5(",".join(chunk).encode()).hexdigest()[:8]
            fp = RAW / f"{name}_{j.w0}_{j.w1}_{h}.json"
            if fp.exists():
                try:
                    json.loads(fp.read_text(encoding="utf-8"))
                    done += 1
                    continue
                except (json.JSONDecodeError, OSError):
                    fp.unlink()
            lat = ",".join(f"{STADIUM_COORDS[s][0]:.4f}" for s in chunk)
            lon = ",".join(f"{STADIUM_COORDS[s][1]:.4f}" for s in chunk)
            p = {"latitude": lat, "longitude": lon, "start_date": j.w0, "end_date": j.w1,
                 "hourly": ",".join(variables), "wind_speed_unit": "mph",
                 "temperature_unit": "fahrenheit", "timezone": "UTC", **(extra or {})}
            d = om_get(url, p, pacer, len(chunk))
            d = d if isinstance(d, list) else [d]
            fp.write_text(json.dumps({"stadiums": chunk, "resp": d}), encoding="utf-8")
            fetched += 1
            if fetched % 25 == 0:
                log(f"  {name}: {fetched} fetched, {done} cached, calls so far {pacer.total}")
    log(f"  {name}: done ({fetched} fetched, {done} already cached, {len(frame)} games)")


def consolidate(prefix, rename, out_name):
    rows = []
    for fp in sorted(RAW.glob(f"{prefix}_*.json")):
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            log(f"  unreadable {fp.name}, skipped")
            continue
        for sid, resp in zip(d["stadiums"], d["resp"]):
            h = resp.get("hourly") or {}
            if not h:
                continue
            f = pd.DataFrame({"stadium_id": sid, "ts": pd.to_datetime(h["time"], utc=True)})
            for src, dst in rename.items():
                f[dst] = pd.to_numeric(pd.Series(h.get(src)), errors="coerce").values \
                    if h.get(src) is not None else float("nan")
            rows.append(f)
    if not rows:
        log(f"  {out_name}: nothing to write")
        return
    a = pd.concat(rows, ignore_index=True).drop_duplicates(["stadium_id", "ts"])
    a.to_parquet(CACHE / out_name, index=False)
    log(f"  wrote {out_name}: {len(a):,} stadium-hours, {a.stadium_id.nunique()} stadiums")


def era5_check() -> int:
    """Measurement check, 2010 and 2019 outdoor games: Open-Meteo's default
    archive model ('best_match') is IFS HRES from 2017 and ERA5/ERA5-Land before
    (Open-Meteo docs), so the rain lead's 2017-2025 'ERA5' precipitation is mostly
    IFS. The same games with models=era5 show how far the two scales differ."""
    RAW.mkdir(exist_ok=True)
    g = game_hours()
    fr = g[~g.indoor & g.season.isin([2010, 2019])]
    pacer = Pacer(per_min=120, per_hour=600)
    try:
        run_group("era5m", ARCHIVE_URL, ERA5_VARS, fr, pacer, extra={"models": "era5"})
    except DailyLimit as e:
        log(f"daily limit: {e}")
    consolidate("era5m", {"precipitation": "e5_precip", "wind_speed_10m": "e5_wind",
                          "temperature_2m": "e5_temp"}, "era5_model_check.parquet")
    log(f"calls: {pacer.total}")
    return 0


def main() -> int:
    if "--era5-check" in sys.argv:
        return era5_check()
    RAW.mkdir(exist_ok=True)
    pbp_weather()
    g = game_hours()
    out = ~g.indoor
    groups = [
        ("era5", ARCHIVE_URL, ERA5_VARS, g[out & (g.season <= 2015)], "A ERA5 outdoor 1999-2015"),
        ("era5", ARCHIVE_URL, ERA5_VARS, g[out & (g.season >= 2016)], "B ERA5 outdoor 2016-2025"),
        ("issued", HISTFC_URL, ISSUED_VARS, g[g.season.between(2024, 2025)], "C issued 2024-25"),
        # the hold-out era's dome placebo before the fit era's: the daily limit may cut the last group
        ("era5", ARCHIVE_URL, ERA5_VARS, g[g.indoor & g.season.between(2000, 2015)], "E ERA5 dome 2000-2015"),
        ("era5", ARCHIVE_URL, ERA5_VARS, g[g.indoor & (g.season >= 2016)], "D ERA5 dome 2016-2025"),
    ]
    pacer = Pacer()
    pacer.seed(RAW)
    stopped = None
    for name, url, var, fr, label in groups:
        log(f"group {label}: {len(fr)} games")
        try:
            run_group(name, url, var, fr, pacer)
        except DailyLimit as e:
            stopped = f"daily limit hit in {label}: {e}"
            log(stopped)
            break
    log(f"Open-Meteo calls this run (location-requests): {pacer.total}")
    consolidate("era5", {"precipitation": "era5_precip", "wind_speed_10m": "era5_wind",
                         "temperature_2m": "era5_temp"}, "era5_kick_1999_2025.parquet")
    consolidate("issued", {"precipitation": "om_precip", "temperature_2m": "om_temp",
                           "precipitation_previous_day1": "pc_d1",
                           "precipitation_previous_day2": "pc_d2",
                           "precipitation_previous_day3": "pc_d3",
                           "temperature_2m_previous_day1": "tc_d1",
                           "temperature_2m_previous_day3": "tc_d3",
                           "wind_speed_10m_previous_day1": "wc_d1",
                           "wind_speed_10m_previous_day3": "wc_d3"},
                "issued_wx_2024_2025.parquet")
    if stopped:
        log("INCOMPLETE: " + stopped)
        return 2
    log("complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
