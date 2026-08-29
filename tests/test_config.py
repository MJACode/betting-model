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
    MODEL_EDGE_THRESHOLDS,
    RETURN_RAMP,
)


def test_models_include_expected_ids():
    expected = {
        # MLB full-game + F5
        "mlb_moneyline", "mlb_over_under", "mlb_runline",
        "mlb_f5_moneyline", "mlb_f5_over_under", "mlb_f5_runline",
        # NHL
        "nhl_moneyline", "nhl_moneyline_regulation", "nhl_over_under", "nhl_puckline",
        # WNBA
        "wnba_moneyline", "wnba_over_under", "wnba_spread",
        # NBA
        "nba_moneyline", "nba_over_under", "nba_spread",
        # UFC
        "ufc_moneyline", "ufc_total_rounds", "ufc_method_of_victory",
        # GOLF
        "golf_outright", "golf_top10", "golf_top20", "golf_make_cut", "golf_matchup",
        # NCAAF (spread + spread_premium are DISJOINT bands of one opener rule)
        "ncaaf_moneyline", "ncaaf_over_under", "ncaaf_spread",
        "ncaaf_spread_premium",
    }
    assert set(MODELS.keys()) == expected


def test_models_map_to_known_sports():
    for model_id, (sport, market, desc) in MODELS.items():
        assert sport in ("MLB", "NHL", "WNBA", "NBA", "UFC", "GOLF", "NCAAF"), f"{model_id} has unknown sport '{sport}'"


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
    # BET/AVOID_EDGE_THRESHOLD are the FALLBACK cut for a model with no entry in
    # MODEL_EDGE_THRESHOLDS. They were raised 0.03 -> 0.10 with the general
    # tightening; this test kept asserting 0.03 and has been the suite's one
    # standing failure ever since, which trained everyone to read a red suite as
    # normal. Assert the real value, and the invariant below is what actually
    # protects us.
    assert BET_EDGE_THRESHOLD == 0.10
    assert AVOID_EDGE_THRESHOLD == 0.10
    assert MAX_KELLY_FRACTION == 0.05
    assert MIN_GAMES_BASELINE == 10


def test_every_model_carries_its_own_thresholds():
    """The per-model cut is the swept, validated one; the module-level fallback
    is a number nobody chose for any particular market. A model that reaches
    production without its own entry would be scored against that fallback
    silently, so the fallback must stay unreachable."""
    from config import LIVE_MODELS, MODEL_PROB_THRESHOLDS, PROP_MODELS

    registered = set(MODELS) | set(PROP_MODELS) | set(LIVE_MODELS)
    assert not registered - set(MODEL_EDGE_THRESHOLDS), \
        f"no edge threshold: {sorted(registered - set(MODEL_EDGE_THRESHOLDS))}"
    assert not registered - set(MODEL_PROB_THRESHOLDS), \
        f"no prob threshold: {sorted(registered - set(MODEL_PROB_THRESHOLDS))}"


def test_return_ramp_stages_ordered():
    assert RETURN_RAMP["early"] < RETURN_RAMP["mid"] < RETURN_RAMP["full"]
    assert RETURN_RAMP["full"] == 1.0
    assert RETURN_RAMP["early"] > 0.0
