"""
The BET decision is made on the CALIBRATED probability (mike, 2026-08-31).

WHY THIS EXISTS
---------------
A model's probability is a separate claim from its point estimate. Until this
change the calibration map only moved a DISPLAY column: picks.model_probability_cal
was stamped and nothing read it back, so `edge` and the BET call were computed
on the raw number.

mlb_f5_moneyline is what exposed it. Its probabilities are honest to about
0.60 and then run 10-12pp hot -- claimed 0.68 delivers 0.56, 0.72 delivers
0.62, 0.77 delivers 0.67, across 270 graded rows. Clearing a 7pp edge bar
against a 66% implied price needs a ~74% claim, which is the worst-calibrated
band by construction. So a -195 bet arrived with a "+8.85pp edge" that was
almost entirely calibration error.

The properties that matter, and the one that keeps this safe:
  * an endorsed map TIGHTENS a hot model out of a marginal bet
  * an UNMAPPED model is completely unaffected -- this is what stops the change
    silently re-cutting all ~70 models at once
  * the RAW numbers are still what gets stored, so history stays comparable
"""

from __future__ import annotations

import pytest

import config
from models import scorer


IMPLIED = 0.661          # a -195 price
# A real registered id: _make_pick resolves the sport from config.MODELS,
# so a synthetic id cannot exercise the real path. Its thresholds are
# monkeypatched below, so this is about the decision logic, not this model.
MODEL = "mlb_moneyline"


@pytest.fixture(autouse=True)
def _thresholds(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, MODEL, 0.07)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, MODEL, 0.67)
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", config.MODEL_EDGE_THRESHOLDS)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", config.MODEL_PROB_THRESHOLDS)
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set())
    monkeypatch.setattr(scorer, "REQUIRE_DK_PRICE", False)


def _pick(monkeypatch, *, raw_prob, calibrated_to, decide_on_cal=True):
    """Build one pick at a -195 price with a given calibration behaviour."""
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", decide_on_cal)
    monkeypatch.setattr(scorer, "_calibrated",
                        lambda mid, p: calibrated_to if mid == MODEL else p)
    return scorer._make_pick(
        game_id="G1", model_id=MODEL, sport="MLB", game_date="2026-08-31",
        pick_side="home", pick_label="TB ML F5",
        model_prob=raw_prob, dk_implied_prob=IMPLIED,
        edge=raw_prob - IMPLIED, dk_odds=-195.0, bankroll=10000.0, features={})


def _pick_at(monkeypatch, *, raw_prob, calibrated_to, decide_on_cal=True):
    """Same as _pick but for the AVOID side, where the model is UNDER the price."""
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", decide_on_cal)
    monkeypatch.setattr(scorer, "_calibrated",
                        lambda mid, p: calibrated_to if mid == MODEL else p)
    return scorer._make_pick(
        game_id="G1", model_id=MODEL, sport="MLB", game_date="2026-08-31",
        pick_side="home", pick_label="x", model_prob=raw_prob,
        dk_implied_prob=IMPLIED, edge=raw_prob - IMPLIED, dk_odds=-195.0,
        bankroll=10000.0, features={})


# ── the case that started this ───────────────────────────────────────────────

def test_a_hot_model_no_longer_fires_the_marginal_bet(monkeypatch):
    """Raw 0.7496 clears 0.07; calibrated to 0.65 it does not."""
    p = _pick(monkeypatch, raw_prob=0.7496, calibrated_to=0.65)
    assert p["signal_type"] == "NONE"


def test_the_same_pick_WOULD_have_fired_on_the_raw_number(monkeypatch):
    """Pins that the test above is testing the calibration, not the price."""
    p = _pick(monkeypatch, raw_prob=0.7496, calibrated_to=0.65, decide_on_cal=False)
    assert p["signal_type"] == "BET"


def test_a_genuinely_big_edge_still_fires_after_calibration(monkeypatch):
    """Calibration must tighten, not veto. 0.86 -> 0.79 still clears both bars."""
    p = _pick(monkeypatch, raw_prob=0.86, calibrated_to=0.79)
    assert p["signal_type"] == "BET"


# ── the safety property: unmapped models are untouched ───────────────────────

def test_an_unmapped_model_is_completely_unaffected(monkeypatch):
    """No promoted map => calibrates to itself => identical decision.

    This is what stops the change re-cutting every model at once."""
    on = _pick(monkeypatch, raw_prob=0.7496, calibrated_to=0.7496, decide_on_cal=True)
    off = _pick(monkeypatch, raw_prob=0.7496, calibrated_to=0.7496, decide_on_cal=False)
    assert on["signal_type"] == off["signal_type"] == "BET"


def test_a_calibration_failure_falls_back_to_raw_rather_than_blocking(monkeypatch):
    """_calibrated returns None on any failure; that must not swallow the pick."""
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", True)
    monkeypatch.setattr(scorer, "_calibrated", lambda mid, p: None)
    p = scorer._make_pick(
        game_id="G1", model_id=MODEL, sport="MLB", game_date="2026-08-31",
        pick_side="home", pick_label="x", model_prob=0.7496,
        dk_implied_prob=IMPLIED, edge=0.7496 - IMPLIED, dk_odds=-195.0,
        bankroll=10000.0, features={})
    assert p["signal_type"] == "BET"


# ── what gets STORED stays raw ───────────────────────────────────────────────

def test_the_stored_edge_and_probability_remain_the_RAW_numbers(monkeypatch):
    """History has to stay comparable: every past sweep was on raw edge."""
    p = _pick(monkeypatch, raw_prob=0.7496, calibrated_to=0.65)
    assert p["model_probability"] == pytest.approx(0.7496)
    assert p["edge"] == pytest.approx(0.7496 - IMPLIED)


# ── AVOID moves with it ──────────────────────────────────────────────────────

def test_avoid_is_judged_on_the_calibrated_number_too(monkeypatch):
    """AVOID moves with the calibrated number as well as BET.

    Raw 0.60 against a 0.661 price is -6.1pp -- inside the dead zone. Calibrated
    to 0.55 it is -11.1pp, which is a real AVOID. Chosen to sit under
    MAX_EDGE_CAP: that cap is deliberately applied to the RAW edge first, as a
    noise guard on the model's own output, and a bigger gap would be dropped
    before any of this ran."""
    p = _pick_at(monkeypatch, raw_prob=0.60, calibrated_to=0.55)
    assert p["signal_type"] == "AVOID"
    off = _pick_at(monkeypatch, raw_prob=0.60, calibrated_to=0.55,
                   decide_on_cal=False)
    assert off["signal_type"] == "NONE", "pins that calibration caused the AVOID"


def test_a_paused_model_never_fires_regardless(monkeypatch):
    monkeypatch.setattr(scorer, "PAUSED_MODELS", {MODEL})
    p = _pick(monkeypatch, raw_prob=0.86, calibrated_to=0.79)
    assert p["signal_type"] == "NONE"


# ── the config decisions themselves ──────────────────────────────────────────

def test_mlb_f5_moneyline_is_on_the_out_of_sample_cut():
    """0.58/0.02, and the history behind it is why this assertion exists.

    2026-08-31 (mike): paused at 0.67/0.15 after a -195 pick, then unpaused the
    same afternoon at 0.74/0.00 on `calibrated_threshold_sweep` -- the morning's
    wider edge bar was aimed at the wrong quantity.

    2026-09-03 (mike): the `mlb_pitcher_stats` leak repair forced a retrain
    (docs/team_stats_leak.md), and 0.74 did not survive it. Scored across 2026
    the new artifact's MAXIMUM probability is 0.734, so the cut fired ZERO bets
    -- mlb_runline's failure mode, and worse here, because f5 is PAPER ONLY
    after a retrain and a cut that fires nothing can never reach the >=50
    settled picks §2's gate needs. It was also a CALIBRATED bar applied to a RAW
    probability, since f5's map has never been promoted.

    The replacement comes from `scripts/mlb_f5_sweep` on 2026 (held out of the
    retrain, the only season with DK first-five prices), on raw probabilities
    with the price floor applied: 76 bets, 45-31, 59.2%, +3.52%.

    THE EVIDENCE IS THIN AND THIS TEST SAYS SO. One of 50 non-thin cells is
    positive and it fails the plateau check 0 of 8 -- the isolated-peak shape
    sessions 74 and 87 retracted. That is an argument against ever making this
    cut LIVE. It is not an argument against measuring it: these picks are PAPER,
    the retrain reset §2's gate, and nothing is backed at 0.58/0.02. Pausing
    would differ only in producing no record at all -- and a paused model cannot
    clear the gate that would unpause it.

    Kill criterion is pre-committed in config: review at 50 settled picks, pause
    if flat ROI is negative, and do NOT go looking for a better cell.
    """
    assert "mlb_f5_moneyline" not in config.PAUSED_MODELS
    assert config.ACTION_THRESHOLDS["mlb_f5_moneyline"] == {"min_prob": 0.58,
                                                            "min_edge": 0.02}
    assert config.MODEL_PROB_THRESHOLDS["mlb_f5_moneyline"] == 0.58
    assert config.MODEL_EDGE_THRESHOLDS["mlb_f5_moneyline"] == 0.02


def test_the_f5_cut_is_reachable_by_the_model_that_carries_it():
    """The check the old cut failed, kept as a rule rather than an anecdote.

    A prob floor above what the model can produce is not a conservative cut, it
    is an off switch nobody labelled. 0.74 sat above the retrained model's
    maximum of 0.734 and f5 published nothing while looking live in config,
    model_action_thresholds and the mobile fallback -- exactly how mlb_runline
    went dormant for six weeks.

    0.58 is well inside the observed range (283 of 2,036 sides reach it), so
    this is a real bar rather than a silent pause.
    """
    assert config.MODEL_PROB_THRESHOLDS["mlb_f5_moneyline"] < 0.734


def test_a_calibrated_cut_is_paired_with_a_calibrated_decision():
    """The cuts in `_FLOOR_CORRECTED_CUTS` are bars on the CALIBRATED number.
    Applying one to the raw probability -- which runs ~10pp higher for a hot
    model -- is a different, looser cut that nobody measured. So the flag that
    makes the decision path read the calibrated probability must stay on
    wherever those cuts are live.

    (mlb_f5_moneyline is no longer among them: its map was never promoted, so
    it calibrates to itself and its 2026-09-03 cut was swept on raw
    probabilities. That is the scale it is decided on.)"""
    assert config.DECIDE_ON_CALIBRATED_PROB is True


def test_mlb_runline_is_paused():
    """Dormant since 2026-07-19 (it cannot reach its own prob floor) and the
    calibrated sweep finds no cut that fixes it. Paused 2026-08-31 (mike) so
    "publishes nothing" and "is switched off" stop looking identical."""
    assert "mlb_runline" in config.PAUSED_MODELS


# ── the floor-corrected slate (2026-08-31, mike) ─────────────────────────────
#
# Every cut below was chosen on CALIBRATED probabilities with
# config.MODEL_MIN_ODDS applied. Both halves matter: a calibrated cut applied
# to raw probabilities is looser than intended, and a cut swept without the
# price floor is measured on bets the scorer refuses. The first sweep, run
# without the floor, recommended four cuts that the corrected one withdrew --
# including one (wnba_prop_player_threes) that had already been unpaused on it.

_FLOOR_CORRECTED_CUTS = {
    # mlb_prop_batter_rbi (0.62, 0.12; 19-16 +23.9%) was swept here too, and
    # RETIRED 2026-09-02 (matt) two days later -- see config.PROP_MODELS.
    "mlb_prop_batter_runs":      (0.62, 0.10),   # 18-9  +25.6%, halves +25.6/+25.6
    "mlb_prop_pitcher_hits":     (0.54, 0.08),   # 49-46 +11.0%, unpaused
    "mlb_prop_pitcher_k":        (0.58, 0.08),   # 15-10 +14.8%
    "mlb_prop_pitcher_outs":     (0.50, 0.12),   # 46-33 +20.7%, unpaused, cut unchanged
    "wnba_prop_player_assists":  (0.50, 0.10),   # 35-22 +23.1%
    "wnba_prop_player_rebounds": (0.62, 0.00),   # 19-11 +12.5%, halves +1.5/+22.2
    # mlb_f5_moneyline was here at (0.74, 0.00) and LEFT on 2026-09-03 (mike).
    # Not because the calibrated sweep was wrong, but because the model it swept
    # no longer exists: the mlb_pitcher_stats leak repair forced a retrain, and
    # 0.74 then fired ZERO bets (max raw probability 0.734). Its replacement
    # comes from a different sweep on a different scale -- raw probabilities,
    # out of sample on 2026 -- so it does not belong in this dict, which is
    # specifically the calibrated slate. See
    # test_mlb_f5_moneyline_is_on_the_out_of_sample_cut.
    "wnba_moneyline":            (0.50, 0.06),   # 18-7  +24.3%
}


@pytest.mark.parametrize("model_id,cut", sorted(_FLOOR_CORRECTED_CUTS.items()))
def test_the_shipped_cut_is_the_one_that_was_swept(model_id, cut):
    prob, edge = cut
    assert config.ACTION_THRESHOLDS[model_id]["min_prob"] == pytest.approx(prob)
    assert config.ACTION_THRESHOLDS[model_id]["min_edge"] == pytest.approx(edge)
    assert config.MODEL_PROB_THRESHOLDS[model_id] == pytest.approx(prob)
    assert config.MODEL_EDGE_THRESHOLDS[model_id] == pytest.approx(edge)


@pytest.mark.parametrize("model_id", sorted(_FLOOR_CORRECTED_CUTS))
def test_a_model_on_a_calibrated_cut_is_not_paused(model_id):
    """Shipping a cut and leaving the model paused is a silent no-op, and it
    has happened here before: the cut moves, nobody sees a pick change, and the
    pause is only noticed when someone asks why volume never rose."""
    assert model_id not in config.PAUSED_MODELS


def test_wnba_threes_is_re_paused_after_the_floor_correction():
    """Unpaused 2026-08-30 on a sweep that ignored the -140 price floor, and
    re-paused 2026-08-31 when it was applied: 37.5% of the rows behind that
    decision were bets the scorer refuses, and with them excluded no cell in
    the grid clears 25 settled bets profitably. Kept as a test because it is
    the one case where a measurement bug reached a live threshold."""
    assert "wnba_prop_player_threes" in config.PAUSED_MODELS
