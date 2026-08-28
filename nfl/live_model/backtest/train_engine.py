"""
Fit the engine: Stage 1 remaining-points models, then Stage 2 residuals.

    python -m live_model.backtest.train_engine --fit

Walk-forward by design. Stage 2's residual distribution MUST be fitted on
OUT-OF-SAMPLE Stage 1 predictions, not in-sample ones. An in-sample residual
is too tight, so the fitted distribution is too confident, so every downstream
market looks like it has an edge. That single mistake would make the whole
system look profitable and be worthless. Stage 1 trains on TRAIN_SEASONS and
Stage 2 is fitted on its predictions over VALID_SEASONS.
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from ..config import ARTIFACT_DIR, TRAIN_SEASONS, VALID_SEASONS, HOLDOUT_SEASONS
from ..engine.distribution import ScoreDistribution
from ..engine.remaining import (
    predict_remaining, save_models, train_remaining,
)

STATES_PATH = ARTIFACT_DIR / "states_all.parquet"


def load_states() -> pd.DataFrame:
    if not STATES_PATH.exists():
        raise FileNotFoundError(
            f"{STATES_PATH} missing. Build it with live_model.backtest.states."
        )
    return pd.read_parquet(STATES_PATH)


WF_FIRST_SEASON = 2018      # first season with enough prior data to predict


def walk_forward_oos(states: pd.DataFrame, sample_every: int,
                     rounds: int) -> pd.DataFrame:
    """
    Out-of-sample Stage 1 predictions for every season from WF_FIRST_SEASON on,
    each produced by a model trained ONLY on prior seasons.

    Stage 2 needs a lot of out-of-sample rows to populate its (mean, time)
    cells, and it needs them to be honestly out of sample. A single train/valid
    split gives one or the other, not both: two seasons of validation leaves
    the late-game cells nearly empty, and fitting Stage 2 on in-sample
    predictions makes the spread of actual-given-predicted too tight, which
    makes every derived market look more certain than it is. An expanding
    window gives both, at the cost of one fit per season.
    """
    frames = []
    seasons = sorted(s for s in states.season.unique()
                     if WF_FIRST_SEASON <= s <= max(VALID_SEASONS))
    for season in seasons:
        prior = states[states.season < season]
        cur = states[states.season == season]
        if prior.empty or cur.empty:
            continue
        models = train_remaining(prior.iloc[::sample_every], None, num_rounds=rounds)
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

    # Consecutive plays are near duplicates. Thinning cuts correlated rows and
    # fit time without touching the clock coverage.
    train_s = train.iloc[::sample_every]
    valid_s = valid.iloc[::sample_every]

    print(f"stage 1: train {len(train_s):,} rows "
          f"({min(TRAIN_SEASONS)}-{max(TRAIN_SEASONS)}), "
          f"valid {len(valid_s):,} rows ({VALID_SEASONS})")

    models = train_remaining(train_s, valid_s, num_rounds=rounds)

    pred_valid = predict_remaining(models, valid)
    resid_h = valid["home_remaining_pts"].to_numpy() - pred_valid["home_remaining_hat"].to_numpy()
    resid_a = valid["away_remaining_pts"].to_numpy() - pred_valid["away_remaining_hat"].to_numpy()
    print(f"stage 1 OOS mae home {np.abs(resid_h).mean():.3f} "
          f"away {np.abs(resid_a).mean():.3f}")

    print("stage 2: walk-forward out-of-sample predictions")
    oos = walk_forward_oos(states, sample_every, rounds)
    print(f"stage 2: fitting on {len(oos):,} out-of-sample rows "
          f"({oos.season.min()}-{oos.season.max()})")

    dist = ScoreDistribution.fit(
        oos["home_remaining_pts"].to_numpy(),
        oos["home_remaining_hat"].to_numpy(),
        oos["away_remaining_pts"].to_numpy(),
        oos["away_remaining_hat"].to_numpy(),
        oos["seconds_remaining"].to_numpy(),
    )
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
    print(f"artifacts -> {ARTIFACT_DIR}")

    imp = sorted(
        zip(models["home"].feature_name(),
            models["home"].feature_importance("gain")),
        key=lambda t: -t[1],
    )[:12]
    total = sum(v for _, v in
                zip(models["home"].feature_name(),
                    models["home"].feature_importance("gain")))
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
