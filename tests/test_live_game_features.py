"""
Pure-function tests for features/live_game_features.py (Phase 2b).
No DB, no network — mirrors the test style of test_mlb_pbp_ingestor.py.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.live_game_features import (
    LIVE_FEATURE_MAP,
    LIVE_STATE_FEATURES,
    build_live_state_row,
    compute_live_target,
    half_innings_left,
    parse_bases,
    state_features,
)
from config import LIVE_MODELS


# ── parse_bases ───────────────────────────────────────────────────────────────

def test_parse_bases_loaded():
    assert parse_bases("111") == (1, 1, 1)


def test_parse_bases_corners():
    assert parse_bases("101") == (1, 0, 1)


def test_parse_bases_empty_and_malformed():
    assert parse_bases("000") == (0, 0, 0)
    assert parse_bases(None) == (0, 0, 0)
    assert parse_bases("") == (0, 0, 0)
    assert parse_bases("10") == (0, 0, 0)


# ── half_innings_left ─────────────────────────────────────────────────────────

def test_half_innings_left_top_first():
    assert half_innings_left(1, True) == 18


def test_half_innings_left_bottom_ninth():
    assert half_innings_left(9, False) == 1


def test_half_innings_left_extras_clamps_to_one():
    assert half_innings_left(10, True) == 1
    assert half_innings_left(12, False) == 1


# ── state_features ────────────────────────────────────────────────────────────

def test_state_features_basic():
    st = state_features(5, "top", 2, "110", 4, 3)
    assert st == {
        "inning": 5, "is_top_inning": 1, "outs": 2,
        "on_1b": 1, "on_2b": 1, "on_3b": 0,
        "score_diff": 1, "total_runs": 7,
        "half_innings_left": 18 - 8,
    }


def test_state_features_bottom_half():
    st = state_features(3, "bottom", 0, "000", 0, 2)
    assert st["is_top_inning"] == 0
    assert st["score_diff"] == -2
    assert st["half_innings_left"] == 18 - 5


def test_state_features_unusable_returns_none():
    assert state_features(None, "top", 1, "000", 0, 0) is None
    assert state_features(4, "top", 1, "000", None, 0) is None


def test_state_features_outs_clamped():
    assert state_features(1, "top", 3, "000", 0, 0)["outs"] == 2
    assert state_features(1, "top", None, "000", 0, 0)["outs"] == 0


# ── compute_live_target ───────────────────────────────────────────────────────

def test_target_win_prob():
    assert compute_live_target("mlb_live_win_prob", 1, 5, 3, 4) == 1.0
    assert compute_live_target("mlb_live_win_prob", 0, 3, 5, 4) == 0.0
    assert compute_live_target("mlb_live_win_prob", None, 5, 3, 4) is None


def test_target_runline_home_by_two_plus():
    assert compute_live_target("mlb_live_runline", 1, 5, 3, 0) == 1.0   # by 2
    assert compute_live_target("mlb_live_runline", 1, 4, 3, 0) == 0.0   # by 1
    assert compute_live_target("mlb_live_runline", 0, 2, 6, 0) == 0.0


def test_target_total_runs_remaining():
    # Final 5-3 = 8 total, 4 already scored → 4 remaining
    assert compute_live_target("mlb_live_total_runs", 1, 5, 3, 4) == 4.0
    # State glitch (more runs before than final) → row dropped
    assert compute_live_target("mlb_live_total_runs", 1, 2, 1, 9) is None


def test_target_unknown_model_raises():
    with pytest.raises(ValueError):
        compute_live_target("mlb_moneyline", 1, 5, 3, 0)


# ── feature map / registry consistency ────────────────────────────────────────

def test_every_mlb_live_model_has_a_feature_map():
    # LIVE_FEATURE_MAP serves the MLB live loop only; the NCAAF live models
    # in LIVE_MODELS are served by the ncaaf_live/ package's own engine and
    # are in the registry for SETTLEMENT market mapping, not for this map.
    mlb_live = {m for m in LIVE_MODELS if m.startswith("mlb_live_")}
    assert mlb_live == set(LIVE_FEATURE_MAP.keys())
    for m in LIVE_MODELS:
        assert m.startswith(("mlb_live_", "ncaaf_live_")), (
            f"{m}: unknown live-model family — decide which engine serves it")


def test_feature_maps_start_with_state_features():
    for cols in LIVE_FEATURE_MAP.values():
        assert cols[:len(LIVE_STATE_FEATURES)] == LIVE_STATE_FEATURES


# ── build_live_state_row (serving path) ───────────────────────────────────────

def test_build_live_state_row_merges_pregame_context():
    state = {"inning": 6, "inning_half": "bottom", "outs": 1,
             "bases_state": "010", "home_score": 2, "away_score": 2}
    pregame = {"d_team_era": -0.4, "home_win_pct": 0.55, "away_win_pct": 0.48}
    row = build_live_state_row(state, pregame, "mlb_live_win_prob")
    assert row["inning"] == 6
    assert row["is_top_inning"] == 0
    assert row["on_2b"] == 1
    assert row["score_diff"] == 0
    assert row["d_team_era"] == -0.4
    # Context columns absent from pregame come through as None (XGBoost NaN)
    assert row["d_bullpen_era"] is None


def test_build_live_state_row_unusable_state():
    state = {"inning": None, "inning_half": "top", "outs": 0,
             "bases_state": "000", "home_score": 0, "away_score": 0}
    assert build_live_state_row(state, {}, "mlb_live_win_prob") is None
