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


# ── Per-model EV floors (mike, 2026-09-20: "each model will need its own
# floor"). These four pin the ways the widened MODEL_OWN_EV_FLOOR can go wrong.
def test_own_ev_floor_and_model_min_ev_stay_disjoint():
    """min_ev_for returns MODEL_OWN_EV_FLOOR OUTRIGHT, so an entry in both
    dicts silently overrides a swept floor. The three live models whose floors
    were swept on their own settled records must never appear in the first."""
    import config

    overlap = set(config.MODEL_OWN_EV_FLOOR) & set(config.MODEL_MIN_EV)
    assert not overlap, (
        f"{sorted(overlap)} carry both an own floor and a MODEL_MIN_EV entry; "
        "the own floor wins and the swept number is discarded"
    )
    for model_id, swept in config.MODEL_MIN_EV.items():
        assert config.min_ev_for(model_id) == max(config.GLOBAL_MIN_EV, swept)


def test_no_own_floor_tightens_a_model_past_the_global_floor():
    """The dict exists to let a model bet BELOW the global floor. An entry
    above it would be a tightening smuggled in as a restoration.

    Read from the environment rather than config.GLOBAL_MIN_EV: the autouse
    _platform_gates_at_identity fixture patches that attribute to -1.0 for
    every test in this directory, so the live number is not visible here.
    """
    import os

    import config

    live_floor = float(os.environ.get("GLOBAL_MIN_EV", "0.20"))
    too_tight = {
        m: ev for m, ev in config.MODEL_OWN_EV_FLOOR.items() if ev > live_floor
    }
    assert not too_tight, f"{too_tight} sit above the global floor {live_floor}"


def test_only_a_market_priced_model_carries_a_negative_floor():
    """A floor below zero would enshrine betting a quote the juice has eaten.
    mlb_prop_pitcher_hits, mlb_prop_pitcher_k and mlb_spread_market have all
    written negative-EV bets and are floored at 0.00 rather than at their own
    minimum -- the one deliberate tightening in the dict.

    mlb_total_public_fade is the single exception: its model probability is the
    market's own implied probability, so EV is zero by construction (all 37
    bets fall in -0.0001..+0.0001) and a 0.00 floor drops half its card on the
    sign of a rounding error. Any OTHER negative entry is a bug.
    """
    import config

    negative = {m: ev for m, ev in config.MODEL_OWN_EV_FLOOR.items() if ev < 0}
    assert set(negative) <= {"mlb_total_public_fade"}, (
        f"{negative} would permit negative-EV bets"
    )
    for model_id in ("mlb_prop_pitcher_hits", "mlb_prop_pitcher_k",
                     "mlb_spread_market"):
        assert config.MODEL_OWN_EV_FLOOR[model_id] == 0.00


def test_models_on_own_probability_is_not_derived_from_the_floor_dict():
    """These were one expression while the floor dict held exactly these two.
    Widening the floors must not take 36 more models off the calibration map."""
    import config

    assert config.MODELS_ON_OWN_PROBABILITY == frozenset(
        {"nfl_wind_totals", "nfl_opener_spread"}
    )


def test_every_own_floor_names_a_live_model():
    """A floor for a retired or misspelt model is dead config that reads as
    cover. Retired models are gone from the registry and carry no floor."""
    import config

    unknown = [m for m in config.MODEL_OWN_EV_FLOOR if m not in config.ACTION_THRESHOLDS]
    assert not unknown, f"{unknown} carry a floor but are not registered models"
    retired = [m for m in config.MODEL_OWN_EV_FLOOR if m in config.RETIRED_MODELS]
    assert not retired, f"{retired} are retired and should carry no floor"


def test_the_models_the_global_floor_silently_removed_can_bet_again():
    """The three models GLOBAL_MIN_EV=0.20 switched off on 2026-09-19.

    Measured 2026-09-20 over every BET each has written: mlb_spread_market
    -0.034..+0.026 (25), mlb_total_public_fade exactly 0.000 (37),
    nfl_live_prop +0.062..+0.231 (12). Not one of the 74 clears 0.20, so under
    the global floor alone each is permanently unable to place a bet -- and
    none of the three writes a row when it finds nothing, so it goes dark
    without a trace. Their own floors must sit at or under their own smallest
    written bet.
    """
    import os

    import config

    # The autouse _platform_gates_at_identity fixture patches GLOBAL_MIN_EV to
    # -1.0, which would make every model look unblocked. Put the live number
    # back for the length of this test, or it proves nothing.
    live_floor = float(os.environ.get("GLOBAL_MIN_EV", "0.20"))
    original = config.GLOBAL_MIN_EV
    config.GLOBAL_MIN_EV = live_floor
    try:
        for model_id, smallest_written in (
            ("mlb_spread_market", 0.00),  # negative min, floored at zero
            ("mlb_total_public_fade", 0.00),
            ("nfl_live_prop", 0.062),
        ):
            assert config.min_ev_for(model_id) <= smallest_written, (
                f"{model_id} cannot place the smallest bet it has ever written"
            )
    finally:
        config.GLOBAL_MIN_EV = original


def test_an_own_floor_does_not_take_a_model_off_the_calibration_map():
    """Carrying an own EV floor and deciding on the model's OWN probability
    were one expression until 2026-09-20. They are separate questions: where a
    model's edges sit, versus whether its calibration map can be trusted. Every
    model but the two NFL rules keeps the promoted map."""
    import config

    assert "mlb_moneyline" in config.MODEL_OWN_EV_FLOOR
    assert "mlb_moneyline" not in config.MODELS_ON_OWN_PROBABILITY
    on_own_but_not_a_rule = config.MODELS_ON_OWN_PROBABILITY - {
        "nfl_wind_totals", "nfl_opener_spread"
    }
    assert not on_own_but_not_a_rule
