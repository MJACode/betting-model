"""
Stage 1: expected remaining points per team (NCAAF port).

Ported from nfl/live_model/engine/remaining.py; the feature rationale lives
there. Differences are the input schema (this reads the CFB states built by
ncaaf_live.backtest.states, which are already home/away relabelled and
pre-play) and the pace prior (CFB teams run more plays).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import LEAGUE_PLAYS_PER_GAME

FEATURES = [
    "seconds_remaining",
    "sqrt_seconds_remaining",
    "half_seconds_remaining",
    "period",
    "clock_seconds",
    "score_diff",
    "score_diff_x_sqrt_time",
    "score_diff_per_min",
    "home_score",
    "away_score",
    "total_points_so_far",
    "spread_decayed",
    "total_decayed",
    "pregame_spread",
    "pregame_total",
    "expected_remaining_total",
    "has_ball_home",
    "down",
    "distance",
    "yardline_100",
    "field_pos_value",
    "timeout_diff",
    "home_timeouts",
    "away_timeouts",
    "plays_run",
    "plays_per_min",
    "pace_ratio",
    "home_pass_rate",
    "away_pass_rate",
    "wind_mph",
    "is_dome",
    "wind_x_pass_rate",
]

TARGETS = ("home_remaining_pts", "away_remaining_pts")

GAME_SECONDS = 3600.0


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorised feature construction from the CFB state schema
    (ncaaf_live.backtest.states.build_states or the live equivalent).
    """
    d = pd.DataFrame(index=df.index)

    secs = df["seconds_remaining"].astype(float).clip(lower=0, upper=GAME_SECONDS)
    elapsed = GAME_SECONDS - secs
    frac_elapsed = elapsed / GAME_SECONDS

    d["seconds_remaining"] = secs
    d["sqrt_seconds_remaining"] = np.sqrt(secs)
    d["period"] = df["period"].astype(float)
    d["clock_seconds"] = df["clock_in_period"].astype(float)
    d["half_seconds_remaining"] = df["half_seconds_remaining"].astype(float)

    home = df["home_score"].astype(float)      # PRE-play by construction
    away = df["away_score"].astype(float)
    d["home_score"] = home
    d["away_score"] = away
    d["score_diff"] = home - away
    d["total_points_so_far"] = home + away

    # sqrt(time): the value of a lead decays with remaining possessions.
    d["score_diff_x_sqrt_time"] = d["score_diff"] * np.sqrt(secs / GAME_SECONDS)
    d["score_diff_per_min"] = d["score_diff"] / np.maximum(secs / 60.0, 1.0)

    spread = df["pregame_spread"].astype(float)
    total = df["pregame_total"].astype(float)
    d["pregame_spread"] = spread
    d["pregame_total"] = total
    d["spread_decayed"] = spread * (1.0 - frac_elapsed)
    d["total_decayed"] = total * (1.0 - frac_elapsed)
    d["expected_remaining_total"] = total * (secs / GAME_SECONDS)

    d["has_ball_home"] = df["has_ball_home"].astype(float)

    d["down"] = df["down"].astype(float)
    d["distance"] = df["distance"].astype(float)
    yl = df["yardline_100"].astype(float)
    d["yardline_100"] = yl
    d["field_pos_value"] = np.where(yl.notna(), (100.0 - yl) / 100.0, np.nan)

    hto = df["home_timeouts"].astype(float)
    ato = df["away_timeouts"].astype(float)
    d["home_timeouts"] = hto
    d["away_timeouts"] = ato
    d["timeout_diff"] = hto - ato

    plays = df["plays_run"].astype(float)
    d["plays_run"] = plays
    d["plays_per_min"] = plays / np.maximum(elapsed / 60.0, 1.0)
    expected_plays = LEAGUE_PLAYS_PER_GAME * frac_elapsed
    d["pace_ratio"] = plays / np.maximum(expected_plays, 1.0)

    hpr = df["home_pass_rate"].astype(float)
    apr = df["away_pass_rate"].astype(float)
    d["home_pass_rate"] = hpr
    d["away_pass_rate"] = apr

    wind = df["wind_mph"].astype(float)
    dome = df["is_dome"].astype(float)
    d["wind_mph"] = np.where(dome > 0, 0.0, wind)
    d["is_dome"] = dome
    d["wind_x_pass_rate"] = d["wind_mph"] * ((hpr + apr) / 2.0)

    return d[FEATURES]


LGB_PARAMS = dict(
    objective="regression",
    metric="l2",
    learning_rate=0.05,
    num_leaves=63,
    min_data_in_leaf=200,
    feature_fraction=0.85,
    bagging_fraction=0.85,
    bagging_freq=1,
    lambda_l2=1.0,
    verbose=-1,
)


def train_remaining(train_states: pd.DataFrame,
                    valid_states: pd.DataFrame | None = None,
                    num_rounds: int = 700, seed: int = 7):
    """Fit both regressors. Returns {'home': booster, 'away': booster}."""
    import lightgbm as lgb

    X = build_features(train_states)
    out = {}
    for side, target in zip(("home", "away"), TARGETS):
        y = train_states[target].astype(float)
        dtrain = lgb.Dataset(X, label=y, free_raw_data=False)
        valid_sets, cbs = [], []
        if valid_states is not None and len(valid_states):
            dvalid = lgb.Dataset(
                build_features(valid_states),
                label=valid_states[target].astype(float),
                reference=dtrain, free_raw_data=False)
            valid_sets = [dvalid]
            cbs = [lgb.early_stopping(50, verbose=False)]
        params = dict(LGB_PARAMS, seed=seed)
        out[side] = lgb.train(params, dtrain, num_boost_round=num_rounds,
                              valid_sets=valid_sets, callbacks=cbs)
    return out


def predict_remaining(models: dict, states: pd.DataFrame) -> pd.DataFrame:
    X = build_features(states)
    return pd.DataFrame({
        "home_remaining_hat": np.maximum(models["home"].predict(X), 0.0),
        "away_remaining_hat": np.maximum(models["away"].predict(X), 0.0),
    }, index=states.index)


def save_models(models: dict, out_dir: Path, meta: dict | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for side, booster in models.items():
        booster.save_model(str(out_dir / f"remaining_{side}.txt"))
    (out_dir / "remaining_meta.json").write_text(
        json.dumps({"features": FEATURES, **(meta or {})}, indent=2))


def load_models(out_dir: Path) -> dict:
    import lightgbm as lgb
    models = {}
    for side in ("home", "away"):
        path = out_dir / f"remaining_{side}.txt"
        if not path.exists():
            raise FileNotFoundError(f"{path} missing. Train Stage 1 first.")
        models[side] = lgb.Booster(model_file=str(path))
    meta_path = out_dir / "remaining_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("features") != FEATURES:
            raise RuntimeError(
                "Stage 1 artifact was trained on a different feature list. "
                "Retrain rather than serving a mismatched model.")
    return models
