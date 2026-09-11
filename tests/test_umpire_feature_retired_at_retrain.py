"""The umpire features leave the pitcher-K and walks models at their next retrain.

Decided 2026-09-10 (session 278, mike: "ship a fix ... and any other bugs like
the umpire one"). The evidence:

- A BET locks at its first signal, and the first signal is the evening
  look-ahead pass or the first same-day pass -- both before MLB posts the
  home-plate umpire. So at the moment a bet is made the feature is ALWAYS the
  imputed league-average 0.0 (models.scorer.PROP_IMPUTED_FEATURES). Every
  training row carried the real value. A feature that is real in training
  and constant at decision time is a train/score mismatch that no imputation
  closes; making training match production means imputing 0.0 for every
  training row, which is the same as dropping it.
- It never carried signal: 3.6% importance on the live artifact, and the v2
  retrain note in docs/sports/mlb.md: "did NOT appear in top features --
  career-average encoding too coarse to add signal".

Mechanics: the LIVE artifacts still list the features, and the scoring
builder must keep producing the columns for them (the scorer reads the
artifact's feature_cols). So the drop applies to the TRAINING path only --
`training_feature_cols(model_id)` -- and the next
`python -m models.trainer --model mlb_prop_pitcher_k` (and `_walks`)
produces an artifact without it. Nothing changes for the artifact in
production until that retrain lands and is committed.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTheDropIsDeclared:
    def test_the_two_umpire_features_and_nothing_else(self):
        from features.prop_feature_engine import PENDING_RETRAIN_DROP_FEATURES
        assert PENDING_RETRAIN_DROP_FEATURES == {
            "mlb_prop_pitcher_k":     ["ump_k_plus_minus"],
            "mlb_prop_pitcher_walks": ["ump_bb_plus_minus"],
        }

    def test_every_dropped_feature_is_one_the_scorer_imputes(self):
        """A dropped feature must be one the live artifact can still be fed
        (imputed) until the retrain lands; otherwise the drop would have to
        wait for the retrain and the two would be coupled."""
        from features.prop_feature_engine import PENDING_RETRAIN_DROP_FEATURES
        from models.scorer import PROP_IMPUTED_FEATURES
        for cols in PENDING_RETRAIN_DROP_FEATURES.values():
            for c in cols:
                assert c in PROP_IMPUTED_FEATURES, c


class TestTrainingExcludesThemAndScoringDoesNot:
    def test_training_feature_cols_drops_them(self):
        from features.prop_feature_engine import training_feature_cols
        k = training_feature_cols("mlb_prop_pitcher_k")
        w = training_feature_cols("mlb_prop_pitcher_walks")
        assert "ump_k_plus_minus" not in k
        assert "ump_bb_plus_minus" not in w

    def test_every_other_feature_survives_in_order(self):
        from features.prop_feature_engine import PROP_FEATURE_MAP, training_feature_cols
        full = PROP_FEATURE_MAP["mlb_prop_pitcher_k"]
        assert training_feature_cols("mlb_prop_pitcher_k") == [c for c in full if c != "ump_k_plus_minus"]

    def test_a_model_with_nothing_pending_is_unchanged(self):
        from features.prop_feature_engine import PROP_FEATURE_MAP, training_feature_cols
        assert training_feature_cols("mlb_prop_pitcher_hits") == PROP_FEATURE_MAP["mlb_prop_pitcher_hits"]

    def test_the_scoring_map_still_carries_them_for_the_live_artifacts(self):
        """build_pitcher_scoring_rows keeps only PROP_FEATURE_MAP columns; the
        live artifacts list the umpire features, so the map must too until
        the retrained artifacts are committed."""
        from features.prop_feature_engine import PROP_FEATURE_MAP
        assert "ump_k_plus_minus" in PROP_FEATURE_MAP["mlb_prop_pitcher_k"]
        assert "ump_bb_plus_minus" in PROP_FEATURE_MAP["mlb_prop_pitcher_walks"]

    def test_the_training_dataset_builder_uses_the_training_list(self):
        from features.prop_feature_engine import build_prop_training_dataset
        src = inspect.getsource(build_prop_training_dataset)
        assert "training_feature_cols(model_id)" in src

    def test_the_trainer_uses_the_training_list_for_mlb_props(self):
        from models.trainer import train_prop_model
        src = inspect.getsource(train_prop_model)
        assert "training_feature_cols(model_id)" in src
        assert "feature_cols     = PROP_FEATURE_MAP[model_id]" not in src
