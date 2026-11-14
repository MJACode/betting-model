"""Blind favourite / underdog at the BestFightOdds open, the favourite defined
by the OPEN price itself (no look-ahead to the close)."""
import numpy as np
from ml_base import load, units, ci
M = load()
fav_a = M.p_open >= 0.5
for side in ("fav", "dog"):
    take_a = fav_a if side == "fav" else ~fav_a
    price = np.where(take_a, M.a_open, M.b_open); won = np.where(take_a, M.a_won, ~M.a_won)
    u, r = units(price, won); lo, hi = ci(u, r)
    print(f"blind {side} @ open: {len(u)} bets {u.sum():+.1f}u ret {100*u.sum()/r.sum():+.2f}% [{lo:+.1f},{hi:+.1f}]")
