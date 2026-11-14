"""Invention 3: is the favourite priced the same in five-round fights as in
three-round ones? Blind favourite and underdog at the middle of the closing
range and at the open, split by scheduled rounds."""
import numpy as np, pandas as pd
from ml_base import load, units, ci
M = load()
F = pd.read_parquet("fights.parquet").set_index("game_id")
M = M.join(F[["sched"]], on="game_id", rsuffix="_f")
for sched in (3, 5):
    T = M[M.sched == sched]
    for when, pa, pb, pcol in (("open", "a_open", "b_open", "p_open"), ("close mid", "a_close_mid", "b_close_mid", "p_close")):
        fav = T[pcol] >= 0.5
        for side in ("fav", "dog"):
            ta = fav if side == "fav" else ~fav
            price = np.where(ta, T[pa], T[pb]); won = np.where(ta, T.a_won, ~T.a_won)
            u, r = units(price, won); lo, hi = ci(u, r)
            print(f"{sched} rounds {when:9} {side}: {len(u):5d} bets ret {100*u.sum()/r.sum():+6.2f}% [{lo:+.1f},{hi:+.1f}]")
