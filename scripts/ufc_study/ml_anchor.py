"""Market-anchored moneyline model, walk-forward by year.

logit P(A wins) = logit(no-vig market) + b . z, the market log-odds an
unpenalised offset, z the A-minus-B feature differences (standardised on the
training years), b ridge-penalised. Decided at a fixed moment (the open, or the
close) and graded at that moment's price. Also the information test: does b.z
add anything the market lacks, out of sample (Brier and log loss vs market).
"""
import sys
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from ml_base import load, units, dec, novig, ci

pd.set_option("display.width", 250)
M = load()
F = pd.read_parquet("fights.parquet").set_index("game_id")
M = M.join(F[[c for c in F.columns if c not in M.columns]], on="game_id")

DIFFS = ["elo", "n", "days_off", "win_rate", "fin_rate", "ko_win", "sub_win", "ko_loss", "dec_rate",
         "slpm", "sapm", "td15", "kd15", "sub15", "avg_mins", "age", "reach", "height", "streak"]
for f in DIFFS:
    M[f"d_{f}"] = pd.to_numeric(M[f"a_{f}"], errors="coerce") - pd.to_numeric(M[f"b_{f}"], errors="coerce")
M["d_debut"] = (M.a_n == 0).astype(int) - (M.b_n == 0).astype(int)
Z = [f"d_{f}" for f in DIFFS] + ["d_debut"]
for z in Z:
    M[z] = M[z].astype(float)


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def fit(X, off, y, lam):
    def nll(b):
        s = off + X @ b
        return np.sum(np.logaddexp(0, s) - y * s) + lam * np.sum(b ** 2)
    def grad(b):
        s = off + X @ b
        p = 1 / (1 + np.exp(-s))
        return X.T @ (p - y) + 2 * lam * b
    return minimize(nll, np.zeros(X.shape[1]), jac=grad, method="L-BFGS-B").x


def prep(df, mu, sd):
    X = ((df[Z] - mu) / sd).fillna(0.0).to_numpy()
    return X


def walk(moment, lam, first_year=2014, min_n=0):
    pcol = "p_open" if moment == "open" else "p_close"
    out = []
    for Y in range(first_year, 2027):
        tr = M[(M.year < Y) & (M.a_n >= min_n) & (M.b_n >= min_n)]
        te = M[(M.year == Y) & (M.a_n >= min_n) & (M.b_n >= min_n)].copy()
        if len(te) == 0:
            continue
        mu, sd = tr[Z].mean(), tr[Z].std().replace(0, 1)
        b = fit(prep(tr, mu, sd), logit(tr[pcol].to_numpy()), tr.a_won.to_numpy(float), lam)
        te["p_model"] = 1 / (1 + np.exp(-(logit(te[pcol].to_numpy()) + prep(te, mu, sd) @ b)))
        out.append(te)
    return pd.concat(out)


def grade(T, moment, cut, floor=-300, price_kind="worst"):
    if moment == "open":
        pa, pb = T.a_open, T.b_open
    elif price_kind == "worst":
        pa, pb = T.a_close_lo, T.b_close_lo
    elif price_kind == "best":
        pa, pb = T.a_close_hi, T.b_close_hi
    else:
        pa, pb = T.a_close_mid, T.b_close_mid
    ev_a = T.p_model * dec(pa) - 1
    ev_b = (1 - T.p_model) * dec(pb) - 1
    take_a = ev_a >= ev_b
    ev = np.where(take_a, ev_a, ev_b)
    price = np.where(take_a, pa, pb)
    won = np.where(take_a, T.a_won, ~T.a_won)
    sel = (ev >= cut) & (price >= floor)
    u, r = units(price[sel], won[sel])
    return sel, u, r, price[sel], T.year.to_numpy()[sel], T.date.to_numpy()[sel]


def report(T, moment, cuts, price_kind="worst"):
    y = T.a_won.astype(float)
    pc = "p_open" if moment == "open" else "p_close"
    for col in (pc, "p_model"):
        p = T[col].clip(1e-4, 1 - 1e-4)
        print(f"   {col:8} logloss {-(y*np.log(p)+(1-y)*np.log(1-p)).mean():.5f} brier {((p-y)**2).mean():.5f}")
    for cut in cuts:
        sel, u, r, price, yrs, dates = grade(T, moment, cut, price_kind=price_kind)
        if len(u) < 10:
            print(f"   EV>={cut:.2f}: {len(u)} bets"); continue
        lo, hi = ci(u, r)
        dates = pd.to_datetime(dates).astype("int64"); half = np.median(dates)
        early = dates <= half
        by = pd.Series(u).groupby(yrs).sum() / pd.Series(r).groupby(yrs).sum() * 100
        pos = (by > 0).sum()
        print(f"   EV>={cut:.2f}: {len(u):5d} bets {u.sum():+7.1f}u ret {100*u.sum()/r.sum():+6.2f}% "
              f"[{lo:+.1f},{hi:+.1f}] early {100*u[early].sum()/r[early].sum():+.1f}% "
              f"late {100*u[~early].sum()/r[~early].sum():+.1f}% years+ {pos}/{len(by)} "
              f"dogs {np.mean(price>0):.0%} medprice {np.median(price):+.0f}")


if __name__ == "__main__":
    for moment in ("close", "open"):
        for lam in (1.0, 30.0, 300.0):
            T = walk(moment, lam)
            print(f"== decided at {moment}, ridge {lam}, {len(T)} fights 2014-2026")
            report(T, moment, (0.0, 0.03, 0.06, 0.10), price_kind="worst" if moment == "close" else "open")
