"""Rebuild stage 2 of ncaaf_live_total: the score distribution is the wrong shape.

mike, 2026-09-12: *"find evidence about .72, refine the models or approach"* ->
*"start the rebuild now"*.

WHAT IS WRONG, measured before any of this was written (2025 states, one state
per game per 5-minute bucket, Stage 1 predictions out of sample):

  * STAGE 1 IS FINE AND IS NOT TOUCHED HERE. Predicted remaining points are
    biased by +0.2..+1.2 across every time bucket and every predicted level,
    and the error on the TOTAL matches the error on the MARGIN (RMSE 6.38 vs
    5.69 late, 15.57 vs 15.03 early). The engine knows how much scoring is left.

  * STAGE 2 IS TOO WIDE, AND ONLY LATE. Implied SD of remaining total against
    the realised SD:

        <10 min left   6.30 real vs 10.65 implied   ratio 0.59
        10-20 min      8.40 vs 10.49                ratio 0.80
        20-30 min      9.91 vs 11.21                ratio 0.88
        >50 min       15.57 vs 16.21                ratio 0.96

    The margin ratio is 0.95+ everywhere except the last ten minutes, which is
    why the SAME engine prices ncaaf_live_win_prob acceptably and this one
    badly: margin errors partly cancel between the two sides, the total's do
    not.

  * AND THE SHAPE IS WRONG THE SAME WAY. A probability-integral-transform of
    the remaining total puts 15.2% of outcomes in the two extreme deciles
    (uniform: 20%) and 64.0% in the middle six (uniform: 60%) -- too fat in the
    middle, too thin in the tails.

THE SUSPECT. The shipped artifact carries `shrink_k: 0.0` with `min_cell: 200`
and 56 (mu, time) cells "still_mu_only" -- i.e. those cells fall back to a
prior POOLED ACROSS ALL TIME BUCKETS. A late-game cell that backs off to a
time-pooled prior inherits the width of a first-quarter state, which is exactly
the defect's shape. `ScoreDistribution.fit` already has a hierarchical path for
this (`shrink_k > 0`, added after a CFB gate failure) and it is switched off.

THE EXPERIMENT. Fit stage 2 on the FIRST half of 2025 and read the SECOND,
never both, sweeping shrink_k. Three read-outs, all out of sample:

  1. width ratio by time bucket   -- 1.00 is right, <1 is too wide
  2. PIT extreme-decile mass      -- 20% is right, <20% is too thin in the tails
  3. the calibration slope of the resulting BET probability, which is the
     number that actually matters: the shipped model's is 0.135, where 1.0
     would mean fully informative and 0.0 none.

A candidate only ships if it beats the shipped artifact on (3) out of sample.
Nothing here changes stage 1, any threshold, or any live model's state.

    python -m scripts.ncaaf_live_total_rebuild
    python -m scripts.ncaaf_live_total_rebuild --shrink 0 5 20 50 200
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ncaaf_live.config import ARTIFACT_DIR                      # noqa: E402
from ncaaf_live.engine.distribution import ScoreDistribution    # noqa: E402
from ncaaf_live.engine.remaining import load_models, predict_remaining  # noqa: E402

STATES = ROOT / "ncaaf_live" / "data" / "artifacts" / "states_2025.parquet"


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def fit_logistic(X, y, l2=1e-4):
    w = np.zeros(X.shape[1])
    for _ in range(120):
        p = sigmoid(X @ w)
        g = X.T @ (y - p) - l2 * w
        W = p * (1 - p) + 1e-12
        H = (X * W[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        w += step
        if np.max(np.abs(step)) < 1e-10:
            break
    return w


def total_pmf_from_joint(j):
    n = j.shape[0]
    T = (np.arange(n)[:, None] + np.arange(n)[None, :]).ravel()
    return np.bincount(T, weights=j.ravel(), minlength=2 * n)


def evaluate(dist, states, mu_h, mu_a, tag):
    """Width ratio by time bucket, PIT mass, and the calibration slope."""
    ah = states["home_remaining_pts"].values.astype(float)
    aa = states["away_remaining_pts"].values.astype(float)
    secs = states["seconds_remaining"].values.astype(float)
    pre_tot = states["pregame_total"].values.astype(float)
    cur_tot = (states["home_score"] + states["away_score"]).values.astype(float)

    idx = np.linspace(0, len(states) - 1, min(1800, len(states))).astype(int)
    rows = []
    for k in idx:
        j = dist.joint_remaining(float(mu_h[k]), float(mu_a[k]), float(secs[k]))
        tot = total_pmf_from_joint(j)
        g = np.arange(len(tot))
        m = float((tot * g).sum())
        sd = math.sqrt(float((tot * (g - m) ** 2).sum()))
        a = int(round(ah[k] + aa[k]))
        rows.append({
            "i": k, "secs": secs[k], "sd": sd,
            "resid": (ah[k] + aa[k]) - (mu_h[k] + mu_a[k]),
            "pit": float(tot[:a + 1].sum()),
            # the BET probability: P(remaining total > line - current), using
            # the pregame total as a stand-in line so every state is priced
            "p_over": float(tot[int(max(0, math.ceil(pre_tot[k] - cur_tot[k]))):].sum()),
            "y_over": 1.0 if (ah[k] + aa[k]) > (pre_tot[k] - cur_tot[k]) else 0.0,
        })
    d = pd.DataFrame(rows).dropna()
    out = {"tag": tag}
    parts = []
    for lo, hi in ((0, 600), (600, 1200), (1200, 1800), (1800, 3601)):
        s = d[(d.secs >= lo) & (d.secs < hi)]
        if len(s) < 80:
            continue
        parts.append(f"{lo // 60}-{hi // 60}m {s.resid.std() / s.sd.mean():.2f}")
    out["width"] = "  ".join(parts)
    h, _ = np.histogram(d.pit, bins=np.linspace(0, 1, 11))
    out["pit_extreme"] = 100 * (h[0] + h[9]) / len(d)
    dd = d[(d.p_over > 0.001) & (d.p_over < 0.999)]
    if len(dd) > 200 and dd.y_over.nunique() > 1:
        w = fit_logistic(np.column_stack([np.ones(len(dd)), logit(dd.p_over)]),
                         dd.y_over.values)
        out["slope"] = w[1]
    else:
        out["slope"] = float("nan")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--shrink", nargs="+", type=float, default=[0, 5, 20, 50, 200])
    ap.add_argument("--min-cell", nargs="+", type=int, default=[200])
    args = ap.parse_args()

    df = pd.read_parquet(STATES)
    df = df[df["seconds_remaining"] > 0].copy()
    # A state with no wallclock cannot be placed on either side of the season
    # split, and a NaT silently sorts to one end -- drop it and say how many.
    n0 = len(df)
    df = df[df["wall_ts"].notna()].copy()
    if len(df) < n0:
        print(f"dropped {n0 - len(df):,} states with no wallclock")
    df = df.sort_values("wall_ts")
    days = sorted(df["wall_ts"].dt.date.unique())
    mid = days[len(days) // 2]
    tr = df[df["wall_ts"].dt.date <= mid]
    te_all = df[df["wall_ts"].dt.date > mid].copy()
    te_all["tb"] = (te_all["seconds_remaining"] // 300).astype(int)
    te = te_all.groupby(["game_id", "tb"], sort=False).head(1).copy()
    print(f"fit on <= {mid}: {len(tr):,} states; read on > {mid}: "
          f"{len(te):,} sampled states from {te['game_id'].nunique()} games")

    models = load_models(ARTIFACT_DIR)
    p_tr = predict_remaining(models, tr)
    p_te = predict_remaining(models, te)
    mu_h_te = p_te["home_remaining_hat"].values
    mu_a_te = p_te["away_remaining_hat"].values

    print("\nSHIPPED artifact, read on the held-out half:")
    base = evaluate(ScoreDistribution.load(ARTIFACT_DIR / "score_distribution.npz"),
                    te, mu_h_te, mu_a_te, "shipped")
    print(f"  width ratio (1.00 = right): {base['width']}")
    print(f"  PIT extreme-decile mass   : {base['pit_extreme']:.1f}%  (20% = right)")
    print(f"  calibration slope         : {base['slope']:+.3f}  (1.0 = informative)")

    print(f"\n{'shrink_k':>9} {'min_cell':>9} | {'width ratio by time left':<44} "
          f"{'PIT ext':>8} {'slope':>7}")
    best = None
    for mc in args.min_cell:
        for sk in args.shrink:
            ScoreDistribution.MIN_CELL = mc
            d = ScoreDistribution.fit(
                tr["home_remaining_pts"].values, p_tr["home_remaining_hat"].values,
                tr["away_remaining_pts"].values, p_tr["away_remaining_hat"].values,
                tr["seconds_remaining"].values, shrink_k=sk)
            r = evaluate(d, te, mu_h_te, mu_a_te, f"sk={sk}")
            print(f"{sk:>9.0f} {mc:>9} | {r['width']:<44} {r['pit_extreme']:>7.1f}% "
                  f"{r['slope']:>+7.3f}")
            if best is None or (r["slope"] > best[0]["slope"]):
                best = (r, sk, mc)
    r, sk, mc = best
    print(f"\nBEST out of sample: shrink_k={sk:g} min_cell={mc} slope {r['slope']:+.3f} "
          f"against the shipped {base['slope']:+.3f}")
    print("  ships only if that slope beats the shipped one; a slope near 0 means "
          "the probability still carries no information and stage 2 is not the "
          "whole defect.")


if __name__ == "__main__":
    main()
