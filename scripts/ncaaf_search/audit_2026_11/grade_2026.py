"""2026 season, every scored NCAAF pre-game row graded (BET, AVOID and NONE alike).

The graded-universe matview holds no NCAAF rows (measured 2026-11-10: 0 rows for sport NCAAF),
so this grades from the local copies of `picks` and `games`.
A NONE/AVOID row is the game's LAST pre-kick state (rescored every pass); a BET row is the lock.
"""
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
from paths import CACHE as D, TOTALS_ARTIFACT  # noqa: E402
pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
pd.set_option("display.max_rows", 300)


def dec(a):
    a = np.asarray(a, float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def units(price, res):
    d = dec(price)
    risk = np.minimum(1 / (d - 1), 3.0)
    win = risk * (d - 1)
    pnl = np.where(res > 0, win, np.where(res < 0, -risk, 0.0))
    return pnl, np.where(res != 0, risk, 0.0)


def summ(x, tag):
    if not len(x):
        return f"{tag:<34} 0"
    pnl, risk = units(x.price, x.res)
    w, l, p = int((x.res > 0).sum()), int((x.res < 0).sum()), int((x.res == 0).sum())
    return (f"{tag:<34} {len(x):>4} {w:>3}-{l:<3}-{p} {pnl.sum():>+7.2f}u {100*pnl.sum()/max(risk.sum(),1e-9):>+6.1f}%  "
            f"win {w/max(w+l,1):.3f}")


g = pd.read_parquet(D / "g.parquet")
g = g[g.margin.notna()][["game_id", "margin", "total", "kick", "week"]]
p = pd.read_parquet(D / "ncaaf_picks.parquet")
p = p[(p.game_date >= "2026-08-01")].merge(g, on="game_id", how="inner")
for c in ("model_probability", "dk_odds", "decision_odds", "scored_line", "edge", "decision_edge", "dk_implied_prob"):
    p[c] = pd.to_numeric(p[c], errors="coerce")
p["price"] = p.decision_odds.fillna(p.dk_odds)
p["void"] = p.condition_status.fillna("").isin(["VOID", "DUPLICATE"])
p["month"] = p.game_date.str.slice(0, 7)

# ───────────────────────────── totals ─────────────────────────────
art = pickle.load(open(TOTALS_ARTIFACT, "rb"))
res = np.sort(np.asarray(art["residuals"], float))
print("totals artifact: residuals", len(res), "mean", res.mean().round(3), "gate", art["d_threshold"], "P at gate", art["prob_at_threshold"])


def p_over(d):
    return (res > -d).mean()


grid = np.arange(-30, 30.001, 0.05)
pgrid = np.array([p_over(d) for d in grid])


def d_from_pover(po):
    return np.interp(po, pgrid, grid)          # pgrid is non-decreasing in d


t = p[(p.model_id == "ncaaf_over_under") & p.scored_line.notna() & p.model_probability.notna() & p.price.notna()].copy()
t["po"] = np.where(t.pick_side == "over", t.model_probability, 1 - t.model_probability)
t["d"] = d_from_pover(t.po)
t["res_side"] = np.sign(np.where(t.pick_side == "over", t.total - t.scored_line, t.scored_line - t.total))
t["res"] = t.res_side
# one row per game for the bias read: prefer the BET row, else the over row
one = t.sort_values(["game_id", "signal_type"]).assign(isbet=(t.signal_type == "BET")).sort_values(
    ["game_id", "isbet"], ascending=[True, False]).drop_duplicates("game_id")
print(f"\nTOTALS 2026: completed games with a row: {one.game_id.nunique()}  (BET rows {int((one.signal_type=='BET').sum())}, of which void {int((one.void & (one.signal_type=='BET')).sum())})")
b = one.assign(al=one.total - one.scored_line)
print("mean(model - line) =", round(one.d.mean(), 2), "| mean(actual - line) =", round(b.al.mean(), 2),
      "| games over/under the line:", int((b.al > 0).sum()), int((b.al < 0).sum()))
print(b.groupby("month").agg(games=("d", "size"), model_minus_line=("d", "mean"), actual_minus_line=("al", "mean")).round(2).to_string())
slope = np.polyfit(one.d, b.al, 1)
print("actual-minus-line regressed on model-minus-line: slope", round(slope[0], 3), "intercept", round(slope[1], 2),
      "| corr", round(np.corrcoef(one.d, b.al)[0, 1], 3))

print("\nevery scored game, the side the model leans to, by size of the disagreement (each game's stored row; price = that row's best price):")
lean = t[((t.pick_side == "over") & (t.d > 0)) | ((t.pick_side == "under") & (t.d < 0))].drop_duplicates(["game_id"])
lean = lean.assign(ad=lean.d.abs())
for lo, hi in ((0, 2), (2, 4), (4, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 12), (12, 99)):
    x = lean[(lean.ad >= lo) & (lean.ad < hi)]
    print("  " + summ(x, f"|d| {lo}-{hi}") + "   | over " + summ(x[x.pick_side == 'over'], "")[35:] + " | under " + summ(x[x.pick_side == 'under'], "")[35:])

print("\nthe BETs as placed (lock price), void and duplicate out:")
bets = t[(t.signal_type == "BET") & ~t.void]
print("  " + summ(bets, "all BETs"))
for s in ("over", "under"):
    print("  " + summ(bets[bets.pick_side == s], s))
bets = bets.assign(ad=bets.d.abs())
for lo, hi in ((7.9, 8.5), (8.5, 9), (9, 10), (10, 12), (12, 99)):
    print("  " + summ(bets[(bets.ad >= lo) & (bets.ad < hi)], f"BET |d| {lo}-{hi}"))
v = t[(t.signal_type == "BET") & t.void]
print("  " + summ(v, "voided BETs (graded for reference)"))

print("\nre-centred gate on every scored game (d + shift, gate 8): what a shift in the model's level would have bet")
for sh in (0.0, 0.5, 1.0, 1.5, 2.0, 2.5):
    dd = one.d + sh
    ov = one[dd >= 8].assign(res=np.sign(one.total - one.scored_line)[dd >= 8])
    un = one[dd <= -8].assign(res=np.sign(one.scored_line - one.total)[dd <= -8])
    print(f"  shift {sh:+.1f}: over " + summ(ov, "")[35:] + " | under " + summ(un, "")[35:])

# ───────────────────────────── moneyline (paused) ─────────────────────────────
m = p[(p.model_id == "ncaaf_moneyline") & p.model_probability.notna() & p.price.notna()].copy()
m["res"] = np.sign(np.where(m.pick_side == "home", m.margin, -m.margin))
m["e"] = m.decision_edge.fillna(m.edge)
print(f"\nMONEYLINE 2026 (paused; rows are what it would have said): {len(m)} graded sides on {m.game_id.nunique()} games")
m["pb"] = pd.cut(m.model_probability, [0, .3, .45, .55, .62, .70, .80, 1.01], right=False)
cal = m.groupby("pb", observed=True).agg(n=("res", "size"), claimed=("model_probability", "mean"), won=("res", lambda v: (v > 0).mean()),
                                         implied=("dk_implied_prob", "mean"))
print(cal.round(3).to_string())
print("\nsides priced -250 or longer, by claimed probability and edge (the live cut is 0.62 / 0.08):")
mm = m[m.price >= -250]
for plo in (0.50, 0.55, 0.62, 0.70, 0.75):
    for elo in (0.0, 0.04, 0.08, 0.12, 0.16):
        x = mm[(mm.model_probability >= plo) & (mm.e >= elo)]
        print("  " + summ(x, f"p>={plo} edge>={elo}"))
print("  " + summ(m[(m.signal_type == 'BET') & ~m.void], "rows it marked BET"))
half = mm[(mm.model_probability >= 0.62) & (mm.e >= 0.08)]
mid = half.game_date.sort_values().iloc[len(half) // 2] if len(half) else None
if mid:
    print("  " + summ(half[half.game_date < mid], f"0.62/0.08 before {mid}"))
    print("  " + summ(half[half.game_date >= mid], f"0.62/0.08 from {mid}"))
