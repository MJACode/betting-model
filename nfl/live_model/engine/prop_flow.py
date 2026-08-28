"""
Live player props, priced RELATIVE TO THE STARTING LINE.

THE THESIS, stated so it cannot drift again.
A book does not re-project a player from scratch when it reprices his prop
in-game. It re-anchors: it takes the number it opened, credits what he has
already produced, and prorates the rest by how much game is left. Roughly

    live_line  ~=  accrued  +  pregame_line * fraction_of_game_remaining

That is a MECHANICAL rule and it is blind to game flow. A back whose team went
up 17 will not get his prorated carries. A slot receiver whose team fell behind
by three scores will beat his prorated yardage badly. The edge is not speed and
it is not reacting to line movement. It is knowing WHERE that mechanical
re-anchoring is wrong, and by how much.

WHY THE FIRST VERSION OF THIS PACKAGE FAILED ITS GATE.
engine/props.py rebuilt the projection from first principles: remaining plays
times play mix times usage share times efficiency. That competes with the
market's own full-game projection instead of using it, and it lost, badly:
+45% bias on receiving yards. The pregame line is a season's worth of
information about a player, priced by people who do this professionally, handed
to us for free. Throwing it away and rederiving it from four carries is the
single worst modelling decision in this package.

So this module models the RESIDUAL:

    actual_remaining  =  f( naive_prorated_remaining,  game flow )

The anchor carries the level. The model only has to learn the deviation, which
is a far better conditioned problem and is exactly the quantity a bet needs.

This is the same shape as the opener model already validated in this repo:
there, bet when a soft book's number deviates from the sharp number by enough;
here, bet when our flow model deviates from the mechanically prorated number by
enough. Both are deviation-gated, and both are evaluated the same way.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

# Markets, and the accrual column each settles on.
FLOW_MARKETS = {
    "player_pass_yds": "pass_yds",
    "player_pass_attempts": "pass_att",
    "player_pass_completions": "pass_cmp",
    "player_rush_yds": "rush_yds",
    "player_rush_attempts": "rush_att",
    "player_reception_yds": "rec_yds",
    "player_receptions": "receptions",
}

FEATURES = [
    # The anchor. The book's number, reconstructed. Everything else in this
    # list exists to explain where it is wrong.
    "naive_remaining",
    "baseline_per_game",
    "frac_remaining",
    "accrued",
    # Pace of his own production against his own baseline. Running hot is
    # partly real (he is being fed) and partly mean reverting; the model has to
    # learn which, and that is not something a prorate can express.
    "accrued_vs_expected",
    "rate_ratio",
    # GAME FLOW. This is the whole thesis: the scoreboard rewrites who touches
    # the ball, and the mechanical line does not know that.
    "team_margin",
    "team_margin_x_frac",
    "trailing_by_two_scores",
    "leading_by_two_scores",
    "abs_margin",
    "seconds_remaining",
    "period",
    # Team level flow: how pass heavy the offence has actually been, and how
    # fast the game is going, both against expectation.
    "team_pass_rate",
    "pass_rate_vs_league",
    "pace_ratio",
    "team_plays_so_far",
    # The player's own share of the pool so far, which is the closest thing to
    # a role signal available in-game.
    "usage_share",
    "is_home",
    # Context the pregame line already priced, kept so the model can tell a
    # blowout it should have expected from one it should not.
    "pregame_total",
    "pregame_spread_team",
    "wind_mph",
    "is_dome",
]

LEAGUE_PASS_RATE = 0.575
LEAGUE_PLAYS_PER_GAME = 62.6        # per team, measured on 2023-2024


def naive_line(accrued: float, baseline_per_game: float,
               frac_remaining: float) -> float:
    """
    The book's number, reconstructed.

    This is deliberately the SIMPLEST mechanical rule, not an attempt to mimic
    any particular book exactly. If the real rule is slightly smarter, the
    measured edge shrinks; if we modelled a rule more sophisticated than the
    books actually use, the measured edge would be fiction. Erring toward the
    naive version is the conservative direction.
    """
    return float(accrued) + float(baseline_per_game) * float(frac_remaining)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Vectorised. One row per (player, state)."""
    d = pd.DataFrame(index=df.index)

    frac = df["frac_remaining"].astype(float).clip(0.0, 1.0)
    base = df["baseline_per_game"].astype(float)
    acc = df["accrued"].astype(float)

    d["frac_remaining"] = frac
    d["baseline_per_game"] = base
    d["accrued"] = acc
    d["naive_remaining"] = base * frac

    # How he is doing against his own pace. expected_by_now is what the
    # baseline says he should already have.
    expected_by_now = base * (1.0 - frac)
    d["accrued_vs_expected"] = acc - expected_by_now
    d["rate_ratio"] = np.where(expected_by_now > 0.5, acc / expected_by_now, 1.0)
    d["rate_ratio"] = np.clip(d["rate_ratio"], 0.0, 5.0)

    margin = df["team_margin"].astype(float)
    d["team_margin"] = margin
    d["team_margin_x_frac"] = margin * np.sqrt(frac)
    d["trailing_by_two_scores"] = (margin <= -9).astype(float)
    d["leading_by_two_scores"] = (margin >= 9).astype(float)
    d["abs_margin"] = margin.abs()

    d["seconds_remaining"] = df["seconds_remaining"].astype(float)
    d["period"] = df["qtr"].astype(float)

    tpr = df["team_pass_rate"].astype(float)
    d["team_pass_rate"] = tpr
    d["pass_rate_vs_league"] = tpr - LEAGUE_PASS_RATE

    plays = df["team_plays_so_far"].astype(float)
    d["team_plays_so_far"] = plays
    expected_plays = LEAGUE_PLAYS_PER_GAME * (1.0 - frac)
    d["pace_ratio"] = plays / np.maximum(expected_plays, 1.0)

    d["usage_share"] = df["usage_share"].astype(float)
    d["is_home"] = (df["team_side"] == "home").astype(float)
    d["pregame_total"] = df["pregame_total"].astype(float)
    d["pregame_spread_team"] = df["pregame_spread_team"].astype(float)
    d["wind_mph"] = df["wind_mph"].astype(float).fillna(0.0)
    d["is_dome"] = df["is_dome"].astype(float)
    return d[FEATURES]


LGB_PARAMS = dict(
    objective="regression",
    metric="l2",
    learning_rate=0.05,
    num_leaves=31,
    min_data_in_leaf=150,
    feature_fraction=0.85,
    bagging_fraction=0.85,
    bagging_freq=1,
    lambda_l2=2.0,
    verbose=-1,
    # 0 is LightGBM's "one thread per detected core", which is right on a
    # workstation and wrong in a container: OpenMP counts the host's cores
    # while the cgroup hands out a fraction of them, so the default
    # oversubscribes badly and can stop making progress altogether. Set
    # LGB_NUM_THREADS to the container's real CPU allowance.
    num_threads=int(os.getenv("LGB_NUM_THREADS", "0")),
)


def train_flow(train: pd.DataFrame, valid: pd.DataFrame | None = None,
               rounds: int = 500, seed: int = 5, features: list | None = None):
    """
    Fit the deviation model for one market.

    The target is actual remaining production. The naive prorate is a FEATURE,
    not a subtracted offset, so the model can learn that the anchor is more
    trustworthy in some states than others rather than being forced to treat it
    as unbiased everywhere.
    """
    import lightgbm as lgb
    cols = features or FEATURES
    X = build_features(train)[cols]
    y = train["actual_remaining"].astype(float)
    dtrain = lgb.Dataset(X, label=y, free_raw_data=False)
    valid_sets, cbs = [], []
    if valid is not None and len(valid):
        dvalid = lgb.Dataset(build_features(valid)[cols],
                             label=valid["actual_remaining"].astype(float),
                             reference=dtrain, free_raw_data=False)
        valid_sets, cbs = [dvalid], [lgb.early_stopping(40, verbose=False)]
    return lgb.train(dict(LGB_PARAMS, seed=seed), dtrain, num_boost_round=rounds,
                     valid_sets=valid_sets, callbacks=cbs)


def predict_flow(model, df: pd.DataFrame, features: list | None = None) -> np.ndarray:
    return np.maximum(model.predict(build_features(df)[features or FEATURES]), 0.0)


def save_flow(models: dict, out_dir: Path, meta: dict | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for market, booster in models.items():
        booster.save_model(str(out_dir / f"flow_{market}.txt"))
    (out_dir / "flow_meta.json").write_text(
        json.dumps({"features": FEATURES, **(meta or {})}, indent=2))


def load_flow(out_dir: Path) -> dict:
    import lightgbm as lgb
    models = {}
    for market in FLOW_MARKETS:
        path = out_dir / f"flow_{market}.txt"
        if path.exists():
            models[market] = lgb.Booster(model_file=str(path))
    if not models:
        raise FileNotFoundError(f"no flow models in {out_dir}; train them first")
    meta_path = out_dir / "flow_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        if meta.get("features") != FEATURES:
            raise RuntimeError(
                "flow artifact was trained on a different feature list. "
                "Retrain rather than serving a mismatched model.")
    return models
