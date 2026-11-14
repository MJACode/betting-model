"""Five-round underdogs: at the worst and best closing price, by price band,
early/late, by year, and title fights against non-title main events."""
import numpy as np, pandas as pd
from ml_base import load, units, ci
M = load()
F = pd.read_parquet("fights.parquet").set_index("game_id")
M = M.join(F[["sched", "title"]], on="game_id", rsuffix="_f")
T = M[M.sched == 5].copy()
fav = T.p_close >= 0.5
for kind, pa, pb in (("worst", "a_close_lo", "b_close_lo"), ("mid", "a_close_mid", "b_close_mid"), ("best", "a_close_hi", "b_close_hi")):
    price = np.where(fav, T[pb], T[pa]); won = np.where(fav, ~T.a_won, T.a_won)
    u, r = units(price, won); lo, hi = ci(u, r)
    half = T.date.median(); e = (T.date <= half).to_numpy()
    print(f"5-round dog @ close {kind:5}: {len(u)} ret {100*u.sum()/r.sum():+.2f}% [{lo:+.1f},{hi:+.1f}] early {100*u[e].sum()/r[e].sum():+.1f}% late {100*u[~e].sum()/r[~e].sum():+.1f}%")
    if kind == "worst":
        band = pd.cut(price, [100, 150, 250, 400, 5000])
        d = pd.DataFrame(dict(b=band, u=u, r=r, y=T.year.to_numpy(), t=T.title.to_numpy()))
        g = d.groupby("b", observed=True).agg(n=("u","size"), u=("u","sum"), r=("r","sum")); g["ret"] = 100*g.u/g.r; print(g.round(2))
        g = d.groupby("t").agg(n=("u","size"), u=("u","sum"), r=("r","sum")); g["ret"] = 100*g.u/g.r; print("by title flag\n", g.round(2))
        g = d.groupby("y").agg(n=("u","size"), u=("u","sum"), r=("r","sum")); g["ret"] = 100*g.u/g.r
        print("years positive", (g.ret > 0).sum(), "of", len(g)); print(g.ret.round(1).to_dict())
