"""
test_ufc_feature_engine.py — Pure-function tests for UFC career stats,
feature assembly, and target computation. No DB, no network.
"""

import pytest

from features.ufc_feature_engine import (
    METHOD_CLASSES,
    MIN_UFC_FIGHTS,
    _assemble_ufc_features,
    career_stats,
    compute_ufc_target,
    infer_five_rounds,
    synthetic_round_total,
)


def _fight(date, result="win", method="decision", end_round=3, end_time_sec=300,
           scheduled=3, sig_l=50, sig_a=100, sig_abs=30, td_l=2, td_a=4,
           sub=1, game_id=None):
    return {
        "game_id":               game_id or f"UFC_{date}_x_y",
        "game_date":             date,
        "result":                result,
        "method":                method,
        "end_round":             end_round,
        "end_time_sec":          end_time_sec,
        "scheduled_rounds":      scheduled,
        "sig_strikes_landed":    sig_l,
        "sig_strikes_attempted": sig_a,
        "sig_strikes_absorbed":  sig_abs,
        "takedowns_landed":      td_l,
        "takedowns_attempted":   td_a,
        "sub_attempts":          sub,
    }


PROFILE = {"height_in": 76.0, "reach_in": 79.0, "stance": "Orthodox", "dob": "1990-01-01"}


def test_career_stats_requires_min_fights():
    rows = [_fight("2022-01-01"), _fight("2022-06-01")]
    assert len(rows) < MIN_UFC_FIGHTS
    assert career_stats(rows, {}, "2023-01-01", PROFILE) is None


def test_career_stats_basic():
    rows = [
        _fight("2022-01-01", result="win",  method="ko_tko", end_round=1, end_time_sec=120),
        _fight("2022-06-01", result="loss", method="decision"),
        _fight("2023-01-01", result="win",  method="submission", end_round=2, end_time_sec=90),
        _fight("2023-06-01", result="win",  method="decision"),
    ]
    s = career_stats(rows, {}, "2024-01-01", PROFILE)
    assert s["experience"] == 4
    assert s["career_win_pct"] == 0.75
    assert s["win_streak"] == 2          # last two fights were wins
    assert s["ko_rate"] == 0.25
    assert s["sub_rate"] == 0.25
    assert s["dec_rate"] == 0.5
    assert s["finish_rate"] == 0.5
    assert s["layoff_days"] == 214       # 2023-06-01 → 2024-01-01
    assert s["age"] == pytest.approx(34.0, abs=0.1)
    assert s["height_in"] == 76.0
    assert s["stance"] == "Orthodox"


def test_career_stats_streak_broken_by_loss():
    rows = [
        _fight("2022-01-01", result="win"),
        _fight("2022-06-01", result="win"),
        _fight("2023-01-01", result="loss"),
    ]
    s = career_stats(rows, {}, "2024-01-01", PROFILE)
    assert s["win_streak"] == 0


def test_career_stats_defense_from_opponent_rows():
    rows = [
        _fight("2022-01-01", sig_abs=30, game_id="g1"),
        _fight("2022-06-01", sig_abs=20, game_id="g2"),
        _fight("2023-01-01", sig_abs=50, game_id="g3"),
    ]
    # Opponents attempted 200 sig strikes total; 100 landed (absorbed) →
    # striking defense = 1 − 100/200 = 0.5. Opp takedowns 1 of 4 → td_def 0.75.
    opp = {
        "g1": {"sig_strikes_attempted": 60,  "takedowns_landed": 0, "takedowns_attempted": 2},
        "g2": {"sig_strikes_attempted": 40,  "takedowns_landed": 1, "takedowns_attempted": 1},
        "g3": {"sig_strikes_attempted": 100, "takedowns_landed": 0, "takedowns_attempted": 1},
    }
    s = career_stats(rows, opp, "2024-01-01", PROFILE)
    assert s["str_def"] == 0.5
    assert s["td_def"] == 0.75


def test_synthetic_round_total():
    assert synthetic_round_total(3) == 2.5
    assert synthetic_round_total(5) == 4.5
    assert synthetic_round_total(None) == 2.5


def test_infer_five_rounds():
    assert infer_five_rounds(None, scheduled_rounds=5) == 1
    assert infer_five_rounds(None, scheduled_rounds=3) == 0
    assert infer_five_rounds(4.5) == 1     # DK line ≥ 3.5 → 5-round bout
    assert infer_five_rounds(2.5) == 0
    assert infer_five_rounds(None) == 0    # unknown → assume 3 rounds


def _stats_pair():
    rows = [
        _fight("2022-01-01", result="win", method="ko_tko", end_round=1, end_time_sec=100),
        _fight("2022-06-01", result="win", method="decision"),
        _fight("2023-01-01", result="loss", method="decision"),
    ]
    home = career_stats(rows, {}, "2024-01-01", PROFILE)
    away = career_stats(rows, {}, "2024-01-01",
                        {**PROFILE, "stance": "Southpaw", "reach_in": 74.0})
    return home, away


def test_assemble_features_diffs_and_stance():
    home, away = _stats_pair()
    feat = _assemble_ufc_features("UFC_2024-01-01_b_a", "2024-01-01",
                                  "Fighter A", "Fighter B", 2024,
                                  home, away, odds_row=None)
    assert feat["d_reach_in"] == 5.0
    assert feat["stance_mismatch"] == 1
    assert feat["d_career_win_pct"] == 0.0
    assert feat["is_five_rounds"] == 0
    assert feat["total_line"] == 2.5      # synthetic 3-round default
    assert feat["sport"] == "UFC"


def test_assemble_features_uses_dk_line():
    home, away = _stats_pair()
    feat = _assemble_ufc_features("g", "2024-01-01", "A", "B", 2024,
                                  home, away, odds_row={"total_line": 4.5})
    assert feat["total_line"] == 4.5
    assert feat["is_five_rounds"] == 1


def test_assemble_features_none_when_fighter_missing():
    home, _ = _stats_pair()
    assert _assemble_ufc_features("g", "2024-01-01", "A", "B", 2024,
                                  home, None, odds_row=None) is None


# ── Targets ───────────────────────────────────────────────────────────────────

def test_target_h2h():
    assert compute_ufc_target("ufc_moneyline", "h2h", None, 1, None) == 1
    assert compute_ufc_target("ufc_moneyline", "h2h", None, 0, None) == 0
    assert compute_ufc_target("ufc_moneyline", "h2h", None, None, None) is None  # draw/NC


def test_target_totals():
    finish_r1 = {"method": "ko_tko", "end_round": 1, "end_time_sec": 100,
                 "scheduled_rounds": 3}
    decision3 = {"method": "decision", "end_round": 3, "end_time_sec": 300,
                 "scheduled_rounds": 3}
    # Finish in R1 vs 2.5 line → under (0); decision vs 2.5 → over (1)
    assert compute_ufc_target("ufc_total_rounds", "totals", finish_r1, None, 2.5) == 0
    assert compute_ufc_target("ufc_total_rounds", "totals", decision3, None, 2.5) == 1
    # Stoppage exactly at the half-round mark → push → None
    push = {"method": "ko_tko", "end_round": 3, "end_time_sec": 150,
            "scheduled_rounds": 3}
    assert compute_ufc_target("ufc_total_rounds", "totals", push, None, 2.5) is None
    # Missing result → None
    assert compute_ufc_target("ufc_total_rounds", "totals", None, None, 2.5) is None
    # No line passed → synthetic line from scheduled rounds (2.5 for 3-rounder)
    assert compute_ufc_target("ufc_total_rounds", "totals", decision3, None, None) == 1


def test_target_method():
    assert METHOD_CLASSES == ["decision", "ko_tko", "submission"]
    for method, expected in (("decision", 0), ("ko_tko", 1), ("submission", 2)):
        row = {"method": method, "end_round": 1, "end_time_sec": 60, "scheduled_rounds": 3}
        assert compute_ufc_target("ufc_method_of_victory", "method", row, None, None) == expected
    dq = {"method": "dq", "end_round": 2, "end_time_sec": 30, "scheduled_rounds": 3}
    assert compute_ufc_target("ufc_method_of_victory", "method", dq, None, None) is None
