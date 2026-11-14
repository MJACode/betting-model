"""Placebo for the open-anchored model: keep each year's fitted coefficients,
but give every fight a donor fight's model opinion (b.z permuted within the
year). If the donors earn what the real opinions earn, the result is the open's
shape, not the ratings. 50 permutations, ridge 30, EV >= 0.06."""
import numpy as np, pandas as pd
import ml_anchor as A
from ml_base import dec, units
rng = np.random.default_rng(7)
M = A.M
parts = []
for Y in range(2014, 2027):
    tr, te = M[M.year < Y], M[M.year == Y].copy()
    mu, sd = tr[A.Z].mean(), tr[A.Z].std().replace(0, 1)
    b = A.fit(A.prep(tr, mu, sd), A.logit(tr.p_open.to_numpy()), tr.a_won.to_numpy(float), 30.0)
    te["xb"] = A.prep(te, mu, sd) @ b
    parts.append(te)
T = pd.concat(parts)
def ret(xb, cut=0.06):
    pm = 1/(1+np.exp(-(A.logit(T.p_open.to_numpy()) + xb)))
    ea = pm*dec(T.a_open)-1; eb = (1-pm)*dec(T.b_open)-1
    ta = ea >= eb; ev = np.where(ta, ea, eb); price = np.where(ta, T.a_open, T.b_open)
    won = np.where(ta, T.a_won, ~T.a_won); s = (ev >= cut) & (price >= -300)
    u, r = units(price[s], won[s]); return s.sum(), 100*u.sum()/r.sum()
n, real = ret(T.xb.to_numpy())
plac = []
yrs = T.year.to_numpy()
for _ in range(50):
    xb = T.xb.to_numpy().copy()
    for y in np.unique(yrs):
        i = np.where(yrs == y)[0]; xb[i] = xb[rng.permutation(i)]
    plac.append(ret(xb))
pn = np.array([p[0] for p in plac]); pr = np.array([p[1] for p in plac])
print(f"real: {n} bets {real:+.2f}%   placebo: bets median {np.median(pn):.0f}, return median {np.median(pr):+.2f}% "
      f"p95 {np.percentile(pr,95):+.2f}% max {pr.max():+.2f}%")
