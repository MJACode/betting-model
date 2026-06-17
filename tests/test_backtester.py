"""
test_backtester.py — Tests for backtesting: P&L evaluation, calibration
metrics, and go-live gate assessment.
"""

import pytest
import numpy as np
import pandas as pd

from models.backtester import (
    _calibration_error,
    _evaluate_result,
    compute_backtest_summary,
    _iter_sides,
    GO_LIVE_MIN_PICKS,
    GO_LIVE_MIN_ROI,
    GO_LIVE_MAX_CAL_ERR,
)


# ── _calibration_error ────────────────────────────────────────────────────────

class TestCalibrationError:
    def test_perfect_calibration_50_50(self):
        # All probs = 0.5, outcomes exactly 50% wins → error = 0
        probs = np.full(100, 0.5)
        outcomes = np.array([1, 0] * 50)
        error = _calibration_error(probs, outcomes)
        assert error == pytest.approx(0.0, abs=1e-9)

    def test_overconfident_model(self):
        # Predict 0.9 probability but all outcomes are 0 → error ≈ 0.9
        probs = np.full(30, 0.9)
        outcomes = np.zeros(30)
        error = _calibration_error(probs, outcomes)
        assert error > 0.8

    def test_underconfident_model(self):
        # Predict 0.1 probability but all outcomes are 1 → error ≈ 0.9
        probs = np.full(30, 0.1)
        outcomes = np.ones(30)
        error = _calibration_error(probs, outcomes)
        assert error > 0.8

    def test_returns_float(self):
        probs = np.array([0.5] * 20)
        outcomes = np.array([1, 0] * 10)
        error = _calibration_error(probs, outcomes)
        assert isinstance(error, float)
        assert error >= 0.0

    def test_small_bins_skipped(self):
        # Only 2 samples — both below the min-3-per-bin threshold
        probs = np.array([0.5, 0.6])
        outcomes = np.array([1, 0])
        # Should not crash; returns 0.0 when no valid bins
        error = _calibration_error(probs, outcomes)
        assert error == 0.0


# ── _evaluate_result ──────────────────────────────────────────────────────────

class TestEvaluateResult:
    def test_h2h_home_wins(self):
        won, result, pf, pk = _evaluate_result(
            "home", "h2h", 5, 3, 1, None, 0, -150, 50, "BET"
        )
        assert won == 1
        assert result == "WIN"
        assert pf > 0
        assert pk > 0

    def test_h2h_home_loses(self):
        won, result, pf, pk = _evaluate_result(
            "home", "h2h", 2, 5, 0, None, 0, -150, 50, "BET"
        )
        assert won == 0
        assert result == "LOSS"
        assert pf == pytest.approx(-100.0)
        assert pk == pytest.approx(-50.0)

    def test_h2h_away_wins(self):
        won, result, pf, pk = _evaluate_result(
            "away", "h2h", 2, 5, 0, None, 0, 130, 50, "BET"
        )
        assert won == 1
        assert result == "WIN"

    def test_h2h_away_loses(self):
        won, result, pf, pk = _evaluate_result(
            "away", "h2h", 5, 2, 1, None, 0, 130, 50, "BET"
        )
        assert won == 0
        assert result == "LOSS"

    def test_avoid_signal_inverts_won(self):
        # AVOID on home: home team wins. We avoided them → we lose (won=0)
        won, result, pf, pk = _evaluate_result(
            "home", "h2h", 5, 3, 1, None, 0, -150, 50, "AVOID"
        )
        assert won == 0

    def test_avoid_signal_inverts_when_team_loses(self):
        # AVOID on home: home team loses → AVOID was correct → won=1
        won, result, pf, pk = _evaluate_result(
            "home", "h2h", 2, 5, 0, None, 0, -150, 50, "AVOID"
        )
        assert won == 1

    def test_profit_flat_on_positive_american_odds(self):
        # +100 → decimal 2.0 → profit = 100 * (2.0 - 1) = 100.0
        _, _, pf, _ = _evaluate_result(
            "home", "h2h", 5, 3, 1, None, 0, 100, 50, "BET"
        )
        assert pf == pytest.approx(100.0)

    def test_profit_kelly_scales_with_bet_size(self):
        _, _, _, pk_small = _evaluate_result(
            "home", "h2h", 5, 3, 1, None, 0, 100, 10, "BET"
        )
        _, _, _, pk_large = _evaluate_result(
            "home", "h2h", 5, 3, 1, None, 0, 100, 100, "BET"
        )
        assert pk_large == pytest.approx(10 * pk_small)

    def test_nhl_h2h_3way_home_wins_in_regulation(self):
        won, result, _, _ = _evaluate_result(
            "home", "h2h_3way", 3, 2, 1, 1, 0, -120, 50, "BET"
        )
        assert won == 1
        assert result == "WIN"

    def test_nhl_h2h_3way_away_wins_in_regulation(self):
        # home_win_reg=0, went_to_ot=0 → away won in regulation
        won, result, _, _ = _evaluate_result(
            "away", "h2h_3way", 2, 3, 0, 0, 0, 130, 50, "BET"
        )
        assert won == 1

    def test_nhl_h2h_3way_away_loses_if_went_to_ot(self):
        # Game went to OT → no away win in regulation
        won, _, _, _ = _evaluate_result(
            "away", "h2h_3way", 2, 3, 0, 0, 1, 130, 50, "BET"
        )
        assert won == 0


# ── _iter_sides ───────────────────────────────────────────────────────────────

class TestIterSides:
    def test_h2h_yields_home_and_away(self):
        dk_odds = {"home_price": -150, "away_price": 130}
        sides = list(_iter_sides("h2h", 0.60, 0.40, dk_odds))
        assert len(sides) == 2
        labels = [s[0] for s in sides]
        assert "home" in labels
        assert "away" in labels

    def test_h2h_home_gets_home_prob(self):
        dk_odds = {"home_price": -150, "away_price": 130}
        sides = {s[0]: s for s in _iter_sides("h2h", 0.60, 0.40, dk_odds)}
        assert sides["home"][1] == 0.60
        assert sides["away"][1] == 0.40

    def test_h2h_3way_not_handled_by_iter_sides(self):
        # NHL regulation 3-way is a 3-class model scored in its own run_backtest
        # block (away/draw/home), not via _iter_sides — which yields nothing.
        dk_odds = {"home_price": -120, "away_price": 110, "draw_price": 240}
        sides = list(_iter_sides("h2h_3way", 0.55, 0.45, dk_odds))
        assert len(sides) == 0

    def test_totals_yields_over_and_under(self):
        dk_odds = {"over_price": -110, "under_price": -110}
        sides = list(_iter_sides("totals", 0.55, 0.45, dk_odds))
        assert len(sides) == 2
        labels = [s[0] for s in sides]
        assert "over" in labels
        assert "under" in labels

    def test_spreads_yields_home_and_away(self):
        dk_odds = {"home_price": -110, "away_price": -110}
        sides = list(_iter_sides("spreads", 0.55, 0.45, dk_odds))
        assert len(sides) == 2


# ── compute_backtest_summary ──────────────────────────────────────────────────

class TestComputeBacktestSummary:
    def _make_df(self, n_bets=120, win_rate=0.55, signal_type="BET"):
        n_wins = int(n_bets * win_rate)
        n_losses = n_bets - n_wins
        rows = []
        for _ in range(n_wins):
            rows.append({
                "signal_type":      signal_type,
                "won":              1,
                "profit_flat":      90.0,
                "profit_kelly":     45.0,
                "recommended_bet":  50.0,
                "edge":             0.05,
                "model_prob":       0.55,
                "confidence_tier":  "MED",
            })
        for _ in range(n_losses):
            rows.append({
                "signal_type":      signal_type,
                "won":              0,
                "profit_flat":      -100.0,
                "profit_kelly":     -50.0,
                "recommended_bet":  50.0,
                "edge":             0.05,
                "model_prob":       0.55,
                "confidence_tier":  "MED",
            })
        return pd.DataFrame(rows)

    def test_empty_dataframe_returns_empty_dict(self):
        assert compute_backtest_summary(pd.DataFrame()) == {}

    def test_summary_contains_expected_keys(self):
        df = self._make_df(n_bets=150)
        summary = compute_backtest_summary(df)
        required_keys = [
            "total_picks", "bets", "avoids",
            "bet_win_rate", "bet_flat_roi", "avg_edge",
            "go_live_ready", "go_live_blockers",
        ]
        for key in required_keys:
            assert key in summary, f"Missing key: {key}"

    def test_not_ready_when_fewer_than_min_picks(self):
        df = self._make_df(n_bets=GO_LIVE_MIN_PICKS - 1)
        summary = compute_backtest_summary(df)
        assert summary["go_live_ready"] is False
        blockers_text = " ".join(summary["go_live_blockers"]).lower()
        assert "picks" in blockers_text or "insufficient" in blockers_text

    def test_go_live_blockers_is_list(self):
        df = self._make_df(n_bets=50)
        summary = compute_backtest_summary(df)
        assert isinstance(summary["go_live_blockers"], list)
        assert len(summary["go_live_blockers"]) >= 1

    def test_win_rate_computed_correctly(self):
        df = self._make_df(n_bets=100, win_rate=0.60)
        summary = compute_backtest_summary(df)
        assert summary["bet_win_rate"] == pytest.approx(0.60, abs=0.01)

    def test_calibration_computed_when_sufficient_bets(self):
        df = self._make_df(n_bets=150)
        summary = compute_backtest_summary(df)
        assert "calibration_error" in summary
        assert summary["calibration_error"] >= 0.0

    def test_tier_breakdown_present_when_bets_exist(self):
        df = self._make_df(n_bets=150)
        summary = compute_backtest_summary(df)
        # MED tier was used in fixture
        assert "med_picks" in summary
        assert "med_win_rate" in summary


# ── Go-Live Gate Constants ────────────────────────────────────────────────────

class TestGoLiveGateConstants:
    def test_min_picks_threshold(self):
        assert GO_LIVE_MIN_PICKS == 100

    def test_min_roi_threshold(self):
        assert GO_LIVE_MIN_ROI == 0.00

    def test_max_calibration_error_threshold(self):
        assert GO_LIVE_MAX_CAL_ERR == 0.05
