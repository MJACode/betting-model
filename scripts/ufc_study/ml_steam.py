"""Scouted lead: big line moves are under-reacted to even at the close. Bet the
side the line moved toward (no-vig open -> no-vig close), at the WORST closing
price, by size of move; early/late and years positive."""
import numpy as np, pandas as pd
from ml_base import load, units, ci
M = load()
mv = M.p_close - M.p_open                 # toward A when positive
take_a = mv > 0
price = np.where(take_a, M.a_close_lo, M.b_close_lo)
won = np.where(take_a, M.a_won, ~M.a_won)
size = np.abs(mv)
half = M.date.median(); early = (M.date <= half).to_numpy()
for lo_, hi_ in ((0.0, 0.05), (0.05, 0.10), (0.10, 0.15), (0.15, 1.0), (0.10, 1.0)):
    s = (size >= lo_) & (size < hi_) & (price >= -300)
    u, r = units(price[s], won[s]); a, b = ci(u, r)
    by = pd.Series(u).groupby(M.year.to_numpy()[s]).sum() / pd.Series(r).groupby(M.year.to_numpy()[s]).sum()
    print(f"move {lo_:.2f}-{hi_:.2f}: {s.sum():5d} bets ret {100*u.sum()/r.sum():+6.2f}% [{a:+.1f},{b:+.1f}] "
          f"early {100*u[early[s]].sum()/r[early[s]].sum():+.1f}% late {100*u[~early[s]].sum()/r[~early[s]].sum():+.1f}% "
          f"years+ {(by>0).sum()}/{len(by)} dogs {np.mean(price[s]>0):.0%}")
