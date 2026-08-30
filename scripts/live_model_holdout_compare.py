"""Compare two live-model artifacts on a holdout season, side by side.

**Why this exists rather than re-running `tracking/live_calibration.py`.** That
module grades SETTLED LIVE PICKS, and every settled live pick was made by the
model that is being replaced. Its numbers are byte-identical the moment a
retrain lands, so reading them as "did the retrain work" reports a false
negative on day one. The live calibration gap can only move FORWARD, over
weeks, on the dashboard.

The retrain-day evidence is a different measurement: **score both artifacts over
the same holdout states and compare their bias.** `mlb_live_total_runs` predicts
runs in the REMAINDER of the game, so the honest question is whether mean
predicted remaining runs tracks mean actual — overall and, more importantly, in
the innings where live picks actually cluster (avg inning at pick is ~2-3).

A second, softer question the retrain forces: **does the deployed cutoff still
reach?** A better-calibrated model produces compressed probabilities, and the
`mlb_moneyline` precedent is explicit — after a retrain "the old 0.70/0.11 cut
produces <20 bets/season on the new model". So this also reports how often each
model would be confident enough to clear the live probability floor. That half
is a PROXY (it prices against a fair line derived from the model's own
prediction, because holdout states carry no live DK line) and is labelled as
one: read it for the direction of the shift, not as a volume forecast.

Usage
-----
    python -m scripts.live_model_holdout_compare \\
        --model mlb_live_total_runs --season 2026 \\
        --old models/saved/mlb_live_total_runs_20260614_075301.pkl \\
        --new models/saved/mlb_live_total_runs_<new>.pkl

Keep the superseded .pkl on disk until this has run — the retrain workflow's
habit is to delete it immediately, and then there is nothing to compare against.
"""
from __future__ import annotations

import argparse
import pickle
from math import exp, lgamma, log

import numpy as np

import config

# Innings 1-3 is where the live picks cluster, so it is reported separately
# rather than being averaged away into a single season-wide number.
BUCKETS = (("1-3", 1, 3), ("4-6", 4, 6), ("7+", 7, 99))


def load_artifact(path: str) -> dict:
    with open(path, "rb") as fh:
        return pickle.load(fh)


def predict(artifact: dict, frame) -> np.ndarray:
    cols = artifact["feature_cols"]
    x = frame[cols].to_numpy(dtype=float)
    return np.asarray(artifact["model"].predict(x), dtype=float)


def poisson_sf(k: int, lam: float) -> float:
    """P(X > k) for X ~ Poisson(lam). Serving uses the same CDF to price a total."""
    if lam <= 0:
        return 0.0
    total, term = 0.0, exp(-lam)
    for i in range(0, k + 1):
        if i:
            term *= lam / i
        total += term
    return max(0.0, 1.0 - total)


def confident_share(lams: np.ndarray, floor: float) -> float:
    """Share of states where the model's better side clears the probability floor.

    PROXY: holdout states carry no live DK line, so each state is priced against
    a FAIR line at the model's own median-ish expectation (lambda rounded to the
    nearest half-run). That is deliberately the hardest line to beat, so the
    absolute level means little — the comparison between two models on the same
    states is the readable part.
    """
    hits = 0
    for lam in lams:
        line = round(float(lam) * 2) / 2.0          # e.g. 3.5 remaining runs
        k = int(line)                                # over needs > line
        p_over = poisson_sf(k, float(lam))
        if max(p_over, 1.0 - p_over) >= floor:
            hits += 1
    return hits / len(lams) if len(lams) else 0.0


def bias_table(frame, preds: np.ndarray, target: str) -> list[dict]:
    actual = frame[target].to_numpy(dtype=float)
    inning = frame["inning"].to_numpy(dtype=float)
    out = []
    for label, lo, hi in (("all", 1, 99), *BUCKETS):
        m = (inning >= lo) & (inning <= hi)
        if not m.any():
            continue
        out.append({
            "bucket": label, "n": int(m.sum()),
            "pred": float(preds[m].mean()),
            "actual": float(actual[m].mean()),
            "bias": float(preds[m].mean() - actual[m].mean()),
            "mae": float(np.abs(preds[m] - actual[m]).mean()),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="mlb_live_total_runs")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--old", required=True, help="path to the superseded .pkl")
    ap.add_argument("--new", required=True, help="path to the retrained .pkl")
    ap.add_argument("--sample-frac", type=float, default=1.0)
    args = ap.parse_args()

    from features.live_game_features import build_live_training_dataset

    print(f"building {args.season} holdout states for {args.model} ...")
    frame = build_live_training_dataset(args.model, [args.season], args.sample_frac)
    if frame.empty:
        raise SystemExit(f"no {args.season} states — is the PBP backfill complete?")
    target = "target"
    print(f"  {len(frame):,} states from {frame['game_id'].nunique():,} games")

    floor = config.MODEL_PROB_THRESHOLDS.get(args.model, 0.70)
    rows = []
    for label, path in (("old", args.old), ("new", args.new)):
        art = load_artifact(path)
        preds = predict(art, frame)
        rows.append((label, path, art.get("trained_at"), art.get("train_seasons"),
                     bias_table(frame, preds, target),
                     confident_share(preds, floor)))

    print("\n" + "=" * 78)
    print(f"{args.model} — holdout {args.season}")
    print("=" * 78)
    for label, path, trained, seasons, table, conf in rows:
        print(f"\n{label.upper()}  {path}")
        print(f"  trained {trained} on {seasons}")
        print(f"  {'bucket':<8}{'n':>9}{'pred':>9}{'actual':>9}{'bias':>9}{'MAE':>8}")
        for r in table:
            print(f"  {r['bucket']:<8}{r['n']:>9,}{r['pred']:>9.3f}"
                  f"{r['actual']:>9.3f}{r['bias']:>+9.3f}{r['mae']:>8.3f}")
        print(f"  clears the {floor:.2f} prob floor on {100 * conf:.1f}% of states "
              f"(proxy — fair line, see the module docstring)")

    old_all = next(r for r in rows[0][4] if r["bucket"] == "all")
    new_all = next(r for r in rows[1][4] if r["bucket"] == "all")
    print("\n" + "-" * 78)
    print(f"VERDICT  bias {old_all['bias']:+.3f} -> {new_all['bias']:+.3f} "
          f"runs/state   |   MAE {old_all['mae']:.3f} -> {new_all['mae']:.3f}")
    if abs(new_all["bias"]) >= abs(old_all["bias"]):
        print("  The retrain did NOT reduce bias on the holdout. Adding a season is")
        print("  not the lever; say so rather than shipping it as an improvement.")
    else:
        print("  Bias reduced. NOTE this is the holdout, not the live record — the")
        print("  live gap can only move forward, on the dashboard, over weeks. Part")
        print("  of it is structural to the first-signal lock, which takes the FIRST")
        print("  crossing of a noisy estimate and so selects positive noise.")


if __name__ == "__main__":
    main()
