"""
test_scorer.py — Tests for scoring engine: odds conversion, Kelly sizing,
signal classification, and pick construction.
"""

import math

import pytest

import models.scorer as scorer
from models.scorer import (
    american_to_implied_prob,
    american_to_decimal,
    quarter_kelly,
    _confidence_tier,
    _build_pick_label,
    _build_injury_flag,
    _make_pick,
    _feature_value,
    score_game,
)
from config import BET_EDGE_THRESHOLD, AVOID_EDGE_THRESHOLD, MAX_KELLY_FRACTION


# ── american_to_implied_prob ──────────────────────────────────────────────────

class TestAmericanToImpliedProb:
    def test_even_money(self):
        # +100 → 100 / (100 + 100) = 0.50
        assert american_to_implied_prob(100) == pytest.approx(0.50)

    def test_negative_favourite(self):
        # -150 → 150 / (150 + 100) = 0.60
        assert american_to_implied_prob(-150) == pytest.approx(0.60)

    def test_underdog(self):
        # +200 → 100 / (200 + 100) = 0.333...
        assert american_to_implied_prob(200) == pytest.approx(1 / 3, rel=1e-4)

    def test_heavy_favourite(self):
        # -300 → 300 / (300 + 100) = 0.75
        assert american_to_implied_prob(-300) == pytest.approx(0.75)

    def test_none_returns_none(self):
        assert american_to_implied_prob(None) is None

    @pytest.mark.parametrize("odds", [-500, -200, -110, 100, 110, 200, 500])
    def test_result_is_valid_probability(self, odds):
        p = american_to_implied_prob(odds)
        assert 0 < p < 1, f"Probability out of range for {odds}: {p}"


# ── american_to_decimal (scorer version) ──────────────────────────────────────

class TestAmericanToDecimalScorer:
    def test_even_money_positive(self):
        assert american_to_decimal(100) == pytest.approx(2.0)

    def test_even_money_negative(self):
        assert american_to_decimal(-100) == pytest.approx(2.0)

    def test_positive_underdog(self):
        assert american_to_decimal(200) == pytest.approx(3.0)

    def test_negative_favourite(self):
        assert american_to_decimal(-200) == pytest.approx(1.5)

    def test_none_returns_none(self):
        assert american_to_decimal(None) is None


# ── quarter_kelly ─────────────────────────────────────────────────────────────

class TestQuarterKelly:
    # The multiplier is a TUNED constant (0.25 at launch, 0.10 since
    # 2026-05-04). Asserting a hardcoded fraction re-breaks this test at every
    # retune, so the tests pin the FORMULA against whatever config says:
    #   f = KELLY_MULTIPLIER * (p - q) / (1 - q), capped at MAX_KELLY_FRACTION.
    def test_normal_bet_sizing(self):
        import config
        expect = config.KELLY_MULTIPLIER * (0.60 - 0.50) / (1 - 0.50)
        frac, bet = quarter_kelly(0.60, 0.50, 1000)
        assert frac == pytest.approx(min(expect, MAX_KELLY_FRACTION))
        assert bet == pytest.approx(frac * 1000)

    def test_small_edge(self):
        import config
        expect = config.KELLY_MULTIPLIER * (0.53 - 0.50) / (1 - 0.50)
        frac, bet = quarter_kelly(0.53, 0.50, 1000)
        assert frac == pytest.approx(min(expect, MAX_KELLY_FRACTION))
        assert bet == pytest.approx(frac * 1000)

    def test_zero_edge_returns_zero(self):
        frac, bet = quarter_kelly(0.50, 0.50, 1000)
        assert frac == 0.0
        assert bet == 0.0

    def test_negative_edge_returns_zero(self):
        frac, bet = quarter_kelly(0.40, 0.50, 1000)
        assert frac == 0.0
        assert bet == 0.0

    def test_capped_at_max_kelly_fraction(self):
        # Enormous edge should be capped
        frac, bet = quarter_kelly(0.95, 0.05, 1000)
        assert frac == pytest.approx(MAX_KELLY_FRACTION)
        assert bet == pytest.approx(MAX_KELLY_FRACTION * 1000)

    def test_scales_linearly_with_bankroll(self):
        _, bet_1000 = quarter_kelly(0.60, 0.50, 1000)
        _, bet_2000 = quarter_kelly(0.60, 0.50, 2000)
        assert bet_2000 == pytest.approx(2 * bet_1000)

    def test_bet_never_exceeds_max_kelly_cap(self):
        frac, bet = quarter_kelly(0.80, 0.20, 1000)
        assert frac <= MAX_KELLY_FRACTION
        assert bet <= MAX_KELLY_FRACTION * 1000


# ── _confidence_tier ──────────────────────────────────────────────────────────

class TestConfidenceTier:
    def test_high_tier_at_8_percent(self):
        assert _confidence_tier(0.08) == "HIGH"

    def test_high_tier_above_8_percent(self):
        assert _confidence_tier(0.10) == "HIGH"
        assert _confidence_tier(0.20) == "HIGH"

    def test_high_tier_negative_edge(self):
        assert _confidence_tier(-0.09) == "HIGH"

    def test_med_tier_at_5_percent(self):
        assert _confidence_tier(0.05) == "MED"

    def test_med_tier_below_8_percent(self):
        assert _confidence_tier(0.07) == "MED"
        assert _confidence_tier(-0.06) == "MED"

    def test_low_tier_at_3_percent(self):
        assert _confidence_tier(0.03) == "LOW"

    def test_low_tier_below_5_percent(self):
        assert _confidence_tier(0.04) == "LOW"
        assert _confidence_tier(-0.04) == "LOW"

    def test_boundary_high_exactly_08(self):
        assert _confidence_tier(0.08) == "HIGH"
        assert _confidence_tier(0.0799) == "MED"

    def test_boundary_med_exactly_05(self):
        assert _confidence_tier(0.05) == "MED"
        assert _confidence_tier(0.0499) == "LOW"


# ── _build_pick_label ─────────────────────────────────────────────────────────

class TestBuildPickLabel:
    def test_h2h_home_pick(self):
        assert _build_pick_label("home", "NYY", "BOS", "h2h") == "NYY ML"

    def test_h2h_away_pick(self):
        assert _build_pick_label("away", "NYY", "BOS", "h2h") == "BOS ML"

    def test_h2h_3way_home(self):
        assert _build_pick_label("home", "TOR", "MTL", "h2h_3way") == "TOR ML"

    def test_totals_over(self):
        label = _build_pick_label("over", "NYY", "BOS", "totals")
        assert "Over" in label

    def test_totals_under(self):
        label = _build_pick_label("under", "NYY", "BOS", "totals")
        assert "Under" in label

    def test_spreads_home(self):
        label = _build_pick_label("home", "NYY", "BOS", "spreads")
        assert "NYY" in label
        assert "Spread" in label

    def test_spreads_away(self):
        label = _build_pick_label("away", "NYY", "BOS", "spreads")
        assert "BOS" in label


# ── _build_injury_flag ────────────────────────────────────────────────────────

class TestBuildInjuryFlag:
    def _features(self, **kwargs):
        base = {
            "home_injury_adj": 0.0, "away_injury_adj": 0.0,
            "home_has_returnee": 0, "away_has_returnee": 0,
            "home_starter_out": 0, "away_starter_out": 0,
            "home_goalie_out": 0, "away_goalie_out": 0,
        }
        base.update(kwargs)
        return base

    def test_no_flags_returns_none_none(self):
        flag, detail = _build_injury_flag(self._features(), "MLB", "home")
        assert flag is None
        assert detail is None

    def test_starter_out_is_deliberately_not_a_display_flag(self):
        # _has_starter_out() fires for ANY IL10/IL15/IL60 player (there is no
        # position data), so it triggered on essentially every team and was
        # meaningless as a warning. It was removed from the DISPLAY flag while
        # staying in the model features. This pins the exclusion so a
        # well-meaning re-add gets flagged.
        flag, detail = _build_injury_flag(
            self._features(home_starter_out=1), "MLB", "home"
        )
        assert flag is None and detail is None

    def test_goalie_out_is_not_a_display_flag_either(self):
        flag, detail = _build_injury_flag(
            self._features(home_goalie_out=1), "NHL", "home"
        )
        assert flag is None and detail is None

    def test_home_returnee_flag(self):
        flag, detail = _build_injury_flag(
            self._features(home_has_returnee=1), "MLB", "home"
        )
        assert flag == "returning"

    def test_opponent_heavy_injury_burden(self):
        # Away team has high injury burden → opponent_edge for home pick
        flag, detail = _build_injury_flag(
            self._features(away_injury_adj=0.9, home_injury_adj=0.1),
            "MLB", "home"
        )
        assert flag == "opponent_edge"
        assert "0.90" in detail

    def test_combined_flag_on_multiple_conditions(self):
        # returnee + opponent-injury-edge together -> "combined"
        flag, _ = _build_injury_flag(
            self._features(home_has_returnee=1,
                           away_injury_adj=0.9, home_injury_adj=0.1),
            "MLB", "home"
        )
        assert flag == "combined"

    def test_away_side_checks_away_features(self):
        # Picking away: the away team's returnee is OUR returnee.
        flag, detail = _build_injury_flag(
            self._features(away_has_returnee=1), "MLB", "away"
        )
        assert flag == "returning"


# ── _make_pick ─────────────────────────────────────────────────────────────────

class TestMakePick:
    def _call(self, edge=0.05, model_prob=0.55, dk_implied_prob=0.50,
              pick_side="home", dk_odds=-120):
        features = {
            "home_injury_adj": 0.0, "away_injury_adj": 0.0,
            "home_has_returnee": 0, "away_has_returnee": 0,
            "home_starter_out": 0, "away_starter_out": 0,
        }
        return _make_pick(
            game_id="MLB_2024-04-01_BOS_NYY",
            model_id="mlb_moneyline",
            sport="MLB",
            game_date="2024-04-01",
            pick_side=pick_side,
            pick_label="NYY ML",
            model_prob=model_prob,
            dk_implied_prob=dk_implied_prob,
            edge=edge,
            dk_odds=dk_odds,
            bankroll=1000,
            features=features,
        )

    # Signal classification has moved on twice since these tests were first
    # written, and both moves are documented decisions the tests must follow:
    #   * PER-MODEL thresholds override the global BET_EDGE_THRESHOLD -- a BET
    #     needs the model's own prob floor AND edge floor (config
    #     MODEL_PROB_THRESHOLDS / MODEL_EDGE_THRESHOLDS).
    #   * Dead-zone picks are WRITTEN as signal_type='NONE' rows with a zero
    #     stake (session 16, for the website) instead of being discarded.
    def _model_floors(self):
        import config
        return (config.MODEL_PROB_THRESHOLDS["mlb_moneyline"],
                config.MODEL_EDGE_THRESHOLDS["mlb_moneyline"])

    def test_bet_signal_needs_both_per_model_floors(self):
        prob_f, edge_f = self._model_floors()
        pick = self._call(edge=edge_f + 0.01, model_prob=prob_f + 0.01)
        assert pick is not None
        assert pick["signal_type"] == "BET"
        assert pick["kelly_fraction"] > 0

    def test_edge_alone_is_not_enough_for_a_bet(self):
        # Clears the edge floor but not the prob floor -> NONE, not BET.
        prob_f, edge_f = self._model_floors()
        pick = self._call(edge=edge_f + 0.01, model_prob=prob_f - 0.05)
        assert pick is not None
        assert pick["signal_type"] == "NONE"

    def test_avoid_signal_on_edge_below_negative_threshold(self):
        # AVOID mirrors the per-model edge floor, not the global one.
        _, edge_f = self._model_floors()
        pick = self._call(edge=-(edge_f + 0.01), model_prob=0.30)
        assert pick is not None
        assert pick["signal_type"] == "AVOID"

    def test_dead_zone_writes_a_none_row_with_zero_stake(self):
        pick = self._call(edge=0.01)
        assert pick is not None, "dead-zone picks are stored, not discarded"
        assert pick["signal_type"] == "NONE"
        assert pick["kelly_fraction"] == 0
        assert pick["recommended_bet"] == 0

    def test_exact_threshold_is_a_signal(self):
        prob_f, edge_f = self._model_floors()
        pick = self._call(edge=edge_f, model_prob=prob_f)
        assert pick is not None
        assert pick["signal_type"] == "BET"

    def test_pick_has_all_required_fields(self):
        pick = self._call(edge=0.05)
        assert pick is not None
        required = [
            "game_id", "model_id", "sport", "game_date", "pick_side",
            "pick_label", "model_probability", "dk_implied_prob", "edge",
            "dk_odds", "kelly_fraction", "recommended_bet", "bankroll_at_pick",
            "signal_type", "confidence_tier",
        ]
        for field in required:
            assert field in pick, f"Missing field: {field}"

    def test_result_fields_are_absent_at_creation(self):
        # _make_pick no longer emits result/profit keys at all -- settlement
        # owns them, and _insert_picks normalizes what the row needs. What
        # matters here is that a fresh pick cannot smuggle in a result.
        pick = self._call(edge=0.05)
        for field in ("result", "profit_flat", "profit_kelly", "settled_at"):
            assert pick.get(field) is None

    def test_confidence_tier_set(self):
        pick = self._call(edge=0.05)
        assert pick["confidence_tier"] in ("HIGH", "MED", "LOW")

    def test_edge_rounded_to_4_places(self):
        pick = self._call(edge=0.051234567)
        assert pick["edge"] == round(0.051234567, 4)


# ── _feature_value (serve-time encoding) ──────────────────────────────────────

class TestFeatureValue:
    def test_none_becomes_nan(self):
        # Missing feature → NaN (XGBoost handles it), NOT 0.0 — a 0.00 ERA/WHIP
        # is an impossible value that skews the model out-of-distribution.
        assert math.isnan(_feature_value(None))

    def test_real_zero_preserved(self):
        # Legitimate zeros (is_dome_game=0, wind=0) must stay 0.0, not NaN.
        v = _feature_value(0)
        assert v == 0.0 and not math.isnan(v)

    def test_float_passthrough(self):
        assert _feature_value(3.5) == 3.5

    def test_int_coerced_to_float(self):
        assert _feature_value(4) == 4.0


# ── missing-starter gate (the spurious-morning-BET fix) ───────────────────────

class TestMissingStarterGate:
    """MLB game models must not score off a missing probable starter — the live
    vector would 0-fill the (top-importance) starter ERA to an impossible 0.00
    and fire a bogus BET that corrects itself once real ERAs load."""

    BASE = {
        "home_starter_era": 3.2,
        "away_starter_era": 4.1,
        "home_team": "BOS",
        "away_team": "COL",
        "game_date": "2026-06-23",
    }

    def test_missing_home_starter_skips_before_model_load(self, monkeypatch):
        calls = []
        monkeypatch.setattr(scorer, "load_model", lambda mid: calls.append(mid) or None)
        out = score_game(None, "g1", "mlb_over_under",
                         {**self.BASE, "home_starter_era": None}, 1000.0)
        assert out == []
        assert calls == []  # gated before the model (and DB) are ever touched

    def test_missing_away_starter_skips(self, monkeypatch):
        calls = []
        monkeypatch.setattr(scorer, "load_model", lambda mid: calls.append(mid) or None)
        out = score_game(None, "g1", "mlb_runline",
                         {**self.BASE, "away_starter_era": None}, 1000.0)
        assert out == []
        assert calls == []

    def test_both_starters_present_passes_gate(self, monkeypatch):
        # Guard must NOT short-circuit when starters are loaded: execution
        # proceeds to load_model (here stubbed to None → [] via the no-model path).
        calls = []
        monkeypatch.setattr(scorer, "load_model", lambda mid: calls.append(mid) or None)
        out = score_game(None, "g1", "mlb_over_under", dict(self.BASE), 1000.0)
        assert out == []
        assert calls == ["mlb_over_under"]  # reached the model load → gate passed
