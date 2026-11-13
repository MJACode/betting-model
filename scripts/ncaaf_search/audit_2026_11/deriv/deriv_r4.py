"""R4 (first half against the full game, walk-forward) and the two follow-ups the baseline raised.

R4, fixed before it was run: for test season S, from seasons before S only,
    first-half margin  = a * (-full-game middle spread)            + leftover
    first-half total   = b * full-game middle total + c            + leftover
with a, b, c by least squares and the leftovers kept as they fell (no shape assumed). A first-half
quote's chance of winning and of pushing is the share of leftovers that clear its line. Bet when the
expected return per unit risked is above the cut; one bet a game and market; no price shorter than
-200 (moneyline) / -125 (spread, total). Test seasons: 2024 (fitted on 2023), 2025 (on 2023-2024).

The follow-ups are NOT pre-registered: they come from the baseline's side table, so they are read as
questions to carry forward, never as results.
    F1  the under on the away underdog's team total, at the best line then price
    F2  the first-half moneyline favourite at the best price
"""
import sys

import numpy as np
import pandas as pd

import deriv_lab as lab
from deriv_lab import BETTABLE, D, summ
from deriv_rules import show, tag_sides


def fit_tables(G, season):
    tr = G[(G.season < season) & G.h1m.notna() & G.fg_spread.notna() & G.fg_total.notna()]
    x = -tr.fg_spread.to_numpy(float)
    a = float((x * tr.h1m).sum() / (x * x).sum())
    A = np.c_[tr.fg_total.to_numpy(float), np.ones(len(tr))]
    b, c = np.linalg.lstsq(A, tr.h1t.to_numpy(float), rcond=None)[0]
    return dict(a=a, b=float(b), c=float(c), rm=np.sort((tr.h1m - a * x).to_numpy(float)),
                rt=np.sort((tr.h1t - (b * tr.fg_total + c)).to_numpy(float)), n=len(tr))


def tail(sorted_res, thr):
    """Share of leftovers above thr, and the share within a hair of it (a push)."""
    hi = np.searchsorted(sorted_res, thr + 1e-9, side="right")
    lo = np.searchsorted(sorted_res, thr - 1e-9, side="left")
    n = len(sorted_res)
    return (n - hi) / n, (hi - lo) / n


def r4(L):
    G = L.drop_duplicates(["canon", "slot"])[["canon", "slot", "season", "h1m", "h1t", "fg_spread", "fg_total"]]
    G = G[G.slot == "am"]
    X = L[L.market.isin(["h2h_h1", "spreads_h1", "totals_h1"]) & L.bookmaker.isin(BETTABLE)
          & L.fg_spread.notna() & L.fg_total.notna() & (L.fg_n >= 4) & L.season.isin([2024, 2025])].copy()
    pw, pp = np.full(len(X), np.nan), np.full(len(X), np.nan)
    info = []
    for s in (2024, 2025):
        t = fit_tables(G, s)
        info.append(dict(season=s, fitted_on=t["n"], margin_slope=round(t["a"], 4), total_slope=round(t["b"], 4),
                         total_const=round(t["c"], 3)))
        m = (X.season == s).to_numpy()
        mu_m = (t["a"] * -X.fg_spread).to_numpy(float)
        mu_t = (t["b"] * X.fg_total + t["c"]).to_numpy(float)
        mk, side, line = X.market.to_numpy(), X.side.to_numpy(), X.line.to_numpy(float)
        for i in np.flatnonzero(m):
            if mk[i] == "h2h_h1":
                w, p = tail(t["rm"], -mu_m[i])                    # home leads at the half
                if side[i] == "away":
                    w = 1 - w - p
            elif mk[i] == "spreads_h1":
                # home covers when margin + spread_home > 0; an away row's line is -spread_home
                sh = line[i] if side[i] == "home" else -line[i]
                w, p = tail(t["rm"], -sh - mu_m[i])
                if side[i] == "away":
                    w = 1 - w - p
            else:
                w, p = tail(t["rt"], line[i] - mu_t[i])            # over
                if side[i] == "under":
                    w = 1 - w - p
            pw[i], pp[i] = w, p
    X["pw"], X["pp"] = pw, pp
    X["ev"] = (X.pw * X.win - (1 - X.pw - X.pp) * X.risk) / X.risk
    X["edge"] = X.ev
    print("\n== R4 fits (earlier seasons only)")
    print(pd.DataFrame(info).to_string(index=False))
    # is the fitted chance any good? (spread and total rows, pushes out)
    c = X[(X.slot == "am") & X.res.notna() & (X.res != 0) & X.market.isin(["spreads_h1", "totals_h1"])].copy()
    c["p"] = c.pw / (1 - c.pp)
    c["bin"] = pd.cut(c.p, [0, .40, .45, .48, .52, .55, .60, 1])
    print("\n== R4 fitted chance against how often the quote won (first-half spread and total, game-day read)")
    print(c.groupby("bin", observed=True).agg(quotes=("res", "size"), fitted=("p", "mean"),
                                              won=("res", lambda s: (s > 0).mean())).round(4).to_string())
    rows = []
    for mk in ("h2h_h1", "spreads_h1", "totals_h1"):
        floor = -200 if mk == "h2h_h1" else lab.MIN_PRICE
        for slot in ("am", "pm"):
            x = X[(X.market == mk) & (X.slot == slot) & (X.price >= floor)]
            for cut in (0.0, 0.02, 0.04, 0.06, 0.08, 0.12):
                rows.append(dict(market=mk, read=slot, cut=cut, **summ(lab.one_per_game(x[x.ev > cut]), "R4")))
    show(rows, "R4 first half priced from the full game: best quote a game, expected return above the cut")
    rows = []
    for mk in ("h2h_h1", "spreads_h1", "totals_h1"):
        floor = -200 if mk == "h2h_h1" else lab.MIN_PRICE
        x = X[(X.market == mk) & (X.slot == "am") & (X.price >= floor)]
        b = lab.one_per_game(x[x.ev > 0.04])
        keys = ["side"] if mk == "totals_h1" else ["role", "team"]
        for k, xx in b.groupby(keys):
            k = k if isinstance(k, tuple) else (k,)
            rows.append(dict(market=mk, split=" ".join(map(str, k)), **summ(xx, "")))
    show(rows, "R4 at the 0.04 cut, game-day read: who it backs")


def followups(L):
    T = L[L.market.isin(["team_totals_home", "team_totals_away"]) & L.bookmaker.isin(BETTABLE) & L.main
          & (L.price >= lab.MIN_PRICE) & L.role.isin(["fav", "dog"])].copy()
    # best line for the side, then best price
    T["edge"] = np.where(T.side == "over", -T.line, T.line) + T.dec / 1000
    rows = []
    for slot in ("am", "pm"):
        for team in ("away", "home"):
            for role in ("dog", "fav"):
                for side in ("under", "over"):
                    x = T[(T.slot == slot) & (T.team == team) & (T.role == role) & (T.side == side)]
                    b = lab.one_per_game(x)
                    rows.append(dict(read=slot, team=team, role=role, side=side, **summ(b, "F1")))
    show(rows, "F1 team totals at the best line then price, one bet a team: all eight corners (not pre-registered)")
    x = T[(T.slot == "am") & (T.team == "away") & (T.role == "dog") & (T.side == "under")]
    b = lab.one_per_game(x).copy()
    b["dog_by"] = pd.cut(b.fg_spread.abs(), [0, 3, 7, 14, 21, 80])
    rows = [dict(split=f"underdog by {k}", **summ(xx, "")) for k, xx in b.groupby("dog_by", observed=True)]
    b["tt"] = pd.cut(b.line, [0, 13.5, 17.5, 21.5, 27.5, 80])
    rows += [dict(split=f"team total {k}", **summ(xx, "")) for k, xx in b.groupby("tt", observed=True)]
    rows += [dict(split="book " + k, **summ(xx, "")) for k, xx in b.groupby("bookmaker")]
    show(rows, "F1 away underdog under, game-day read: by size of underdog, by line, by book")

    M = L[(L.market == "h2h_h1") & L.bookmaker.isin(BETTABLE) & L.role.isin(["fav", "dog"])].copy()
    M["edge"] = M.dec
    rows = []
    for slot in ("am", "pm"):
        for role in ("fav", "dog"):
            for team in ("home", "away"):
                b = lab.one_per_game(M[(M.slot == slot) & (M.role == role) & (M.team == team)])
                rows.append(dict(read=slot, role=role, team=team, **summ(b, "F2")))
    show(rows, "F2 first-half moneyline at the best price, one bet a game and side (not pre-registered)")
    b = lab.one_per_game(M[(M.slot == "am") & (M.role == "fav")]).copy()
    b["px"] = pd.cut(b.price, [-100000, -500, -300, -200, -150, -100, 1000])
    show([dict(split=f"favourite priced {k}", **summ(xx, "")) for k, xx in b.groupby("px", observed=True)],
         "F2 favourites, game-day read, by price")


def main():
    which = sys.argv[1:] or ["r4", "f"]
    L = tag_sides(lab.load())
    if "r4" in which:
        r4(L)
    if "f" in which:
        followups(L)


if __name__ == "__main__":
    main()
