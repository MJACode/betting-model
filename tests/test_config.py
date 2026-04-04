"""
test_config.py — Tests for central configuration constants and structure.
"""

from config import (
    MODELS,
    SPORTS,
    BET_EDGE_THRESHOLD,
    AVOID_EDGE_THRESHOLD,
    MAX_KELLY_FRACTION,
    MIN_GAMES_BASELINE,
    RETURN_RAMP,
)


def test_models_registry_has_seven_entries():
    assert len(MODELS) == 7


def test_models_include_expected_ids():
    expected = {
        "mlb_moneyline", "mlb_over_under", "mlb_runline",
        "nhl_moneyline", "nhl_moneyline_regulation", "nhl_over_under", "nhl_puckline",
    }
    assert set(MODELS.keys()) == expected


def test_models_map_to_known_sports():
    for model_id, (sport, market, desc) in MODELS.items():
        assert sport in ("MLB", "NHL"), f"{model_id} has unknown sport '{sport}'"


def test_models_have_non_empty_descriptions():
    for model_id, (sport, market, desc) in MODELS.items():
        assert desc, f"{model_id} has empty description"


def test_sports_has_mlb_and_nhl():
    assert "MLB" in SPORTS
    assert "NHL" in SPORTS


def test_sports_have_required_keys():
    required = {"odds_api_key", "seasons", "train_seasons", "test_season", "sbr_dir"}
    for sport, cfg in SPORTS.items():
        for key in required:
            assert key in cfg, f"{sport} missing key '{key}'"


def test_train_seasons_precede_test_season():
    for sport, cfg in SPORTS.items():
        assert max(cfg["train_seasons"]) < cfg["test_season"], \
            f"{sport}: train seasons should not include the test season"


def test_default_thresholds():
    assert BET_EDGE_THRESHOLD == 0.03
    assert AVOID_EDGE_THRESHOLD == 0.03
    assert MAX_KELLY_FRACTION == 0.05
    assert MIN_GAMES_BASELINE == 10


def test_return_ramp_stages_ordered():
    assert RETURN_RAMP["early"] < RETURN_RAMP["mid"] < RETURN_RAMP["full"]
    assert RETURN_RAMP["full"] == 1.0
    assert RETURN_RAMP["early"] > 0.0
