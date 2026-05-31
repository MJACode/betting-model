"""
test_feature_engine.py — Tests for feature engineering pure functions.
"""

import pytest

from features.feature_engine import (
    _compute_injury_adjustment,
    _has_starter_out,
    _has_returnee,
    _compute_target,
    _market_for_odds,
    FEATURE_MAP,
)


# ── _compute_injury_adjustment ─────────────────────────────────────────────────

class TestComputeInjuryAdjustment:
    def test_no_injuries_returns_zero(self):
        assert _compute_injury_adjustment([]) == 0.0

    def test_scenario_a_uses_severity_weight(self):
        injuries = [{"scenario": "A", "severity_weight": 1.0}]
        assert _compute_injury_adjustment(injuries) == pytest.approx(1.0)

    def test_scenario_a_dtd_weight(self):
        injuries = [{"scenario": "A", "severity_weight": 0.7}]
        assert _compute_injury_adjustment(injuries) == pytest.approx(0.7)

    def test_scenario_b_ramp_070_gives_030_penalty(self):
        # player at early ramp (0.70) → penalty = 1.0 - 0.70 = 0.30
        injuries = [{"scenario": "B", "return_ramp_factor": 0.70, "severity_weight": 1.0}]
        assert _compute_injury_adjustment(injuries) == pytest.approx(0.30, rel=1e-5)

    def test_scenario_b_ramp_085_gives_015_penalty(self):
        injuries = [{"scenario": "B", "return_ramp_factor": 0.85, "severity_weight": 1.0}]
        assert _compute_injury_adjustment(injuries) == pytest.approx(0.15, rel=1e-5)

    def test_scenario_b_full_ramp_gives_no_penalty(self):
        injuries = [{"scenario": "B", "return_ramp_factor": 1.00, "severity_weight": 1.0}]
        assert _compute_injury_adjustment(injuries) == pytest.approx(0.0, abs=1e-9)

    def test_scenario_c_is_ignored(self):
        # Scenario C (opponent edge) is handled separately at game level
        injuries = [{"scenario": "C", "severity_weight": 1.0}]
        assert _compute_injury_adjustment(injuries) == 0.0

    def test_multiple_scenario_a_injuries_summed(self):
        injuries = [
            {"scenario": "A", "severity_weight": 1.0},
            {"scenario": "A", "severity_weight": 0.7},
        ]
        assert _compute_injury_adjustment(injuries) == pytest.approx(1.7)

    def test_mixed_a_and_b_scenarios(self):
        injuries = [
            {"scenario": "A", "severity_weight": 1.0},
            {"scenario": "B", "return_ramp_factor": 0.85, "severity_weight": 0.9},
        ]
        # A: 1.0, B: 1.0 - 0.85 = 0.15 → total = 1.15
        assert _compute_injury_adjustment(injuries) == pytest.approx(1.15)

    def test_result_is_rounded_to_3_decimal_places(self):
        injuries = [{"scenario": "A", "severity_weight": 0.333}]
        result = _compute_injury_adjustment(injuries)
        assert result == round(result, 3)


# ── _has_starter_out ──────────────────────────────────────────────────────────

class TestHasStarterOut:
    def test_no_injuries_returns_0(self):
        assert _has_starter_out([], "MLB") == 0

    def test_il60_scenario_a_high_severity_triggers(self):
        injuries = [{"status": "IL60", "scenario": "A", "severity_weight": 1.0}]
        assert _has_starter_out(injuries, "MLB") == 1

    def test_il15_scenario_a_high_severity_triggers(self):
        injuries = [{"status": "IL15", "scenario": "A", "severity_weight": 0.9}]
        assert _has_starter_out(injuries, "MLB") == 1

    def test_il10_severity_08_triggers(self):
        injuries = [{"status": "IL10", "scenario": "A", "severity_weight": 0.8}]
        assert _has_starter_out(injuries, "MLB") == 1

    def test_il10_severity_07_does_not_trigger(self):
        # severity_weight < 0.8 → not counted as starter
        injuries = [{"status": "IL10", "scenario": "A", "severity_weight": 0.7}]
        assert _has_starter_out(injuries, "MLB") == 0

    def test_out_status_high_severity_triggers(self):
        injuries = [{"status": "Out", "scenario": "A", "severity_weight": 0.9}]
        assert _has_starter_out(injuries, "MLB") == 1

    def test_scenario_b_does_not_trigger(self):
        # Return-ramp players are not counted as "out"
        injuries = [{"status": "IL60", "scenario": "B", "severity_weight": 1.0}]
        assert _has_starter_out(injuries, "MLB") == 0

    def test_nhl_goalie_out(self):
        injuries = [{"status": "IL15", "scenario": "A", "severity_weight": 0.9}]
        assert _has_starter_out(injuries, "NHL") == 1


# ── _has_returnee ─────────────────────────────────────────────────────────────

class TestHasReturnee:
    def test_empty_returns_0(self):
        assert _has_returnee([]) == 0

    def test_scenario_b_returns_1(self):
        assert _has_returnee([{"scenario": "B"}]) == 1

    def test_scenario_a_returns_0(self):
        assert _has_returnee([{"scenario": "A"}]) == 0

    def test_scenario_c_returns_0(self):
        assert _has_returnee([{"scenario": "C"}]) == 0

    def test_mixed_a_and_b_returns_1(self):
        injuries = [{"scenario": "A"}, {"scenario": "B"}]
        assert _has_returnee(injuries) == 1

    def test_multiple_a_only_returns_0(self):
        injuries = [{"scenario": "A"}, {"scenario": "A"}]
        assert _has_returnee(injuries) == 0


# ── _compute_target ────────────────────────────────────────────────────────────

class TestComputeTarget:
    # h2h (full-game moneyline)

    def test_h2h_home_win(self):
        result = _compute_target(
            "mlb_moneyline", "h2h",
            home_score=5, away_score=3,
            home_win=1, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=None
        )
        assert result == 1

    def test_h2h_away_win(self):
        result = _compute_target(
            "mlb_moneyline", "h2h",
            home_score=2, away_score=5,
            home_win=0, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=None
        )
        assert result == 0

    def test_h2h_no_scores_returns_none(self):
        result = _compute_target(
            "mlb_moneyline", "h2h",
            home_score=None, away_score=None,
            home_win=None, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=None
        )
        assert result is None

    # h2h_3way (NHL regulation)

    def test_h2h_3way_home_wins_in_regulation(self):
        result = _compute_target(
            "nhl_moneyline_regulation", "h2h_3way",
            home_score=3, away_score=2,
            home_win=1, home_win_reg=1,
            went_to_ot=0, reg_tie=0, odds=None
        )
        assert result == 1

    def test_h2h_3way_away_wins_in_regulation(self):
        result = _compute_target(
            "nhl_moneyline_regulation", "h2h_3way",
            home_score=2, away_score=3,
            home_win=0, home_win_reg=0,
            went_to_ot=0, reg_tie=0, odds=None
        )
        assert result == 0

    # totals (over/under)

    def test_totals_over(self):
        odds = {"total_line": 8.5}
        result = _compute_target(
            "mlb_over_under", "totals",
            home_score=5, away_score=4,  # total=9 > 8.5
            home_win=1, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=odds
        )
        assert result == 1

    def test_totals_under(self):
        odds = {"total_line": 8.5}
        result = _compute_target(
            "mlb_over_under", "totals",
            home_score=3, away_score=4,  # total=7 < 8.5
            home_win=0, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=odds
        )
        assert result == 0

    def test_totals_exact_push_returns_none(self):
        odds = {"total_line": 7.0}
        result = _compute_target(
            "mlb_over_under", "totals",
            home_score=3, away_score=4,  # total=7 == 7.0
            home_win=0, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=odds
        )
        assert result is None

    def test_totals_no_odds_returns_none(self):
        result = _compute_target(
            "mlb_over_under", "totals",
            home_score=5, away_score=4,
            home_win=1, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=None
        )
        assert result is None

    # spreads (run/puck line)

    def test_spreads_home_covers_minus_1_5(self):
        odds = {"spread_home": -1.5}
        result = _compute_target(
            "mlb_runline", "spreads",
            home_score=5, away_score=3,  # margin=2, covered=2-1.5=0.5>0
            home_win=1, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=odds
        )
        assert result == 1

    def test_spreads_home_fails_to_cover(self):
        odds = {"spread_home": -1.5}
        result = _compute_target(
            "mlb_runline", "spreads",
            home_score=4, away_score=3,  # margin=1, covered=1-1.5=-0.5<0
            home_win=1, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=odds
        )
        assert result == 0

    def test_spreads_push_returns_none(self):
        odds = {"spread_home": -1.5}
        result = _compute_target(
            "mlb_runline", "spreads",
            home_score=4.5, away_score=3,  # margin=1.5, covered=1.5-1.5=0
            home_win=1, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=odds
        )
        assert result is None

    def test_spreads_no_odds_returns_none(self):
        result = _compute_target(
            "mlb_runline", "spreads",
            home_score=5, away_score=3,
            home_win=1, home_win_reg=None,
            went_to_ot=0, reg_tie=0, odds=None
        )
        assert result is None


# ── _market_for_odds ──────────────────────────────────────────────────────────

class TestMarketForOdds:
    def test_known_markets_pass_through(self):
        assert _market_for_odds("h2h") == "h2h"
        assert _market_for_odds("h2h_3way") == "h2h_3way"
        assert _market_for_odds("totals") == "totals"
        assert _market_for_odds("spreads") == "spreads"

    def test_unknown_market_passes_through(self):
        assert _market_for_odds("unknown") == "unknown"


# ── FEATURE_MAP ────────────────────────────────────────────────────────────────

class TestFeatureMap:
    def test_all_models_present(self):
        expected = {
            # MLB full-game + F5
            "mlb_moneyline", "mlb_over_under", "mlb_runline",
            "mlb_f5_moneyline", "mlb_f5_over_under", "mlb_f5_runline",
            # NHL
            "nhl_moneyline", "nhl_moneyline_regulation",
            "nhl_over_under", "nhl_puckline",
            # WNBA
            "wnba_moneyline", "wnba_over_under", "wnba_spread",
        }
        assert set(FEATURE_MAP.keys()) == expected

    def test_feature_lists_are_non_empty(self):
        for model_id, cols in FEATURE_MAP.items():
            assert len(cols) > 0, f"{model_id} has empty feature list"

    def test_mlb_h2h_includes_injury_features(self):
        cols = FEATURE_MAP["mlb_moneyline"]
        assert "home_injury_adj" in cols
        assert "away_injury_adj" in cols
        assert "home_starter_out" in cols
        assert "is_early_season" in cols

    def test_nhl_h2h_includes_corsi_features(self):
        cols = FEATURE_MAP["nhl_moneyline"]
        assert "d_corsi_for_pct" in cols
        assert "d_xgf_pct" in cols

    def test_totals_models_include_absolute_values(self):
        # Totals models use absolute stats, not differentials
        mlb_cols = FEATURE_MAP["mlb_over_under"]
        assert "home_runs_per_game" in mlb_cols
        assert "away_runs_per_game" in mlb_cols

    def test_spreads_models_include_spread_feature(self):
        assert "spread_home" in FEATURE_MAP["mlb_runline"]
        assert "spread_home" in FEATURE_MAP["nhl_puckline"]
