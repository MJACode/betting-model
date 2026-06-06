"""Pure-function tests for features/live_game_features.py (no DB)."""

from features.live_game_features import (
    bases_code, state_cols, LIVE_FEATURE_MAP, LIVE_STATE_FEATURES,
)


def test_bases_code_enum():
    assert bases_code("000") == 0
    assert bases_code("100") == 1   # runner on first
    assert bases_code("010") == 2   # runner on second
    assert bases_code("110") == 3
    assert bases_code("001") == 4   # runner on third
    assert bases_code("101") == 5
    assert bases_code("011") == 6
    assert bases_code("111") == 7   # bases loaded


def test_bases_code_handles_bad_input():
    assert bases_code("") == 0
    assert bases_code(None) == 0


def test_state_cols_basic():
    st = state_cols(inning=3, inning_half="top", outs=2, bases_state="101",
                    home_score=4, away_score=2)
    assert st["inning"] == 3
    assert st["inning_half_top"] == 1
    assert st["home_batting"] == 0
    assert st["outs"] == 2
    assert st["bases_code"] == 5
    assert st["score_diff"] == 2
    assert st["abs_score_diff"] == 2
    assert st["current_total_runs"] == 6


def test_state_cols_bottom_half_and_negative_diff():
    st = state_cols(inning=7, inning_half="bottom", outs=0, bases_state="000",
                    home_score=1, away_score=5)
    assert st["inning_half_top"] == 0
    assert st["home_batting"] == 1
    assert st["score_diff"] == -4
    assert st["abs_score_diff"] == 4


def test_feature_map_includes_state_and_pregame():
    for model_id in ("mlb_live_moneyline", "mlb_live_over_under"):
        cols = LIVE_FEATURE_MAP[model_id]
        # every state feature is present, and there is pre-game context layered on
        for c in LIVE_STATE_FEATURES:
            assert c in cols
        assert len(cols) > len(LIVE_STATE_FEATURES)
    # totals model carries the pre-game market total as context
    assert "total_line" in LIVE_FEATURE_MAP["mlb_live_over_under"]
