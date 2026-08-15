"""
Does the CLOSING line have exploitable bias in identifiable subsets?

This is a different question from "can we predict the close". The oracle
analysis bounded prediction strategies. This asks whether the market's final
number is itself wrong in ways that repeat.

Method
------
For every candidate subset, compute the ATS record against the closing spread
(and O/U record against the closing total). Test against the -110 breakeven of
52.38%, not against 50%. Report a binomial p-value and apply a Benjamini-
Hochberg false-discovery correction, because scanning dozens of subsets will
manufacture 'significant' results by construction.

Also splits every subset into a discovery era and a holdout era, because a
bias that existed in 2003 and died in 2012 is worthless.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

BREAKEVEN = 0.5238   # -110
HOLDOUT_FROM = 2016  # bias must survive here to be actionable


def load():
    g = pd.read_csv("data/raw/games.csv")
    g = g.dropna(subset=["spread_line", "result", "total_line", "total"]).copy()
    g = g[g.season <= 2025]

    g["margin"] = g.result                      # home - away
    # ATS vs closing spread (spread_line positive = home favored)
    g["home_cover"] = np.where(g.margin > g.spread_line, 1.0,
                        np.where(g.margin < g.spread_line, 0.0, np.nan))
    g["over_hit"] = np.where(g.total > g.total_line, 1.0,
                      np.where(g.total < g.total_line, 0.0, np.nan))

    g["fav_home"] = g.spread_line > 0
    g["abs_spread"] = g.spread_line.abs()
    g["is_dome"] = g.roof.isin(["dome", "closed"])
    g["rest_diff"] = g.home_rest - g.away_rest
    g["is_div"] = g.div_game == 1
    g["is_playoff"] = g.game_type != "REG"
    g["wind"] = pd.to_numeric(g.wind, errors="coerce")
    g["temp"] = pd.to_numeric(g.temp, errors="coerce")
    g["primetime"] = g.weekday.isin(["Thursday", "Sunday Night", "Monday"]) | \
                     (g.gametime >= "19:00")
    return g


def binom_p(wins, n, p0=BREAKEVEN):
    if n == 0:
        return np.nan
    return stats.binomtest(int(wins), int(n), p0, alternative="two-sided").pvalue


def eval_rule(df, mask, side_col, label, market="ATS"):
    """side_col holds 1 if the bet won, 0 if lost, NaN if push."""
    s = df.loc[mask, side_col].dropna()
    n = len(s)
    if n < 100:
        return None
    w = s.sum()
    wr = w / n
    roi = wr * (100 / 110) - (1 - wr)
    ho = df.loc[mask & (df.season >= HOLDOUT_FROM), side_col].dropna()
    ho_wr = ho.mean() if len(ho) >= 50 else np.nan
    return dict(label=label, market=market, n=n, win_rate=wr, roi=roi,
                p=binom_p(w, n), n_hold=len(ho), hold_wr=ho_wr)


def bh_fdr(pvals, q=0.10):
    p = np.array(pvals, dtype=float)
    ok = ~np.isnan(p)
    idx = np.where(ok)[0]
    order = idx[np.argsort(p[idx])]
    m = len(order)
    keep = np.zeros(len(p), dtype=bool)
    for i, j in enumerate(order, start=1):
        if p[j] <= q * i / m:
            keep[order[:i]] = True
    return keep


def main():
    g = load()
    print(f"games: {len(g)}  seasons {g.season.min()}-{g.season.max()}")
    print(f"breakeven at -110 = {BREAKEVEN:.2%}, holdout era from {HOLDOUT_FROM}\n")

    rules = []

    # ---- baseline sanity ----
    rules.append(("ALL: bet home ATS", g.index.to_series().notna(), "home_cover", "ATS"))
    g["away_cover"] = 1 - g.home_cover
    rules.append(("ALL: bet away ATS", g.index.to_series().notna(), "away_cover", "ATS"))
    g["under_hit"] = 1 - g.over_hit
    rules.append(("ALL: bet over", g.index.to_series().notna(), "over_hit", "OU"))
    rules.append(("ALL: bet under", g.index.to_series().notna(), "under_hit", "OU"))

    # ---- classic dog / favorite biases ----
    rules.append(("Home underdog", ~g.fav_home, "home_cover", "ATS"))
    rules.append(("Home dog >= 3", (~g.fav_home) & (g.abs_spread >= 3), "home_cover", "ATS"))
    rules.append(("Home dog >= 7", (~g.fav_home) & (g.abs_spread >= 7), "home_cover", "ATS"))
    rules.append(("Road underdog", g.fav_home, "away_cover", "ATS"))
    rules.append(("Road dog >= 7", g.fav_home & (g.abs_spread >= 7), "away_cover", "ATS"))
    rules.append(("Big dog >= 10 (any)", g.abs_spread >= 10,
                  np.where(g.fav_home, "away_cover", "home_cover"), "ATS"))
    rules.append(("Big favorite >= 10", g.abs_spread >= 10,
                  np.where(g.fav_home, "home_cover", "away_cover"), "ATS"))
    rules.append(("Small spread <= 3", g.abs_spread <= 3, "home_cover", "ATS"))

    # ---- divisional ----
    rules.append(("Divisional: home", g.is_div, "home_cover", "ATS"))
    rules.append(("Divisional: away", g.is_div, "away_cover", "ATS"))
    rules.append(("Divisional under", g.is_div, "under_hit", "OU"))

    # ---- rest ----
    rules.append(("Home off bye (rest>=12)", g.home_rest >= 12, "home_cover", "ATS"))
    rules.append(("Away off bye (rest>=12)", g.away_rest >= 12, "away_cover", "ATS"))
    rules.append(("Home rest edge >=3", g.rest_diff >= 3, "home_cover", "ATS"))
    rules.append(("Away rest edge >=3", g.rest_diff <= -3, "away_cover", "ATS"))
    rules.append(("Thursday game under", g.weekday == "Thursday", "under_hit", "OU"))

    # ---- weather / venue ----
    rules.append(("Wind >= 15 under", g.wind >= 15, "under_hit", "OU"))
    rules.append(("Wind >= 20 under", g.wind >= 20, "under_hit", "OU"))
    rules.append(("Temp <= 32 under", g.temp <= 32, "under_hit", "OU"))
    rules.append(("Dome over", g.is_dome, "over_hit", "OU"))
    rules.append(("Outdoor under", (~g.is_dome), "under_hit", "OU"))

    # ---- season timing ----
    rules.append(("Week 1-4 home", g.week <= 4, "home_cover", "ATS"))
    rules.append(("Week 1-4 away", g.week <= 4, "away_cover", "ATS"))
    rules.append(("Week 15+ home", g.week >= 15, "home_cover", "ATS"))
    rules.append(("Week 15+ under", g.week >= 15, "under_hit", "OU"))
    rules.append(("Playoffs under", g.is_playoff, "under_hit", "OU"))
    rules.append(("Playoffs home", g.is_playoff, "home_cover", "ATS"))

    # ---- primetime ----
    rules.append(("Primetime under", g.primetime, "under_hit", "OU"))
    rules.append(("Primetime home", g.primetime, "home_cover", "ATS"))

    # ---- key numbers ----
    rules.append(("Spread exactly 3, take dog", g.abs_spread == 3,
                  np.where(g.fav_home, "away_cover", "home_cover"), "ATS"))
    rules.append(("Spread 3.5-6.5, take dog", g.abs_spread.between(3.5, 6.5),
                  np.where(g.fav_home, "away_cover", "home_cover"), "ATS"))

    # ---- totals level ----
    rules.append(("Total >= 50 under", g.total_line >= 50, "under_hit", "OU"))
    rules.append(("Total <= 40 over", g.total_line <= 40, "over_hit", "OU"))

    out = []
    for label, mask, col, mkt in rules:
        if isinstance(col, np.ndarray):
            tmp = g.copy()
            tmp["_dyn"] = np.where(col == "home_cover", g.home_cover, g.away_cover)
            r = eval_rule(tmp, mask, "_dyn", label, mkt)
        else:
            r = eval_rule(g, mask, col, label, mkt)
        if r:
            out.append(r)

    res = pd.DataFrame(out)
    res["sig_fdr10"] = bh_fdr(res.p.values, q=0.10)
    res = res.sort_values("win_rate", ascending=False)

    print(f"{'rule':32s}{'mkt':5s}{'n':>6}{'win%':>8}{'ROI':>8}{'p':>10}"
          f"{'n_hold':>8}{'hold%':>8}  FDR")
    print("-" * 96)
    for r in res.itertuples():
        hw = f"{r.hold_wr:7.2%}" if not np.isnan(r.hold_wr) else "      -"
        print(f"{r.label:32s}{r.market:5s}{r.n:>6d}{r.win_rate:>8.2%}"
              f"{r.roi:>+8.2%}{r.p:>10.4f}{r.n_hold:>8d}{hw}  "
              f"{'YES' if r.sig_fdr10 else ''}")

    res.to_csv("data/processed/bias_scan.csv", index=False)


if __name__ == "__main__":
    main()
