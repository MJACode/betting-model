"""The decision point: does the rebuilt stage 2 price BETTER AGAINST THE REAL LINE?

mike, 2026-09-12. `ncaaf_live_total_rebuild.py` showed the shipped score
distribution is ~70% too wide inside ten minutes and that switching on the
hierarchical smoothing (`shrink_k`, shipped at 0.0) repairs it -- width ratio
0.51 -> 0.92, PIT extreme mass 15.7% -> 18.8%.

THAT IS NOT A REASON TO SHIP IT. The rebuild script's third read-out scored the
probability against the PREGAME total as a stand-in line, which is a far easier
question than the one we bet -- by late in a game you largely know whether the
pregame number is beaten. It returns a slope near 1.3 for the shipped
distribution, which against DraftKings' LIVE line scores 0.135. A proxy line
cannot decide this.

So this re-prices the 2025 in-play candidates at THEIR OWN DK LINE, the number
actually bet, under both distributions, and compares:

  1. the calibration SLOPE of the resulting P(side) against the realised
     outcome -- 1.0 fully informative, 0.0 none. The shipped model is 0.135.
  2. Brier and log-loss on the same rows.
  3. what each would have BET at the shipped cut, and how that graded.

HONESTY. Stage 2 is fitted on the FIRST half of 2025 and every number here is
read on the SECOND, so the rebuilt distribution never saw these games. The
shipped artifact did see them (it was fitted on 286k states across seasons), so
this comparison is if anything generous to the incumbent.

    python -m scripts.ncaaf_live_total_repricing
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ncaaf_live.config import ARTIFACT_DIR                            # noqa: E402
from ncaaf_live.engine.distribution import ScoreDistribution          # noqa: E402
from ncaaf_live.engine.pricing import total_pmf                       # noqa: E402
from ncaaf_live.engine.remaining import load_models, predict_remaining  # noqa: E402

LANE = "ncaaf_live_total"
STATES = ROOT / "ncaaf_live" / "data" / "artifacts" / "states_2025.parquet"


def logit(p):
    return np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def fit_logistic(X, y, l2=1e-4):
    w = np.zeros(X.shape[1])
    for _ in range(120):
        p = sigmoid(X @ w)
        H = (X * (p * (1 - p) + 1e-12)[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p) - l2 * w)
        w += step
        if np.max(np.abs(step)) < 1e-10:
            break
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return w, se


def wilson(w, n, z=1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--shrink", type=float, default=5.0)
    args = ap.parse_args()

    df = pd.read_parquet(STATES)
    df = df[(df["seconds_remaining"] > 0) & df["wall_ts"].notna()].sort_values("wall_ts")
    days = sorted(df["wall_ts"].dt.date.unique())
    mid = days[len(days) // 2]
    tr = df[df["wall_ts"].dt.date <= mid]
    print(f"stage 2 fit on <= {mid}: {len(tr):,} states")

    models = load_models(ARTIFACT_DIR)
    p_tr = predict_remaining(models, tr)
    rebuilt = ScoreDistribution.fit(
        tr["home_remaining_pts"].values, p_tr["home_remaining_hat"].values,
        tr["away_remaining_pts"].values, p_tr["away_remaining_hat"].values,
        tr["seconds_remaining"].values, shrink_k=args.shrink)
    shipped = ScoreDistribution.load(ARTIFACT_DIR / "score_distribution.npz")

    cache = Path(tempfile.gettempdir()) / "ncaaf_inplay_candidates_2025.pkl"
    cands = [c for c in pickle.loads(cache.read_bytes())
             if c["model_id"] == LANE and c["points_since_update"] == 0
             and c["result"] in ("WIN", "LOSS")
             and c["served"].date() > mid]
    cands.sort(key=lambda c: c["served"])
    print(f"held-out {LANE} candidates to re-price: {len(cands):,}")

    by_game = {g: d.reset_index(drop=True) for g, d in df.groupby("game_id", sort=False)}
    rows = []
    for c in cands:
        g = by_game.get(c["game_id"])
        if g is None:
            continue
        ts = pd.Timestamp(c["served"])
        if ts.tzinfo is not None and g["wall_ts"].dt.tz is None:
            ts = ts.tz_localize(None)
        j = int(np.searchsorted(g["wall_ts"].values, ts.to_datetime64(), "right")) - 1
        if j < 0:
            continue
        st = g.iloc[[j]]
        rows.append((c, st))
    print(f"paired to a state: {len(rows):,}")

    states = pd.concat([s for _, s in rows], ignore_index=True)
    pred = predict_remaining(models, states)
    mu_h = pred["home_remaining_hat"].values
    mu_a = pred["away_remaining_hat"].values
    hs = states["home_score"].values.astype(float)
    as_ = states["away_score"].values.astype(float)
    secs = states["seconds_remaining"].values.astype(float)

    def price(dist, k, line, side):
        j = dist.joint_remaining(float(mu_h[k]), float(mu_a[k]), float(secs[k]))
        values, probs = total_pmf(j, hs[k] + as_[k])
        over = float(probs[values > line].sum())
        return over if side == "over" else 1.0 - over

    out = {"shipped": [], "rebuilt": []}
    ys, evs = [], []
    for k, (c, _) in enumerate(rows):
        line = float(c["scored_line"])
        side = c["pick_side"]
        out["shipped"].append(price(shipped, k, line, side))
        out["rebuilt"].append(price(rebuilt, k, line, side))
        ys.append(1.0 if c["result"] == "WIN" else 0.0)
        pr = c["dk_odds"]
        evs.append({"profit": (pr / 100.0) if pr > 0 else (100.0 / abs(pr)),
                    "implied": c["dk_implied_prob"], "game": c["game_id"],
                    "edge_floor_ok": True})
    y = np.array(ys)
    print(f"\n{'distribution':>14} {'slope':>18} {'brier':>9} {'logloss':>9}")
    for nm in ("shipped", "rebuilt"):
        p = np.clip(np.array(out[nm]), 1e-6, 1 - 1e-6)
        w, se = fit_logistic(np.column_stack([np.ones(len(p)), logit(p)]), y)
        br = float(np.mean((p - y) ** 2))
        ll = float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
        print(f"{nm:>14} {w[1]:>+9.3f} +- {se[1]:<5.3f} {br:>9.5f} {ll:>9.5f}")

    # what each would have BET at the shipped cut, first-signal lock
    import config
    pmin = config.ACTION_THRESHOLDS[LANE]["min_prob"]
    emin = config.ACTION_THRESHOLDS[LANE]["min_edge"]
    evmin = config.MODEL_MIN_EV.get(LANE)
    cap = 0.18
    print(f"\nBETS at the shipped cut (prob>={pmin}, edge>={emin}, ev>={evmin}):")
    for nm in ("shipped", "rebuilt"):
        seen, n, wn, units = set(), 0, 0, 0.0
        for k, (c, _) in enumerate(rows):
            if c["game_id"] in seen:
                continue
            p = out[nm][k]
            e = p - evs[k]["implied"]
            if p < pmin or e < emin or abs(e) > cap:
                continue
            if evmin is not None and (p * evs[k]["profit"] - (1 - p)) < evmin:
                continue
            seen.add(c["game_id"])
            n += 1
            wn += int(y[k])
            units += evs[k]["profit"] if y[k] else -1.0
        lo, hi = wilson(wn, n)
        roi = 100 * units / n if n else float("nan")
        print(f"  {nm:>10}: {n:>3} bets {wn}-{n - wn:<3} {units:>+7.2f}u {roi:>+6.1f}%"
              f"  win CI [{100 * lo:.1f}, {100 * hi:.1f}]")


if __name__ == "__main__":
    main()
