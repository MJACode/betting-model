"""The totals rule in its LIVE shape, per random seed: first morning DraftKings read (5 days out to
game day) at which |model - DraftKings total| >= gate, bet at DraftKings' line and price. 2023-2025."""
from pathlib import Path

import numpy as np
import pandas as pd

import lab
from lab import D, dec, stake

RNG = np.random.default_rng(11)
S = pd.read_parquet(D / "totals_seeds.parquet").rename(columns={"_game_id": "game_id"})
seeds = [c for c in S.columns if c.startswith("p")]
g = pd.read_parquet(D / "g.parquet")
_, q = lab.load()
q = q[(q.bookmaker == "draftkings") & q.total_line.notna() & q.over_price.notna() & q.under_price.notna()
      & q.slot.isin([f"D{k}_AM" for k in range(6)])].copy()
q["canon"] = q.game_id.map(g.set_index("game_id").twin_of).fillna(q.game_id)
q = q[q.canon.isin(set(S.game_id))]
q["k"] = q.slot.str.slice(1, 2).astype(int)
q = q.sort_values(["canon", "k"], ascending=[True, False]).drop_duplicates(["canon", "k"])
P = S.set_index("game_id")
print("games:", q.canon.nunique())


def first_cross(col, gate=8.0):
    x = q.assign(pred=q.canon.map(P[col]))
    x["d"] = x.pred - x.total_line
    hit = x[x.d.abs() >= gate].drop_duplicates("canon")          # sorted k desc: earliest read first
    over = hit.d > 0
    res = np.sign(np.where(over, hit.total - hit.total_line, hit.total_line - hit.total))
    price = np.where(over, hit.over_price, hit.under_price)
    risk, win = stake(dec(price))
    pnl = np.where(res > 0, win, np.where(res < 0, -risk, 0.0))
    rk = np.where(res != 0, risk, 0.0)
    return hit.assign(res=res, pnl=pnl, rk=rk, over=over)


print("\nseed  gate 8: bets  W-L   units   ROI    | by season units | overs")
rows = []
for c in seeds:
    for gate in (7.0, 8.0, 9.0, 10.0):
        h = first_cross(c, gate)
        w, l = int((h.res > 0).sum()), int((h.res < 0).sum())
        rows.append(dict(seed=c, gate=gate, bets=len(h), w=w, l=l, units=h.pnl.sum(), roi=100 * h.pnl.sum() / h.rk.sum(),
                         s23=h[h.season == 2023].pnl.sum(), s24=h[h.season == 2024].pnl.sum(), s25=h[h.season == 2025].pnl.sum(),
                         overs=int(h.over.sum())))
R = pd.DataFrame(rows)
pd.set_option("display.width", 200)
for gate in (7.0, 8.0, 9.0, 10.0):
    x = R[R.gate == gate]
    print(f"\n-- gate {gate} --")
    print(x.drop(columns="gate").round(2).to_string(index=False))
    one = x[x.seed != "pavg"]
    print(f"   single seeds: ROI min {one.roi.min():+.1f}%  median {one.roi.median():+.1f}%  max {one.roi.max():+.1f}%  | units min {one.units.min():+.1f} max {one.units.max():+.1f}"
          f" | seeds with all three seasons positive: {int(((one.s23>0)&(one.s24>0)&(one.s25>0)).sum())} of {len(one)}")
# interval for the seed-average model at gate 8
h = first_cross("pavg", 8.0)
by = h.groupby("et_date").agg(p=("pnl", "sum"), r=("rk", "sum"))
idx = RNG.integers(0, len(by), size=(4000, len(by)))
boot = by.p.to_numpy()[idx].sum(1) / by.r.to_numpy()[idx].sum(1)
print("\nseed-average model, gate 8: ROI 95% interval by date", np.percentile(boot, [2.5, 97.5]).round(3) * 100,
      "| share of resamples above zero:", round(float((boot > 0).mean()), 3))
mid = {s: x.et_date.sort_values().iloc[len(x) // 2] for s, x in h.groupby("season")}
early = h[h.et_date < h.season.map(mid)]
late = h[h.et_date >= h.season.map(mid)]
print(f"early half of each season: {len(early)} bets {early.pnl.sum():+.1f}u {100*early.pnl.sum()/early.rk.sum():+.1f}% | late half: {len(late)} bets {late.pnl.sum():+.1f}u {100*late.pnl.sum()/late.rk.sum():+.1f}%")
print("overs:", int(h.over.sum()), f"{h[h.over].pnl.sum():+.1f}u", "| unders:", int((~h.over).sum()), f"{h[~h.over].pnl.sum():+.1f}u")
