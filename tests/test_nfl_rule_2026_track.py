"""Pins the 2026 opener/wind paper-track: no unit bump, retire-if-flat, MAX_FIRE_LEAD=4.

The tracker is a reader of `picks`. These tests pin the policy and the grading
math so a later session cannot quietly raise a unit, widen the fire window, or
count VOID rows as the 2026 record. They do not hit the database.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import config
from scripts import nfl_rule_2026_track as track

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _row(**kw):
    base = dict(
        model_id="nfl_opener_spread", game_id="NFL_2026_01_X_Y",
        game_date="2026-09-13", pick_label="X @ Y — X +1 (Opener -2 vs Pinnacle, DK) · 0.98u",
        pick_side="away", scored_line=-1.0, odds=-115.0, result="WIN",
        condition_status="GONE", profit_flat=86.96, created_at=None,
        commence_time=None,
    )
    base.update(kw)
    return base


def test_live_cuts_did_not_move():
    """Paper-track is comments + a reader. Emission thresholds stay put."""
    assert config.ACTION_THRESHOLDS["nfl_opener_spread"] == {
        "min_prob": 0.55, "min_edge": 0.00}
    assert config.ACTION_THRESHOLDS["nfl_wind_totals"] == {
        "min_prob": 0.52, "min_edge": 0.03}
    assert track.NO_UNIT_BUMP is True
    assert track.OPENER_RETIRE_IF_FLAT_2026 is True
    assert track.WIND_MAX_FIRE_LEAD_STAYS == 4.0
    assert track.DO_NOT_UNPAUSE_XGB_PROPS is True
    assert track.MODELS == ("nfl_opener_spread", "nfl_wind_totals")


def test_void_rows_are_not_the_record():
    """A VOID pick existed; it is not a 2026 settled BET (CLAUDE.md section 1c)."""
    g = track.grade_rows([
        _row(),
        _row(result="NO_ACTION", condition_status="VOID", profit_flat=0, odds=-110.0),
        _row(result=None, condition_status="OK", profit_flat=None, odds=-105.0,
             model_id="nfl_wind_totals"),
    ])
    assert g["settled"] == 1 and g["wins"] == 1 and g["losses"] == 0
    assert g["void"] == 1 and g["unsettled"] == 1
    assert g["priced"] == 1
    assert g["units"] == 0.87
    assert g["roi"] == 87.0


def test_unpriced_settled_bets_do_not_invent_minus_110():
    """profit_flat fabricates -110 when the price is missing (CLAUDE.md section 6)."""
    assert track.units_from_profit_flat(-100.0, None, "LOSS") is None
    assert round(track.units_from_profit_flat(86.96, -115.0, "WIN"), 4) == 0.8696
    assert track.units_from_profit_flat(0.0, -110.0, "PUSH") == 0.0
    g = track.grade_rows([_row(odds=None, profit_flat=-100.0, result="LOSS")])
    assert g["settled"] == 1 and g["priced"] == 0 and g["roi"] is None


def test_opener_does_not_retire_mid_season_even_if_currently_up():
    g = track.grade_rows([_row(), _row(pick_label="SF @ LA — SF +4.5 (Opener -1 vs Pinnacle, DK) · 0.57u")])
    v = track.opener_verdict(g, 2026, season_over=False)
    assert v.startswith("HOLD")
    assert "Retire if 2026 finishes <= flat" in v
    assert "RETIRE-CANDIDATE" not in v


def test_opener_retire_candidate_only_when_the_season_finished_flat_or_worse():
    loss = _row(result="LOSS", profit_flat=-100.0, odds=-110.0)
    g = track.grade_rows([loss, loss])
    assert g["roi"] == -100.0
    v = track.opener_verdict(g, 2026, season_over=True)
    assert v.startswith("RETIRE-CANDIDATE")
    assert "<= flat" in v
    hold = track.opener_verdict(track.grade_rows([_row()]), 2026, season_over=True)
    assert hold.startswith("HOLD")
    assert "above flat" in hold


def test_wind_verdict_never_widens_the_window():
    v = track.wind_verdict(track.grade_rows([]), past_window=[])
    assert "MAX_FIRE_LEAD stays 4" in v
    assert "no unit bump" in v
    flagged = track.wind_verdict(track.grade_rows([]), past_window=[{"pick_label": "x"}])
    assert "FLAG" in flagged
    assert "MAX_FIRE_LEAD=4" in flagged


def test_units_stay_at_one_percent_on_both_cards():
    opener = _src("nfl/models/opener_spread.py")
    wind = _src("nfl/models/wind_totals.py")
    assert "UNIT_PCT = 0.01" in opener
    assert "UNIT_PCT = 0.01" in wind
    assert "MAX_UNITS = 2.0" in wind
    assert "MAX_FIRE_LEAD = 4.0" in wind


def test_max_fire_lead_stays_four_in_the_live_model():
    sys_path_ok = _src("nfl/models/wind_totals.py")
    assert "MAX_FIRE_LEAD = 4.0" in sys_path_ok
    # A raise to 7 would look like a comment tweak. Pin the assignment.
    assert sys_path_ok.count("MAX_FIRE_LEAD = 4.0") == 1


def test_config_comments_state_the_policy():
    src = _src("config.py")
    ath = src[src.index("# NFL opener-spread"):src.index("# NFL opener-spread") + 1500]
    assert "no unit bump" in ath.lower()
    assert "retire if 2026" in ath.lower()
    wind_ath = src[src.index("# NFL — the standalone wind-totals"):
                   src.index("# NFL — the standalone wind-totals") + 1500]
    assert "MAX_FIRE_LEAD stays 4" in wind_ath
    assert "no unit bump" in wind_ath.lower()


def test_paused_xgb_props_stay_paused():
    """Paper-tracking opener/wind is not an unpause of the distributional props."""
    from tests.test_retired_models import NFL_DISTRIBUTIONAL_PAUSED, NFL_KEEP_LIVE
    assert NFL_DISTRIBUTIONAL_PAUSED <= set(config.PAUSED_MODELS)
    for mid in NFL_KEEP_LIVE:
        assert mid not in config.PAUSED_MODELS, mid
    assert track.DO_NOT_UNPAUSE_XGB_PROPS is True


def test_the_script_does_not_write_thresholds_or_units():
    src = _src("scripts/nfl_rule_2026_track.py")
    for banned in ("UPDATE model_action_thresholds", "PAUSED_MODELS.remove",
                   "UNIT_PCT = 0.02", "MAX_FIRE_LEAD = 7", "MAX_FIRE_LEAD = 5"):
        assert banned not in src, banned
    assert "settle_picks" in src
    assert "--settle" in src


def test_a_wind_lock_past_four_days_is_flagged_not_resized():
    created = datetime(2026, 9, 5, tzinfo=timezone.utc)
    kick = created + timedelta(days=8.7)
    lead = track.lead_days(created, kick)
    assert lead is not None and lead > track.WIND_MAX_FIRE_LEAD_STAYS
    created_ok = datetime(2026, 9, 11, tzinfo=timezone.utc)
    kick_ok = datetime(2026, 9, 14, tzinfo=timezone.utc)
    assert track.lead_days(created_ok, kick_ok) < track.WIND_MAX_FIRE_LEAD_STAYS


def test_tracking_doc_names_the_command_and_the_criteria():
    doc = _src("docs/nfl_rule_2026_track.md")
    assert "python -m scripts.nfl_rule_2026_track" in doc
    assert "Retire if 2026" in doc or "retire if 2026" in doc.lower()
    assert "MAX_FIRE_LEAD` stays 4" in doc or "MAX_FIRE_LEAD stays 4" in doc
    assert "no unit bump" in doc.lower()
    assert "Do not unpause" in doc or "do not unpause" in doc.lower()
    # Labels quoted, not rebuilt from scored_line.
    assert "BUF @ HOU — BUF +1" in doc
    assert "SF @ LA — SF +4.5" in doc
    assert "DEN @ KC Under 43.5" in doc
