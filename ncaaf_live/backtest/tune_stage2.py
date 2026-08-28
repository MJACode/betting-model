"""
Choose the Stage 2 smoothing on 2024, NOT on the 2025 holdout.

    python -m ncaaf_live.backtest.tune_stage2

WHY THIS EXISTS. The first 2025 gate run failed coverage at 4.02pp with a
zero mean bias (-0.08 pts) - a SHAPE failure, not a drift. The suspect is the
fit's uniform Laplace smoothing: 0.5 pseudo-counts per support cell is 45.5
pseudo-rows spread evenly over 0..90 remaining points, so a (mu, time) cell
near MIN_CELL carries ~18% uniform mass, most of it on near-zero outcomes
that never happen from a high-mu state. That fattens the low tail, pushes PIT
values up, and under-covers the low quantiles - exactly the observed
signature.

The candidate fix is hierarchical: shrink each (mu, time) cell toward the
MU-ONLY pmf (real football mass) instead of toward uniform, keeping only a
token uniform floor so no alternate line ever prices at zero.

THE DISCIPLINE. Re-tuning against the failed gate is fitting to it. So the
smoothing is chosen here on a 2024 pseudo-holdout (Stage 2 fitted on OOS
2017-2023 predictions, coverage measured on 2024), and 2025 is then re-run
ONCE with the winner. That re-run is the honest verdict and its one-shot
nature is recorded in the README.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.backtest.train_engine import load_states, walk_forward_oos  # noqa: E402
from ncaaf_live.config import ARTIFACT_DIR  # noqa: E402
from ncaaf_live.engine.distribution import (  # noqa: E402
    ScoreDistribution, time_bucket)
from ncaaf_live.engine.pricing import total_pmf  # noqa: E402

QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
OOS_CACHE = ARTIFACT_DIR / "stage1_oos.parquet"


def get_oos(states: pd.DataFrame) -> pd.DataFrame:
    """Walk-forward Stage 1 predictions, cached - they take ~15 min to build."""
    if OOS_CACHE.exists():
        return pd.read_parquet(OOS_CACHE)
    oos = walk_forward_oos(states, sample_every=3, rounds=700)
    oos.to_parquet(OOS_CACHE)
    return oos


def coverage_on(dist: ScoreDistribution, ev: pd.DataFrame,
                seed: int = 11) -> float:
    """Worst-quantile randomised-PIT coverage error, in pp."""
    rng = np.random.default_rng(seed)
    pit = np.zeros(len(ev))
    mu_h = ev["home_remaining_hat"].to_numpy()
    mu_a = ev["away_remaining_hat"].to_numpy()
    secs = ev["seconds_remaining"].to_numpy()
    actual = (ev["home_remaining_pts"] + ev["away_remaining_pts"]).to_numpy()
    for i in range(len(ev)):
        out = dist.final_score_pmf(mu_h[i], mu_a[i], secs[i], 0, 0)
        values, probs = total_pmf(out["joint_remaining"], 0)
        below = float(probs[values < actual[i]].sum())
        at = float(probs[values == actual[i]].sum())
        pit[i] = below + rng.random() * at
    return max(abs(float((pit <= q).mean()) - q) * 100 for q in QUANTILES)


def main() -> int:
    states = load_states()
    oos = get_oos(states)
    fit_part = oos[oos.season <= 2023]
    eval_part = oos[oos.season == 2024].iloc[::10].reset_index(drop=True)
    print(f"stage 2 fit rows (2017-2023): {len(fit_part):,}   "
          f"2024 eval states: {len(eval_part):,}")

    def build(**kw):
        return ScoreDistribution.fit(
            fit_part["home_remaining_pts"].to_numpy(),
            fit_part["home_remaining_hat"].to_numpy(),
            fit_part["away_remaining_pts"].to_numpy(),
            fit_part["away_remaining_hat"].to_numpy(),
            fit_part["seconds_remaining"].to_numpy(), **kw)

    candidates = [
        ("uniform laplace 0.5 (shipped)", dict(laplace=0.5)),
        ("uniform laplace 0.05", dict(laplace=0.05)),
        ("shrink-to-mu k=50", dict(laplace=0.01, shrink_k=50.0)),
        ("shrink-to-mu k=150", dict(laplace=0.01, shrink_k=150.0)),
        ("shrink-to-mu k=400", dict(laplace=0.01, shrink_k=400.0)),
    ]
    results = []
    for name, kw in candidates:
        try:
            worst = coverage_on(build(**kw), eval_part)
        except TypeError as exc:
            print(f"  {name}: SKIP ({exc})")
            continue
        results.append((worst, name, kw))
        print(f"  {name:32s} worst 2024 coverage {worst:.2f}pp")

    results.sort()
    worst, name, kw = results[0]
    print(f"\nWINNER on 2024: {name} ({worst:.2f}pp). "
          f"Refit on all OOS (2017-2024) with it, then re-run the 2025 gate "
          f"ONCE:\n  python -m ncaaf_live.backtest.train_engine --fit "
          f"# picks up STAGE2_FIT_KW\n"
          f"  python -m ncaaf_live.backtest.calibrate --season 2025")
    return 0


if __name__ == "__main__":
    sys.exit(main())
