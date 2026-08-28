"""
Stage 1: expected remaining points for each team, given the game state.

Two LightGBM regressors, home and away. Two rather than one symmetric model
because home field advantage is real and asymmetric, and because the away
model has to learn a different relationship to possession and the clock.

ONE feature definition, used by training, backtest and live serving. The
vectorised `build_features(df)` is canonical; `features_from_state` wraps a
single GameState into a one-row frame and calls the same function. Any other
arrangement is how train/serve skew gets in.

The interactions listed in the build spec are constructed EXPLICITLY rather
than left for the trees to find. score_diff x sqrt(time) is the shape of the
whole problem (a 7 point lead with 2 minutes left is a different animal from a
7 point lead in the first quarter) and handing it over directly costs nothing
and saves the model from having to approximate a curve with axis-aligned
splits.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

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
    "has_ball_away",
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
# League pace prior: a full regulation game runs roughly 130 scrimmage plays.
LEAGUE_PLAYS_PER_GAME = 130.0


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Vectorised feature construction. Input must already carry the pre-play
    state columns produced by backtest.states.build_states, or their live
    equivalents from features_from_state.
    """
    d = pd.DataFrame(index=df.index)

    secs = df["seconds_remaining"].astype(float).clip(lower=0, upper=GAME_SECONDS)
    elapsed = GAME_SECONDS - secs
    frac_elapsed = elapsed / GAME_SECONDS

    d["seconds_remaining"] = secs
    d["sqrt_seconds_remaining"] = np.sqrt(secs)
    d["period"] = df["qtr"].astype(float)
    d["clock_seconds"] = df["quarter_seconds_remaining"].astype(float)
    d["half_seconds_remaining"] = np.where(
        d["period"] <= 2,
        d["clock_seconds"] + (2 - d["period"]) * 900,
        d["clock_seconds"] + (4 - d["period"]) * 900,
    )

    home = df["home_score_pre"].astype(float)
    away = df["away_score_pre"].astype(float)
    d["home_score"] = home
    d["away_score"] = away
    d["score_diff"] = home - away
    d["total_points_so_far"] = home + away

    # The core interaction. sqrt(time) because the value of a lead decays
    # roughly with the square root of remaining possessions, not linearly.
    d["score_diff_x_sqrt_time"] = d["score_diff"] * np.sqrt(secs / GAME_SECONDS)
    d["score_diff_per_min"] = d["score_diff"] / np.maximum(secs / 60.0, 1.0)

    spread = df["pregame_spread"].astype(float)
    total = df["pregame_total"].astype(float)
    d["pregame_spread"] = spread
    d["pregame_total"] = total

    # The pregame number matters less as the game writes its own story. A
    # linear decay in elapsed time is the honest shape: at kickoff the market
    # number IS the estimate, at the two minute warning it is nearly irrelevant.
    d["spread_decayed"] = spread * (1.0 - frac_elapsed)
    d["total_decayed"] = total * (1.0 - frac_elapsed)
    # What the pregame total says is still to come, prorated by clock. Gives
    # the model a sane baseline before it has any in-game evidence.
    d["expected_remaining_total"] = total * (secs / GAME_SECONDS)

    poss = df["posteam"] if "posteam" in df.columns else pd.Series(index=df.index, dtype=object)
    home_team = df["home_team"] if "home_team" in df.columns else pd.Series(index=df.index, dtype=object)
    has_home = poss.eq(home_team) & poss.notna()
    has_away = poss.notna() & ~has_home
    d["has_ball_home"] = has_home.astype(float)
    d["has_ball_away"] = has_away.astype(float)

    d["down"] = df["down"].astype(float)
    d["distance"] = df["ydstogo"].astype(float)
    yl = df["yardline_100"].astype(float)
    d["yardline_100"] = yl
    # Crude but monotone field position value: closer to the end zone is worth
    # more, and the last 20 yards are worth disproportionately more. The trees
    # can bend it; this just gives them a sensible axis.
    d["field_pos_value"] = np.where(yl.notna(), (100.0 - yl) / 100.0, np.nan)

    hto = df["home_timeouts_remaining"].astype(float)
    ato = df["away_timeouts_remaining"].astype(float)
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
    # Wind suppresses scoring through the passing game specifically. The wind
    # totals model in this package is built on exactly that mechanism, so the
    # live model gets the interaction rather than the two marginals.
    d["wind_x_pass_rate"] = d["wind_mph"] * ((hpr + apr) / 2.0)

    return d[FEATURES]


def features_from_state(state) -> pd.DataFrame:
    """One-row feature frame for a live GameState. Same code path as training."""
    poss_team = None
    if state.possession == "home":
        poss_team = "HOME"
    elif state.possession == "away":
        poss_team = "AWAY"

    row = {
        "seconds_remaining": state.seconds_remaining,
        "qtr": state.period,
        "quarter_seconds_remaining": state.clock_seconds,
        "home_score_pre": state.home_score,
        "away_score_pre": state.away_score,
        "pregame_spread": state.pregame_spread,
        "pregame_total": state.pregame_total,
        "posteam": poss_team,
        "home_team": "HOME",
        "down": np.nan if state.down is None else state.down,
        "ydstogo": np.nan if state.distance is None else state.distance,
        "yardline_100": np.nan if state.yardline_100 is None else state.yardline_100,
        "home_timeouts_remaining": state.home_timeouts,
        "away_timeouts_remaining": state.away_timeouts,
        "plays_run": state.plays_run,
        "home_pass_rate": state.home_pass_rate,
        "away_pass_rate": state.away_pass_rate,
        "wind_mph": np.nan if state.wind_mph is None else state.wind_mph,
        "is_dome": 1.0 if state.is_dome else 0.0,
    }
    return build_features(pd.DataFrame([row]))


# ------------------------------------------------------------------ training
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


def train_remaining(train_states: pd.DataFrame, valid_states: pd.DataFrame | None = None,
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
                reference=dtrain,
                free_raw_data=False,
            )
            valid_sets = [dvalid]
            cbs = [lgb.early_stopping(50, verbose=False)]
        params = dict(LGB_PARAMS, seed=seed)
        out[side] = lgb.train(params, dtrain, num_boost_round=num_rounds,
                              valid_sets=valid_sets, callbacks=cbs)
    return out


def predict_remaining(models: dict, states: pd.DataFrame) -> pd.DataFrame:
    """Expected remaining points per team. Clipped at zero, which is a floor
    the model has no way to violate meaningfully but a regression can."""
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
        json.dumps({"features": FEATURES, **(meta or {})}, indent=2)
    )


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
                "Retrain rather than serving a mismatched model."
            )
    return models
