"""R4b: R4 again with the first-half table fitted on every earlier season back to 2015.

Fixed before it was run (2026-11-11, after R4's first-half spread read +6.7% on 301 bets at one cut
on a table fitted on 711 and 1,419 games):

  TRAINING  every scored game of a season before S that has a half-time score (h1_scores.py over the
            play-by-play pulled for 2015-2025) and CFBD's closing spread and total. The full-game
            number in training is that close; in the test it is the middle of the ten books at the
            minute of the quote.
  FIT       first-half margin = a * (-spread) + leftover; first-half total = b * total + c + leftover.
  LEFTOVERS two forms, both reported: POOLED (one set), and BY SIZE (three sets by |spread| <= 7,
            7 to 17, over 17 for the margin; by total <= 48, 48 to 58, over 58 for the total).
  TEST      2023, 2024 and 2025 quotes at the deciding books, same cuts and price floors as R4.
"""
import sys

import numpy as np
import pandas as pd

import deriv_lab as lab
from deriv_lab import BETTABLE, D, summ
from deriv_r4 import tail
from deriv_rules import show, tag_sides

M_EDGES = [0, 7, 17, 200]
T_EDGES = [0, 48, 58, 200]


def train_frame():
    g = pd.read_parquet(D / "g.parquet")
    g = g[g.twin_of.isna() & g.margin.notna() & g.close_spread.notna() & g.close_total.notna()]
    h = pd.read_parquet(D / "h1_scores.parquet")[["game_id", "h1_home", "h1_away"]]
    t = g.merge(h, on="game_id", how="inner")
    t["h1m"] = t.h1_home - t.h1_away
    t["h1t"] = t.h1_home + t.h1_away
    t["x"] = -t.close_spread
    return t[["game_id", "season", "x", "close_total", "h1m", "h1t"]]


def fit(T, season, by_size):
    tr = T[T.season < season]
    x = tr.x.to_numpy(float)
    a = float((x * tr.h1m).sum() / (x * x).sum())
    A = np.c_[tr.close_total.to_numpy(float), np.ones(len(tr))]
    b, c = np.linalg.lstsq(A, tr.h1t.to_numpy(float), rcond=None)[0]
    rm = (tr.h1m - a * x).to_numpy(float)
    rt = (tr.h1t - (b * tr.close_total + c)).to_numpy(float)
    if by_size:
        mb = np.digitize(np.abs(x), M_EDGES[1:-1], right=True)
        tb = np.digitize(tr.close_total.to_numpy(float), T_EDGES[1:-1], right=True)
        RM = [np.sort(rm[mb == k]) for k in range(3)]
        RT = [np.sort(rt[tb == k]) for k in range(3)]
    else:
        RM, RT = [np.sort(rm)] * 3, [np.sort(rt)] * 3
    return dict(a=a, b=float(b), c=float(c), RM=RM, RT=RT, n=len(tr), seasons=tr.season.nunique(),
                sizes=[len(r) for r in RM])


def price(L, T, by_size):
    X = L[L.market.isin(["h2h_h1", "spreads_h1", "totals_h1"]) & L.bookmaker.isin(BETTABLE)
          & L.fg_spread.notna() & L.fg_total.notna() & (L.fg_n >= 4)].copy()
    pw, pp = np.full(len(X), np.nan), np.full(len(X), np.nan)
    info = []
    mk, side, line = X.market.to_numpy(), X.side.to_numpy(), X.line.to_numpy(float)
    fs, ft = X.fg_spread.to_numpy(float), X.fg_total.to_numpy(float)
    for s in (2023, 2024, 2025):
        if (T.season < s).sum() < 500:        # no table without earlier seasons to fit it on
            continue
        t = fit(T, s, by_size)
        info.append(dict(season=s, fitted_on=t["n"], seasons=t["seasons"], margin_slope=round(t["a"], 4),
                         total_slope=round(t["b"], 4), total_const=round(t["c"], 3), by_size=str(t["sizes"])))
        mb = np.digitize(np.abs(fs), M_EDGES[1:-1], right=True)
        tb = np.digitize(ft, T_EDGES[1:-1], right=True)
        for i in np.flatnonzero((X.season == s).to_numpy()):
            mu_m, mu_t = t["a"] * -fs[i], t["b"] * ft[i] + t["c"]
            if mk[i] == "h2h_h1":
                w, p = tail(t["RM"][mb[i]], -mu_m)
                if side[i] == "away":
                    w = 1 - w - p
            elif mk[i] == "spreads_h1":
                sh = line[i] if side[i] == "home" else -line[i]
                w, p = tail(t["RM"][mb[i]], -sh - mu_m)
                if side[i] == "away":
                    w = 1 - w - p
            else:
                w, p = tail(t["RT"][tb[i]], line[i] - mu_t)
                if side[i] == "under":
                    w = 1 - w - p
            pw[i], pp[i] = w, p
    X["pw"], X["pp"] = pw, pp
    X["ev"] = (X.pw * X.win - (1 - X.pw - X.pp) * X.risk) / X.risk
    X["edge"] = X.ev
    return X, pd.DataFrame(info)


def price_kernel(L, T):
    """R4c: the same means, with the repo's margin-distribution kernel in place of the leftovers
    (models/ncaab_margin_dist: results of earlier games whose mean was near this one's, key numbers
    as history has them). Fixed with R4b, before either was run on the longer table."""
    sys.path.insert(0, str(lab.Path(__file__).resolve().parents[4]))
    from models import ncaab_margin_dist as md

    X = L[L.market.isin(["h2h_h1", "spreads_h1", "totals_h1"]) & L.bookmaker.isin(BETTABLE)
          & L.fg_spread.notna() & L.fg_total.notna() & (L.fg_n >= 4)].copy()
    X["pw"], X["pp"] = np.nan, np.nan
    info = []
    SH = 27
    for s in (2023, 2024, 2025):
        tr = T[T.season < s]
        if len(tr) < 500:
            continue
        x = tr.x.to_numpy(float)
        a = float((x * tr.h1m).sum() / (x * x).sum())
        A = np.c_[tr.close_total.to_numpy(float), np.ones(len(tr))]
        b, c = np.linalg.lstsq(A, tr.h1t.to_numpy(float), rcond=None)[0]
        Tm = md.fit(tr.h1m.astype(int).to_numpy(), a * x)
        Tt = md.fit((tr.h1t.astype(int) - SH).to_numpy(), (b * tr.close_total + c - SH).to_numpy(float))
        info.append(dict(season=s, fitted_on=len(tr), seasons=tr.season.nunique(), margin_slope=round(a, 4),
                         total_slope=round(float(b), 4), total_const=round(float(c), 3)))
        m = X.season == s
        mu_m = (a * -X.fg_spread).to_numpy(float)
        mu_t = (b * X.fg_total + c - SH).to_numpy(float)
        # the margin the home side must beat
        thr = np.where(X.market == "h2h_h1", 0.0, np.where(X.side == "home", -X.line, X.line))
        is_m = (X.market != "totals_h1").to_numpy()
        pw_m, pp_m, pl_m = md.probs(mu_m, np.where(is_m, thr, 0.0), Tm)
        pw_t, pp_t, pl_t = md.probs(mu_t, np.where(is_m, 0.0, X.line.to_numpy(float) - SH), Tt)
        first = np.where(is_m, X.side == "home", X.side == "over")
        w = np.where(is_m, np.where(first, pw_m, pl_m), np.where(first, pw_t, pl_t))
        p = np.where(is_m, pp_m, pp_t)
        X.loc[m, "pw"] = w[m.to_numpy()]
        X.loc[m, "pp"] = p[m.to_numpy()]
    X["ev"] = (X.pw * X.win - (1 - X.pw - X.pp) * X.risk) / X.risk
    X["edge"] = X.ev
    return X[X.pw.notna()], pd.DataFrame(info)


def report(X, info, name):
    print(f"\n== {name}: fits (earlier seasons only)")
    print(info.to_string(index=False))
    c = X[(X.slot == "am") & X.res.notna() & (X.res != 0) & X.market.isin(["spreads_h1", "totals_h1"])].copy()
    c["p"] = c.pw / (1 - c.pp)
    c["bin"] = pd.cut(c.p, [0, .40, .45, .48, .52, .55, .60, 1])
    print(f"\n== {name}: fitted chance against how often the quote won (first-half spread and total, game-day read)")
    print(c.groupby(["market", "bin"], observed=True).agg(quotes=("res", "size"), fitted=("p", "mean"),
                                                        won=("res", lambda s: (s > 0).mean())).round(4).to_string())
    rows = []
    for mk in ("h2h_h1", "spreads_h1", "totals_h1"):
        floor = -200 if mk == "h2h_h1" else lab.MIN_PRICE
        for slot in ("am", "pm"):
            x = X[(X.market == mk) & (X.slot == slot) & (X.price >= floor)]
            for cut in (0.0, 0.02, 0.04, 0.06, 0.08, 0.12):
                rows.append(dict(market=mk, read=slot, cut=cut, **summ(lab.one_per_game(x[x.ev > cut]), name)))
    show(rows, f"{name}: best quote a game, expected return above the cut")
    rows = []
    for mk in ("spreads_h1", "totals_h1"):
        for slot in ("am", "pm"):
            x = X[(X.market == mk) & (X.slot == slot) & (X.price >= lab.MIN_PRICE)]
            b = lab.one_per_game(x[x.ev > 0.04])
            keys = ["side"] if mk == "totals_h1" else ["role", "team"]
            for k, xx in b.groupby(keys):
                k = k if isinstance(k, tuple) else (k,)
                rows.append(dict(market=mk, read=slot, split=" ".join(map(str, k)), **summ(xx, "")))
    show(rows, f"{name} at the 0.04 cut: who it backs")


def main():
    T = train_frame()
    print("training games by season:\n", T.groupby("season").size().to_string())
    L = tag_sides(lab.load(verbose=False))
    for by_size, name in ((False, "R4b pooled"), (True, "R4b by size")):
        X, info = price(L, T, by_size)
        report(X[X.pw.notna()], info, name)
    X, info = price_kernel(L, T)
    report(X, info, "R4c kernel")


if __name__ == "__main__":
    main()
