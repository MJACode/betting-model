"""Women's totals, part C: the cut. Compact tables only.

1. Each priced season graded with the blend fitted on the OTHER priced season
   (2025-26 from 2024-25 is walk-forward; 2024-25 from 2025-26 is not), pooled,
   by cut, with a 95% interval resampled by date.
2. The blend as it would run live in 2026-27 (fitted on both seasons): the
   same grid, by season (in sample for its three numbers).
3. Claimed against realised win rate, by claimed band.
4. Splits at the chosen neighbourhood: side, phase, how long the first post
   stood, how far ahead of the tip it was posted.
"""
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401
import models.ncaab_total_blend as nb  # noqa: E402

RNG = np.random.default_rng(20261109)
CUTS = (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.10)

x = pd.read_parquet(CACHE / "totals_scored_input.parquet")
x["phase"] = [nb.phase_of(v) for v in x["game_date"]]


def blends(tr):
    out = {"all": nb.fit_blend(tr)}
    for ph in nb.PHASES:
        out[ph] = nb.fit_blend(tr[tr["phase"] == ph])
    return out


def score(te, bl):
    rows = []
    for r in te.itertuples(index=False):
        b = bl.get(r.phase) or bl["all"]
        pz = nb.price(r.pt, r.line, r.over_price, r.under_price, b)
        rows.append((pz.side, pz.price, pz.edge, pz.prob))
    out = te.copy()
    out[["side", "price", "edge", "prob"]] = pd.DataFrame(rows, index=out.index)
    dd = out["price"].map(nb.dec)
    out["risk"] = np.minimum(1.0 / (dd - 1.0), 3.0)
    res = np.where(out["side"] == "over", out["total"] - out["line"], out["line"] - out["total"])
    out["units"] = np.where(res > 0, out["risk"] * (dd - 1.0), np.where(res < 0, -out["risk"], 0.0))
    out["won"] = np.where(res > 0, 1.0, np.where(res < 0, 0.0, np.nan))
    out["clv"] = np.where(out["side"] == "over", out["cons_close"] - out["line"], out["line"] - out["cons_close"])
    return out


def line_of(b, label):
    if not len(b):
        return f"  {label:30s} 0 bets"
    ud = b.groupby("game_date")["units"].sum().values
    rd = b.groupby("game_date")["risk"].sum().values
    idx = RNG.integers(0, len(ud), size=(3000, len(ud)))
    lo, hi = np.percentile(ud[idx].sum(axis=1) / rd[idx].sum(axis=1) * 100, [2.5, 97.5])
    w = int((b["won"] == 1).sum()); l = int((b["won"] == 0).sum())
    return (f"  {label:30s} {len(b):4d} bets {w}-{l}  {b['units'].sum():+7.2f}u {b['units'].sum() / b['risk'].sum() * 100:+6.2f}% "
            f"[{lo:+5.1f}, {hi:+5.1f}]  overs {int((b['side'] == 'over').sum()):3d}  close {b['clv'].mean():+.2f}")


s25, s26, s27 = (x[x["season"] == s] for s in (2025, 2026, 2027))
a = score(s26, blends(s25)); b = score(s25, blends(s26))
loso = pd.concat([a, b])
print("1. EACH SEASON ON THE OTHER SEASON'S BLEND, pooled (2025-26 walk-forward, 2024-25 not)")
for c in CUTS:
    print(line_of(loso[loso["edge"] > c], f"edge > {c:.2f}"))
print("   by season at each cut (bets, units): " + " | ".join(
    f"{c:.2f}: 25-26 {int((a['edge'] > c).sum())} {a[a['edge'] > c]['units'].sum():+.1f}, "
    f"24-25 {int((b['edge'] > c).sum())} {b[b['edge'] > c]['units'].sum():+.1f}" for c in (0.03, 0.05, 0.08)))

live = blends(pd.concat([s25, s26]))
print("\n2. THE LIVE BLEND (fitted on both seasons): " + ", ".join(
    f"{k} c {v['c']:+.2f} beta {v['beta']:.3f} sigma {v['sigma']:.2f} n {v['n']}" for k, v in live.items() if v))
both = score(pd.concat([s25, s26]), live)
for c in CUTS:
    z = both[both["edge"] > c]
    print(line_of(z, f"edge > {c:.2f}") + "  | " + " ".join(
        f"{s}: {len(zz)} {zz['units'].sum():+.1f}" for s, zz in z.groupby("season")))
w27 = score(s27, live)
print("   2026-27 to date on it: " + " | ".join(
    f"> {c:.2f}: {int((w27['edge'] > c).sum())} bets {w27[w27['edge'] > c]['units'].sum():+.2f}u" for c in (0.03, 0.05, 0.08)))
print(f"   share of priced games bet: " + ", ".join(f"> {c:.2f}: {(both['edge'] > c).mean():.1%}" for c in CUTS))

print("\n3. CLAIMED AGAINST REALISED (each season on the other's blend; every scored game)")
bands = [(0.0, 0.52), (0.52, 0.55), (0.55, 0.58), (0.58, 0.62), (0.62, 0.70), (0.70, 1.0)]
for lo, hi in bands:
    z = loso[(loso["prob"] >= lo) & (loso["prob"] < hi) & loso["won"].notna()]
    if len(z):
        print(f"  claimed {lo:.2f}-{hi:.2f}: n {len(z):4d}  claimed {z['prob'].mean():.3f}  won {z['won'].mean():.3f}")
z = both[both["won"].notna()]
print("  the live blend, in sample: " + " ".join(
    f"[{lo:.2f}-{hi:.2f}: n {int(((z['prob'] >= lo) & (z['prob'] < hi)).sum())} claimed "
    f"{z[(z['prob'] >= lo) & (z['prob'] < hi)]['prob'].mean():.3f} won {z[(z['prob'] >= lo) & (z['prob'] < hi)]['won'].mean():.3f}]"
    for lo, hi in bands if ((z['prob'] >= lo) & (z['prob'] < hi)).sum()))

print("\n4. SPLITS, the live blend, edge > 0.04 and > 0.06 (both seasons)")
for c in (0.04, 0.06):
    z = both[both["edge"] > c]
    for label, m in (("overs", z["side"] == "over"), ("unders", z["side"] == "under"),
                     ("November", z["phase"] == "Nov"), ("December on", z["phase"] != "Nov"),
                     ("first post stood 10+ min", z["stood_min"].fillna(1e9) >= 10),
                     ("stood under 10 min", z["stood_min"].fillna(1e9) < 10),
                     ("posted 6+ h before tip", z["lead_h"] >= 6), ("posted under 6 h before", z["lead_h"] < 6),
                     ("price -110 or better", z["price"] >= -110), ("price worse than -110", z["price"] < -110)):
        print(line_of(z[m], f"> {c:.2f} {label}"))
print(f"\nprices bet at edge > 0.04 (live blend): {both[both['edge'] > 0.04]['price'].min():.0f} to "
      f"{both[both['edge'] > 0.04]['price'].max():.0f}; EV min "
      f"{(both[both['edge'] > 0.04]['prob'] * both[both['edge'] > 0.04]['price'].map(nb.dec) - 1).min():.4f}")
both.to_parquet(CACHE / "totals_live_blend_scored.parquet", index=False)
