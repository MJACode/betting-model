"""
NFL edge search: QB passing UNDERS in high wind -- resolve the earlier result.

    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_qb_wind [--fetch-only]

The earlier wind-props run (scripts/nfl_edge_prop_wind.py) found QB passing
yards finished far under the line in windy open-air games, and a bettable
"day-1 forecast >= 15 mph" cell that went 50 bets, +46.7% over 2024-25. Its
statistics check found a spike in one forecast band instead of a dose-response,
profit that followed the FORECAST LABEL rather than the wind that blew, name-
matching zero-fill bugs, and a T-24 quote cell that used a forecast not yet
issued. This script answers those four points. It does not re-sell the cell.

CONSTRUCTION (written before any outcome below was read; not changed after)
===========================================================================
Venues. Open-air = nflverse roof 'outdoors' or 'open'. Dome = 'dome'/'closed'.
Coordinates: scripts.nfl_edge_weather_fetch.STADIUM_COORDS (copied from
nfl/data_ingest/weather.py, plus checked 1999-2015 venues) and RIO00
(Maracana, -22.9122, -43.2302). One venue fix: a game whose stadium NAME is
Tottenham is played at LON02 whatever its stadium_id says (2026_05_PHI_JAX is
filed as JAX00). For the BETTABLE rule only, the five retractable-roof venues
(ATL97 DAL00 HOU00 IND00 PHO00) are never eligible: their roof state is only
known after the game, so it is not information at the decision time.

[1] TRUTH. ERA5 reanalysis (archive-api.open-meteo.com, the default ERA5
family) at the venue coordinates. H0 = kickoff (UTC) floored to the hour.
    era5_mean / era5_max = mean / max of hourly 10 m wind at H0..H0+3 (mph)
    era5_kick            = the H0 value (what a kickoff-hour forecast targets)
    era5_temp            = mean 2 m temperature H0..H0+3 (F)
    era5_precip          = sum of hourly precipitation at H0+1..H0+3 (each value
                           is the preceding hour's total, so this is H0..H0+3)
    era5_gust_max        = max hourly gust H0..H0+3 where fetched (2026 only;
                           2016-2025 gusts were NOT fetched, see caveats)
Sources, all free and cached: 2016-2025 wind/temp/precip from the parallel job's
raw responses (Temp/nfl_edge/wx_fetch/era5_*.json); 2023-08..2026-09 wind from
era5_wind_stadiums_2023_2026.parquet (cross-checked on the overlap); 2026-09/10
fetched here into Temp/nfl_edge/openmeteo/. Compared with nflverse `wind`
(recorded at the game) on every 2016-2026 regular-season open-air game.

[2] MECHANISM, no prices, 2016-2025 regular season, open-air games. QB stats
graded from play-by-play (passer_player_id): attempts = completions +
incompletions + interceptions, yards = sum(passing_yards), TDs =
pass_touchdown, two-point tries excluded; cross-checked against the player log.
Starter = the team's passer with the most dropbacks (attempts + sacks).
    PRIMARY population: starters with >= 15 attempts (the task's spec).
    VARIANT: starters with no attempt floor (the floor is post-treatment: wind
    cuts attempts, so a 14-attempt windy game drops out of the primary).
Pre-game expectations, neither using any wind information about THIS game:
    trail8  = the QB's mean passing yards over his previous 8 starts (any
              venue, back to 2015), >= 4 prior starts required.
    exp_A   = trail8 x (team implied total / season-mean implied total), the
              implied total from the nflverse CLOSING spread and total. The
              closing total already prices part of the wind, so the residual
              under A measures the wind effect BEYOND the totals market.
    exp_B   = trail8 x (opponent's trailing-8 passing yards allowed / the mean
              of that over all teams in the same season-week). Market-free,
              so its residual measures the whole physical wind effect.
Regression: residual = actual - exp on ERA5-mean wind bands 0-8 (reference),
8-12, 12-15, 15-18, 18-22, 22+; temperature bands (<32, 32-50, 50-70 ref, 70+);
precipitation (dry < 0.1 mm ref, 0.1-1, >= 1 mm); stadium and season fixed
effects; OLS with standard errors clustered by game. Dose-response: the same
model with a hinge, yards per mph below and above 10 mph (also knots 8, 12).
Same for completions, attempts, TDs (each with its own trail8 and exp_A).

[3] PRICED, 2023-2025 (regular + postseason), main lines player_pass_yds,
player_pass_completions, player_pass_attempts, player_pass_tds, each market
separately. Decision = the latest snapshot strictly before the nflverse
kickoff among BETTABLE books (EXCLUDED dropped); only quotes AT that snapshot;
>= 2 bettable books; line = the modal line (ties: nearest the median, then the
lower); bet UNDER at the best bettable under price at that line; fair under =
mean proportional no-vig split at that line. DraftKings-only version = DK's own
latest pre-kick quote (its line, its price). Pushes return the stake.
Name matching, in order (counts printed): R1 normalised full name among the
game's passers; R2 nickname-canonical first name + last name; R3 first initial
+ last name (also against the play-by-play "J.Allen" form); R4 last name unique
among the game's passers. Unmatched: if snap counts show the player on the
field (offense_pct > 0) he played and threw nothing, actual = 0 ("zero-fill");
otherwise he did not play and the prop is void. Printed: count per rule.
Tables: (actual - line), under hit rate minus fair, under ROI (best / DK) by
ERA5-mean band (open-air) with a dome row, and by issued-forecast band. The
line's own wind adjustment: line minus the same QB's median line over his
previous <= 4 calm games (ERA5 mean < 8 open-air, or dome), against actual
minus the same baseline; and the line move from the T-48h consensus to the
decision quote.

[4] THE FORECAST-LABEL PARADOX, 2024-25 open-air QB passing-yards bets:
forecast flag x truth flag cross-tab (truth = ERA5 mean, and nflverse wind);
covariates of flagged vs truth-windy-but-missed vs calm games; the missed games
listed with stadium and ERA5/nflverse disagreement; a stadium fixed-effect
regression with the forecast and ERA5 both in; a permutation that keeps ERA5
truth fixed and shuffles the FORECAST ERROR (fc - era5_kick) within
stadium x season-month (and within season-month), 5,000 draws: how often a
proxy as noisy as the real forecast beats the truth by as much as it did.

[5] BETTABLE RULE (pre-registered here).
    Population  QB player_pass_yds main line, fixed open-air venue (not a
                retractable), a forecast present for the kickoff hour.
    Decision    the latest pre-kick snapshot, as in [3].
    Forecast    must be ISSUED before the decision. Open-Meteo documents
                `_previous_day0` as "the current model run (equivalent to the
                live Forecast API)", so a day-0 value can postdate a quote taken
                hours before kickoff: day-0 is EXCLUDED. `_previous_dayN` is
                "the value that was predicted N x 24 hours before valid time";
                allowing ~6 h for a run to publish, day-1 is usable when the
                quote is <= 18 h before kickoff, day-2 when <= 42 h, day-3 when
                <= 66 h; otherwise no bet. Value = the forecast for H0.
    Selection   forecast >= T, T in 10..20 mph (1-mph steps, Open-Meteo scale).
    Bets        UNDER, at most 2 per game: one per team, the higher-line QB if
                a team has two quoted.
    Price       best bettable price at the modal line; and DK-only.
    Fit         T* = argmax over T in 11..19 of the fit season's ROI averaged
                over {T-1, T, T+1}, among T whose own cell has >= 10 fit-season
                bets; ties -> the lower T. Fit 2024 -> read 2025 once; fit 2025
                -> read 2024 once. 2023 has no issued-forecast archive
                (Open-Meteo previous runs start 2024-01-18): untestable.
    Placebos    P1 domes, with the ERA5 ambient kickoff-hour wind >= T (the
                roof removes the wind); P2 open-air, with the SAME venue's
                day-1 forecast for H0 + 7 days (next week's weather).
    Inference   cluster bootstrap by game (90%); intra-game correlation and the
                effective number of independent bets; every season; early
                (weeks 1-9) vs late (10+); bets per season per cell (cells with
                <= 15 bets per season flagged LOW-VOL).
    Family      every forecast cell printed in [3] and [5]: 4 markets x 11
                thresholds x {best, DK} on pooled 2024-25 = 88 cells. Max-T
                permutation (forecast vectors shuffled across games within
                season-week, 5,000 draws) and Benjamini-Hochberg q-values.

[6] 2026 FORWARD, weeks 1-5: day-1/2/3 issued forecasts for each eligible
venue's kickoff hour fetched from historical-forecast-api.open-meteo.com (the
same endpoint and scale as stadium_weather_hourly); the props_2026 latest
pre-kick QB passing-yards quote (lead_label 0, i.e. the smallest bucket >= 0
with >= 2 bettable books) and, so the two seasons are the same rule, the T-6h
quote (smallest bucket >= 6); graded on 2026 play-by-play. Every bet listed.

Units: 1 unit = one flat bet (CLAUDE.md section 4). No database, no Odds API,
nothing paid. Open-Meteo calls are cached; a re-run makes none.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm

from scripts.nfl_edge_lib import (BETTABLE, CACHE, EXCLUDED, am_to_dec, boot_ci,
                                  devig2, games, profit_units, props_market)
from scripts.nfl_edge_weather_fetch import STADIUM_COORDS as _COORDS

pd.set_option("display.width", 260)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 600)

T0 = time.time()
QW = CACHE / "qbwind"
OM = CACHE / "openmeteo"
QW.mkdir(exist_ok=True)
OM.mkdir(exist_ok=True)

COORDS = dict(_COORDS)
COORDS.update({"RIO00": (-22.9122, -43.2302),       # Maracana
               "DUB00": (53.3607, -6.2512),         # Croke Park
               "BER00": (52.5147, 13.2395)})        # Olympiastadion Berlin
# nflverse files the 2025 international games under the "home" team's US
# stadium; play-by-play `stadium` holds the real venue (checked over 2016-2026,
# these seven are the only disagreements besides renamings). Bernabeu has a
# retractable roof whose state is unknown here: excluded.
GAME_VENUE = {"2025_01_KC_LAC": ("SAO00", "outdoor"), "2025_04_MIN_PIT": ("DUB00", "outdoor"),
              "2025_05_MIN_CLE": ("LON02", "outdoor"), "2025_06_DEN_NYJ": ("LON02", "outdoor"),
              "2025_07_LA_JAX": ("LON00", "outdoor"), "2025_10_ATL_IND": ("BER00", "outdoor"),
              "2025_11_WAS_MIA": ("MAD00", "unknown")}
RETRACTABLE = {"ATL97", "DAL00", "HOU00", "IND00", "PHO00"}
OUTDOOR_ROOFS = {"outdoors", "open"}
DOME_ROOFS = {"dome", "closed"}
MARKETS = {"player_pass_yds": "passing_yards", "player_pass_completions": "completions",
           "player_pass_attempts": "attempts", "player_pass_tds": "passing_tds"}
SHORT = {"player_pass_yds": "pass_yds", "player_pass_completions": "pass_cmp",
         "player_pass_attempts": "pass_att", "player_pass_tds": "pass_tds"}
WBANDS = [0, 8, 12, 15, 18, 22, 99]
WLAB = ["0-8", "8-12", "12-15", "15-18", "18-22", "22+"]
PBANDS = [0, 8, 12, 15, 18, 99]          # priced tables: 18+ pooled (thin)
PLAB = ["0-8", "8-12", "12-15", "15-18", "18+"]
TGRID = list(range(10, 21))
FIT_MIN_BETS = 10
LOWVOL = 15
NPERM = 5000
RNG = np.random.default_rng(20261011)


def log(*a):
    print(*a, flush=True)


def hdr(s):
    log("\n" + "=" * 110 + f"\n{s}\n" + "=" * 110)


# ─── names ─────────────────────────────────────────────────────────────────
_SUF = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b")
NICK = {"kenny": "kenneth", "josh": "joshua", "mitch": "mitchell", "gabe": "gabriel",
        "mike": "michael", "chig": "chigoziem", "matt": "matthew", "nick": "nicholas",
        "danny": "daniel", "dan": "daniel", "cam": "cameron", "zach": "zachary",
        "rob": "robert", "bobby": "robert", "will": "william", "chris": "christopher",
        "tom": "thomas", "tommy": "thomas", "tony": "anthony", "jon": "jonathan",
        "ben": "benjamin", "sam": "samuel", "alex": "alexander", "drew": "andrew",
        "andy": "andrew", "jake": "jacob", "joe": "joseph", "jim": "james",
        "jimmy": "james", "pat": "patrick", "dave": "david", "nate": "nathan",
        "tim": "timothy", "jeff": "jeffrey", "greg": "gregory", "steve": "steven",
        "teddy": "theodore", "ted": "theodore", "phil": "phillip", "trev": "trevor"}


def tokens(s) -> list[str]:
    if not isinstance(s, str):
        return []
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.replace(".", " ").replace("'", "").replace("-", "")
    s = _SUF.sub(" ", s)
    return [re.sub(r"[^a-z]", "", t) for t in s.split() if re.sub(r"[^a-z]", "", t)]


def nkey(s) -> str:
    return "".join(tokens(s))


def nick_key(s) -> str:
    t = tokens(s)
    if not t:
        return ""
    return NICK.get(t[0], t[0]) + "".join(t[1:])


def init_last(s) -> str:
    t = tokens(s)
    if len(t) < 2:
        return ""
    if len(t[0]) <= 2 and len(t) >= 3:          # "C J Stroud" -> c + stroud
        return t[0][0] + t[-1]
    return t[0][0] + t[-1]


def last(s) -> str:
    t = tokens(s)
    return t[-1] if t else ""


# ─── games and venues ──────────────────────────────────────────────────────

def load_games() -> pd.DataFrame:
    g = games()
    g = g[g.season.between(2015, 2026)].copy()
    g["venue"] = g.stadium_id
    g.loc[g.stadium.fillna("").str.contains("Tottenham"), "venue"] = "LON02"
    roof = g.roof.fillna("").astype(str).str.strip()
    g["env"] = np.where(roof.isin(OUTDOOR_ROOFS), "outdoor",
                        np.where(roof.isin(DOME_ROOFS), "dome", "unknown"))
    # bettable-rule eligibility: a fixed open-air venue, known before the game
    g["fixed_open"] = (~g.venue.isin(RETRACTABLE)) & (roof.isin(OUTDOOR_ROOFS) | (roof == ""))
    g.loc[g.venue.isin({"LAX01", "MEL00", "MUN01", "PAR00", "MAD01", "DET00", "MIN01",
                        "NOR00", "VEG00", "ATL00"}), "fixed_open"] = False
    for gid, (v, env) in GAME_VENUE.items():
        k = g.game_id == gid
        g.loc[k, "venue"], g.loc[k, "env"] = v, env
        g.loc[k, "fixed_open"] = env == "outdoor"
    g["gid"] = "NFL_" + g.game_id
    g["H0"] = g.kick.dt.floor("h").astype("datetime64[ns, UTC]")
    g["month"] = g.kick.dt.tz_convert("America/New_York").dt.month
    g["smonth"] = g.season.astype(str) + "-" + g.month.astype(str).str.zfill(2)
    g["home_imp"] = (g.total_line + g.spread_line) / 2
    g["away_imp"] = (g.total_line - g.spread_line) / 2
    return g


# ─── Open-Meteo (2026 only) ────────────────────────────────────────────────

def om_get(url, params, name):
    fp = OM / f"{name}.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    for attempt in range(6):
        r = requests.get(url, params=params, timeout=120)
        if r.status_code == 200:
            fp.write_text(r.text, encoding="utf-8")
            time.sleep(1.5)
            return r.json()
        if r.status_code == 429:
            raise SystemExit(f"Open-Meteo 429 ({r.text[:200]}); stopping, nothing more requested")
        if r.status_code == 400:
            raise SystemExit(f"Open-Meteo 400 for {name}: {r.text[:200]}")
        time.sleep(5 * (attempt + 1))
    raise SystemExit(f"Open-Meteo failed: {url} {params}")


def fetch_2026(g: pd.DataFrame) -> pd.DataFrame:
    """ERA5 truth + issued forecasts (day 1-3) for 2026 weeks 1-5 open-air
    venues (2026-09-08 .. 2026-10-10/11, one window per venue per endpoint) and
    for the six 2025 international games nflverse files under a US stadium."""
    x = g[(g.season == 2026) & (g.week <= 5) & (g.env != "dome") & g.venue.isin(COORDS)]
    x = x[~x.venue.isin(RETRACTABLE)]
    jobs = [(sid, "2026-09-08", "2026-10-10", "2026-10-11", f"2026_{sid}") for sid in sorted(x.venue.unique())]
    for gid, (v, env) in GAME_VENUE.items():
        if env != "outdoor":
            continue
        k = g[g.game_id == gid].kick.iloc[0]
        a = (k - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        b = (k + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        jobs.append((v, a, b, b, f"intl_{gid}"))
    rows = []
    for sid, start, end_e, end_f, tag in jobs:
        lat, lon = COORDS[sid]
        base = {"latitude": f"{lat:.4f}", "longitude": f"{lon:.4f}", "start_date": start,
                "wind_speed_unit": "mph", "temperature_unit": "fahrenheit", "timezone": "UTC"}
        e = om_get("https://archive-api.open-meteo.com/v1/archive",
                   dict(base, end_date=end_e,
                        hourly="wind_speed_10m,wind_gusts_10m,temperature_2m,precipitation"),
                   f"era5_{tag}")
        f = om_get("https://historical-forecast-api.open-meteo.com/v1/forecast",
                   dict(base, end_date=end_f,
                        hourly="wind_speed_10m,wind_speed_10m_previous_day1,"
                               "wind_speed_10m_previous_day2,wind_speed_10m_previous_day3"),
                   f"issued_{tag}")
        he, hf = e["hourly"], f["hourly"]
        a = pd.DataFrame({"stadium_id": sid, "ts": pd.to_datetime(he["time"], utc=True),
                          "wind": he["wind_speed_10m"], "gust": he["wind_gusts_10m"],
                          "temp": he["temperature_2m"], "precip": he["precipitation"]})
        b = pd.DataFrame({"stadium_id": sid, "ts": pd.to_datetime(hf["time"], utc=True),
                          "hr_an": hf["wind_speed_10m"],
                          "fc_d1": hf["wind_speed_10m_previous_day1"],
                          "fc_d2": hf["wind_speed_10m_previous_day2"],
                          "fc_d3": hf["wind_speed_10m_previous_day3"]})
        rows.append(a.merge(b, on=["stadium_id", "ts"], how="outer"))
    out = pd.concat(rows, ignore_index=True)
    for c in out.columns[2:]:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float)
    out["ts"] = out.ts.astype("datetime64[ns, UTC]")
    return out


# ─── ERA5 hourly, assembled ────────────────────────────────────────────────

def era5_hourly(w26: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    raw = CACHE / "wx_fetch"
    frames = []
    nfiles = 0
    for fp in sorted(raw.glob("era5_*.json")):
        w0 = fp.name.split("_")[1]
        if w0 < "2015-08-01":
            continue
        try:
            d = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:                       # noqa: BLE001 - a file mid-write
            continue
        nfiles += 1
        for sid, resp in zip(d["stadiums"], d["resp"]):
            h = resp.get("hourly") or {}
            if not h:
                continue
            frames.append(pd.DataFrame({
                "stadium_id": sid, "ts": pd.to_datetime(h["time"], utc=True),
                "wind": pd.to_numeric(pd.Series(h.get("wind_speed_10m")), errors="coerce").values,
                "temp": pd.to_numeric(pd.Series(h.get("temperature_2m")), errors="coerce").values,
                "precip": pd.to_numeric(pd.Series(h.get("precipitation")), errors="coerce").values}))
    a = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["stadium_id", "ts", "wind", "temp", "precip"])
    a["ts"] = a.ts.astype("datetime64[ns, UTC]")
    a = a.drop_duplicates(["stadium_id", "ts"])
    e = pd.read_parquet(CACHE / "era5_wind_stadiums_2023_2026.parquet")
    e = e.rename(columns={"ts_e": "ts", "era5_mph": "wind_e"})
    e["ts"] = e.ts.astype("datetime64[ns, UTC]")
    m = a.merge(e, on=["stadium_id", "ts"], how="outer")
    ov = m.dropna(subset=["wind", "wind_e"])
    info = {"wx_files": nfiles, "overlap_hours": len(ov),
            "overlap_maxabs": float((ov.wind - ov.wind_e).abs().max()) if len(ov) else np.nan,
            "overlap_mae": float((ov.wind - ov.wind_e).abs().mean()) if len(ov) else np.nan}
    m["wind"] = m.wind.fillna(m.wind_e)
    m = m.drop(columns="wind_e")
    m["gust"] = np.nan
    w = w26[["stadium_id", "ts", "wind", "gust", "temp", "precip"]].copy()
    m = pd.concat([m[~m.set_index(["stadium_id", "ts"]).index.isin(
        w.set_index(["stadium_id", "ts"]).index)], w], ignore_index=True)
    m = m.drop_duplicates(["stadium_id", "ts"], keep="last")
    return m, info


def game_weather(g: pd.DataFrame, H: pd.DataFrame) -> pd.DataFrame:
    H = H.set_index(["stadium_id", "ts"]).sort_index()
    out = []
    for k in range(5):
        key = pd.MultiIndex.from_arrays([g.venue, g.H0 + pd.Timedelta(hours=k)])
        r = H.reindex(key)
        out.append(r.reset_index(drop=True).add_suffix(f"_{k}"))
    W = pd.concat(out, axis=1)
    wind = W[[f"wind_{k}" for k in range(4)]].values
    res = pd.DataFrame({"gid": g.gid.values})
    full = ~np.isnan(wind).any(1)
    res["era5_ok"] = full
    res["era5_kick"] = W["wind_0"].values
    res["era5_mean"] = np.where(full, np.nanmean(np.where(np.isnan(wind), 0, wind), 1), np.nan)
    res["era5_max"] = np.where(full, np.nanmax(np.where(np.isnan(wind), -1, wind), 1), np.nan)
    temp = W[[f"temp_{k}" for k in range(4)]].values
    res["era5_temp"] = np.where(~np.isnan(temp).any(1), temp.mean(1), np.nan)
    pr = W[[f"precip_{k}" for k in (1, 2, 3)]].values
    res["era5_precip"] = np.where(~np.isnan(pr).any(1), pr.sum(1), np.nan)
    gu = W[[f"gust_{k}" for k in range(4)]].values
    res["era5_gust_max"] = np.where(~np.isnan(gu).any(1), gu.max(1), np.nan)
    return res


def forecasts(g: pd.DataFrame, w26: pd.DataFrame) -> pd.DataFrame:
    """Issued forecasts at H0 (fc_d1..3), the day-1 forecast one week later
    (placebo), and the high-resolution near-analysis (`wind_speed_10m` without
    a suffix on the historical-forecast endpoint = the latest run, ~0-24 h
    lead): hr_kick at H0 and hr_mean over H0..H0+3. hr_* is a SECOND TRUTH,
    from the same model family as the forecast; never a bettable input."""
    w = pd.read_parquet(CACHE / "stadium_weather_hourly.parquet",
                        columns=["stadium_id", "ts", "wind_analysis_mph", "fc_d1_mph", "fc_d2_mph", "fc_d3_mph"])
    w = w.rename(columns={"fc_d1_mph": "fc_d1", "fc_d2_mph": "fc_d2", "fc_d3_mph": "fc_d3",
                          "wind_analysis_mph": "hr_an"})
    for c in ("fc_d1", "fc_d2", "fc_d3", "hr_an"):
        w[c] = pd.to_numeric(w[c], errors="coerce").astype(float)
    w["ts"] = w.ts.astype("datetime64[ns, UTC]")
    w = w.drop_duplicates(["stadium_id", "ts"])
    w = pd.concat([w, w26[["stadium_id", "ts", "fc_d1", "fc_d2", "fc_d3", "hr_an"]]], ignore_index=True)
    w = w.drop_duplicates(["stadium_id", "ts"], keep="last").set_index(["stadium_id", "ts"])
    res = pd.DataFrame({"gid": g.gid.values})
    r = w.reindex(pd.MultiIndex.from_arrays([g.venue, g.H0]))
    for c in ("fc_d1", "fc_d2", "fc_d3"):
        res[c] = r[c].values
    res["hr_kick"] = r["hr_an"].values
    hr = np.column_stack([w.reindex(pd.MultiIndex.from_arrays([g.venue, g.H0 + pd.Timedelta(hours=k)]))
                          ["hr_an"].values for k in range(4)])
    res["hr_mean"] = np.where(~np.isnan(hr).any(1), np.nan_to_num(hr).mean(1), np.nan)
    r7 = w.reindex(pd.MultiIndex.from_arrays([g.venue, g.H0 + pd.Timedelta(days=7)]))
    res["fc_d1_shift7"] = r7["fc_d1"].values
    return res


# ─── play-by-play passer stats ─────────────────────────────────────────────

def passers() -> pd.DataFrame:
    fp = QW / "passers_2015_2026.parquet"
    if fp.exists():
        return pd.read_parquet(fp)
    cols = ["game_id", "season", "season_type", "week", "posteam", "defteam",
            "passer_player_id", "passer_player_name", "complete_pass", "incomplete_pass",
            "interception", "passing_yards", "pass_touchdown", "sack", "two_point_attempt"]
    out = []
    for s in range(2015, 2027):
        p = pd.read_parquet(CACHE / f"pbp_{s}.parquet", columns=cols)
        p = p[p.passer_player_id.notna() & (p.two_point_attempt.fillna(0) != 1)]
        for c in ("complete_pass", "incomplete_pass", "interception", "passing_yards",
                  "pass_touchdown", "sack"):
            p[c] = pd.to_numeric(p[c], errors="coerce").fillna(0)
        p["att"] = ((p.complete_pass == 1) | (p.incomplete_pass == 1) | (p.interception == 1)).astype(int)
        a = p.groupby(["game_id", "season", "season_type", "week", "posteam", "defteam",
                       "passer_player_id"], as_index=False).agg(
            pbp_name=("passer_player_name", "first"), attempts=("att", "sum"),
            completions=("complete_pass", "sum"), passing_yards=("passing_yards", "sum"),
            passing_tds=("pass_touchdown", "sum"), sacks=("sack", "sum"))
        out.append(a)
    d = pd.concat(out, ignore_index=True)
    d["dropbacks"] = d.attempts + d.sacks
    d["gid"] = "NFL_" + d.game_id
    d.to_parquet(fp, index=False)
    return d


def team_plan(seasons) -> pd.DataFrame:
    """Team pass rate over expected (nflverse xpass): first half, downs 1-2,
    win probability 20-80% ('proe_1h'), and the whole game ('proe_all')."""
    out = []
    for s in seasons:
        p = pd.read_parquet(CACHE / f"pbp_{s}.parquet",
                            columns=["game_id", "posteam", "down", "qtr", "wp", "pass", "xpass", "play_type"])
        p = p[p.play_type.isin(["pass", "run"]) & p.xpass.notna() & p["pass"].notna()]
        p["oe"] = p["pass"] - p.xpass
        n = p[(p.qtr <= 2) & p.down.isin([1, 2]) & p.wp.between(0.2, 0.8)]
        a = n.groupby(["game_id", "posteam"]).oe.mean().rename("proe_1h")
        b = p.groupby(["game_id", "posteam"]).agg(proe_all=("oe", "mean"), plays=("oe", "size"))
        out.append(b.join(a).reset_index())
    d = pd.concat(out, ignore_index=True)
    d["gid"] = "NFL_" + d.game_id
    return d.rename(columns={"posteam": "team"})[["gid", "team", "proe_1h", "proe_all", "plays"]]


def id_names() -> pd.Series:
    a = pd.read_parquet(CACHE / "local_nfl_player_game_log.parquet", columns=["player_id", "player_name"])
    b = pd.read_parquet(CACHE / "player_game_log_2025_2026.parquet", columns=["player_id", "player_name"])
    x = pd.concat([a, b]).dropna().drop_duplicates("player_id", keep="last")
    return x.set_index("player_id").player_name


def log_crosscheck(P: pd.DataFrame) -> pd.DataFrame:
    a = pd.read_parquet(CACHE / "local_nfl_player_game_log.parquet",
                        columns=["player_id", "game_id", "season", "attempts", "completions",
                                 "passing_yards", "passing_tds"])
    b = pd.read_parquet(CACHE / "player_game_log_2025_2026.parquet",
                        columns=["player_id", "game_id", "season", "attempts", "completions",
                                 "passing_yards", "passing_tds"])
    L = pd.concat([a[a.season < 2025], b], ignore_index=True)
    L = L[pd.to_numeric(L.attempts, errors="coerce") > 0]
    j = L.merge(P, left_on=["game_id", "player_id"], right_on=["gid", "passer_player_id"],
                suffixes=("_log", "_pbp"))
    rows = []
    for c in ("attempts", "completions", "passing_yards", "passing_tds"):
        x = pd.to_numeric(j[c + "_log"], errors="coerce").astype(float)
        rows.append({"stat": c, "pairs": len(j), "exact_match_%": round(100 * (x == j[c + "_pbp"]).mean(), 2),
                     "within_1_%": round(100 * ((x - j[c + "_pbp"]).abs() <= 1).mean(), 2)})
    rows.append({"stat": "log rows with attempts>0 not found in pbp", "pairs": int(len(L) - len(j)),
                 "exact_match_%": np.nan, "within_1_%": np.nan})
    return pd.DataFrame(rows)


def starters(P: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    """One starter per team-game (most dropbacks) with trailing expectations."""
    s = P.sort_values(["gid", "posteam", "dropbacks", "attempts"], ascending=[True, True, False, False])
    s = s.drop_duplicates(["gid", "posteam"]).copy()
    s = s.merge(g[["gid", "kick", "home_team", "away_team", "home_imp", "away_imp", "total_line",
                   "spread_line"]], on="gid", how="left")
    s = s.sort_values("kick")
    for c in ("passing_yards", "completions", "attempts", "passing_tds"):
        s[f"tr8_{c}"] = s.groupby("passer_player_id")[c].transform(
            lambda x: x.shift(1).rolling(8, min_periods=4).mean())
    s["n_prior"] = s.groupby("passer_player_id").cumcount()
    # team passing yards allowed (all passers) -> opponent trailing 8
    tp = P.groupby(["gid", "defteam"], as_index=False).passing_yards.sum().rename(
        columns={"passing_yards": "allowed"})
    tp = tp.merge(g[["gid", "kick", "season", "week"]], on="gid").sort_values("kick")
    tp["opp_tr8"] = tp.groupby("defteam").allowed.transform(
        lambda x: x.shift(1).rolling(8, min_periods=4).mean())
    tp["opp_tr8_wkmean"] = tp.groupby(["season", "week"]).opp_tr8.transform("mean")
    tp["opp_ratio"] = tp.opp_tr8 / tp.opp_tr8_wkmean
    s = s.merge(tp[["gid", "defteam", "opp_ratio", "opp_tr8"]], on=["gid", "defteam"], how="left")
    s["imp"] = np.where(s.posteam == s.home_team, s.home_imp, s.away_imp)
    mimp = g[g.game_type == "REG"].groupby("season").total_line.mean() / 2
    s["imp_ratio"] = s.imp / s.season.map(mimp)
    for c in ("passing_yards", "completions", "attempts", "passing_tds"):
        s[f"expA_{c}"] = s[f"tr8_{c}"] * s.imp_ratio
        s[f"expB_{c}"] = s[f"tr8_{c}"] * s.opp_ratio
    return s


# ─── props -> decisions ────────────────────────────────────────────────────

def modal_best(x: pd.DataFrame, keys: list[str], min_books: int = 2) -> pd.DataFrame:
    x = x.reset_index(drop=True)
    nb = x.groupby(keys).bookmaker.nunique().rename("n_books")
    x = x.join(nb, on=keys)
    x = x[x.n_books >= min_books]
    if x.empty:
        return pd.DataFrame(columns=keys + ["line", "price", "book", "n_books", "fair_under"])
    cnt = x.groupby(keys + ["line"]).size().rename("n").reset_index()
    med = x.groupby(keys).line.median().rename("med")
    cnt = cnt.join(med, on=keys)
    cnt["dist"] = (cnt.line - cnt.med).abs()
    cnt = cnt.sort_values(keys + ["n", "dist", "line"],
                          ascending=[True] * len(keys) + [False, True, True])
    cons = cnt.drop_duplicates(keys)[keys + ["line"]]
    at = x.merge(cons, on=keys + ["line"]).reset_index(drop=True)
    a = at.dropna(subset=["under_price"]).copy()
    a["dec"] = am_to_dec(a.under_price)
    best = a.loc[a.groupby(keys).dec.idxmax(), keys + ["line", "under_price", "bookmaker", "n_books"]]
    best = best.rename(columns={"under_price": "price", "bookmaker": "book"})
    medp = a.groupby(keys).dec.median().rename("dec_median")
    both = at.dropna(subset=["over_price", "under_price"])
    if len(both):
        _, pu = devig2(both.over_price.values, both.under_price.values)
        fair = pd.Series(pu, index=both.index).groupby([both[k] for k in keys]).mean().rename("fair_under")
        best = best.join(fair, on=keys)
    else:
        best["fair_under"] = np.nan
    best = best.join(medp, on=keys)
    return best


def decisions_hist(market: str, g: pd.DataFrame) -> pd.DataFrame:
    fp = QW / f"dec_{SHORT[market]}_2023_2025.parquet"
    if fp.exists():
        return pd.read_parquet(fp)
    p = props_market(market)[["game_id", "player_name", "line", "over_price", "under_price",
                              "bookmaker", "snapshot_at"]].copy()
    p["bookmaker"] = p.bookmaker.astype(str)
    p = p[~p.bookmaker.isin(EXCLUDED) & p.bookmaker.isin(BETTABLE)]
    p = p.rename(columns={"game_id": "gid"})
    p = p[p.gid.str[4:8].astype(int).between(2023, 2025)]
    p = p.merge(g[["gid", "kick"]], on="gid", how="inner")
    p["lead_h"] = (p.kick - p.snapshot_at).dt.total_seconds() / 3600
    p = p[p.lead_h > 0]
    p["pname"] = p.player_name
    p["key"] = p.player_name.map(nkey)
    p = p.drop_duplicates(["gid", "key", "bookmaker", "snapshot_at"])
    keys = ["gid", "key"]
    last_ = p.groupby(keys).snapshot_at.transform("max")
    x = p[p.snapshot_at == last_]
    best = modal_best(x, keys)
    lead = x.groupby(keys).agg(lead_h=("lead_h", "first"), pname=("pname", "first"))
    best = best.join(lead, on=keys)
    # DraftKings only: DK's own latest pre-kick quote
    d = p[p.bookmaker == "draftkings"]
    d = d.sort_values("snapshot_at").drop_duplicates(keys, keep="last")
    d = d[keys + ["line", "under_price", "over_price", "lead_h"]].rename(
        columns={"line": "dk_line", "under_price": "dk_price", "over_price": "dk_over", "lead_h": "dk_lead_h"})
    best = best.merge(d, on=keys, how="left")
    # T-48 consensus line
    t = p[p.lead_h >= 48]
    t = t[t.snapshot_at == t.groupby(keys).snapshot_at.transform("max")]
    t48 = modal_best(t, keys, min_books=1)[keys + ["line"]].rename(columns={"line": "line_t48"})
    best = best.merge(t48, on=keys, how="left")
    best["market"] = market
    best.to_parquet(fp, index=False)
    return best


def decisions_2026(g: pd.DataFrame, L: float) -> pd.DataFrame:
    p = pd.read_parquet(CACHE / "props_2026.parquet",
                        columns=["game_id", "player_name", "market", "bookmaker", "line",
                                 "over_price", "under_price", "snapshot_at", "lead_h", "lead_label"],
                        filters=[("market", "in", list(MARKETS))])
    p = p[p.bookmaker.isin(BETTABLE) & ~p.bookmaker.isin(EXCLUDED) & (p.lead_label >= L)]
    p = p.rename(columns={"game_id": "gid"})
    p["snapshot_at"] = pd.to_datetime(p.snapshot_at, utc=True, format="mixed")
    p["key"] = p.player_name.map(nkey)
    p["pname"] = p.player_name
    keys = ["gid", "market", "key"]
    p = p.sort_values("snapshot_at").drop_duplicates(keys + ["bookmaker", "lead_label"], keep="last")
    nb = p.groupby(keys + ["lead_label"]).bookmaker.nunique().rename("nb").reset_index()
    nb = nb[nb.nb >= 2].sort_values("lead_label").drop_duplicates(keys)
    x = p.merge(nb[keys + ["lead_label"]], on=keys + ["lead_label"])
    best = modal_best(x, keys)
    lead = x.groupby(keys).agg(lead_h=("lead_h", "max"), lead_label=("lead_label", "first"),
                               pname=("pname", "first"))
    best = best.join(lead, on=keys)
    d = p[p.bookmaker == "draftkings"].sort_values(["lead_label", "snapshot_at"],
                                                   ascending=[True, False]).drop_duplicates(keys)
    d = d[keys + ["line", "under_price", "over_price", "lead_h"]].rename(
        columns={"line": "dk_line", "under_price": "dk_price", "over_price": "dk_over", "lead_h": "dk_lead_h"})
    best = best.merge(d, on=keys, how="left")
    return best


# ─── matching and grading ──────────────────────────────────────────────────

def match_grade(dec: pd.DataFrame, P: pd.DataFrame, names: pd.Series, snaps: pd.DataFrame,
                stat: str) -> tuple[pd.DataFrame, dict]:
    """dec: gid, pname (+ line etc). Adds team, passer id, actual, rule."""
    Pg = P[P.gid.isin(dec.gid.unique())].copy()
    Pg["full"] = Pg.passer_player_id.map(names).fillna(Pg.pbp_name)
    Pg["k1"] = Pg.full.map(nkey)
    Pg["k2"] = Pg.full.map(nick_key)
    Pg["k3a"] = Pg.full.map(init_last)
    Pg["k3b"] = Pg.pbp_name.map(init_last)
    Pg["k4"] = Pg.full.map(last)
    d = dec.copy()
    d["k1"] = d.pname.map(nkey)
    d["k2"] = d.pname.map(nick_key)
    d["k3"] = d.pname.map(init_last)
    d["k4"] = d.pname.map(last)
    d["rule"] = ""
    d["pid"] = None
    d["team"] = None
    d["opp"] = None
    by_g = {k: v for k, v in Pg.groupby("gid")}
    for i, r in d.iterrows():
        cand = by_g.get(r.gid)
        if cand is None:
            continue
        for rule, mask in (("R1", cand.k1 == r.k1), ("R2", cand.k2 == r.k2),
                           ("R3", (cand.k3a == r.k3) | (cand.k3b == r.k3)),
                           ("R4", cand.k4 == r.k4)):
            if r[{"R1": "k1", "R2": "k2", "R3": "k3", "R4": "k4"}[rule]] == "":
                continue
            m = cand[mask]
            if len(m) == 1:
                d.at[i, "rule"], d.at[i, "pid"] = rule, m.passer_player_id.iloc[0]
                d.at[i, "team"], d.at[i, "opp"] = m.posteam.iloc[0], m.defteam.iloc[0]
                break
            if len(m) > 1:                      # ambiguous at this rule: stop, void
                d.at[i, "rule"] = "AMBIG"
                break
    stats = Pg.set_index(["gid", "passer_player_id"])[stat]
    ok = d.rule.isin(["R1", "R2", "R3", "R4"])
    d["actual"] = np.nan
    d.loc[ok, "actual"] = stats.reindex(pd.MultiIndex.from_arrays(
        [d.loc[ok, "gid"], d.loc[ok, "pid"]])).values
    # unmatched: did he take a snap?
    sn = snaps[snaps.game_id.isin(d.gid[~ok].unique()) & (snaps.offense_pct > 0)]
    sn_by = {k: v for k, v in sn.groupby("game_id")}
    zf = 0
    for i in d.index[~ok]:
        s = sn_by.get(d.at[i, "gid"])
        if s is None:
            d.at[i, "rule"] = d.at[i, "rule"] or "VOID"
            continue
        k1, k2, k3, k4 = d.at[i, "k1"], d.at[i, "k2"], d.at[i, "k3"], d.at[i, "k4"]
        hit = s[(s.norm_name == k1) | (s.norm_name.map(nick_key_flat) == k2) |
                (s.norm_name.str.startswith(k3[:1]) & s.norm_name.str.endswith(k4) & (k4 != ""))]
        if len(hit) >= 1 and d.at[i, "rule"] != "AMBIG":
            d.at[i, "rule"], d.at[i, "actual"] = "ZERO", 0.0
            d.at[i, "team"] = hit.team.iloc[0]
            zf += 1
        else:
            d.at[i, "rule"] = d.at[i, "rule"] or "VOID"
    counts = d.rule.value_counts().to_dict()
    return d.drop(columns=["k1", "k2", "k3", "k4"]), counts


def nick_key_flat(n: str) -> str:
    """nick-canonical form of a concatenated snap-count name ('kennethgainwell')."""
    for short, full in NICK.items():
        if n.startswith(short) and not n.startswith(full):
            return full + n[len(short):]
    return n


def grade(d: pd.DataFrame) -> pd.DataFrame:
    d = d.dropna(subset=["actual"]).copy()
    d["push"] = (d.actual == d.line).astype(int)
    d["won"] = (d.actual < d.line).astype(int)
    d["profit"] = profit_units(d.won.values, d.price.values, d.push.values)
    d["profit_med"] = np.where(d.push == 1, 0.0, np.where(d.won == 1, d.dec_median - 1, -1.0))
    dk = d.dk_price.notna() & d.dk_line.notna()
    d["dk_push"] = np.where(dk, (d.actual == d.dk_line).astype(float), np.nan)
    d["dk_won"] = np.where(dk, (d.actual < d.dk_line).astype(float), np.nan)
    d["dk_profit"] = np.nan
    d.loc[dk, "dk_profit"] = profit_units(d.loc[dk, "dk_won"].values, d.loc[dk, "dk_price"].values,
                                          d.loc[dk, "dk_push"].values)
    d["a_l"] = d.actual - d.line
    return d


# ─── inference helpers ─────────────────────────────────────────────────────

def roi_row(x: pd.DataFrame, col="profit", seasons=None) -> dict:
    x = x.dropna(subset=[col])
    if len(x) == 0:
        return {"bets": 0, "games": 0, "units": 0.0, "ROI%": np.nan, "ci90": "", "win%": np.nan}
    r, (lo, hi) = boot_ci(x[col].values, x.gid.values, n=3000)
    out = {"bets": len(x), "games": x.gid.nunique(), "units": round(x[col].sum(), 2),
           "ROI%": round(100 * r, 1), "ci90": f"({100*lo:+.1f},{100*hi:+.1f})",
           "win%": round(100 * (x[col] > 0).mean(), 1)}
    return out


def icc_neff(x: pd.DataFrame, col="profit") -> tuple[float, float]:
    x = x.dropna(subset=[col])
    if x.gid.nunique() < 3 or len(x) == x.gid.nunique():
        return np.nan, float(len(x))
    grp = x.groupby("gid")[col]
    n_i = grp.size().values
    k = len(n_i)
    N = n_i.sum()
    mu = x[col].mean()
    msb = (n_i * (grp.mean().values - mu) ** 2).sum() / (k - 1)
    msw = ((x[col] - x.gid.map(grp.mean())) ** 2).sum() / (N - k)
    n0 = (N - (n_i ** 2).sum() / N) / (k - 1)
    rho = (msb - msw) / (msb + (n0 - 1) * msw) if (msb + (n0 - 1) * msw) > 0 else 0.0
    rho = max(rho, 0.0)
    mbar = N / k
    return rho, N / (1 + (mbar - 1) * rho)


def ols(df: pd.DataFrame, y: str, terms: list[str], fe: list[str], cluster: str):
    X = df[terms].astype(float).copy()
    for f in fe:
        X = X.join(pd.get_dummies(df[f], prefix=f, drop_first=True, dtype=float))
    X = sm.add_constant(X, has_constant="add")
    m = sm.OLS(df[y].astype(float), X).fit(cov_type="cluster",
                                          cov_kwds={"groups": pd.factorize(df[cluster])[0]})
    return m


def fmt_coef(m, t):
    return f"{m.params[t]:+.1f} ({m.bse[t]:.1f})"


def bh(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank, idx in reversed(list(enumerate(o, start=1))):
        prev = min(prev, p[idx] * n / rank)
        q[idx] = prev
    return q


# ─── sections ──────────────────────────────────────────────────────────────

def sec1(g, W, F):
    hdr("[1] TRUTH: ERA5 wind over the game window (kickoff..kickoff+3h) vs nflverse `wind`")
    x = g[(g.game_type == "REG") & g.season.between(2016, 2026) & (g.env == "outdoor") &
          g.result.notna()].merge(W, on="gid").merge(F[["gid", "hr_mean", "fc_d1"]], on="gid")
    cov = x.groupby("season").agg(open_air_games=("gid", "size"), era5_complete=("era5_ok", "sum"),
                                  nflverse_wind=("wind", lambda s: s.notna().sum()),
                                  temp_precip=("era5_temp", lambda s: s.notna().sum()),
                                  gust=("era5_gust_max", lambda s: s.notna().sum()))
    log("coverage, regular-season open-air games:")
    log(cov.to_string())
    y = x[x.era5_ok & x.wind.notna()].copy()
    y["d"] = y.wind - y.era5_mean
    log(f"\nboth measures present: {len(y)} games 2016-{int(y.season.max())}")
    rows = []
    for lab, s in (("era5_mean", y.era5_mean), ("era5_max", y.era5_max), ("era5_kick", y.era5_kick)):
        rows.append({"ERA5 measure": lab, "corr_with_nflverse": round(np.corrcoef(s, y.wind)[0, 1], 3),
                     "mean(nflverse-ERA5)": round((y.wind - s).mean(), 2),
                     "sd(diff)": round((y.wind - s).std(), 2),
                     "MAE": round((y.wind - s).abs().mean(), 2),
                     "|diff|>=5 %": round(100 * ((y.wind - s).abs() >= 5).mean(), 1),
                     "|diff|>=10 %": round(100 * ((y.wind - s).abs() >= 10).mean(), 1)})
    log(pd.DataFrame(rows).to_string(index=False))
    log("\nERA5 mean vs ERA5 kickoff-hour corr: "
        f"{np.corrcoef(y.era5_mean, y.era5_kick)[0,1]:.3f}; mean vs max {np.corrcoef(y.era5_mean, y.era5_max)[0,1]:.3f}")
    # quantile-matched scale
    qs = [0.5, 0.75, 0.9, 0.95, 0.98]
    log("\nscale: quantiles of each measure (same games)")
    log(pd.DataFrame({"q": qs, "nflverse": y.wind.quantile(qs).values.round(1),
                      "era5_mean": y.era5_mean.quantile(qs).values.round(1),
                      "era5_max": y.era5_max.quantile(qs).values.round(1)}).to_string(index=False))
    for T in (12, 15):
        ct = pd.crosstab(np.where(y.wind >= T, f"nflverse>={T}", f"nflverse<{T}"),
                         np.where(y.era5_mean >= T, f"era5_mean>={T}", f"era5_mean<{T}"))
        log(f"\nflag agreement at {T} mph (games):\n{ct.to_string()}")
        rate = (y.wind >= T).mean()
        thr = y.era5_mean.quantile(1 - rate)
        ag = ((y.wind >= T) == (y.era5_mean >= thr)).mean()
        log(f"  rate-matched: nflverse>={T} is {100*rate:.1f}% of games = era5_mean>={thr:.1f}; "
            f"flag agreement at matched rates {100*ag:.1f}%")
    log("\nby season: corr(nflverse, era5_mean), mean diff")
    log(y.groupby("season").apply(lambda z: pd.Series({
        "n": len(z), "corr": round(np.corrcoef(z.wind, z.era5_mean)[0, 1], 3),
        "mean_diff": round((z.wind - z.era5_mean).mean(), 2)})).to_string())
    log("\nlargest disagreements (|nflverse - ERA5 mean|):")
    z = y.reindex(y.d.abs().sort_values(ascending=False).index).head(12)
    log(z[["game_id", "venue", "wind", "era5_mean", "era5_max", "era5_kick"]].round(1).to_string(index=False))
    h = x[x.era5_ok & x.hr_mean.notna()]
    log(f"\nHR = Open-Meteo short-range (0-24h) model wind, same model family as the forecast, NOT an observation, over the same window:"
        f" {len(h)} games 2024-26")
    rows = []
    for a, b in (("hr_mean", "era5_mean"), ("hr_mean", "wind"), ("era5_mean", "wind"),
                 ("fc_d1", "hr_mean"), ("fc_d1", "era5_mean"), ("fc_d1", "wind")):
        z = h.dropna(subset=[a, b])
        rows.append({"pair": f"{a} vs {b}", "n": len(z), "corr": round(np.corrcoef(z[a], z[b])[0, 1], 3),
                     "mean diff": round((z[a] - z[b]).mean(), 2), "MAE": round((z[a] - z[b]).abs().mean(), 2)})
    log(pd.DataFrame(rows).to_string(index=False))
    return y


def sec2(g, W, S):
    hdr("[2] MECHANISM (no prices): QB passing vs a wind-free pre-game expectation, 2016-2025 REG, open-air")
    x = S.merge(g[["gid", "game_type", "env", "venue", "wind"]], on="gid").merge(W, on="gid")
    x = x[(x.game_type == "REG") & x.season.between(2016, 2025) & (x.env == "outdoor") & x.era5_ok]
    base = x.dropna(subset=["expA_passing_yards", "expB_passing_yards", "era5_temp", "era5_precip"]).copy()
    log(f"QB starts, open-air REG 2016-25 with complete ERA5 window: {len(x)}; with trail-8 (>=4 prior starts),"
        f" opp ratio, temp/precip: {len(base)}  (dropped for <4 prior starts etc.: {len(x)-len(base)})")
    cv = x.groupby("season").agg(qb_starts_era5=("gid", "size"),
                                 with_temp_precip=("era5_temp", lambda s: s.notna().sum()))
    cv["in_controlled_sample"] = base.groupby("season").size()
    log("per-season coverage of the mechanism sample:\n" + cv.fillna(0).astype(int).to_string())
    # fallback without temp/precip: every season with ERA5 wind
    nc = x.dropna(subset=["expA_passing_yards", "expB_passing_yards"]).copy()
    nc = nc[nc.attempts >= 15]
    nc["rA"] = nc.passing_yards - nc.expA_passing_yards
    nc["rB"] = nc.passing_yards - nc.expB_passing_yards
    nc["wband"] = pd.cut(nc.era5_mean, WBANDS, right=False, labels=WLAB)
    for b in WLAB[1:]:
        nc[f"w_{b}"] = (nc.wband == b).astype(float)
    mAn = ols(nc, "rA", [f"w_{b}" for b in WLAB[1:]], ["venue", "season"], "gid")
    mBn = ols(nc, "rB", [f"w_{b}" for b in WLAB[1:]], ["venue", "season"], "gid")
    tn = nc.groupby("wband", observed=False).agg(qb_starts=("gid", "size"), mean_resid_A=("rA", "mean"),
                                                 mean_resid_B=("rB", "mean"))
    tn["coef_A (se)"] = ["ref"] + [fmt_coef(mAn, f"w_{b}") for b in WLAB[1:]]
    tn["coef_B (se)"] = ["ref"] + [fmt_coef(mBn, f"w_{b}") for b in WLAB[1:]]
    nc["w_lo"], nc["w_hi"] = nc.era5_mean.clip(upper=10), (nc.era5_mean - 10).clip(lower=0)
    hA = ols(nc, "rA", ["w_lo", "w_hi"], ["venue", "season"], "gid")
    hB = ols(nc, "rB", ["w_lo", "w_hi"], ["venue", "season"], "gid")
    log(f"\nFALLBACK (no temp/precip controls; every season with an ERA5 window; starters >= 15 att):"
        f" n={len(nc)} QB starts, seasons {sorted(nc.season.unique())}")
    log(tn.round(1).to_string())
    log(f"  hinge at 10: A below/above {fmt_coef(hA, 'w_lo')} / {fmt_coef(hA, 'w_hi')} p={hA.pvalues['w_hi']:.4f};"
        f"  B below/above {fmt_coef(hB, 'w_lo')} / {fmt_coef(hB, 'w_hi')} p={hB.pvalues['w_hi']:.4f}")
    base["wband"] = pd.cut(base.era5_mean, WBANDS, right=False, labels=WLAB)
    base["tband"] = pd.cut(base.era5_temp, [-99, 32, 50, 70, 200], right=False,
                           labels=["t<32", "t32-50", "t50-70", "t70+"])
    base["pband"] = pd.cut(base.era5_precip, [-1, 0.1, 1.0, 999], right=False, labels=["dry", "p0.1-1", "p1+"])
    for b in WLAB[1:]:
        base[f"w_{b}"] = (base.wband == b).astype(float)
    for b in ["t<32", "t32-50", "t70+"]:
        base[b] = (base.tband == b).astype(float)
    for b in ["p0.1-1", "p1+"]:
        base[b] = (base.pband == b).astype(float)
    ctrl = ["t<32", "t32-50", "t70+", "p0.1-1", "p1+"]
    wterms = [f"w_{b}" for b in WLAB[1:]]
    pops = {"primary (>=15 att)": base[base.attempts >= 15], "variant (no floor)": base}
    res = {}
    for pname, d in pops.items():
        d = d.copy()
        d["rA"] = d.passing_yards - d.expA_passing_yards
        d["rB"] = d.passing_yards - d.expB_passing_yards
        mA = ols(d, "rA", wterms + ctrl, ["venue", "season"], "gid")
        mB = ols(d, "rB", wterms + ctrl, ["venue", "season"], "gid")
        mR = ols(d, "passing_yards", wterms + ctrl + ["tr8_passing_yards", "imp_ratio", "opp_ratio"],
                 ["venue", "season"], "gid")
        tab = d.groupby("wband", observed=False).agg(qb_starts=("gid", "size"), games=("gid", "nunique"),
                                                     mean_resid_A=("rA", "mean"), mean_resid_B=("rB", "mean"),
                                                     mean_att=("attempts", "mean"), mean_yds=("passing_yards", "mean"))
        tab["coef_A (se)"] = ["ref"] + [fmt_coef(mA, t) for t in wterms]
        tab["coef_B (se)"] = ["ref"] + [fmt_coef(mB, t) for t in wterms]
        tab["coef_reg (se)"] = ["ref"] + [fmt_coef(mR, t) for t in wterms]
        log(f"\n{pname}: passing yards, n={len(d)} QB starts in {d.gid.nunique()} games. coef = yards vs the 0-8 mph band,"
            " controls temp/precip bands + stadium + season FE, SE clustered by game.\n"
            "  A = residual vs trail8 x implied-total ratio (closing total: beyond the totals market);"
            " B = residual vs trail8 x opponent-defence ratio (market-free);"
            " reg = yards on trail8, implied ratio, opp ratio as regressors")
        log(tab.round(1).to_string())
        ca = [mA.params[t] for t in wterms]
        log(f"  monotone non-increasing (A): {all(np.diff(ca) <= 0)}; sequence {np.round(ca,1).tolist()}")
        res[pname] = (d, mA, mB)
    # dose-response hinge
    log("\ndose-response: hinge regressions, yards per mph below / above the knot (ERA5 mean), same controls + FE")
    rows = []
    for pname, (d, _, _) in res.items():
        for knot in (8, 10, 12):
            d = d.copy()
            d["w_lo"] = d.era5_mean.clip(upper=knot)
            d["w_hi"] = (d.era5_mean - knot).clip(lower=0)
            for y in ("rA", "rB"):
                m = ols(d, y, ["w_lo", "w_hi"] + ctrl, ["venue", "season"], "gid")
                rows.append({"population": pname, "resid": y, "knot": knot,
                             "yds/mph below": fmt_coef(m, "w_lo"), "yds/mph above": fmt_coef(m, "w_hi"),
                             "p(above)": round(m.pvalues["w_hi"], 4),
                             "n_above_knot": int((d.era5_mean >= knot).sum())})
    log(pd.DataFrame(rows).to_string(index=False))
    # other stats
    log("\nother passing stats, primary population, hinge at 10 mph (residual vs A-type expectation):")
    d = res["primary (>=15 att)"][0].copy()
    d["w_lo"], d["w_hi"] = d.era5_mean.clip(upper=10), (d.era5_mean - 10).clip(lower=0)
    rows = []
    for st in ("completions", "attempts", "passing_tds", "passing_yards"):
        d["r"] = d[st] - d[f"expA_{st}"]
        dd = d.dropna(subset=["r"])
        m = ols(dd, "r", ["w_lo", "w_hi"] + ctrl, ["venue", "season"], "gid")
        mb = ols(dd, "r", wterms + ctrl, ["venue", "season"], "gid")
        rows.append({"stat": st, "mean": round(dd[st].mean(), 2), "per mph above 10": fmt_coef(m, "w_hi"),
                     "p": round(m.pvalues["w_hi"], 4),
                     **{f"band {b}": round(mb.params[f"w_{b}"], 2) for b in WLAB[1:]}})
    log(pd.DataFrame(rows).to_string(index=False))
    # era split and nflverse wind
    log("\nstability: hinge (knot 10) slope above, by era, residuals A and B, primary population")
    rows = []
    for samp, src, cc in (("controlled", d, ctrl), ("fallback, no temp/precip", nc, [])):
        for lab, ss in (("2016-2020", range(2016, 2021)), ("2021-2025", range(2021, 2026))):
            dd = src[src.season.isin(ss)].copy()
            if len(dd) < 200:
                rows.append({"sample": samp, "era": lab, "n": len(dd), "yds/mph above 10": "too few"})
                continue
            dd["rA"] = dd.passing_yards - dd.expA_passing_yards
            dd["rB"] = dd.passing_yards - dd.expB_passing_yards
            dd["w_lo"], dd["w_hi"] = dd.era5_mean.clip(upper=10), (dd.era5_mean - 10).clip(lower=0)
            m = ols(dd, "rA", ["w_lo", "w_hi"] + cc, ["venue", "season"], "gid")
            mb = ols(dd, "rB", ["w_lo", "w_hi"] + cc, ["venue", "season"], "gid")
            rows.append({"sample": samp, "era": lab, "n": len(dd), "A yds/mph above 10": fmt_coef(m, "w_hi"),
                         "p_A": round(m.pvalues["w_hi"], 4), "B yds/mph above 10": fmt_coef(mb, "w_hi"),
                         "p_B": round(mb.pvalues["w_hi"], 4), "n_above10": int((dd.era5_mean >= 10).sum())})
    log(pd.DataFrame(rows).to_string(index=False))
    dn = d.dropna(subset=["wind"]).copy()
    dn["rA"] = dn.passing_yards - dn.expA_passing_yards
    dn["nb"] = pd.cut(dn.wind, WBANDS, right=False, labels=WLAB)
    for b in WLAB[1:]:
        dn[f"n_{b}"] = (dn.nb == b).astype(float)
    mn = ols(dn, "rA", [f"n_{b}" for b in WLAB[1:]] + ctrl, ["venue", "season"], "gid")
    t2 = dn.groupby("nb", observed=False).agg(qb_starts=("gid", "size"), mean_resid_A=("rA", "mean"))
    t2["coef_A (se)"] = ["ref"] + [fmt_coef(mn, f"n_{b}") for b in WLAB[1:]]
    log("\nsame population, bands on nflverse `wind` instead of ERA5 (comparison only):")
    log(t2.round(1).to_string())
    return res


def build_priced(g, W, F, P, names, snaps):
    out = {}
    counts = []
    for mk, stat in MARKETS.items():
        dec = decisions_hist(mk, g)
        dec = dec.merge(g[["gid", "season", "week", "game_type", "env", "venue", "fixed_open", "smonth",
                           "wind", "total_line", "spread_line", "home_team", "kick"]], on="gid", how="left")
        m, c = match_grade(dec, P, names, snaps, stat)
        c.update({"market": SHORT[mk], "props": len(dec)})
        counts.append(c)
        m = grade(m)
        m = m.merge(W, on="gid", how="left").merge(F, on="gid", how="left")
        out[mk] = m
    return out, pd.DataFrame(counts)


def fc_at_decision(d: pd.DataFrame) -> pd.Series:
    lead = d.lead_h
    return pd.Series(np.select([lead <= 18, lead <= 42, lead <= 66], [d.fc_d1, d.fc_d2, d.fc_d3], np.nan),
                     index=d.index)


def band_table(x: pd.DataFrame, col: str, bands, labels, dome: pd.DataFrame | None = None) -> pd.DataFrame:
    x = x.copy()
    x["band"] = pd.cut(x[col], bands, right=False, labels=labels)
    rows = []
    groups = [(b, x[x.band == b]) for b in labels]
    if dome is not None:
        groups.append(("DOME", dome))
    for b, z in groups:
        r = {"band": b, "props": len(z), "games": z.gid.nunique(),
             "mean(a-l)": round(z.a_l.mean(), 2) if len(z) else np.nan,
             "under%": round(100 * z.won.mean(), 1) if len(z) else np.nan,
             "hit-fair pp": round(100 * (z.won - z.fair_under).mean(), 1) if len(z) else np.nan}
        rb = roi_row(z, "profit")
        rd = roi_row(z, "dk_profit")
        r.update({"ROI_best%": rb["ROI%"], "ci90_best": rb["ci90"], "units_best": rb["units"],
                  "DK_bets": rd["bets"], "ROI_DK%": rd["ROI%"], "ci90_DK": rd["ci90"]})
        rows.append(r)
    return pd.DataFrame(rows)


def sec3(pr, cnt):
    hdr("[3] PRICED 2023-2025: QB passing props, latest pre-kick quote, UNDER")
    log("name matching (propositions per rule; ZERO = on the field per snap counts, no dropback -> actual 0;"
        " VOID = no passer and no snaps, dropped; AMBIG = two candidates, dropped):")
    log(cnt.fillna(0).to_string(index=False))
    for mk, d in pr.items():
        o = d[d.env == "outdoor"]
        dome = d[d.env == "dome"]
        log(f"\n--- {SHORT[mk]}: by ERA5-mean band over the game window, open-air 2023-25 (+ dome row) ---")
        log(band_table(o[o.era5_ok == True], "era5_mean", PBANDS, PLAB, dome).to_string(index=False))  # noqa: E712
        f = o[o.season.isin([2024, 2025])].copy()
        f["fc"] = fc_at_decision(f)
        nf = f.fc.isna().sum()
        log(f"--- {SHORT[mk]}: by ISSUED forecast at the decision (day-1 if quote <=18h, day-2 <=42h, day-3 <=66h),"
            f" open-air 2024-25; props with no forecast (no bet): {nf} ---")
        log(band_table(f.dropna(subset=["fc"]), "fc", PBANDS, PLAB).to_string(index=False))
        log(f"--- {SHORT[mk]}: by HR = Open-Meteo short-range (0-24h) model wind over the game window -- the SAME"
            " model family as the forecast, so not independent of it -- open-air 2024-25 ---")
        log(band_table(f.dropna(subset=["hr_mean"]), "hr_mean", PBANDS, PLAB).to_string(index=False))
        log("    per season, forecast >= 15:")
        for s in (2024, 2025):
            z = f[(f.season == s) & (f.fc >= 15)]
            r = roi_row(z)
            log(f"      {s}: props {len(z)}, games {z.gid.nunique()}, mean(a-l) {z.a_l.mean():+.2f}, ROI {r['ROI%']}% {r['ci90']}")
    # line's own wind adjustment, pass yds
    d = pr["player_pass_yds"].sort_values("kick").copy()
    d["calm"] = (d.env == "dome") | ((d.env == "outdoor") & (d.era5_mean < 8))
    base = []
    hist: dict = {}
    for i, r in d.iterrows():
        h = hist.get(r.pid, [])
        base.append(np.median(h[-4:]) if len(h) >= 2 else np.nan)
        if r.calm and r.pid is not None:
            hist.setdefault(r.pid, []).append(r.line)
    d["baseline"] = base
    d["line_dev"] = d.line - d.baseline
    d["act_dev"] = d.actual - d.baseline
    d["move"] = d.line - d.line_t48
    o = d[(d.env == "outdoor") & (d.era5_ok == True)].copy()  # noqa: E712
    o["band"] = pd.cut(o.era5_mean, PBANDS, right=False, labels=PLAB)
    t = o.groupby("band", observed=False).agg(
        props=("gid", "size"), with_baseline=("baseline", lambda s: s.notna().sum()),
        line_vs_calm_baseline=("line_dev", "mean"), actual_vs_calm_baseline=("act_dev", "mean"),
        with_t48=("move", lambda s: s.notna().sum()), line_move_T48_to_latest=("move", "mean"))
    cb = t.loc["0-8"]
    t["priced_share_vs_0-8"] = ((t.line_vs_calm_baseline - cb.line_vs_calm_baseline) /
                                (t.actual_vs_calm_baseline - cb.actual_vs_calm_baseline))
    log("\n--- pass_yds: does the LINE move for wind? line and actual vs the same QB's median line in his previous"
        " <=4 calm games (>=2 needed), and the T-48h -> decision line move, by ERA5-mean band ---")
    log(t.round(2).to_string())
    f = d[(d.env == "outdoor") & d.season.isin([2024, 2025])].copy()
    f["fc"] = fc_at_decision(f)
    f["band"] = pd.cut(f.fc, PBANDS, right=False, labels=PLAB)
    t2 = f.groupby("band", observed=False).agg(props=("gid", "size"), line_vs_calm_baseline=("line_dev", "mean"),
                                               actual_vs_calm_baseline=("act_dev", "mean"),
                                               line_move_T48_to_latest=("move", "mean"))
    log("    same, by issued-forecast band, 2024-25:")
    log(t2.round(2).to_string())
    return d


def sec4(d, S, P):
    hdr("[4] THE FORECAST-LABEL PARADOX (2024-25 open-air QB passing-yards UNDER bets, best price)")
    x = d[(d.env == "outdoor") & d.season.isin([2024, 2025]) & (d.era5_ok == True)].copy()  # noqa: E712
    x["fc"] = fc_at_decision(x)
    x = x.dropna(subset=["fc"])
    x = x.merge(S[["gid", "posteam", "tr8_passing_yards", "opp_ratio"]].rename(columns={"posteam": "team"}),
                on=["gid", "team"], how="left")
    log(f"bets with a forecast and a complete ERA5 window: {len(x)} in {x.gid.nunique()} games")

    def cell(z):
        r = roi_row(z)
        return pd.Series({"games": z.gid.nunique(), "bets": len(z), "mean(a-l)": round(z.a_l.mean(), 1),
                          "under%": round(100 * z.won.mean(), 1), "ROI%": r["ROI%"], "ci90": r["ci90"]})
    for truth, T in (("wind", 15), ("era5_mean", 15), ("era5_mean", 12), ("era5_max", 15),
                     ("hr_mean", 15), ("hr_mean", 12)):
        x["F"] = np.where(x.fc >= 15, "fc>=15", "fc<15")
        x["Tr"] = np.where(x[truth] >= T, f"{truth}>={T}", f"{truth}<{T}")
        t = x.dropna(subset=[truth]).groupby(["F", "Tr"]).apply(cell)
        log(f"\nforecast flag (>=15) x truth ({truth} >= {T}):")
        log(t.to_string())
    # covariates
    x["grp"] = np.select([x.fc >= 15, (x.wind >= 15) & (x.fc < 15), (x.fc < 10) & (x.wind < 10)],
                         ["A fc>=15 (flagged)", "B nflverse>=15, fc<15 (missed)", "C calm (fc<10, nflverse<10)"], "")
    cov = x[x.grp != ""].groupby("grp").agg(
        games=("gid", "nunique"), bets=("gid", "size"), stadiums=("venue", "nunique"),
        month=("kick", lambda s: s.dt.month.mean()), era5_temp=("era5_temp", "mean"),
        precip_mm=("era5_precip", "mean"), wet_share=("era5_precip", lambda s: (s.dropna() >= 0.1).mean()),
        total_close=("total_line", "mean"), abs_spread=("spread_line", lambda s: s.abs().mean()),
        qb_trail8=("tr8_passing_yards", "mean"), opp_def_ratio=("opp_ratio", "mean"),
        line=("line", "mean"), fc=("fc", "mean"), era5_kick=("era5_kick", "mean"),
        era5_mean=("era5_mean", "mean"), era5_max=("era5_max", "mean"), nflverse=("wind", "mean"),
        mean_a_l=("a_l", "mean"), ROI=("profit", "mean"))
    log("\ncovariates (means) of flagged, missed and calm games:")
    log(cov.round(2).T.to_string())
    miss = x[x.grp.str.startswith("B")].groupby(["gid", "venue"]).agg(
        nflverse=("wind", "first"), era5_mean=("era5_mean", "first"), era5_max=("era5_max", "first"),
        era5_kick=("era5_kick", "first"), fc=("fc", "first"), bets=("gid", "size"),
        mean_a_l=("a_l", "mean"), units=("profit", "sum")).reset_index()
    log(f"\nthe MISSED games (nflverse >= 15, forecast < 15): {len(miss)}; by stadium "
        f"{miss.venue.value_counts().to_dict()}; ERA5 mean >= 12 in {int((miss.era5_mean>=12).sum())}, "
        f">= 15 in {int((miss.era5_mean>=15).sum())}")
    log(miss.round(1).to_string(index=False))
    flag = x[x.fc >= 15].groupby(["gid", "venue"]).agg(
        nflverse=("wind", "first"), era5_mean=("era5_mean", "first"), era5_kick=("era5_kick", "first"),
        fc=("fc", "first"), bets=("gid", "size"), mean_a_l=("a_l", "mean"), units=("profit", "sum")).reset_index()
    log(f"\nthe FLAGGED games (forecast >= 15): {len(flag)}; by stadium {flag.venue.value_counts().to_dict()}")
    log(flag.round(1).to_string(index=False))
    # game plan vs execution: does the shortfall come from fewer attempts (a plan
    # set from the forecast) or from worse passing (the wind itself)?
    tp = team_plan([2024, 2025])
    x = x.merge(tp, on=["gid", "team"], how="left")
    qs = P[["gid", "passer_player_id", "attempts", "completions", "passing_yards", "sacks"]].rename(
        columns={"passer_player_id": "pid", "passing_yards": "yds"})
    x = x.merge(qs, on=["gid", "pid"], how="left")
    x["ypa"] = x.yds / x.attempts.where(x.attempts > 0)
    x["cmp_pct"] = x.completions / x.attempts.where(x.attempts > 0)
    x["grp2"] = np.select([(x.fc >= 15) & (x.era5_mean < 12), (x.fc >= 15) & (x.era5_mean >= 12),
                           (x.fc < 15) & (x.era5_mean >= 12), (x.fc < 10) & (x.era5_mean < 8)],
                          ["fc>=15, ERA5<12", "fc>=15, ERA5>=12", "fc<15, ERA5>=12", "calm: fc<10, ERA5<8"], "")
    pl = x[x.grp2 != ""].groupby("grp2").agg(
        games=("gid", "nunique"), qb_games=("gid", "size"), line=("line", "mean"), yds=("yds", "mean"),
        mean_a_l=("a_l", "mean"), attempts=("attempts", "mean"), ypa=("ypa", "mean"),
        cmp_pct=("cmp_pct", "mean"), sacks=("sacks", "mean"),
        proe_1h_neutral=("proe_1h", "mean"), proe_game=("proe_all", "mean"), plays=("plays", "mean"))
    log("\nplan vs execution, QB passing-yards bets (QB's own attempts / yards per attempt; team pass rate over"
        " expected, nflverse xpass: first half, downs 1-2, win prob 20-80%, and whole game):")
    log(pl.round(3).T.to_string())
    x["grp3"] = np.select([(x.fc >= 15) & (x.hr_mean < 12), (x.fc >= 15) & (x.hr_mean >= 12),
                           (x.fc < 15) & (x.hr_mean >= 12), (x.fc < 10) & (x.hr_mean < 8)],
                          ["fc>=15, HR<12", "fc>=15, HR>=12", "fc<15, HR>=12", "calm: fc<10, HR<8"], "")
    pl3 = x[x.grp3 != ""].groupby("grp3").agg(
        games=("gid", "nunique"), qb_games=("gid", "size"), mean_a_l=("a_l", "mean"),
        attempts=("attempts", "mean"), ypa=("ypa", "mean"), cmp_pct=("cmp_pct", "mean"),
        proe_1h_neutral=("proe_1h", "mean"), proe_game=("proe_all", "mean"), ROI=("profit", "mean"))
    log("  same, grouped on HR (short-range model wind, same family as the forecast):")
    log(pl3.round(3).T.to_string())
    # regression with stadium FE
    x["fc15"] = (x.fc >= 15).astype(float)
    x["e15"] = (x.era5_mean >= 15).astype(float)
    x["e12_15"] = ((x.era5_mean >= 12) & (x.era5_mean < 15)).astype(float)
    x["e8_12"] = ((x.era5_mean >= 8) & (x.era5_mean < 12)).astype(float)
    x["h15"] = (x.hr_mean >= 15).astype(float)
    x["h12_15"] = ((x.hr_mean >= 12) & (x.hr_mean < 15)).astype(float)
    x["h8_12"] = ((x.hr_mean >= 8) & (x.hr_mean < 12)).astype(float)
    log("\nregressions of (actual - line), stadium FE (+ season FE), SE clustered by game:")
    xh = x.dropna(subset=["hr_mean"])
    for terms in (["fc15"], ["fc15", "e8_12", "e12_15", "e15"], ["fc15", "h8_12", "h12_15", "h15"],
                  ["fc", "era5_mean"], ["fc", "hr_mean"], ["era5_mean"], ["hr_mean"], ["fc"]):
        z = xh if any(t.startswith("h") for t in terms) else x
        m = ols(z, "a_l", terms, ["venue", "season"], "gid")
        log("   " + ", ".join(f"{t}: {fmt_coef(m, t)} p={m.pvalues[t]:.3f}" for t in terms) + f"   n={len(z)}")
        m2 = ols(z, "profit", terms, ["venue", "season"], "gid")
        log("      (under profit, units/bet) " + ", ".join(f"{t}: {m2.params[t]:+.3f} ({m2.bse[t]:.3f})" for t in terms))
    # permutation of the forecast error, ERA5 truth fixed
    gm0 = x.groupby("gid").agg(venue=("venue", "first"), smonth=("smonth", "first"),
                               era5_kick=("era5_kick", "first"), hr_kick=("hr_kick", "first"),
                               fc=("fc", "first")).reset_index()
    log("\npermutation: forecast ERROR (fc - truth at the kickoff hour) shuffled, truth fixed, 5,000 draws."
        " Statistic = ROI (and mean a-l) of the fc* >= T bets. p = share of draws >= the real forecast's value.")
    Ts = (12, 13, 14, 15, 16, 17, 18)
    for truth, cellname, cells in (("era5_kick", "stadium x season-month", ["venue", "smonth"]),
                                   ("era5_kick", "season-month", ["smonth"]),
                                   ("hr_kick", "stadium x season-month", ["venue", "smonth"])):
        gm = gm0.dropna(subset=[truth]).reset_index(drop=True)
        xx = x[x.gid.isin(gm.gid)]
        gm["err"] = gm.fc - gm[truth]
        gidx = xx.gid.map(pd.Series(np.arange(len(gm)), index=gm.gid)).values
        prof, al = xx.profit.values, xx.a_l.values
        grp = [v for v in gm.groupby(cells).indices.values() if len(v) > 1]
        single = len(gm) - sum(len(v) for v in grp)
        log(f"  truth {truth}, cells {cellname}: {len(grp)} shuffled cells, {single} singleton (unshuffled)"
            f" games of {len(gm)}")
        sims_r = {T: [] for T in Ts}
        sims_a = {T: [] for T in Ts}
        for _ in range(NPERM):
            e = gm.err.values.copy()
            for v in grp:
                e[v] = e[RNG.permutation(v)]
            fcs = (gm[truth].values + e)[gidx]
            for T in Ts:
                mm = fcs >= T
                if mm.sum():
                    sims_r[T].append(prof[mm].mean())
                    sims_a[T].append(al[mm].mean())
        rows = []
        tcol = "era5_mean" if truth == "era5_kick" else "hr_mean"
        for T in Ts:
            obs_m = xx.fc.values >= T
            if obs_m.sum() == 0 or not sims_r[T]:
                continue
            o_roi, o_al = prof[obs_m].mean(), al[obs_m].mean()
            sr, sa = np.array(sims_r[T]), np.array(sims_a[T])
            tm = xx[tcol].values >= T
            rows.append({"T": T, "fc>=T bets": int(obs_m.sum()), "ROI(fc>=T)%": round(100 * o_roi, 1),
                         "mean a-l(fc>=T)": round(o_al, 1),
                         f"ROI({tcol}>=T)%": round(100 * prof[tm].mean(), 1) if tm.any() else np.nan,
                         "null ROI median%": round(100 * np.median(sr), 1),
                         "null ROI 95th%": round(100 * np.quantile(sr, 0.95), 1),
                         "null a-l median": round(np.median(sa), 1),
                         "p(ROI)": round((1 + (sr >= o_roi).sum()) / (1 + len(sr)), 4),
                         "p(a-l)": round((1 + (sa <= o_al).sum()) / (1 + len(sa)), 4)})
        log(pd.DataFrame(rows).to_string(index=False))
    return x


def rule_bets(d: pd.DataFrame, fccol="fc") -> pd.DataFrame:
    """max 2 per game: one per team, the higher-line QB."""
    z = d.dropna(subset=[fccol]).sort_values("line", ascending=False)
    z = z[z.team.notna()].drop_duplicates(["gid", "team"])
    return z


def sec5(d: pd.DataFrame, pr: dict):
    hdr("[5] BETTABLE RULE (pre-registered): QB pass-yards UNDER, forecast at decision >= T, fixed open-air venues")
    base = d[(d.fixed_open == True) & d.season.isin([2024, 2025])].copy()  # noqa: E712
    base["fc"] = fc_at_decision(base)
    nofc = base[base.fc.isna()]
    log(f"eligible pass-yds props 2024-25: {len(base)}; with no forecast at the kickoff hour (no bet): "
        f"{len(nofc)} ({nofc.groupby('season').size().to_dict()}; by venue {nofc.venue.value_counts().head(8).to_dict()})")
    B = rule_bets(base)
    log(f"rule population (one QB per team): {len(B)} bets in {B.gid.nunique()} games;"
        f" forecast lead used: {pd.cut(B.lead_h, [0,18,42,66], labels=['day-1','day-2','day-3']).value_counts().to_dict()}")

    def grid(z, col="profit"):
        rows = []
        for T in TGRID:
            q = z[z.fc >= T]
            r = roi_row(q, col)
            rho, ne = icc_neff(q, col)
            seas = {s: roi_row(q[q.season == s], col) for s in (2024, 2025)}
            rows.append({"T": T, "bets": r["bets"], "games": r["games"], "n_eff": round(ne, 1),
                         "units": r["units"], "ROI%": r["ROI%"], "ci90": r["ci90"], "win%": r["win%"],
                         "mean(a-l)": round(q.a_l.mean(), 1) if len(q) else np.nan,
                         "2024 ROI/bets": f"{seas[2024]['ROI%']}/{seas[2024]['bets']}",
                         "2025 ROI/bets": f"{seas[2025]['ROI%']}/{seas[2025]['bets']}",
                         "early(w1-9)": f"{roi_row(q[q.week<=9], col)['ROI%']}/{(q.week<=9).sum()}",
                         "late(w10+)": f"{roi_row(q[q.week>=10], col)['ROI%']}/{(q.week>=10).sum()}",
                         "flag": "LOW-VOL" if min(seas[2024]["bets"], seas[2025]["bets"]) <= LOWVOL else ""})
        return pd.DataFrame(rows)
    log("\nfull grid, best bettable price at the modal line (ROI/bets per season; LOW-VOL = <=15 bets in either season):")
    gb = grid(B)
    log(gb.to_string(index=False))
    log("\nfull grid, DraftKings only (DK's own latest pre-kick line and price):")
    gd = grid(B, "dk_profit")
    log(gd.to_string(index=False))
    # fits
    log("\nFIT (pre-registered criterion: max over T in 11..19 of the fit-season ROI averaged over T-1..T+1,"
        f" own cell >= {FIT_MIN_BETS} fit-season bets; ties -> lower T)")
    fits = {}
    for col, lab in (("profit", "best price"), ("dk_profit", "DK only")):
        for fit, hold in ((2024, 2025), (2025, 2024)):
            zf = B[B.season == fit]
            roi = {T: (zf[zf.fc >= T][col].mean() if zf[zf.fc >= T][col].notna().sum() else np.nan) for T in TGRID}
            nb = {T: int(zf[zf.fc >= T][col].notna().sum()) for T in TGRID}
            sc = {}
            for T in range(11, 20):
                if nb[T] >= FIT_MIN_BETS:
                    vals = [roi[t] if not np.isnan(roi[t]) else 0.0 for t in (T - 1, T, T + 1)]
                    sc[T] = np.mean(vals)
            if not sc:
                log(f"  {lab}: fit {fit}: no T with >= {FIT_MIN_BETS} bets")
                continue
            Ts = max(sc, key=lambda t: (round(sc[t], 10), -t))
            zh = B[(B.season == hold) & (B.fc >= Ts)]
            r = roi_row(zh, col)
            log(f"  {lab}: fit {fit} smoothed ROI by T: " + ", ".join(f"{t}:{100*v:+.1f}" for t, v in sc.items()))
            log(f"      -> T* = {Ts} (fit cell {nb[Ts]} bets, ROI {100*roi[Ts]:+.1f}%). HOLD-OUT {hold}: "
                f"{r['bets']} bets, {r['games']} games, {r['units']:+.2f} u, ROI {r['ROI%']}% {r['ci90']}, win {r['win%']}%")
            fits[(col, fit)] = (Ts, r)
    # placebos
    log("\nPLACEBO P1: domes/closed roofs, ERA5 ambient kickoff-hour wind >= T (QB pass-yds unders, one per team):")
    dm = d[(d.env == "dome") & d.season.isin([2024, 2025])].copy()
    dm["fc"] = dm.era5_kick
    Bd = rule_bets(dm)
    rows = []
    for T in TGRID:
        q = Bd[Bd.fc >= T]
        r = roi_row(q)
        rows.append({"T": T, "bets": r["bets"], "games": r["games"], "ROI%": r["ROI%"], "ci90": r["ci90"],
                     "mean(a-l)": round(q.a_l.mean(), 1) if len(q) else np.nan})
    log(pd.DataFrame(rows).to_string(index=False))
    log(f"  all dome bets: {roi_row(Bd)}")
    log("\nPLACEBO P2: open-air, the same venue's day-1 forecast for kickoff + 7 days (next week's weather) >= T:")
    pz = base.copy()
    pz["fc"] = pz.fc_d1_shift7
    Bp = rule_bets(pz)
    log(f"  coverage: shifted forecast present for {len(Bp)} of {len(B)} rule bets; weeks 1-9 / 10+: "
        f"{(Bp.week<=9).sum()}/{(Bp.week>=10).sum()} (real rule population {(B.week<=9).sum()}/{(B.week>=10).sum()});"
        f" postseason bets {int((Bp.game_type!='REG').sum())} (real {int((B.game_type!='REG').sum())})")
    q15 = Bp[Bp.fc >= 15]
    log(f"  shifted >= 15 cell: months {q15.kick.dt.tz_convert('America/New_York').dt.month.value_counts().sort_index().to_dict()},"
        f" venues {q15.venue.value_counts().head(6).to_dict()}")
    rows = []
    for T in TGRID:
        q = Bp[Bp.fc >= T]
        r = roi_row(q)
        rows.append({"T": T, "bets": r["bets"], "games": r["games"], "ROI%": r["ROI%"], "ci90": r["ci90"],
                     "mean(a-l)": round(q.a_l.mean(), 1) if len(q) else np.nan})
    log(pd.DataFrame(rows).to_string(index=False))
    log(f"  all open-air rule-population bets (no wind filter), 2024-25: {roi_row(B)}; DK {roi_row(B, 'dk_profit')}")
    # family: 4 markets x 11 T x {best, DK}, pooled 2024-25
    log("\nFAMILY-WISE: 4 markets x 11 thresholds x {best, DK} = 88 cells, pooled 2024-25, fixed open-air,"
        " one QB per team. Forecast vectors shuffled across games within season-week (5,000 draws).")
    cells = []
    gl = base.drop_duplicates("gid")[["gid", "season", "week", "fc_d1", "fc_d2", "fc_d3"]]
    gl = gl.dropna(subset=["fc_d1", "fc_d2", "fc_d3"]).reset_index(drop=True)
    gpos = pd.Series(np.arange(len(gl)), index=gl.gid)
    FCM = gl[["fc_d1", "fc_d2", "fc_d3"]].values
    wk = gl.groupby(["season", "week"]).indices
    for mk, dd in pr.items():
        z = dd[(dd.fixed_open == True) & dd.season.isin([2024, 2025]) & dd.gid.isin(gl.gid)].copy()  # noqa: E712
        z["fc"] = fc_at_decision(z)
        z = rule_bets(z)
        li = np.select([z.lead_h <= 18, z.lead_h <= 42, z.lead_h <= 66], [0, 1, 2], -1)
        for col in ("profit", "dk_profit"):
            ok = z[col].notna().values & (li >= 0)
            cells.append({"market": SHORT[mk], "price": "best" if col == "profit" else "DK",
                          "gi": gpos[z.gid].values[ok], "li": li[ok], "y": z[col].values[ok]})

    def tstats(fcm):
        out = []
        for c in cells:
            f = fcm[c["gi"], c["li"]]
            for T in TGRID:
                m = f >= T
                n = m.sum()
                if n < 5:
                    out.append(0.0)
                    continue
                y = c["y"][m]
                gsum = np.bincount(c["gi"][m], weights=y - y.mean())
                se = np.sqrt((gsum ** 2).sum()) / n
                out.append(y.mean() / se if se > 0 else 0.0)
        return np.array(out)
    obs = tstats(FCM)
    roi_obs = []
    for c in cells:
        f = FCM[c["gi"], c["li"]]
        for T in TGRID:
            m = f >= T
            roi_obs.append((c["market"], c["price"], T, int(m.sum()), 100 * c["y"][m].mean() if m.sum() else np.nan))
    sims = np.empty((NPERM, len(obs)))
    for b in range(NPERM):
        perm = np.arange(len(gl))
        for v in wk.values():
            perm[v] = perm[RNG.permutation(v)]
        sims[b] = tstats(FCM[perm])
    p_raw = (1 + (sims >= obs).sum(0)) / (1 + NPERM)
    mx = sims.max(1)
    p_fw = (1 + (mx[:, None] >= obs[None, :]).sum(0)) / (1 + NPERM)
    q = bh(p_raw)
    fam = pd.DataFrame(roi_obs, columns=["market", "price", "T", "bets", "ROI%"])
    fam["t"] = obs.round(2)
    fam["p_raw"] = p_raw.round(4)
    fam["q_BH"] = q.round(4)
    fam["p_familywise(maxT)"] = p_fw.round(4)
    fam["ROI%"] = fam["ROI%"].round(1)
    log(fam.to_string(index=False))
    log(f"  cells with q_BH <= 0.10: {int((q <= 0.10).sum())}; family-wise p <= 0.05: {int((p_fw <= 0.05).sum())}")
    return B, fits, gb, gd


def sec6(g, W, F, P, names, snaps, fits):
    hdr("[6] 2026 FORWARD, weeks 1-5 (graded through the games in 2026 play-by-play)")
    played = set(P[P.season == 2026].gid)
    log(f"2026 games in play-by-play: {len(played)}; weeks {sorted(P[P.season==2026].week.unique())}")
    out = {}
    for L, lab in ((0.0, "latest (lead_label 0 bucket)"), (6.0, "T-6h (lead_label >= 6)")):
        dec = decisions_2026(g, L)
        dec = dec[dec.market == "player_pass_yds"].drop(columns="market")
        dec = dec.merge(g[["gid", "season", "week", "game_type", "env", "venue", "fixed_open", "home_team",
                           "away_team", "kick", "wind"]], on="gid", how="left")
        dec = dec[dec.week <= 5]
        m, c = match_grade(dec, P, names, snaps, "passing_yards")
        m = m.merge(W, on="gid", how="left").merge(F, on="gid", how="left")
        m["fc"] = fc_at_decision(m)
        elig = m[(m.fixed_open == True)]  # noqa: E712
        log(f"\n{lab}: pass-yds props weeks 1-5: {len(m)}; fixed open-air: {len(elig)}; match rules {c}")
        log(f"  forecast present at kickoff hour: {elig.fc.notna().sum()} props; "
            f"max forecast {elig.fc.max():.1f} mph; games with fc>=10: {elig[elig.fc>=10].gid.nunique()}")
        z = rule_bets(elig)
        z = z[z.fc >= 10].copy()
        gz = z[z.gid.isin(played)].copy()
        gz = grade(gz) if len(gz) else gz
        if len(gz):
            gz["result"] = np.where(gz.push == 1, "PUSH", np.where(gz.won == 1, "WIN", "LOSS"))
            gz["fc_lead"] = np.where(gz.lead_h <= 18, "d1", np.where(gz.lead_h <= 42, "d2", "d3"))
            show = gz[["gid", "pname", "team", "line", "price", "book", "lead_h", "fc_lead", "fc", "hr_mean",
                       "era5_mean", "era5_gust_max", "wind", "actual", "result", "profit", "dk_line",
                       "dk_price", "dk_profit"]].sort_values(["fc"], ascending=False)
            log("  every QB pass-yds UNDER at forecast >= 10 mph (the grid's floor), graded:")
            log(show.round(2).to_string(index=False))
            for (col, fit), (Ts, _) in fits.items():
                q = gz[gz.fc >= Ts]
                log(f"  fitted T*={Ts} ({col}, fit {fit}): {len(q)} bets, units {q[col].sum():+.2f}")
        pend = z[~z.gid.isin(played)]
        if len(pend):
            log("  not yet graded (game not in play-by-play):")
            log(pend[["gid", "pname", "line", "price", "book", "fc"]].round(1).to_string(index=False))
        out[L] = (m, gz)
    return out


def sec7(B: pd.DataFrame, res: dict | None):
    from scipy.stats import norm
    hdr("[7] HONEST EFFECT SIZE: what the long-history mechanism and the line's own adjustment imply for the"
        " forecast cells, against what the cells returned")
    ctrl = ["t<32", "t32-50", "t70+", "p0.1-1", "p1+"]
    coefs = {}
    for pname, (dm, _, _) in (res or {}).items():
        dm = dm.copy()
        dm["w_lo"], dm["w_hi"] = dm.era5_mean.clip(upper=10), (dm.era5_mean - 10).clip(lower=0)
        for y in ("rA", "rB"):
            m = ols(dm, y, ["w_lo", "w_hi"] + ctrl, ["venue", "season"], "gid")
            coefs[(pname, y)] = (m.params["w_lo"], m.params["w_hi"])
    calm = B[B.fc < 10]
    s, al0 = calm.a_l.std(), calm.a_l.mean()
    w0e, w0h, L0 = calm.era5_mean.mean(), calm.hr_mean.mean(), calm.line_dev.mean()
    dec = float(np.mean(am_to_dec(B.price)))
    log(f"calm reference (fc < 10): {len(calm)} bets, mean(a-l) {al0:+.1f}, sd(a-l) {s:.1f} yds, "
        f"ERA5 mean {w0e:.1f}, HR mean {w0h:.1f}; average decimal price {dec:.3f}")
    rows = []
    for T in range(12, 19):
        q = B[B.fc >= T]
        Ee, Eh, L = q.era5_mean.mean(), q.hr_mean.mean(), q.line_dev.mean() - L0
        r = {"T": T, "bets": len(q), "games": q.gid.nunique(), "E[ERA5|fc>=T]": round(Ee, 1),
             "E[HR|fc>=T]": round(Eh, 1), "line adj vs calm": round(L, 1),
             "obs mean(a-l)": round(q.a_l.mean(), 1), "obs ROI%": round(100 * q.profit.mean(), 1)}
        for (pname, y), (blo, bhi) in coefs.items():
            pl_ = "flr" if pname.startswith("primary") else "nofl"
            f = lambda w: blo * min(w, 10) + bhi * max(w - 10, 0)   # noqa: E731
            short = f(Ee) - f(w0e)
            net = al0 + short - L
            p = norm.cdf(-net / s)
            r[f"{y}-{pl_}: pred a-l"] = round(net, 1)
            r[f"{y}-{pl_}: impl ROI%"] = round(100 * (p * dec - 1), 1)
        rows.append(r)
    log(pd.DataFrame(rows).to_string(index=False))
    if coefs:
        log("hinge coefficients used (yds per mph below / above 10 on the ERA5 mean; flr = starters >= 15 att,"
            " nofl = no floor; rA = beyond the totals market, rB = market-free): " +
            "; ".join(f"{y}-{'flr' if p_.startswith('primary') else 'nofl'}: {blo:+.2f} / {bhi:+.2f}"
                      for (p_, y), (blo, bhi) in coefs.items()))
    log("pred a-l = calm mean(a-l) + mechanism shortfall at E[truth | fc >= T] - the line's own adjustment;"
        " implied ROI = P(actual < line) under a normal with the calm sd, times the average price.")


def main(argv) -> int:
    g = load_games()
    log(f"games loaded {len(g)}; 2026 eligible-venue count weeks 1-5: "
        f"{int(((g.season==2026)&(g.week<=5)&g.fixed_open).sum())}")
    w26 = fetch_2026(g)
    log(f"2026 Open-Meteo frame: {len(w26)} rows, {w26.stadium_id.nunique()} venues; "
        f"files in {OM}: {len(list(OM.glob('*.json')))}")
    if "--fetch-only" in argv:
        return 0
    H, info = era5_hourly(w26)
    log(f"ERA5 hourly assembled: {len(H):,} venue-hours; wx_fetch files read {info['wx_files']};"
        f" overlap with era5_wind_stadiums file {info['overlap_hours']:,} hours, MAE {info['overlap_mae']:.3f},"
        f" max abs diff {info['overlap_maxabs']:.2f} mph")
    W = game_weather(g, H)
    F = forecasts(g, w26)
    P = passers()
    names = id_names()
    snaps = pd.read_parquet(CACHE / "local_nfl_snap_counts.parquet", columns=["game_id", "team", "norm_name",
                                                                          "offense_pct"])
    snaps["norm_name"] = snaps.norm_name.astype(str).str.replace(r"(jr|sr|iii|ii|iv)$", "", regex=True)
    hdr("[0] GRADING SOURCE: play-by-play passer totals vs the player log (regular season, attempts > 0)")
    log(log_crosscheck(P).to_string(index=False))
    sec1(g, W, F)
    S = starters(P, g)
    res = None
    if "--skip-mechanism" not in argv:
        res = sec2(g, W, S)
    pr, cnt = build_priced(g, W, F, P, names, snaps)
    d = sec3(pr, cnt)
    sec4(d, S, P)
    B, fits, gb, gd = sec5(d, pr)
    sec6(g, W, F, P, names, snaps, fits)
    sec7(B, res)
    log(f"\nelapsed {time.time()-T0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
