"""
Fit the NCAAF engine: Stage 1 remaining-points models, then Stage 2 residuals.

    python -m ncaaf_live.backtest.build_states     # once, after pull_pbp
    python -m ncaaf_live.backtest.train_engine --fit

Port of nfl/live_model/backtest/train_engine.py. The design constraint it
exists to enforce carries over unchanged: STAGE 2 IS FITTED ON WALK-FORWARD
OUT-OF-SAMPLE STAGE 1 PREDICTIONS. An in-sample residual is too tight, the
fitted distribution too confident, and every downstream market would look like
an edge. That one mistake makes the whole system appear profitable and be
worthless.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.config import (  # noqa: E402
    ARTIFACT_DIR, HOLDOUT_SEASONS, STAGE2_FIT_KW,
    STAGE2_RECENT_SEASONS, TRAIN_SEASONS, VALID_SEASONS)
from ncaaf_live.engine.distribution import ScoreDistribution  # noqa: E402
from ncaaf_live.engine.remaining import (  # noqa: E402
    predict_remaining, save_models, train_remaining)

STATES_PATH = ARTIFACT_DIR / "states_all.parquet"

# First season with enough prior seasons behind it to predict out-of-sample.
WF_FIRST_SEASON = 2017


def load_states() -> pd.DataFrame:
    if not STATES_PATH.exists():
        raise FileNotFoundError(
            f"{STATES_PATH} missing - run ncaaf_live.backtest.build_states")
    return pd.read_parquet(STATES_PATH)


def walk_forward_oos(states: pd.DataFrame, sample_every: int,
                     rounds: int) -> pd.DataFrame:
    """OOS Stage 1 predictions per season, each from prior-season-only fits."""
    frames = []
    seasons = sorted(s for s in states.season.unique()
                     if WF_FIRST_SEASON <= s <= max(VALID_SEASONS))
    for season in seasons:
        prior = states[states.season < season]
        cur = states[states.season == season]
        if prior.empty or cur.empty:
            continue
        models = train_remaining(prior.iloc[::sample_every], None,
                                 num_rounds=rounds)
        preds = predict_remaining(models, cur)
        out = cur[["season", "seconds_remaining",
                   "home_remaining_pts", "away_remaining_pts"]].copy()
        out["home_remaining_hat"] = preds["home_remaining_hat"].to_numpy()
        out["away_remaining_hat"] = preds["away_remaining_hat"].to_numpy()
        frames.append(out)
        mae = np.abs(out.home_remaining_pts - out.home_remaining_hat).mean()
        print(f"  walk-forward {season}: trained on <{season} "
              f"({len(prior):,} rows), oos mae home {mae:.3f}")
    return pd.concat(frames, ignore_index=True)


def fit(sample_every: int = 3, rounds: int = 700) -> dict:
    states = load_states()

    train = states[states.season.isin(TRAIN_SEASONS)]
    valid = states[states.season.isin(VALID_SEASONS)]
    holdout = states[states.season.isin(HOLDOUT_SEASONS)]

    train_s = train.iloc[::sample_every]
    valid_s = valid.iloc[::sample_every]
    print(f"stage 1: train {len(train_s):,} rows "
          f"({min(TRAIN_SEASONS)}-{max(TRAIN_SEASONS)}), "
          f"valid {len(valid_s):,} rows ({VALID_SEASONS})")

    models = train_remaining(train_s, valid_s, num_rounds=rounds)

    pred_valid = predict_remaining(models, valid)
    resid_h = valid["home_remaining_pts"].to_numpy() - \
        pred_valid["home_remaining_hat"].to_numpy()
    resid_a = valid["away_remaining_pts"].to_numpy() - \
        pred_valid["away_remaining_hat"].to_numpy()
    print(f"stage 1 OOS mae home {np.abs(resid_h).mean():.3f} "
          f"away {np.abs(resid_a).mean():.3f}")

    print("stage 2: walk-forward out-of-sample predictions")
    oos_cache = ARTIFACT_DIR / "stage1_oos.parquet"
    if oos_cache.exists():
        oos = pd.read_parquet(oos_cache)
        print(f"  (cached: {oos_cache.name})")
    else:
        oos = walk_forward_oos(states, sample_every, rounds)
        oos.to_parquet(oos_cache)
    print(f"stage 2: fitting on {len(oos):,} OOS rows "
          f"({oos.season.min()}-{oos.season.max()})")

    # Era drift in shape (see config): the most recent OOS seasons set the
    # Stage 2 distribution; thin cells back off to the ALL-HISTORY (mu, time)
    # cell (clock conditioning kept) before falling to mu-only.
    def _fit_on(part):
        return ScoreDistribution.fit(
            part["home_remaining_pts"].to_numpy(),
            part["home_remaining_hat"].to_numpy(),
            part["away_remaining_pts"].to_numpy(),
            part["away_remaining_hat"].to_numpy(),
            part["seconds_remaining"].to_numpy(),
            **STAGE2_FIT_KW)

    recent_seasons = sorted(oos.season.unique())[-STAGE2_RECENT_SEASONS:]
    print(f"stage 2 fit window: {recent_seasons} + all-history backoff, "
          f"smoothing {STAGE2_FIT_KW} (tuned on 2024, see tune_stage2)")
    dist = ScoreDistribution.compose(
        _fit_on(oos[oos.season.isin(recent_seasons)]), _fit_on(oos))
    print(f"stage 2 compose: {dist.meta['composed']}")
    thin = int((dist.counts < ScoreDistribution.MIN_CELL).sum())
    print(f"stage 2: {thin} of {dist.counts.size} cells fall back to the "
          f"mean-only pmf")

    save_models(models, ARTIFACT_DIR, meta={
        "train_seasons": list(TRAIN_SEASONS),
        "valid_seasons": list(VALID_SEASONS),
        "sample_every": sample_every,
        "rounds": rounds,
        "oos_mae_home": float(np.abs(resid_h).mean()),
        "oos_mae_away": float(np.abs(resid_a).mean()),
    })
    dist.save(ARTIFACT_DIR / "score_distribution.npz")
    print("rho by time bucket:", np.round(dist.rho, 3).tolist())

    imp = sorted(
        zip(models["home"].feature_name(),
            models["home"].feature_importance("gain")),
        key=lambda t: -t[1])[:12]
    total = sum(models["home"].feature_importance("gain"))
    print("top stage 1 (home) features by gain:")
    for name, gain in imp:
        print(f"  {name:28s} {100 * gain / max(total, 1):5.1f}%")

    return {"models": models, "dist": dist,
            "valid": valid, "holdout": holdout, "states": states}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--sample-every", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=700)
    args = ap.parse_args()
    if args.fit:
        fit(sample_every=args.sample_every, rounds=args.rounds)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
