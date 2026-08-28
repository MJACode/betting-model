"""
Calibration gates for the engine. Run before trusting a single price.

    python -m live_model.backtest.calibrate --season 2025

THIS IS THE GATE THAT DOES NOT NEED ODDS DATA, which makes it the first honest
verdict available on the whole idea. If the engine cannot produce a calibrated
win probability and a calibrated total distribution on a season it has never
seen, then every market it derives is wrong and no amount of hunting for lagging
derivative lines will save it.

Two gates, from the build spec:
  1. Brier score for derived win probability under 0.20 on in-game states.
  2. Total-distribution quantile coverage within 2pp of nominal.

Gate 2 is the one that actually matters for this system. A win probability can
be well calibrated while the SHAPE of the total distribution is wrong, and the
shape is what prices second half totals, team totals and alternate lines. A
model that is right on average and wrong in the tails will find fake edges in
exactly the alternate lines that live furthest from the mean.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from ..config import ARTIFACT_DIR
from ..engine.distribution import ScoreDistribution, SUPPORT, time_bucket
from ..engine.pricing import price_moneyline, total_pmf
from ..engine.remaining import load_models, predict_remaining
from .train_engine import load_states

QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
BRIER_GATE = 0.20
COVERAGE_GATE_PP = 2.0
PIT_SEED = 11
BOOT_DRAWS = 400

# THE TOTAL DISTRIBUTION IS LUMPY, AND THE TEST HAS TO KNOW THAT.
# With two minutes left a team scores exactly zero more points 77.5% of the
# time, so the final-total distribution carries an atom of most of its mass on
# one integer. The usual midpoint PIT, F(t-1) + 0.5 P(T=t), is NOT uniform
# under a discrete distribution: every outcome landing on that atom gets the
# same PIT value, so no quantile inside the atom can be hit and a perfectly
# calibrated model still fails. The RANDOMISED PIT,
#     u = F(t-1) + V * P(T=t),  V ~ Uniform(0,1)
# is exactly uniform when the model is right, discreteness and all. It is the
# correct test; the midpoint version is reported alongside it only to show how
# much of any late-game failure is the atom rather than the model.


def evaluate(season: int, sample_every: int = 10) -> dict:
    states = load_states()
    df = states[states.season == season]
    if df.empty:
        raise SystemExit(f"no states for season {season}")
    df = df.iloc[::sample_every].reset_index(drop=True)

    models = load_models(ARTIFACT_DIR)
    dist = ScoreDistribution.load(ARTIFACT_DIR / "score_distribution.npz")
    preds = predict_remaining(models, df)

    home_won = (df["home_score"] > df["away_score"]).to_numpy().astype(float)
    tied = (df["home_score"] == df["away_score"]).to_numpy()
    actual_total = (df["home_score"] + df["away_score"]).to_numpy().astype(float)

    rng = np.random.default_rng(PIT_SEED)
    wp = np.zeros(len(df))
    pit_rand = np.zeros(len(df))
    pit_mid = np.zeros(len(df))
    tot_mean = np.zeros(len(df))

    mu_h = preds["home_remaining_hat"].to_numpy()
    mu_a = preds["away_remaining_hat"].to_numpy()
    secs = df["seconds_remaining"].to_numpy()
    hs = df["home_score_pre"].to_numpy().astype(int)
    as_ = df["away_score_pre"].to_numpy().astype(int)

    for i in range(len(df)):
        out = dist.final_score_pmf(mu_h[i], mu_a[i], secs[i], hs[i], as_[i])
        out["rho"] = float(dist.rho[int(time_bucket(secs[i]))])
        wp[i] = price_moneyline(out)["home"]

        values, probs = total_pmf(out["joint_remaining"], hs[i] + as_[i])
        tot_mean[i] = float((values * probs).sum())
        # PIT value: P(T < actual) + 0.5 * P(T == actual), the randomised
        # correction for a discrete distribution. Without the half mass a
        # perfectly calibrated discrete model still fails a coverage test.
        below = float(probs[values < actual_total[i]].sum())
        at = float(probs[values == actual_total[i]].sum())
        pit_mid[i] = below + 0.5 * at
        pit_rand[i] = below + rng.random() * at

    # ------------------------------------------------------------ gate 1
    ok = ~tied
    brier = float(np.mean((wp[ok] - home_won[ok]) ** 2))
    base = float(np.mean((home_won[ok].mean() - home_won[ok]) ** 2))

    bins = np.linspace(0, 1, 11)
    idx = np.clip(np.digitize(wp[ok], bins) - 1, 0, 9)
    rel = []
    for b in range(10):
        m = idx == b
        if m.sum() >= 30:
            rel.append((f"{bins[b]:.1f}-{bins[b+1]:.1f}", int(m.sum()),
                        float(wp[ok][m].mean()), float(home_won[ok][m].mean())))

    # ------------------------------------------------------------ gate 2
    coverage = {q: float((pit_rand <= q).mean()) for q in QUANTILES}
    worst_pp = max(abs(coverage[q] - q) * 100 for q in QUANTILES)
    coverage_mid = {q: float((pit_mid <= q).mean()) for q in QUANTILES}
    worst_mid_pp = max(abs(coverage_mid[q] - q) * 100 for q in QUANTILES)

    # STATES INSIDE A GAME ARE NOT INDEPENDENT. One game contributes a dozen
    # correlated rows, so a naive standard error understates the noise by
    # roughly the square root of that. Every interval below is a cluster
    # bootstrap over GAMES, which is the only unit that resamples honestly.
    games = df["game_id"].to_numpy()
    boot = _cluster_bootstrap(games, pit_rand, wp, home_won, ok, rng)

    # Coverage by time bucket. An average that passes while the last two
    # minutes are badly miscalibrated is a model that will lose money on the
    # exact states where the derivative markets are laziest.
    tb = time_bucket(secs)
    by_bucket = []
    for b in sorted(set(tb.tolist())):
        m = tb == b
        if m.sum() < 100:
            continue
        cov = {q: float((pit_rand[m] <= q).mean()) for q in QUANTILES}
        by_bucket.append({
            "bucket": int(b), "n": int(m.sum()),
            "worst_pp": max(abs(cov[q] - q) * 100 for q in QUANTILES),
            "brier": float(np.mean((wp[m & ok] - home_won[m & ok]) ** 2))
            if (m & ok).sum() else float("nan"),
        })

    res = {
        "season": season, "n": int(len(df)),
        "brier": brier, "brier_base": base,
        "brier_skill": 1 - brier / base if base else float("nan"),
        "reliability": rel,
        "coverage": coverage, "worst_coverage_pp": worst_pp,
        "coverage_midpoint": coverage_mid, "worst_midpoint_pp": worst_mid_pp,
        "boot": boot, "n_games": int(df["game_id"].nunique()),
        "by_bucket": by_bucket,
        "total_mae": float(np.abs(tot_mean - actual_total).mean()),
        "gate1_pass": brier < BRIER_GATE,
        "gate2_pass": worst_pp <= COVERAGE_GATE_PP,
        "gate2_pass_ci": boot["worst_coverage_pp_lo"] <= COVERAGE_GATE_PP,
    }
    return res


def _cluster_bootstrap(games, pit, wp, home_won, ok, rng):
    """Resample whole GAMES, not states, and report the spread of each gate."""
    uniq = np.unique(games)
    idx_by_game = {g: np.flatnonzero(games == g) for g in uniq}
    worsts, briers = [], []
    for _ in range(BOOT_DRAWS):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_game[g] for g in pick])
        cov = {q: float((pit[idx] <= q).mean()) for q in QUANTILES}
        worsts.append(max(abs(cov[q] - q) * 100 for q in QUANTILES))
        m = ok[idx]
        if m.sum():
            briers.append(float(np.mean((wp[idx][m] - home_won[idx][m]) ** 2)))
    return {
        "worst_coverage_pp_lo": float(np.percentile(worsts, 5)),
        "worst_coverage_pp_hi": float(np.percentile(worsts, 95)),
        "brier_lo": float(np.percentile(briers, 5)) if briers else float("nan"),
        "brier_hi": float(np.percentile(briers, 95)) if briers else float("nan"),
    }


def report(res: dict) -> None:
    print(f"\n=== engine calibration, season {res['season']} "
          f"({res['n']:,} states) ===")
    print(f"  {res['n_games']} games, so the effective sample is the GAME "
          f"count, not the state count")
    b = res["boot"]
    print(f"gate 1  win prob Brier   {res['brier']:.4f} "
          f"[{b['brier_lo']:.4f}, {b['brier_hi']:.4f}] "
          f"(base {res['brier_base']:.4f}, skill {res['brier_skill']:.3f}) "
          f"{'PASS' if res['gate1_pass'] else 'FAIL'} vs {BRIER_GATE}")
    print("  reliability (predicted vs actual):")
    for label, n, pred, act in res["reliability"]:
        print(f"    {label}  n={n:6d}  pred {pred:.3f}  actual {act:.3f}  "
              f"gap {100*(act-pred):+5.1f}pp")

    print(f"\ngate 2  total quantile coverage (randomised PIT), worst "
          f"{res['worst_coverage_pp']:.2f}pp "
          f"[{b['worst_coverage_pp_lo']:.2f}, {b['worst_coverage_pp_hi']:.2f}] "
          f"{'PASS' if res['gate2_pass'] else 'FAIL'} vs {COVERAGE_GATE_PP}pp")
    print(f"        midpoint PIT for comparison, worst "
          f"{res['worst_midpoint_pp']:.2f}pp (inflated by the discrete atoms)")
    for q, c in res["coverage"].items():
        print(f"    q{q:<5} nominal {100*q:5.1f}%  actual {100*c:5.1f}%  "
              f"{100*(c-q):+5.2f}pp")
    print(f"  total point MAE {res['total_mae']:.2f}")

    print("\n  by time bucket (0 = final 2 min, 6 = pregame/Q1):")
    for b in res["by_bucket"]:
        print(f"    bucket {b['bucket']}  n={b['n']:6d}  "
              f"worst coverage {b['worst_pp']:5.2f}pp  brier {b['brier']:.4f}")

    verdict = "PASS" if (res["gate1_pass"] and res["gate2_pass"]) else "FAIL"
    print(f"\n  VERDICT: {verdict}")
    if not res["gate2_pass"] and res.get("gate2_pass_ci"):
        print("  (gate 2 misses on the point estimate but its bootstrap "
              "interval covers the gate, so the miss is inside sampling noise)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--sample-every", type=int, default=10)
    args = ap.parse_args()
    report(evaluate(args.season, args.sample_every))


if __name__ == "__main__":
    main()
