"""A prop row missing a feature is not scored this pass. It is never zero-filled.

Every prop trainer drops a training row with ANY null feature
(build_*_training_dataset: ``df.dropna(subset=num_cols)``), so no prop model
has ever seen an incomplete row. The scorers nevertheless filled every null
with 0.0 before predicting -- and 0.0 is not "unknown", it is a value the
trees read. Measured 2026-09-10 on the live pitcher-K artifact
(docs/sessions/2026-09.md, session 278): a game with no weather row was priced
as a 0°F game, lambda fell from 5.91 to 5.17, and P(under 6.5) rose from
0.621 to 0.736 -- reproduced to four decimals against the stored pick. A
pitcher with no Savant row was priced as a 0% strikeout rate at 0 mph.

The rule now: a row with a missing feature is dropped from THIS pass, with the
player and the feature named in the log, and is rebuilt on the next one. The
one declared exception is the umpire pair, which MLB posts after the early
passes run and which every training row carried; they are imputed BY NAME to
the league-average value, not by a fill that applies to everything.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

ROOT = Path(__file__).parent.parent

FEATURES = ["k_last3_avg", "savant_k_pct", "temp_f", "ump_k_plus_minus"]


def _frame(**overrides) -> pd.DataFrame:
    base = {
        "player_name":      ["Logan Gilbert", "Jacob deGrom"],
        "k_last3_avg":      [6.333, 5.667],
        "savant_k_pct":     [0.266, 0.299],
        "temp_f":           [67.3, 67.3],
        "ump_k_plus_minus": [0.4, -0.2],
    }
    base.update(overrides)
    return pd.DataFrame(base)


@pytest.fixture
def helper():
    from models.scorer import prop_feature_matrix
    return prop_feature_matrix


class TestARowMissingAFeatureIsNotScored:
    def test_a_missing_temperature_drops_the_row(self, helper):
        df, X = helper(_frame(temp_f=[np.nan, 67.3]), FEATURES, "mlb_prop_pitcher_k")
        assert df["player_name"].tolist() == ["Jacob deGrom"]
        assert X.shape == (1, len(FEATURES))
        assert not np.isnan(X).any()

    def test_nothing_is_zero_filled(self, helper):
        """The failure this guards: a NaN that reaches the model as 0.0."""
        df, X = helper(_frame(savant_k_pct=[np.nan, 0.299]), FEATURES, "mlb_prop_pitcher_k")
        assert "Logan Gilbert" not in df["player_name"].tolist()
        assert 0.0 not in X[:, FEATURES.index("savant_k_pct")]

    def test_a_complete_frame_is_untouched(self, helper):
        src = _frame()
        df, X = helper(src, FEATURES, "mlb_prop_pitcher_k")
        assert len(df) == 2
        np.testing.assert_allclose(X, src[FEATURES].values.astype(float))

    def test_a_feature_column_the_frame_lacks_drops_every_row(self, helper):
        """Fail CLOSED, and say so. Before, a feature the builder never
        produced scored as 0.0 for every player on the board."""
        from loguru import logger
        seen: list[str] = []
        sink = logger.add(lambda m: seen.append(m.record["message"]), level="WARNING")
        try:
            df, X = helper(_frame().drop(columns=["temp_f"]), FEATURES, "mlb_prop_pitcher_k")
        finally:
            logger.remove(sink)
        assert df.empty and X.shape[0] == 0
        assert any("temp_f" in m and "Logan Gilbert" in m for m in seen), seen
        assert any("2 of 2" in m for m in seen), seen

    def test_the_returned_frame_is_positionally_aligned_with_x(self, helper):
        """The loops index ``lambdas[i]`` by the iterrows position, so the
        frame handed back must carry a fresh RangeIndex after the drop."""
        df, X = helper(_frame(temp_f=[np.nan, 67.3]), FEATURES, "mlb_prop_pitcher_k")
        assert list(df.index) == list(range(len(df)))
        assert len(df) == X.shape[0]


class TestTheUmpireIsTheDeclaredException:
    def test_a_missing_umpire_is_imputed_to_league_average_not_dropped(self, helper):
        df, X = helper(_frame(ump_k_plus_minus=[np.nan, np.nan]), FEATURES, "mlb_prop_pitcher_k")
        assert len(df) == 2
        assert (X[:, FEATURES.index("ump_k_plus_minus")] == 0.0).all()

    def test_a_present_umpire_is_kept(self, helper):
        df, X = helper(_frame(), FEATURES, "mlb_prop_pitcher_k")
        np.testing.assert_allclose(X[:, FEATURES.index("ump_k_plus_minus")], [0.4, -0.2])

    def test_the_exception_list_is_the_umpire_pair_and_nothing_else(self):
        from models.scorer import PROP_IMPUTED_FEATURES
        assert set(PROP_IMPUTED_FEATURES) == {"ump_k_plus_minus", "ump_bb_plus_minus"}
        assert all(v == 0.0 for v in PROP_IMPUTED_FEATURES.values())


class TestEveryPropLoopGoesThroughTheHelper:
    """A source tripwire. The behavioural tests above prove the helper; this
    proves the four prop loops (MLB pitcher, MLB batter, WNBA, NBA) call it
    and that no loop kept its own fill."""

    def test_no_prop_loop_fills_nulls_itself(self):
        src = (ROOT / "models" / "scorer.py").read_text(encoding="utf-8")
        assert "np.nan_to_num(X_raw, nan=0.0)" not in src
        assert "np.nan_to_num(df[feature_cols].values.astype(float), nan=0.0)" not in src

    def test_the_four_loops_call_it(self):
        src = (ROOT / "models" / "scorer.py").read_text(encoding="utf-8")
        assert src.count("prop_feature_matrix(df, feature_cols, model_id)") >= 4
