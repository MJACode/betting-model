#!/usr/bin/env python3
"""
Where could a moneyline or non-wind totals edge actually be? Measured, not guessed.

    python scripts/edge_hunt.py                 # all sections
    python scripts/edge_hunt.py --section ml_calib

Sections
  ml_calib   moneyline calibration and favourite-longshot bias, 1999-2025
  ml_spread  does the market's moneyline disagree with its own spread, and does
             the disagreement predict anything
  tot_calib  totals calibration by level: are high or low totals mispriced
  tot_precip precipitation and temperature against the total, wind controlled
  tot_pace   pre-game pace and pass rate against the total

Everything here runs off data already on disk: `data/games.csv` for closing
lines and results, `data/weather_cache` for ERA5. Zero Odds API credits.

READ THIS BEFORE BELIEVING ANY OUTPUT
-------------------------------------
This is a hypothesis scan over many cuts, so some cell will look significant by
construction. Nothing here is a strategy. A cut only graduates to a candidate if
it (a) survives a train/test split in time, (b) has a mechanism that is not
"the market forgot", and (c) still clears the vig once priced at what books
actually quote, which is the step that killed the opener's headline number.
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RNG = np.random.default_rng(20260818)
BREAKEVEN_110 = 0.5238


def _prob(px):
    px = np.asarray(px, dtype=float)
    return np.where(px > 0, 100.0 / (px + 100.0), -px / (-px + 100.0))


def devig_power(px_a, px_b):
    """p_a^k + p_b^k = 1. Correct treatment for longshot prices; see screen_books."""
    a, b = _prob(px_a), _prob(px_b)
    ok = np.isfinite(a) & np.isfinite(b) & (a > 0) & (b > 0)
    out = np.full(a.shape, np.nan)
    lo, hi = np.full(a.shape, 0.2), np.full(a.shape, 5.0)
    for _ in range(60):
        k = (lo + hi) / 2
        s = np.where(ok, a ** k + b ** k, 1.0)
        lo = np.where(s > 1, k, lo)
        hi = np.where(s > 1, hi, k)
    k = (lo + hi) / 2
    np.divide(a ** k, a ** k + b ** k, out=out, where=ok)
    return out


def games() -> pd.DataFrame:
    g = pd.read_csv("data/games.csv")
    g = g[g.result.notna()].copy()
    g["home_win"] = np.select([g.result > 0, g.result == 0], [1.0, 0.5], 0.0)
    return g


def roi_at(win_rate, px):
    dec = np.where(px > 0, 1 + px / 100, 1 + 100 / -px)
    return win_rate * (dec - 1) - (1 - win_rate)


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


# --------------------------------------------------------------------------- #

def sec_ml_calib(a) -> None:
    g = games()
    g = g[g.home_moneyline.notna() & g.away_moneyline.notna()]
    g = g[g.home_win != 0.5]
    print(f"\n=== MONEYLINE CALIBRATION, {int(g.season.min())}-{int(g.season.max())}, "
          f"n={len(g):,} ===")
    g["p_home"] = devig_power(g.home_moneyline.values, g.away_moneyline.values)
    g = g[g.p_home.notna()]

    # Stack both sides so every bet appears once as the side you would back.
    rows = []
    for side, p, px, won in (("home", g.p_home, g.home_moneyline, g.home_win),
                             ("away", 1 - g.p_home, g.away_moneyline, 1 - g.home_win)):
        rows.append(pd.DataFrame(dict(season=g.season.values, side=side,
                                      p=p.values, px=px.values, won=won.values)))
    d = pd.concat(rows, ignore_index=True)

    bins = [0, .10, .20, .30, .40, .50, .60, .70, .80, .90, 1.0]
    d["bucket"] = pd.cut(d.p, bins)
    t = d.groupby("bucket", observed=True).agg(
        n=("won", "size"), fair=("p", "mean"), actual=("won", "mean"),
        mean_px=("px", "median")).reset_index()
    t["diff_pp"] = ((t.actual - t.fair) * 100).round(2)
    t["roi_flat"] = [round(float(roi_at(r.actual, r.mean_px) * 100), 2) for r in t.itertuples()]
    ci = [wilson(r.actual * r.n, r.n) for r in t.itertuples()]
    t["ci95_pp"] = [f"[{(lo - r.fair)*100:+.1f},{(hi - r.fair)*100:+.1f}]"
                    for (lo, hi), r in zip(ci, t.itertuples())]
    t["fair"] = (t.fair * 100).round(2)
    t["actual"] = (t.actual * 100).round(2)
    print(t.to_string(index=False))
    print("\n  `diff_pp` is realised minus de-vigged fair. Positive means that price")
    print("  band wins MORE than the market implies, i.e. it is underpriced.")
    print("  `roi_flat` is what backing every bet in the band would have returned at")
    print("  the actual quoted price. That is the number that has to beat zero.")

    dogs = d[d.p < 0.35]
    favs = d[d.p > 0.65]
    print(f"\n  longshot bias check")
    print(f"    dogs  below 35%: n={len(dogs):,} fair={dogs.p.mean()*100:.2f}% "
          f"actual={dogs.won.mean()*100:.2f}% "
          f"ROI={roi_at(dogs.won.mean(), dogs.px.median())*100:+.2f}%")
    print(f"    favs  above 65%: n={len(favs):,} fair={favs.p.mean()*100:.2f}% "
          f"actual={favs.won.mean()*100:.2f}% "
          f"ROI={roi_at(favs.won.mean(), favs.px.median())*100:+.2f}%")

    print("\n  by era (the market changes; a 1999 edge is not a 2025 edge):")
    for lo, hi in ((1999, 2009), (2010, 2017), (2018, 2025)):
        e = d[d.season.between(lo, hi)]
        ed, ef = e[e.p < 0.35], e[e.p > 0.65]
        print(f"    {lo}-{hi}: dogs n={len(ed):5,} diff={(ed.won.mean()-ed.p.mean())*100:+5.2f}pp"
              f"   favs n={len(ef):5,} diff={(ef.won.mean()-ef.p.mean())*100:+5.2f}pp")


def sec_ml_spread(a) -> None:
    """Is the moneyline consistent with the same book's spread?"""
    g = games()
    g = g[g.home_moneyline.notna() & g.away_moneyline.notna() & g.spread_line.notna()]
    g = g[g.home_win != 0.5]
    g["p_ml"] = devig_power(g.home_moneyline.values, g.away_moneyline.values)
    g = g[g.p_ml.notna()].copy()

    # P(home win) implied by the SPREAD alone, empirically: how often does a home
    # side laying this number actually win outright?
    resid = (g.result - g.spread_line).values
    g["p_spread"] = [float((resid + s > 0).mean() + 0.5 * (resid + s == 0).mean())
                     for s in g.spread_line.values]
    g["gap"] = g.p_ml - g.p_spread

    print(f"\n=== MONEYLINE vs THE MARKET'S OWN SPREAD, n={len(g):,} ===")
    print(f"  mean gap {g.gap.mean()*100:+.3f}pp, sd {g.gap.std()*100:.3f}pp")
    print("  gap > 0: the moneyline rates the home side higher than the spread does.")
    g["bucket"] = pd.qcut(g.gap, 8, duplicates="drop")
    t = g.groupby("bucket", observed=True).agg(
        n=("home_win", "size"), gap=("gap", "mean"),
        p_ml=("p_ml", "mean"), actual=("home_win", "mean"),
        px=("home_moneyline", "median")).reset_index()
    t["vs_ml_pp"] = ((t.actual - t.p_ml) * 100).round(2)
    t["roi_home"] = [round(float(roi_at(r.actual, r.px) * 100), 2) for r in t.itertuples()]
    t["gap"] = (t.gap * 100).round(2)
    t["p_ml"] = (t.p_ml * 100).round(2)
    t["actual"] = (t.actual * 100).round(2)
    print(t[["bucket", "n", "gap", "p_ml", "actual", "vs_ml_pp", "px", "roi_home"]]
          .to_string(index=False))
    print("\n  If the two markets were perfectly consistent the gap would be noise and")
    print("  `vs_ml_pp` would be flat. A monotone pattern means one of the two")
    print("  markets is stale relative to the other, which is tradeable in principle.")


def sec_tot_calib(a) -> None:
    g = games()
    g = g[g.total.notna() & g.total_line.notna()].copy()
    g["under"] = np.select([g.total < g.total_line, g.total == g.total_line], [1.0, 0.5], 0.0)
    d = g[g.under != 0.5]
    print(f"\n=== TOTALS BY LEVEL, {int(d.season.min())}-{int(d.season.max())}, "
          f"n={len(d):,} ===")
    d = d.copy()
    d["bucket"] = pd.cut(d.total_line, [0, 38, 41, 44, 47, 50, 99])
    t = d.groupby("bucket", observed=True).agg(
        n=("under", "size"), under=("under", "mean")).reset_index()
    t["roi110_under"] = (t.under * (100 / 110) - (1 - t.under)).mul(100).round(2)
    ci = [wilson(r.under * r.n, r.n) for r in t.itertuples()]
    t["ci95"] = [f"[{lo*100:.1f},{hi*100:.1f}]" for lo, hi in ci]
    t["under"] = (t.under * 100).round(2)
    print(t.to_string(index=False))

    print("\n  recent only, because scoring levels have moved a lot:")
    r = d[d.season >= 2018]
    t2 = r.groupby(pd.cut(r.total_line, [0, 38, 41, 44, 47, 50, 99]),
                   observed=True).agg(n=("under", "size"), under=("under", "mean")).reset_index()
    t2["roi110_under"] = (t2.under * (100 / 110) - (1 - t2.under)).mul(100).round(2)
    t2["under"] = (t2.under * 100).round(2)
    print(t2.to_string(index=False))


def sec_tot_precip(a) -> None:
    from data_ingest.weather import INDOOR_ROOFS, STADIUM_COORDS, fetch_era5
    from zoneinfo import ZoneInfo

    g = games()
    g = g[(g.season.between(2016, 2025)) & (~g.roof.isin(INDOOR_ROOFS))
          & g.stadium_id.isin(STADIUM_COORDS) & g.total.notna() & g.total_line.notna()].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime, errors="coerce")
    g["kick_utc"] = (dt.dt.tz_localize(ZoneInfo("America/New_York"), ambiguous=True,
                                       nonexistent="shift_forward").dt.tz_convert("UTC"))
    g["hr"] = g.kick_utc.dt.floor("h")

    spans = [("2016-09-01", "2019-02-20"), ("2019-09-01", "2022-02-20"),
             ("2022-09-01", "2024-02-20"), ("2024-09-01", "2026-02-20")]
    frames = []
    print("loading ERA5 (cached) ...", file=sys.stderr)
    for sid in sorted(g.stadium_id.unique()):
        for s, e in spans:
            try:
                frames.append(fetch_era5(sid, s, e))
            except Exception as exc:                          # noqa: BLE001
                print(f"  skip {sid} {s}: {exc}", file=sys.stderr)
    A = pd.concat(frames, ignore_index=True)
    d = g.merge(A, left_on=["stadium_id", "hr"], right_on=["stadium_id", "ts"], how="left")
    d = d.dropna(subset=["era5_wind", "era5_precip"])
    d["under"] = np.select([d.total < d.total_line, d.total == d.total_line], [1.0, 0.5], 0.0)
    d = d[d.under != 0.5]

    print(f"\n=== PRECIPITATION AND TEMPERATURE vs THE TOTAL, n={len(d):,} outdoor ===")
    print(f"  overall outdoor under rate {d.under.mean()*100:.2f}%")

    print("\n  by ERA5 precipitation at kickoff (mm):")
    d["pb"] = pd.cut(d.era5_precip, [-.01, .0001, .2, .5, 1.0, 99])
    t = d.groupby("pb", observed=True).agg(n=("under", "size"), under=("under", "mean"),
                                           wind=("era5_wind", "mean")).reset_index()
    t["roi110"] = (t.under * (100 / 110) - (1 - t.under)).mul(100).round(2)
    t["under"] = (t.under * 100).round(2)
    t["wind"] = t.wind.round(1)
    print(t.to_string(index=False))
    print("  `wind` is the mean wind in that band: rain and wind travel together,")
    print("  so any raw precipitation effect is partly the wind rule in disguise.")

    print("\n  precipitation WITH wind held below the deploy threshold (11 mph):")
    calm = d[d.era5_wind < 11]
    t2 = calm.groupby(pd.cut(calm.era5_precip, [-.01, .0001, .2, .5, 99]),
                      observed=True).agg(n=("under", "size"), under=("under", "mean")).reset_index()
    t2["roi110"] = (t2.under * (100 / 110) - (1 - t2.under)).mul(100).round(2)
    t2["under"] = (t2.under * 100).round(2)
    print(t2.to_string(index=False))

    print("\n  by kickoff temperature (F), wind held below 11:")
    t3 = calm.groupby(pd.cut(calm.era5_temp, [-99, 32, 45, 60, 75, 199]),
                      observed=True).agg(n=("under", "size"), under=("under", "mean")).reset_index()
    t3["roi110"] = (t3.under * (100 / 110) - (1 - t3.under)).mul(100).round(2)
    t3["under"] = (t3.under * 100).round(2)
    print(t3.to_string(index=False))

    print("\n  CONTINUOUS WIND, the dose-response the runbook flags as the next version:")
    d["wb"] = pd.cut(d.era5_wind, [0, 5, 8, 11, 14, 18, 99])
    t4 = d.groupby("wb", observed=True).agg(n=("under", "size"), under=("under", "mean"),
                                            line=("total_line", "mean"),
                                            scored=("total", "mean")).reset_index()
    t4["line_minus_scored"] = (t4.line - t4.scored).round(2)
    t4["under"] = (t4.under * 100).round(2)
    print(t4.to_string(index=False))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", default="all",
                    choices=["ml_calib", "ml_spread", "tot_calib", "tot_precip", "all"])
    a = ap.parse_args()
    run = {"ml_calib": sec_ml_calib, "ml_spread": sec_ml_spread,
           "tot_calib": sec_tot_calib, "tot_precip": sec_tot_precip}
    if a.section == "all":
        for f in run.values():
            f(a)
    else:
        run[a.section](a)
    print("\nNothing above is a strategy. See the header for the bar a cut has to "
          "clear before it becomes one.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
