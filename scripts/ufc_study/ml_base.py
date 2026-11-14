"""Moneyline baselines on the historical BestFightOdds prices (2010-2026).

Price conventions per fighter: open (the first book's opener), close_lo and
close_hi (the lowest and highest closing price across books). Betting a side
at "close_lo" is the WORST closing price on the board, "close_hi" the best.
Stake: 1 unit to win, risk capped at 3."""
import numpy as np
import pandas as pd

pd.set_option("display.width", 250)


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 1 + a / 100, 1 + 100 / -a)


def units(price, won):
    d = dec(price)
    risk = np.minimum(1 / (d - 1), 3.0)
    return np.where(won, risk * (d - 1), -risk), risk


def mid_american(lo, hi):
    """Midpoint in implied probability, back to American."""
    p = (1 / dec(lo) + 1 / dec(hi)) / 2
    return np.where(p >= 0.5, -100 * p / (1 - p), 100 * (1 - p) / p)


def novig(pa, pb):
    ia, ib = 1 / dec(pa), 1 / dec(pb)
    return ia / (ia + ib)


def ci(u, risk, n_boot=2000, seed=0):
    rng = np.random.default_rng(seed)
    u, risk = np.asarray(u), np.asarray(risk)
    idx = rng.integers(0, len(u), (n_boot, len(u)))
    r = u[idx].sum(1) / risk[idx].sum(1)
    return np.percentile(r, [5, 95]) * 100


def load():
    M = pd.read_parquet("ml_hist.parquet")
    M = M[M.result_a.isin(["win", "loss"])].copy()
    M = M[M.a_open.notna() & M.b_open.notna() & M.a_close_lo.notna() & M.b_close_lo.notna()]
    M["a_won"] = M.result_a == "win"
    M["a_close_mid"] = mid_american(M.a_close_lo, M.a_close_hi)
    M["b_close_mid"] = mid_american(M.b_close_lo, M.b_close_hi)
    M["p_open"] = novig(M.a_open, M.b_open)
    M["p_close"] = novig(M.a_close_mid, M.b_close_mid)
    M["year"] = M.date.dt.year
    return M


def table(rows):
    return pd.DataFrame(rows).set_index("rule")


if __name__ == "__main__":
    M = load()
    print("fights", len(M), M.date.min().date(), M.date.max().date())
    y = M.a_won.astype(float)
    for col in ("p_open", "p_close"):
        p = M[col].clip(1e-4, 1 - 1e-4)
        ll = -(y * np.log(p) + (1 - y) * np.log(1 - p)).mean()
        print(f"log loss {col}: {ll:.4f}  brier {((p-y)**2).mean():.4f}")
    rows = []
    for when, pa, pb in (("open", "a_open", "b_open"), ("close worst", "a_close_lo", "b_close_lo"),
                         ("close mid", "a_close_mid", "b_close_mid"), ("close best", "a_close_hi", "b_close_hi")):
        fav_a = M.p_close >= 0.5
        for side in ("fav", "dog"):
            take_a = fav_a if side == "fav" else ~fav_a
            price = np.where(take_a, M[pa], M[pb])
            won = np.where(take_a, M.a_won, ~M.a_won)
            u, r = units(price, won)
            lo, hi = ci(u, r)
            rows.append(dict(rule=f"blind {side} @ {when}", n=len(u), units=u.sum().round(1),
                             ret=round(100 * u.sum() / r.sum(), 2), ci90=f"[{lo:+.1f}, {hi:+.1f}]"))
    print(table(rows))
    # by price band at close mid, favourites
    fav_a = M.p_close >= 0.5
    price = np.where(fav_a, M.a_close_mid, M.b_close_mid)
    won = np.where(fav_a, M.a_won, ~M.a_won)
    band = pd.cut(price, [-5000, -400, -250, -175, -130, -100])
    u, r = units(price, won)
    d = pd.DataFrame(dict(band=band, u=u, r=r))
    s = d.groupby("band", observed=True).agg(n=("u", "size"), units=("u", "sum"), risk=("r", "sum"))
    s["ret"] = 100 * s.units / s.risk
    print("favourites at close mid by band\n", s.round(2))
    dprice = np.where(fav_a, M.b_close_mid, M.a_close_mid)
    band = pd.cut(dprice, [100, 130, 175, 250, 400, 5000])
    u, r = units(dprice, ~won)
    d = pd.DataFrame(dict(band=band, u=u, r=r))
    s = d.groupby("band", observed=True).agg(n=("u", "size"), units=("u", "sum"), risk=("r", "sum"))
    s["ret"] = 100 * s.units / s.risk
    print("underdogs at close mid by band\n", s.round(2))
