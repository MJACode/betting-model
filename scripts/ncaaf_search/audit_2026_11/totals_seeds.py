"""Is the totals rule's walk-forward record at the +/-8 gate stable across random seeds?

Same frame, same features, same hyper-parameters as scripts/ncaaf_margin_eval._fit; only
random_state changes (the fit subsamples rows and columns at 0.8). Walk-forward 2022-2025,
graded at the stored close at -110.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from paths import REPO as ROOT  # noqa: E402
sys.path.insert(0, str(ROOT))
from scripts.ncaaf_margin_eval import TOTAL_FEATURES, _matrix  # noqa: E402
from xgboost import XGBRegressor  # noqa: E402

from paths import CACHE as D  # noqa: E402
frame = pd.read_pickle(D / "totals_frame.pkl")
TEST = [2022, 2023, 2024, 2025]
SEEDS = [42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]


def fit(X, y, seed):
    m = XGBRegressor(n_estimators=700, learning_rate=0.03, max_depth=5, subsample=0.8, colsample_bytree=0.8,
                     min_child_weight=5, objective="reg:squarederror", n_jobs=-1, random_state=seed)
    m.fit(X, y)
    return m


preds = {}
base = None
for s in TEST:
    tr, cols = _matrix(frame[frame["_season"] < s], TOTAL_FEATURES)
    te, _ = _matrix(frame[frame["_season"] == s], TOTAL_FEATURES)
    te = te.dropna(subset=["_total_line"])
    part = te[["_game_id", "_season", "_total", "_total_line"]].copy()
    for seed in SEEDS:
        part[f"p{seed}"] = fit(tr[cols], tr["_total"], seed).predict(te[cols])
    base = part if base is None else pd.concat([base, part])
    print("season", s, "train", len(tr), "test", len(te), flush=True)
base["pavg"] = base[[f"p{s}" for s in SEEDS]].mean(axis=1)
base.to_parquet(D / "totals_seeds.parquet")


def rec(pred, lo=8.0, hi=99.0, df=base):
    d = pred - df._total_line
    m = (d.abs() >= lo) & (d.abs() < hi)
    res = np.sign(np.where(d[m] > 0, df._total[m] - df._total_line[m], df._total_line[m] - df._total[m]))
    w, l = int((res > 0).sum()), int((res < 0).sum())
    return w, l, (w - 1.1 * l), w / max(w + l, 1)


print("\nseed   |d|>=8: W-L  units(-110)  win%   |  7-8 band   |  8-9 band   | >=10")
for seed in SEEDS + ["avg"]:
    p = base[f"p{seed}"]
    a, b, c, e = rec(p), rec(p, 7, 8), rec(p, 8, 9), rec(p, 10)
    print(f"{str(seed):>4}   {a[0]:>3}-{a[1]:<3} {a[2]:>+7.1f}u  {a[3]:.3f}  | {b[0]:>3}-{b[1]:<3} {b[3]:.3f} | {c[0]:>3}-{c[1]:<3} {c[3]:.3f} | {e[0]:>3}-{e[1]:<3} {e[3]:.3f}")
sd = base[[f"p{s}" for s in SEEDS]].std(axis=1)
print("\nseed-to-seed spread of one game's prediction: mean sd", round(sd.mean(), 3), "points; 95th pct", round(sd.quantile(.95), 3))
pairs = [np.corrcoef(base.p42 - base._total_line, base[f"p{s}"] - base._total_line)[0, 1] for s in SEEDS[1:]]
print("correlation of the disagreement between seed 42 and each other seed: min", round(min(pairs), 4), "max", round(max(pairs), 4))
# agreement on WHICH games are bets
b42 = set(base.index[(base.p42 - base._total_line).abs() >= 8])
for s in SEEDS[1:4]:
    bs = set(base.index[(base[f"p{s}"] - base._total_line).abs() >= 8])
    print(f"games at the gate under seed 42: {len(b42)}; under seed {s}: {len(bs)}; in both: {len(b42 & bs)}")
print("\nby season, seed 42 vs the 11-seed average, |d|>=8:")
for s in TEST:
    x = base[base._season == s]
    a, b = rec(x.p42, df=x), rec(x.pavg, df=x)
    print(f"  {s}: seed42 {a[0]}-{a[1]} ({a[3]:.3f})   average {b[0]}-{b[1]} ({b[3]:.3f})")
print("\nthe 11-seed average, by band:")
for lo, hi in ((6, 7), (7, 8), (8, 9), (9, 10), (10, 12), (12, 99), (8, 99)):
    a = rec(base.pavg, lo, hi)
    print(f"  |d| {lo}-{hi}: {a[0]}-{a[1]}  {a[2]:+.1f}u  win {a[3]:.3f}")
