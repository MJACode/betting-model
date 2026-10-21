"""
NFL edge search: does weather BEYOND wind suppress scoring more than the
full-game total prices?

Four parts, one script. Inputs come from the local cache only
(scripts/nfl_edge_lib.CACHE) plus the free weather files that
scripts/nfl_edge_weather_fetch.py writes there (ERA5 at kickoff, issued
Open-Meteo forecasts 2024-25, nflverse pbp weather text 1999-2025). No
database, no Odds API, nothing paid. Results are UNITS (1 unit = 1 flat bet).

PRE-REGISTRATION (written before any outcome in this file was read)
====================================================================
Common to every part
--------------------
Population. nflverse schedules 1999-2025, played games with a closing total
(`total_line`) and a known roof. OUTDOOR = roof 'outdoors' or 'open'; INDOOR
= 'dome' or 'closed' (the placebo population). One bet per game: the UNDER.
Kickoff hour = nflverse gameday+gametime (ET wall clock) floored to the hour
in UTC, exactly as nfl/scripts/edge_hunt.py builds it. nflverse has no
gametime for 1999, so 1999 is OUT of every test that needs the kickoff hour.
Grading. Under wins when total < line, push (stake back) when equal.
Historical price: the nflverse closing total at -110 (no bettable price
exists before 2020 in the cache). Sensitivity: nflverse `under_odds`, the
closing under price, which exists from 2006. Bettable price (Part 2 only):
best under price among BETTABLE_HIST books at the modal line, see Part 2.
Intervals. 90% bootstrap, resampling WEEKS (season-week clusters), not games:
a weather system hits several stadiums on one weekend, so same-week bets are
not independent. One-sided p = the LARGER of the bootstrap share of resampled
ROI <= 0 and the exact binomial tail of the win count against break-even at
the prices used (the bootstrap alone reads p = 0 on a 3-0 cell).
Multiple testing. Benjamini-Hochberg at q = 0.10 over the PRIMARY family
listed at the end of this docstring; grid cells are a second family.

PART 1. Rain in calm conditions, the frozen rule, out of sample
---------------------------------------------------------------
The lead (nfl/nfl_game_lines_model_system.md, "The one live candidate"): ERA5
precipitation at the kickoff hour > 0.2 mm AND ERA5 wind < 11 mph, outdoor,
bet the under. Chosen on 2016-2025 after looking at buckets.
 1a REPRODUCE on 2016-2025 (the era it was chosen on) before reading the
    hold-out: same buckets as the doc, pushes dropped as edge_hunt drops them.
    The target is n=114, 58.77% under. If it does not reproduce, the hold-out
    is not a test of the lead and is reported as such.
 1b HOLD-OUT 2000-2015, read once: the frozen rule, unchanged.
 1c TEXT RULE, an independent measurement. nflverse pbp `weather` text (the
    gamebook line). Only the description before "Temp:" is classified,
    lower-cased:
      PRECIP  \\b(rain\\w*|shower\\w*|drizzl\\w*|snow\\w*|sleet\\w*|flurr\\w*|
               thunder\\w*|t-?storms?|storms?|sprinkl\\w*|downpour\\w*|precip\\w*)\\b
      NEGATED \\bno\\b|\\bzero\\b|\\b0 ?%|\\bnone\\b|\\bnot\\b|without|
               little chance|slight chance|small chance
      HEDGED  \\d+ ?%|pct|percent|chance|po+ssib|forecast|expect|likely|threat|
               probab|later|tonight|overnight|evening|morning|afternoon|
               early|earlier|ended|stopp|clearing|after|before|maybe|\\bmay\\b|
               could|predict|approach
      DEFINITE = PRECIP and not NEGATED and not HEDGED   (primary)
      ANY      = PRECIP and not NEGATED                   (sensitivity)
    Calm = nflverse `wind` < 12 (the nflverse scale of the deployed wind rule,
    NFLVERSE_THRESHOLD; ERA5 11 is its rate-matched equivalent), where nflverse
    wind is missing the "Wind: .. N mph" figure of the same text fills it,
    values > 40 mph are treated as missing. No wind = excluded.
    Audit before any outcome (--audit, outcome-free): 'po+ssib' replaced
    'possib' after the audit showed the typo "poossible"; ANY catches the
    hedged strings that still describe precipitation during the game
    ("rain throughout game, heavy showers possible"), DEFINITE does not.
    Text exists from 2001: TEXT HOLD-OUT = 2001-2015; 2016-2025 is reported
    for comparison only (the ERA5 version of the rule was chosen there).
 1d GRID, reported as a neighbourhood on the hold-out: ERA5 precip >
    {0.1, 0.2, 0.5, 1.0} mm x ERA5 wind < {9, 10, 11, 12} mph.
    Strict low-volume cells: <= 5 bets a season, marked '*'.
 Placebos. P1 same-date domes: indoor games on a calendar date that holds at
    least one flagged outdoor game. P2 rain at the dome: indoor games whose
    OWN coordinates show the rule's weather (ERA5 precip > 0.2, wind < 11).
    Players never feel either, so both must grade like the indoor baseline.
 Early/late: 2000-2007 vs 2008-2015 inside the hold-out; 2016-2020 vs
    2021-2025 inside the fit era.

PART 2. The bettable version, issued forecasts, 2024-25
-------------------------------------------------------
Weather known at the bet: Open-Meteo `precipitation_previous_dayN` and
`wind_speed_10m_previous_dayN` for the kickoff hour, i.e. the forecast issued
N days before that hour. Decisions (the forecast must be published before the
bet; a day-1 run is issued ~24h before kickoff and is NOT assumed available
at T-24h):
    D1@T-3h   day-1 precip and wind, bet at the T-3h price
    D3@T-24h  day-3 precip and wind, bet at the T-24h price
    D3@T-3h   day-3 precip and wind, bet at the T-3h price
Rule: issued precip > thr AND issued wind < 11 (Open-Meteo scale, the deploy
threshold), outdoor. thr grid {0.1, 0.2, 0.5, 1.0} mm. A PRIORI cell: thr 0.2
(the frozen number). FIT cell: the decision x thr with the best 2024 ROI among
cells with >= 5 bets in 2024; its 2025 result is read once. Also the research
pre-registration's heavy-rain arm as far as the data allow: max issued precip
over the kickoff hour and next two >= 2.5 mm (its probability >= 70% leg
cannot be built: the previous-runs archive carries no precipitation
probability).
Price. odds_hist totals, bookmakers in BETTABLE_HIST, EXCLUDED dropped
(price_home = over, price_away = under, db_setup.py). Per game, every book's
latest quote at least L hours before kickoff and no more than L+12 hours (so
a stale quote is not used). Needs >= 2 bettable books. Line = the modal line
among them (ties: nearest the median, then the lower line). Price = the best
under price among books AT that line. No quote after the decision is read.
Controls at the same price: every outdoor game forecast calm AND dry (0.0 mm),
and the dome placebo (indoor games with the rule's forecast at the dome).

PART 3. Heat unders
-------------------
Published (Action Network / Bet Labs, 2021): unders 64-49-1 in kickoffs at
85F or above, 2003-2021, grade B. AS STATED first: outdoor, nflverse `temp`
>= 85, 2003-2021, under at -110, no wind filter. Then out of sample:
2022-2025 (post-publication) and 1999-2002 (pre-sample). Then the grid temp
>= {80, 85, 90} x era {1999-2012, 2013-2025}; every season at >= 85.
Temperature: nflverse `temp` (observed at the game, NOT knowable at the bet;
an upper bound); sensitivity fills missing nflverse temp from the pbp text
"Temp: NN F" (2022 has 107 nflverse temps). Bettable check 2024-25: issued
day-1 temperature >= 85 at the T-3h price. Placebos: indoor games whose own
coordinates are >= 85F in ERA5 at kickoff; same-date domes.

PART 4. Has the market learned wind? The pre-registered slope test
-----------------------------------------------------------------
Outdoor games 2006-2025, nflverse `wind` (text-filled, > 40 dropped).
Per season, OLS:  total_line ~ wind + week   (market slope b_m)
                  total      ~ wind + week   (realised slope b_r)
and a baseline version: y - base ~ wind, base = mean of the two teams'
leave-one-out season-average total_line. Captured share = b_m / b_r, pooled
by five-season era (season-demeaned) with a game bootstrap, and printed only
where the realised slope is below -1 SE (a ratio to a near-zero or positive
denominator means nothing). Trend: WLS of the
season b_m on season (weights 1/SE^2), two-sided. A second table repeats it on
ERA5 kickoff wind 2000-2025. Plus the threshold version: mean(y | wind >= 12)
- mean(y | wind < 8) for line and for realised, by era.

PRIMARY FAMILY for Benjamini-Hochberg (8):
  H1 ERA5 frozen rain-in-calm, hold-out 2000-2015, -110
  H2 text DEFINITE precip in calm, hold-out 2001-2015, -110
  H3 issued D1@T-3h thr 0.2, 2024-25, best bettable price
  H4 issued D3@T-24h thr 0.2, 2024-25, best bettable price
  H5 issued FIT cell, 2025 only, best bettable price
  H6 heat >= 85 as stated, 2022-2025, -110
  H7 heat >= 85, 1999-2002, -110
  H8 market wind slope trend 2006-2025 (two-sided, b_m moving toward b_r)

    PYTHONIOENCODING=utf-8 python -m scripts.nfl_edge_weather [--audit]
"""
from __future__ import annotations

import argparse
import re
import sys

import numpy as np
import pandas as pd

from scipy.stats import binom

from scripts.nfl_edge_lib import BETTABLE_HIST, CACHE, EXCLUDED, am_to_dec, profit_units

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 500)

PRECIP = re.compile(r"\b(rain\w*|shower\w*|drizzl\w*|snow\w*|sleet\w*|flurr\w*|thunder\w*|"
                    r"t-?storms?|storms?|sprinkl\w*|downpour\w*|precip\w*)\b")
NEGATED = re.compile(r"\bno\b|\bzero\b|\b0 ?%|\bnone\b|\bnot\b|without|little chance|"
                     r"slight chance|small chance")
HEDGED = re.compile(r"\d+ ?%|pct|percent|chance|po+ssib|forecast|expect|likely|threat|probab|"
                    r"later|tonight|overnight|evening|morning|afternoon|early|earlier|ended|"
                    r"stopp|clearing|after|before|maybe|\bmay\b|could|predict|approach")
SNOW = re.compile(r"\b(snow\w*|sleet\w*|flurr\w*)\b")
TEMP_RE = re.compile(r"temp:\s*(-?\d+)\s*\D{0,3}f", re.I)
WIND_RE = re.compile(r"wind:\s*([^0-9]*?)(\d+)(?:\s*(?:-|to)\s*(\d+))?\s*(?:mph)?", re.I)

SEASONS_ERA5_HOLD = (2000, 2015)
SEASONS_TEXT_HOLD = (2001, 2015)
FIT = (2016, 2025)
GRID_SEED = 7


# ─── inference ─────────────────────────────────────────────────────────────

def boot(profit, cluster, n=4000, alpha=0.10, seed=GRID_SEED):
    """lib.boot_ci's cluster bootstrap, also returning the one-sided p = P(ROI <= 0)."""
    profit = np.asarray(profit, float)
    if len(profit) == 0:
        return np.nan, np.nan, np.nan, np.nan
    uniq, inv = np.unique(np.asarray(cluster), return_inverse=True)
    sums = np.bincount(inv, weights=profit)
    cnts = np.bincount(inv)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(uniq), size=(n, len(uniq)))
    roi = sums[idx].sum(1) / cnts[idx].sum(1)
    lo, hi = np.quantile(roi, [alpha / 2, 1 - alpha / 2])
    return profit.sum() / len(profit), lo, hi, float((roi <= 0).mean())


def grade(df, label, price=-110.0, n_seasons=None, strict=5):
    """One row: bets, W-L-P, under% (ex push), units, ROI, 90% CI, p, bets/season."""
    if isinstance(price, str):
        px = df[price].astype(float).values
    else:
        px = np.full(len(df), float(price))
    prof = profit_units(df["under"].values, px, df["push"].values) if len(df) else np.array([])
    roi, lo, hi, p = boot(prof, df["wk"].values) if len(df) else (np.nan,) * 4
    w, pu = int(df["under"].sum()), int(df["push"].sum())
    l = len(df) - w - pu
    if w + l:
        # exact one-sided binomial tail against break-even at the prices actually used;
        # a 3-0 cell has bootstrap p = 0, so the reported p is the larger of the two
        decided = (df["push"].values == 0)
        p0 = float(np.mean(1.0 / am_to_dec(px[decided])))
        p = max(p, float(binom.sf(w - 1, w + l, p0)))
    ns = n_seasons if n_seasons else max(df["season"].nunique(), 1)
    bps = len(df) / ns
    return {"cell": label, "bets": len(df), "W-L-P": f"{w}-{l}-{pu}",
            "under%": round(100 * w / (w + l), 2) if w + l else np.nan, "units": round(float(prof.sum()), 2),
            "roi%": round(100 * roi, 2) if len(df) else np.nan,
            "ci90": f"[{100*lo:+.1f}, {100*hi:+.1f}]" if len(df) else "",
            "p_roi<=0": round(p, 3) if len(df) else np.nan,
            "bets/season": round(bps, 1), "strict": "*" if 0 < bps <= strict else ""}


def table(rows, title):
    print(f"\n{title}")
    print(pd.DataFrame(rows).to_string(index=False))


def bh(pvals, q=0.10):
    p = np.asarray(pvals, float)
    m = np.isfinite(p).sum()
    order = np.argsort(np.where(np.isfinite(p), p, 9))
    adj = np.full(len(p), np.nan)
    prev = 1.0
    ranked = [(i, p[i]) for i in order if np.isfinite(p[i])]
    for k in range(len(ranked) - 1, -1, -1):
        i, pi = ranked[k]
        prev = min(prev, pi * m / (k + 1))
        adj[i] = prev
    return adj, adj <= q


# ─── data ──────────────────────────────────────────────────────────────────

def classify(text):
    if not isinstance(text, str) or not text.strip():
        return "none", False, np.nan, np.nan
    low = text.lower()
    desc = low.split("temp:")[0]
    has = bool(PRECIP.search(desc))
    neg = bool(NEGATED.search(desc))
    hed = bool(HEDGED.search(desc))
    cat = "dry" if not has else ("negated" if neg else ("hedged" if hed else "definite"))
    snow = bool(SNOW.search(desc)) and cat in ("definite", "hedged")
    t = TEMP_RE.search(low)
    temp = float(t.group(1)) if t else np.nan
    wm = WIND_RE.search(low)
    wind = np.nan
    if wm:
        a = float(wm.group(2))
        wind = (a + float(wm.group(3))) / 2 if wm.group(3) else a
    elif "wind: calm" in low or re.search(r"wind:\s*calm", low):
        wind = 0.0
    return cat, snow, temp, wind


def load() -> pd.DataFrame:
    from scripts.nfl_edge_weather_fetch import game_hours
    g = pd.read_parquet(CACHE / "nflverse_games.parquet",
                        columns=["game_id", "season", "game_type", "week", "gameday", "home_team",
                                 "away_team", "total", "total_line", "under_odds", "roof",
                                 "temp", "wind", "stadium_id"])
    g = g[g.season.between(1999, 2025) & g.total.notna() & g.total_line.notna()
          & g.roof.notna()].copy()
    gh = game_hours()[["game_id", "hr", "gametime"]]
    g = g.merge(gh, on="game_id", how="left")
    g.loc[g.season == 1999, "hr"] = pd.NaT          # no kickoff time in 1999
    g["outdoor"] = g.roof.isin(["outdoors", "open"])
    g["indoor"] = g.roof.isin(["dome", "closed"])
    g["under"] = (g.total < g.total_line).astype(int)
    g["push"] = (g.total == g.total_line).astype(int)
    g["wk"] = g.season.astype(str) + "_" + g.week.astype(int).astype(str).str.zfill(2)

    w = pd.read_parquet(CACHE / "pbp_weather_1999_2025.parquet", columns=["game_id", "weather"])
    g = g.merge(w, on="game_id", how="left")
    c = g.weather.apply(classify)
    g["txt"] = [x[0] for x in c]
    g["txt_snow"] = [x[1] for x in c]
    g["txt_temp"] = [x[2] for x in c]
    g["txt_wind"] = [x[3] for x in c]
    g["wind_nv"] = g.wind.where(g.wind <= 40)
    g["wind_f"] = g.wind_nv.fillna(g.txt_wind.where(g.txt_wind <= 40))
    g["temp_f"] = g.temp.fillna(g.txt_temp)

    ef = CACHE / "era5_kick_1999_2025.parquet"
    if ef.exists():
        e = pd.read_parquet(ef)
        g = g.merge(e.rename(columns={"ts": "hr"}), on=["stadium_id", "hr"], how="left")
    else:
        g["era5_precip"] = g["era5_wind"] = g["era5_temp"] = np.nan
    return g


# ─── audit (no outcomes) ───────────────────────────────────────────────────

def audit(g):
    o = g[g.season >= 2001]
    print("text classes by roof (no outcomes read):")
    print(pd.crosstab(o.txt, o.outdoor.map({True: "outdoor", False: "indoor"})))
    for cat in ("definite", "hedged", "negated"):
        s = o[o.txt == cat].weather.str.lower().str.split("temp:").str[0].str.strip()
        print(f"\n--- {cat}: {len(s)} games, {s.nunique()} distinct descriptions")
        for k, v in s.value_counts().items():
            print(f"  {v:4d}  {k}")
    both = g[g.wind.notna() & g.txt_wind.notna()]
    print(f"\nnflverse wind vs text wind: n={len(both)}, identical {np.mean(both.wind == both.txt_wind):.3f}, "
          f"corr {both.wind.corr(both.txt_wind):.3f}")
    bt = g[g.temp.notna() & g.txt_temp.notna()]
    print(f"nflverse temp vs text temp: n={len(bt)}, identical {np.mean(bt.temp == bt.txt_temp):.3f}")
    print("outdoor games: wind missing nflverse / filled from text / still missing, by season")
    od = g[g.outdoor]
    print(od.groupby("season").agg(n=("game_id", "size"), nv_wind=("wind", "count"),
                                   filled=("wind_f", "count"), nv_temp=("temp", "count"),
                                   temp_filled=("temp_f", "count"), era5=("era5_precip", "count"),
                                   text=("weather", "count")).T.to_string())
    print("nflverse wind > 40 (treated as missing):", g[g.wind > 40][["game_id", "wind"]].values.tolist())


# ─── part 1 ────────────────────────────────────────────────────────────────

def era(df, a, b):
    return df[df.season.between(a, b)]


def reproduce(g):
    """1a: edge_hunt's own construction on the fit era (pushes dropped, ROI from win rate)."""
    o = g[g.outdoor & g.era5_precip.notna() & g.era5_wind.notna()]
    print(f"outdoor 2016-2025 games with ERA5 at kickoff: {len(era(o, *FIT))}")
    f = era(o, *FIT)
    f = f[f.push == 0]
    calm = f[f.era5_wind < 11]
    t = calm.groupby(pd.cut(calm.era5_precip, [-.01, .0001, .2, .5, 99]), observed=True).agg(
        n=("under", "size"), under=("under", "mean")).reset_index()
    t["roi110"] = (t.under * (100 / 110) - (1 - t.under)).mul(100).round(2)
    t["under"] = (t.under * 100).round(2)
    t["doc_n"] = [1266, 111, 47, 67][:len(t)]
    t["doc_under"] = [48.10, 50.45, 57.45, 59.70][:len(t)]
    print("\n1a REPRODUCTION, 2016-2025, ERA5 wind < 11, pushes dropped (edge_hunt's construction) "
          "vs the documented table")
    print(t.to_string(index=False))
    r = calm[calm.era5_precip > 0.2]
    print(f"   rule precip > 0.2 & wind < 11: n={len(r)}, under {100*r.under.mean():.2f}% "
          f"(doc: n=114, 58.77%)")



def measurement_check(g, o):
    """Outcome-free. Open-Meteo's default archive model is IFS HRES from 2017 and
    ERA5 before, so the lead's 2017-2025 precipitation is IFS while the hold-out's
    is ERA5. Same games, both sources (era5_model_check.parquet, 2010 and 2019)."""
    f = CACHE / "era5_model_check.parquet"
    if not f.exists():
        print("measurement check file missing")
        return
    b = pd.read_parquet(f).rename(columns={"ts": "hr"})
    m = o[o.season.isin([2010, 2019])].merge(b, on=["stadium_id", "hr"], how="inner")
    rows = []
    for s, x in m.groupby("season"):
        fa = (x.era5_precip > 0.2) & (x.era5_wind < 11)
        fb = (x.e5_precip > 0.2) & (x.e5_wind < 11)
        rows.append({"season": s, "games": len(x), "default model": "ERA5" if s < 2017 else "IFS HRES",
                     "precip identical": round(float(np.mean(x.era5_precip == x.e5_precip)), 3),
                     "precip corr": round(x.era5_precip.corr(x.e5_precip), 3),
                     "wind corr": round(x.era5_wind.corr(x.e5_wind), 3),
                     "default >0.2mm": int((x.era5_precip > 0.2).sum()), "ERA5 >0.2mm": int((x.e5_precip > 0.2).sum()),
                     "rule both": int((fa & fb).sum()), "default only": int((fa & ~fb).sum()),
                     "ERA5 only": int((~fa & fb).sum())})
        if s == 2019:
            k = int((x.era5_precip > 0.2).sum())
            if k:
                t = np.sort(x.e5_precip.values)[::-1][k - 1] if k <= len(x) else np.nan
                print(f"   ERA5 threshold giving the same count of >0.2mm hours as the default (IFS) on the "
                      f"same {len(x)} 2019 games: precip >= {t:.2f} mm")
    print("\n1m MEASUREMENT: Open-Meteo default ('best_match') vs explicit models=era5 at kickoff, outdoor")
    print(pd.DataFrame(rows).to_string(index=False))
    calm = o[o.era5_wind < 11]
    for a, b_ in [(2000, 2015), (2016, 2016), (2017, 2025)]:
        x = era(calm, a, b_)
        print(f"   fire rate of precip > 0.2 among calm outdoor games {a}-{b_}: "
              f"{100*(x.era5_precip > 0.2).mean():.2f}% of {len(x)}")


def part1(g, primary):
    print("\n" + "=" * 100 + "\nPART 1  RAIN IN CALM CONDITIONS")
    o = g[g.outdoor & g.era5_precip.notna() & g.era5_wind.notna()].copy()
    ind = g[g.indoor & g.era5_precip.notna() & g.era5_wind.notna()].copy()
    print(f"outdoor games with ERA5 at kickoff: {len(o)} (2000-2015 {len(era(o, 2000, 2015))}, "
          f"2016-2025 {len(era(o, 2016, 2025))}); indoor with ERA5 at the dome: {len(ind)}")

    reproduce(g)
    measurement_check(g, o)

    o["rain"] = (o.era5_precip > 0.2) & (o.era5_wind < 11)
    o["dry_calm"] = (o.era5_precip == 0) & (o.era5_wind < 11)
    rows = []
    for lab, a, b in [("FIT 2016-2025 (rule chosen here)", 2016, 2025), ("  2016-2020", 2016, 2020),
                      ("  2021-2025", 2021, 2025),
                      ("HOLD-OUT 2000-2015 (read once)", 2000, 2015), ("  2000-2007", 2000, 2007),
                      ("  2008-2015", 2008, 2015)]:
        x = era(o, a, b)
        rows.append(grade(x[x.rain], lab, n_seasons=b - a + 1))
    table(rows, "1b FROZEN RULE  ERA5 precip > 0.2 mm & ERA5 wind < 11, outdoor, under at nflverse close -110")
    h1 = era(o, *SEASONS_ERA5_HOLD)
    h1 = h1[h1.rain]
    primary["H1 ERA5 rain-in-calm 2000-15"] = grade(h1, "H1", n_seasons=16)
    rows = []
    for lab, a, b in [("FIT 2016-2025", 2016, 2025), ("HOLD-OUT 2006-2015", 2006, 2015)]:
        x = era(o, a, b)
        x = x[x.rain & x.under_odds.notna()]
        rows.append(grade(x, lab + " @-110", n_seasons=b - a + 1))
        rows.append(grade(x, lab + " @nflverse under_odds", price="under_odds", n_seasons=b - a + 1))
    table(rows, "1b' same rule where nflverse has a closing under price (2006+): -110 vs that price")

    rows = [grade(o[o.rain & (o.season == s)], str(s), n_seasons=1) for s in range(2000, 2026)]
    table(rows, "1b'' FROZEN RULE by season (2000-2015 hold-out, 2016-2025 fit)")

    # grid on the hold-out, and the same cells on the fit era for reference
    best = (-999.0, None, None)
    for lab, a, b in [("HOLD-OUT 2000-2015", 2000, 2015), ("FIT 2016-2025 (reference)", 2016, 2025)]:
        x = era(o, a, b)
        rows = []
        for pt in (0.1, 0.2, 0.5, 1.0):
            for wc in (9, 10, 11, 12):
                sel = x[(x.era5_precip > pt) & (x.era5_wind < wc)]
                rr = grade(sel, f"precip>{pt} wind<{wc}", n_seasons=b - a + 1)
                rows.append(rr)
                if a == 2000:
                    primary.setdefault("_grid", []).append(rr)
                    if rr["strict"] and rr["roi%"] > best[0]:
                        best = (rr["roi%"], pt, wc)
        table(rows, f"1d GRID {lab}: every cell, ERA5, -110 ('*' = <= 5 bets a season)")

    # DESCRIPTIVE, added after the hold-out was read: the strict (<= 5 bets a season)
    # hold-out cell with the highest ROI, every season and both eras. Chosen after the
    # fact inside the declared neighbourhood; it is not a test and is not in BH.
    _, pt, wc = best
    sel = o[(o.era5_precip > pt) & (o.era5_wind < wc)]
    rows = [grade(sel[sel.season == s], str(s), n_seasons=1) for s in range(2000, 2026)]
    rows += [grade(era(sel, a, b), f"{a}-{b}", n_seasons=b - a + 1)
             for a, b in [(2000, 2007), (2008, 2015), (2000, 2015), (2016, 2020), (2021, 2025), (2016, 2025)]]
    table(rows, f"1d' DESCRIPTIVE (chosen after reading 1d): best strict hold-out cell precip>{pt} wind<{wc}, "
                "by season and era, -110")

    # placebos
    rows = []
    for lab, a, b in [("2000-2015", 2000, 2015), ("2016-2025", 2016, 2025)]:
        x = era(o, a, b)
        dates = set(x[x.rain].gameday)
        gi = g[g.indoor & g.season.between(a, b)]
        rows.append(grade(x[x.dry_calm], f"{lab} control: outdoor calm & dry (ERA5 0.0 mm)", n_seasons=b - a + 1))
        rows.append(grade(gi, f"{lab} indoor baseline (all)", n_seasons=b - a + 1))
        rows.append(grade(gi[gi.gameday.isin(dates)], f"{lab} P1 indoor, same dates as rain bets", n_seasons=b - a + 1))
        xi = era(ind, a, b)
        rows.append(grade(xi[(xi.era5_precip > 0.2) & (xi.era5_wind < 11)],
                          f"{lab} P2 indoor, rule weather AT THE DOME", n_seasons=b - a + 1))
    table(rows, "1e PLACEBOS and controls, -110 (should look like the indoor baseline)")

    # text rule
    t_ = g[g.outdoor & g.txt.ne("none") & g.wind_f.notna()].copy()
    t_["calm"] = t_.wind_f < 12
    rows = []
    for lab, a, b in [("HOLD-OUT 2001-2015 (read once)", 2001, 2015), ("  2001-2007", 2001, 2007),
                      ("  2008-2015", 2008, 2015), ("2016-2025 (comparison)", 2016, 2025),
                      ("  2016-2020", 2016, 2020), ("  2021-2025", 2021, 2025)]:
        x = era(t_, a, b)
        rows.append(grade(x[x.calm & (x.txt == "definite")], lab + " DEFINITE", n_seasons=b - a + 1))
        rows.append(grade(x[x.calm & x.txt.isin(["definite", "hedged"])], lab + " ANY (incl hedged)",
                          n_seasons=b - a + 1))
    table(rows, "1c TEXT RULE  pbp weather text precip, nflverse wind < 12 (text-filled), outdoor, -110")
    h2 = era(t_, *SEASONS_TEXT_HOLD)
    primary["H2 text DEFINITE precip-in-calm 2001-15"] = grade(h2[h2.calm & (h2.txt == "definite")], "H2",
                                                              n_seasons=15)
    rows = []
    for lab, a, b in [("2001-2015", 2001, 2015), ("2016-2025", 2016, 2025)]:
        x = era(t_, a, b)
        d = x[x.calm & (x.txt == "definite")]
        rows.append(grade(d[~d.txt_snow], f"{lab} rain only", n_seasons=b - a + 1))
        rows.append(grade(d[d.txt_snow], f"{lab} snow/sleet", n_seasons=b - a + 1))
        rows.append(grade(x[x.calm & (x.txt == "dry")], f"{lab} control: calm, no precip word", n_seasons=b - a + 1))
        rows.append(grade(x[~x.calm & (x.txt == "definite")], f"{lab} windy (>=12) DEFINITE", n_seasons=b - a + 1))
        gi = g[g.indoor & g.season.between(a, b)]
        rows.append(grade(gi[gi.gameday.isin(set(d.gameday))], f"{lab} P1 indoor, same dates", n_seasons=b - a + 1))
        rows.append(grade(gi[gi.txt.isin(["definite", "hedged"])], f"{lab} P indoor with precip text",
                          n_seasons=b - a + 1))
    table(rows, "1c' TEXT RULE splits, controls and placebos, -110")
    rows = [grade(t_[t_.calm & (t_.txt == "definite") & (t_.season == s)], str(s), n_seasons=1)
            for s in range(2001, 2026)]
    table(rows, "1c'' TEXT DEFINITE in calm, by season")

    # agreement
    both = g[g.outdoor & g.era5_precip.notna() & g.txt.ne("none") & g.wind_f.notna()
             & g.era5_wind.notna() & (g.season >= 2001)].copy()
    both["era5_flag"] = (both.era5_precip > 0.2) & (both.era5_wind < 11)
    both["text_flag"] = (both.txt == "definite") & (both.wind_f < 12)
    rows = []
    for (ef, tf), x in both.groupby(["era5_flag", "text_flag"]):
        rows.append(grade(x, f"ERA5 flag={ef} text flag={tf}", n_seasons=25))
    table(rows, "1f AGREEMENT of the two measurements, outdoor 2001-2025, -110")


# ─── part 2 ────────────────────────────────────────────────────────────────

def prices(lead_h, games):
    cols = ["snapshot_at", "game_id", "bookmaker", "market", "point", "price_home", "price_away",
            "lead_hours"]
    d = pd.read_parquet(CACHE / "odds_hist_2020_2025.parquet", columns=cols,
                        filters=[("market", "==", "totals")])
    d = d[d.game_id.isin(games)]
    for c in ("point", "price_home", "price_away", "lead_hours"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[~d.bookmaker.isin(EXCLUDED) & d.bookmaker.isin(BETTABLE_HIST)]
    d = d[(d.lead_hours >= lead_h) & (d.lead_hours <= lead_h + 12)]
    d = d.dropna(subset=["point", "price_away"])
    d = d.sort_values("snapshot_at").groupby(["game_id", "bookmaker"]).tail(1)
    out = []
    for gid, x in d.groupby("game_id"):
        if len(x) < 2:
            continue
        vc = x.point.value_counts()
        modal = vc[vc == vc.max()].index.values
        med = x.point.median()
        line = sorted(modal, key=lambda v: (abs(v - med), v))[0]
        at = x[x.point == line]
        out.append((gid, line, at.price_away.max(), len(x), len(at)))
    return pd.DataFrame(out, columns=["game_id", "bline", "bprice", "n_books", "n_at_line"])


def part2(g, primary):
    print("\n" + "=" * 100 + "\nPART 2  BETTABLE VERSION, ISSUED FORECASTS, 2024-25")
    f = CACHE / "issued_wx_2024_2025.parquet"
    if not f.exists():
        print("issued forecast file missing: PART 2 NOT RUN")
        return
    w = pd.read_parquet(f)
    x = g[g.season.between(2024, 2025) & g.hr.notna()].copy()
    k = w.rename(columns={"ts": "hr"})
    x = x.merge(k, on=["stadium_id", "hr"], how="left")
    for h in (1, 2):
        kk = k.copy()
        kk["hr"] = kk.hr - pd.Timedelta(hours=h)
        x = x.merge(kk[["stadium_id", "hr", "pc_d1", "pc_d3"]].rename(
            columns={"pc_d1": f"pc_d1_{h}", "pc_d3": f"pc_d3_{h}"}), on=["stadium_id", "hr"], how="left")
    x["pc_d1_max3"] = x[["pc_d1", "pc_d1_1", "pc_d1_2"]].max(axis=1)
    x["pc_d3_max3"] = x[["pc_d3", "pc_d3_1", "pc_d3_2"]].max(axis=1)
    print(f"games 2024-25: {len(x)}; with issued d1 precip {x.pc_d1.notna().sum()}, d3 {x.pc_d3.notna().sum()}")
    sw = pd.read_parquet(CACHE / "stadium_weather_hourly.parquet", columns=["stadium_id", "ts", "fc_d1_mph", "fc_d3_mph"])
    for c in ("fc_d1_mph", "fc_d3_mph"):
        sw[c] = pd.to_numeric(sw[c].astype(str), errors="coerce")   # stored as Decimal
    chk = x.merge(sw.rename(columns={"ts": "hr"}), on=["stadium_id", "hr"], how="inner")
    if len(chk):
        print(f"issued wind cross-check vs stadium_weather_hourly: n={len(chk)}, "
              f"mean |d1 diff| {np.nanmean(abs(chk.wc_d1 - chk.fc_d1_mph)):.2f} mph, "
              f"mean |d3 diff| {np.nanmean(abs(chk.wc_d3 - chk.fc_d3_mph)):.2f} mph")
    pr = {L: prices(L, set(x.game_id)) for L in (3, 24)}
    for L, p in pr.items():
        print(f"T-{L}h priced games: {len(p)} of {len(x)} (>= 2 bettable books, quote within 12h of the decision)")
    dec = {"D1@T-3h": ("pc_d1", "wc_d1", 3), "D3@T-24h": ("pc_d3", "wc_d3", 24),
           "D3@T-3h": ("pc_d3", "wc_d3", 3)}

    def priced(sub, L):
        s = sub.drop(columns=[c for c in ("bline", "bprice", "n_books", "n_at_line") if c in sub])
        s = s.merge(pr[L], on="game_id", how="inner")
        s["under"] = (s.total < s.bline).astype(int)
        s["push"] = (s.total == s.bline).astype(int)
        return s

    out = x[x.outdoor]
    ind = x[x.indoor]
    grid, fitpick = [], []
    for dname, (pc, wc, L) in dec.items():
        for thr in (0.1, 0.2, 0.5, 1.0):
            sel = out[(out[pc] > thr) & (out[wc] < 11)]
            s = priced(sel, L)
            for lab, ss in [("2024", s[s.season == 2024]), ("2025", s[s.season == 2025]), ("2024-25", s)]:
                r = grade(ss, f"{dname} thr>{thr} {lab}", price="bprice",
                          n_seasons=1 if lab != "2024-25" else 2)
                grid.append(r)
                if lab == "2024":
                    fitpick.append((dname, thr, r))
            if thr == 0.2:
                key = "H3 issued D1@T-3h 0.2 2024-25" if dname == "D1@T-3h" else (
                    "H4 issued D3@T-24h 0.2 2024-25" if dname == "D3@T-24h" else None)
                if key:
                    primary[key] = grade(s, key, price="bprice", n_seasons=2)
        heavy = priced(out[(out[pc + "_max3"] >= 2.5) & (out[wc] < 11)], L)
        grid.append(grade(heavy, f"{dname} heavy max3h>=2.5 2024-25", price="bprice", n_seasons=2))
    table(grid, "2a ISSUED-FORECAST RULE, outdoor, issued wind < 11, under at BEST BETTABLE price")
    ok = [(d, t, r) for d, t, r in fitpick if r["bets"] >= 5]
    if ok:
        d, t, r = max(ok, key=lambda z: z[2]["roi%"])
        pc, wc, L = dec[d]
        s = priced(out[(out[pc] > t) & (out[wc] < 11)], L)
        res = grade(s[s.season == 2025], f"FIT cell {d} thr>{t}: 2025 read once", price="bprice", n_seasons=1)
        primary["H5 issued FIT cell 2025"] = res
        table([r, res], f"2b FIT on 2024 (best 2024 ROI with >= 5 bets): {d} thr>{t}")
    else:
        print("2b no 2024 cell has >= 5 bets: FIT cell not defined, H5 not tested")
    rows = []
    for dname, (pc, wc, L) in dec.items():
        rows.append(grade(priced(out[(out[pc] == 0) & (out[wc] < 11)], L),
                          f"{dname} control outdoor calm & dry", price="bprice", n_seasons=2))
        rows.append(grade(priced(out, L), f"{dname} every outdoor game", price="bprice", n_seasons=2))
        rows.append(grade(priced(ind, L), f"{dname} every indoor game", price="bprice", n_seasons=2))
        rows.append(grade(priced(ind[(ind[pc] > 0.2) & (ind[wc] < 11)], L),
                          f"{dname} PLACEBO indoor, forecast rain at dome", price="bprice", n_seasons=2))
    table(rows, "2c CONTROLS and PLACEBO at the same best bettable price, 2024-25")
    # how well does the forecast find the ERA5 truth flag
    t = out[out.era5_precip.notna() & out.pc_d1.notna()]
    tf = (t.era5_precip > 0.2) & (t.era5_wind < 11)
    for pc, wc in (("pc_d1", "wc_d1"), ("pc_d3", "wc_d3")):
        ff = (t[pc] > 0.2) & (t[wc] < 11)
        print(f"2d {pc}>0.2 & {wc}<11 vs ERA5 truth flag, outdoor 2024-25: truth {tf.sum()}, forecast {ff.sum()}, "
              f"both {(tf & ff).sum()} (recall {(tf & ff).sum()/max(tf.sum(),1):.2f}, "
              f"precision {(tf & ff).sum()/max(ff.sum(),1):.2f})")
    # heat, bettable
    rows = []
    for thr in (80, 85, 90):
        rows.append(grade(priced(out[out.tc_d1 >= thr], 3), f"issued d1 temp >= {thr}F @T-3h", price="bprice",
                          n_seasons=2))
        rows.append(grade(priced(out[out.tc_d3 >= thr], 24), f"issued d3 temp >= {thr}F @T-24h", price="bprice",
                          n_seasons=2))
    table(rows, "3e HEAT, bettable 2024-25: issued kickoff temperature, best bettable under price")


# ─── part 3 ────────────────────────────────────────────────────────────────

def part3(g, primary):
    print("\n" + "=" * 100 + "\nPART 3  HEAT UNDERS")
    o = g[g.outdoor]
    print("outdoor games with nflverse temp / text-filled temp by era:",
          {f"{a}-{b}": (int(era(o, a, b).temp.notna().sum()), int(era(o, a, b).temp_f.notna().sum()),
                        len(era(o, a, b))) for a, b in [(1999, 2012), (2013, 2025), (2022, 2022)]})
    rows = [grade(era(o, 2003, 2021)[lambda d: d.temp >= 85], "AS STATED 2003-2021 nflverse temp >= 85 "
                  "(published 64-49-1)", n_seasons=19),
            grade(era(o, 2003, 2021)[lambda d: d.temp_f >= 85], "  same, text-filled temp", n_seasons=19),
            grade(era(o, 2022, 2025)[lambda d: d.temp >= 85], "OUT 2022-2025 post-publication", n_seasons=4),
            grade(era(o, 2022, 2025)[lambda d: d.temp_f >= 85], "  same, text-filled temp", n_seasons=4),
            grade(era(o, 1999, 2002)[lambda d: d.temp >= 85], "OUT 1999-2002 pre-sample", n_seasons=4)]
    table(rows, "3a PUBLISHED HEAT RULE as stated: outdoor, kickoff temp >= 85F, under at -110, no wind filter")
    primary["H6 heat>=85 2022-25"] = rows[2]
    primary["H7 heat>=85 1999-2002"] = rows[4]
    # The published record is 114 games; which population it used is not stated. Every
    # reading is graded (declared before any outcome), so none is picked for its result.
    v = era(o, 2003, 2021)
    rows = [grade(v[(v.temp >= 85)], "outdoors+open, all game types", n_seasons=19),
            grade(v[(v.temp >= 85) & (v.game_type == "REG")], "outdoors+open, regular season", n_seasons=19),
            grade(v[(v.temp >= 85) & (v.roof == "outdoors")], "outdoors only, all game types", n_seasons=19),
            grade(v[(v.temp >= 85) & (v.roof == "outdoors") & (v.game_type == "REG")],
                  "outdoors only, regular season", n_seasons=19)]
    table(rows, "3a' AS STATED 2003-2021, population readings (published: 114 games, 64-49-1)")
    for col, lab in (("temp", "nflverse temp"), ("temp_f", "text-filled temp")):
        rows = []
        for thr in (80, 85, 90):
            for a, b in [(1999, 2012), (2013, 2025), (1999, 2025)]:
                rr = grade(era(o, a, b)[lambda d: d[col] >= thr], f"temp>={thr} {a}-{b}", n_seasons=b - a + 1)
                rows.append(rr)
                if col == "temp" and (a, b) != (1999, 2025):
                    primary.setdefault("_grid", []).append(rr)
        table(rows, f"3b HEAT GRID ({lab}), -110, every cell")
    rows = [grade(o[(o.temp_f >= 85) & (o.season == s)], str(s), n_seasons=1) for s in range(1999, 2026)]
    table(rows, "3c HEAT >= 85 (text-filled temp) by season")
    rows = []
    for a, b in [(1999, 2012), (2013, 2025)]:
        x = era(o, a, b)
        hot = x[x.temp >= 85]
        gi = g[g.indoor & g.season.between(a, b)]
        rows.append(grade(x[x.temp.between(60, 79)], f"{a}-{b} control outdoor 60-79F", n_seasons=b - a + 1))
        rows.append(grade(gi[gi.gameday.isin(set(hot.gameday))], f"{a}-{b} P1 indoor, same dates", n_seasons=b - a + 1))
        gie = gi[gi.era5_temp.notna()]
        rows.append(grade(gie[gie.era5_temp >= 85], f"{a}-{b} P2 indoor, ERA5 >= 85F AT THE DOME",
                          n_seasons=b - a + 1))
        rows.append(grade(x[(x.temp >= 85) & (x.wind_f < 12)], f"{a}-{b} hot AND calm (<12)", n_seasons=b - a + 1))
    table(rows, "3d HEAT controls and placebos, -110")


# ─── part 4 ────────────────────────────────────────────────────────────────

def ols(y, X):
    X = np.column_stack([np.ones(len(y)), X])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    s2 = res @ res / max(len(y) - X.shape[1], 1)
    cov = s2 * np.linalg.inv(X.T @ X)
    return beta[1], np.sqrt(cov[1, 1])


def baseline(g):
    """Mean of the two teams' leave-one-out season-average closing totals."""
    long = pd.concat([g[["game_id", "season", "home_team", "total_line"]].rename(columns={"home_team": "team"}),
                      g[["game_id", "season", "away_team", "total_line"]].rename(columns={"away_team": "team"})])
    agg = long.groupby(["season", "team"]).total_line.agg(["sum", "count"]).reset_index()
    out = g[["game_id", "season", "home_team", "away_team", "total_line"]].copy()
    for side in ("home", "away"):
        out = out.merge(agg.rename(columns={"team": f"{side}_team", "sum": f"s_{side}", "count": f"n_{side}"}),
                        on=["season", f"{side}_team"], how="left")
        out[f"b_{side}"] = (out[f"s_{side}"] - out.total_line) / (out[f"n_{side}"] - 1)
    out["base"] = (out.b_home + out.b_away) / 2
    return out[["game_id", "base"]]


def part4(g, primary):
    print("\n" + "=" * 100 + "\nPART 4  HAS THE TOTALS MARKET LEARNED WIND?")
    g = g.merge(baseline(g[g.game_type.notna()]), on="game_id", how="left")
    for wcol, scale, s0 in (("wind_f", "nflverse wind (text-filled, <=40)", 2006),
                            ("era5_wind", "ERA5 kickoff wind", 2000)):
        o = g[g.outdoor & g[wcol].notna() & g.season.between(s0, 2025) & g.base.notna()].copy()
        rows = []
        for s, x in o.groupby("season"):
            bm, sm = ols(x.total_line.values, np.column_stack([x[wcol], x.week]))
            br, sr = ols(x.total.values.astype(float), np.column_stack([x[wcol], x.week]))
            bm2, sm2 = ols((x.total_line - x.base).values, x[wcol].values[:, None])
            br2, sr2 = ols((x.total - x.base).values, x[wcol].values[:, None])
            rows.append({"season": s, "n": len(x), "mkt_slope": round(bm, 3), "se": round(sm, 3),
                         "real_slope": round(br, 3), "se_r": round(sr, 3),
                         "share": round(bm / br, 2) if br < -sr else np.nan,   # undefined unless real < -1 SE
                         "mkt_vs_base": round(bm2, 3), "real_vs_base": round(br2, 3)})
        t = pd.DataFrame(rows)
        print(f"\n4a SEASON SLOPES, points of total per mph, {scale}, outdoor "
              "(mkt = closing total_line ~ wind + week; real = actual total ~ wind + week; "
              "vs_base = minus the team-pair baseline, ~ wind)")
        print(t.to_string(index=False))
        wts = 1 / t.se.values ** 2
        X = np.column_stack([np.ones(len(t)), t.season.values])
        W = np.diag(wts)
        beta = np.linalg.solve(X.T @ W @ X, X.T @ W @ t.mkt_slope.values)
        res = t.mkt_slope.values - X @ beta
        dof = len(t) - 2
        s2 = (res @ W @ res) / dof
        cov = s2 * np.linalg.inv(X.T @ W @ X)
        z = beta[1] / np.sqrt(cov[1, 1])
        from math import erf, sqrt
        p2 = 2 * (1 - 0.5 * (1 + erf(abs(z) / sqrt(2))))
        print(f"   trend in market slope: {beta[1]:+.4f} points/mph per season (SE {np.sqrt(cov[1,1]):.4f}, "
              f"z {z:+.2f}, two-sided p {p2:.3f}); negative = the market cutting more per mph over time")
        if wcol == "wind_f":
            primary["H8 market wind slope trend"] = {"cell": "H8", "bets": len(o), "roi%": np.nan,
                                                     "p_roi<=0": p2, "note": f"trend {beta[1]:+.4f}/season"}
        # pooled eras, season-demeaned, game bootstrap of the share
        rows = []
        rng = np.random.default_rng(GRID_SEED)
        eras = [(2000, 2005), (2006, 2010), (2011, 2015), (2016, 2020), (2021, 2025)]
        for a, b in eras:
            x = era(o, a, b)
            if len(x) < 50:
                continue
            ym = (x.total_line - x.groupby("season").total_line.transform("mean")).values
            yr = (x.total - x.groupby("season").total.transform("mean")).values.astype(float)
            wv = (x[wcol] - x.groupby("season")[wcol].transform("mean")).values
            wk = (x.week - x.groupby("season").week.transform("mean")).values
            bm, sm = ols(ym, np.column_stack([wv, wk]))
            br, sr = ols(yr, np.column_stack([wv, wk]))
            sh = []
            n = len(x)
            for _ in range(1000):
                i = rng.integers(0, n, n)
                b1, _ = ols(ym[i], np.column_stack([wv[i], wk[i]]))
                b2, _ = ols(yr[i], np.column_stack([wv[i], wk[i]]))
                sh.append(b1 / b2 if b2 < 0 else np.nan)
            sh = np.array(sh)
            lo, hi = np.nanquantile(sh, [0.05, 0.95])
            hiw = x[wcol] >= (12 if wcol == "wind_f" else 11)
            low = x[wcol] < 8
            ok = br < -sr                     # a share only where realised slope is < -1 SE
            rows.append({"era": f"{a}-{b}", "n": n, "mkt_slope": round(bm, 3), "se_m": round(sm, 3),
                         "real_slope": round(br, 3), "se_r": round(sr, 3),
                         "share": round(bm / br, 2) if ok else np.nan,
                         "share_ci90": f"[{lo:.2f}, {hi:.2f}]" if ok else "undefined",
                         "n_windy": int(hiw.sum()),
                         "line_gap_windy_minus_calm": round(x[hiw].total_line.mean() - x[low].total_line.mean(), 2),
                         "real_gap": round(x[hiw].total.mean() - x[low].total.mean(), 2),
                         "under%_windy": round(100 * x[hiw & (x.push == 0)].under.mean(), 1)})
        print(f"\n4b POOLED BY ERA ({scale}), season-demeaned; share = mkt/real slope, game bootstrap 90%; "
              f"gaps: windy = {'>=12' if wcol == 'wind_f' else '>=11'} mph vs calm < 8")
        print(pd.DataFrame(rows).to_string(index=False))


# ─── main ──────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true", help="classifier/coverage audit only, no outcomes")
    ap.add_argument("--smoke", action="store_true",
                    help="code test: totals shuffled within season, so no real outcome is read")
    ap.add_argument("--reproduce", action="store_true", help="step 1a only (the fit era)")
    a = ap.parse_args()
    g = load()
    if a.audit:
        audit(g)
        return 0
    if a.smoke:
        rng = np.random.default_rng(1)
        g["total"] = g.groupby("season").total.transform(lambda s: rng.permutation(s.values))
        g["under"] = (g.total < g.total_line).astype(int)
        g["push"] = (g.total == g.total_line).astype(int)
        print("SMOKE RUN: totals shuffled within season; every number below is noise")
    primary = {}
    if a.reproduce:
        reproduce(g)
        return 0
    part1(g, primary)
    part2(g, primary)
    part3(g, primary)
    part4(g, primary)
    print("\n" + "=" * 100 + "\nMULTIPLE TESTING")
    grid = primary.pop("_grid", [])
    keys = list(primary)
    pv = [primary[k]["p_roi<=0"] for k in keys]
    adj, rej = bh(pv)
    rows = [{"hypothesis": k, "bets": primary[k]["bets"], "roi%": primary[k].get("roi%"),
             "ci90": primary[k].get("ci90", ""), "p": round(p, 3), "bh_adj": round(q, 3),
             "reject@0.10": bool(r)} for k, p, q, r in zip(keys, pv, adj, rej)]
    print(f"PRIMARY family, {len(keys)} hypotheses, Benjamini-Hochberg q=0.10 (H8 two-sided, others one-sided)")
    print(pd.DataFrame(rows).to_string(index=False))
    if grid:
        gp = [r["p_roi<=0"] for r in grid]
        gadj, grej = bh(gp)
        print(f"GRID family (rain hold-out 16 cells + heat nflverse-temp era cells 6) = {len(grid)} cells: "
              f"smallest raw p {np.nanmin(gp):.3f}, smallest BH-adjusted {np.nanmin(gadj):.3f}, "
              f"cells surviving q=0.10: {int(np.nansum(grej))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
