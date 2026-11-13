"""Kill tests for the Pinnacle-anchored opening-price rule on the bought
history (feed_open.py, rule B): the rating model on Pinnacle's no-vig price,
the best decidable price in the same pull, the first pull that clears locks
the fight, at least MIN_LEAD hours before the start, -300 floor.

Prints: the cut neighbourhood, by year, by lead band of the locking pull,
by price band, the side split, without the ten best dates, a donor-opinion
placebo (50 permutations within the year), and the decision restricted to
the daily pulls only (the live path sees more pulls than the backtest, so a
first-come lock fires earlier live; this shows whether that matters)."""
import sys

import numpy as np
import pandas as pd

exec(open(__import__("pathlib").Path(__file__).with_name("feed_open.py"), encoding="utf-8")
     .read().split('print("\\n== A.')[0])

MIN_LEAD = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0
rng = np.random.default_rng(11)
P = H2[H2.book == "pinnacle"][["game_id", "served_at", "pa", "pb"]].rename(columns={"pa": "qa", "pb": "qb"})
S = H2[H2.book.isin(DECIDABLE) & (H2.lead_h >= MIN_LEAD)]
J0 = S.merge(P, on=["game_id", "served_at"])
anchor = novig(J0.qa, J0.qb)


def lock(J, xb, cut, stages=None):
    pm = 1 / (1 + np.exp(-(A.logit(np.clip(anchor, 1e-6, 1 - 1e-6)) + xb)))
    ea, eb = pm * dec(J.pa) - 1, (1 - pm) * dec(J.pb) - 1
    ta = ea >= eb
    K = J.assign(ta=ta, ev=np.where(ta, ea, eb), price=np.where(ta, J.pa, J.pb))
    if stages is not None:
        K = K[K.stage.isin(stages)]
    K = K[(K.ev >= cut) & (K.price >= FLOOR)]
    return K.sort_values(["served_at", "ev"], ascending=[True, False]).groupby("game_id").head(1)


def grade(K):
    won = np.where(K.ta, K.a_won, ~K.a_won.astype(bool))
    u, r = units(K.price.to_numpy(), won)
    return u, r


xb = J0.xb.to_numpy()
print(f"min lead {MIN_LEAD}h; pulls joined {len(J0):,}")
print("\n-- neighbourhood")
for cut in (0.00, 0.02, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10, 0.12, 0.15):
    K = lock(J0, xb, cut)
    report(f"EV>={cut:.2f}", K, K.ta.to_numpy(), K.price.to_numpy())

CUT = 0.06
K = lock(J0, xb, CUT)
u, r = grade(K)
K = K.assign(u=u, r=r)
print(f"\n-- EV>={CUT}: by year")
g = K.groupby("year").agg(n=("u", "size"), units=("u", "sum"), risk=("r", "sum"))
g["ret%"] = 100 * g.units / g.risk
print(g.round(2).to_string())
print("\n-- by lead of the locking pull (days)")
K["lead_d"] = pd.cut(K.lead_h / 24, [0, 1, 3, 7, 14, 30, 400])
g = K.groupby("lead_d", observed=True).agg(n=("u", "size"), units=("u", "sum"), risk=("r", "sum"))
g["ret%"] = 100 * g.units / g.risk
print(g.round(2).to_string())
print("\n-- by price band")
K["band"] = pd.cut(K.price, [-301, -200, -130, 100, 150, 250, 400, 5000])
g = K.groupby("band", observed=True).agg(n=("u", "size"), units=("u", "sum"), risk=("r", "sum"))
g["ret%"] = 100 * g.units / g.risk
print(g.round(2).to_string())
print(f"\n-- price range: median {K.price.median():+.0f}, shortest {K.price.min():+.0f}, "
      f"share shorter than -200 {np.mean(K.price < -200):.1%}; dogs {np.mean(K.price > 0):.0%}")
print("-- books named:", K.book.value_counts().to_dict())
best = K.groupby(K.date.astype(str)).u.sum().nlargest(10).index
W = K[~K.date.astype(str).isin(best)]
print(f"-- without the ten best dates: {len(W)} bets {W.u.sum():+.1f}u {100*W.u.sum()/W.r.sum():+.2f}%")

print("\n-- donor-opinion placebo, 50 permutations of the opinion within each year")
real = 100 * u.sum() / r.sum()
years = J0.year.to_numpy()
fight_xb = J0.groupby("game_id").xb.first()
fight_year = J0.groupby("game_id").year.first()
out = []
for _ in range(50):
    perm = fight_xb.copy()
    for y in fight_year.unique():
        ids = fight_year.index[fight_year == y]
        perm[ids] = rng.permutation(fight_xb[ids].to_numpy())
    Kp = lock(J0, J0.game_id.map(perm).to_numpy(), CUT)
    up, rp = grade(Kp)
    out.append((len(up), 100 * up.sum() / rp.sum()))
pr = np.array([o[1] for o in out])
print(f"real {real:+.2f}% on {len(u)} bets; placebo median {np.median(pr):+.2f}% "
      f"(bets {np.median([o[0] for o in out]):.0f}), p95 {np.percentile(pr, 95):+.2f}%, max {pr.max():+.2f}%")

print("\n-- daily pulls only (no card-day pulls)")
for cut in (0.03, 0.06, 0.10):
    Kd = lock(J0, xb, cut, stages=["daily"])
    report(f"daily only EV>={cut:.2f}", Kd, Kd.ta.to_numpy(), Kd.price.to_numpy())
