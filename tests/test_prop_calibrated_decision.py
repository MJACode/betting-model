"""
Player props decide on the CALIBRATED probability too (mike, 2026-09-07).

WHY THIS EXISTS
---------------
`DECIDE_ON_CALIBRATED_PROB` shipped on 2026-08-31 and lived in `classify_edge`.
Player props are not built there — they are built in `_make_prop_pick`, which
had no calibration branch. Every model carrying a promoted calibration map is a
player prop, so for six days the flag was on by default, `tests/
test_decide_on_calibrated.py` asserted it was on, and it changed nothing
anywhere. A guard that dead code can satisfy is not a guard (CLAUDE.md 1b).

Meanwhile the cuts shipped the same day — `mlb_prop_pitcher_k` 0.58/0.08 and
`mlb_prop_pitcher_hits` 0.54/0.08 among them — were chosen on CALIBRATED sweeps
and were being applied to RAW numbers. Measured over the picks that carried a
live map: 56 of 57 MLB prop BETs fail their own cut on the calibrated number the
pick already stored. docs/mlb_volume_efficiency.md section 2.

The same three properties as the game-model test, plus the collation:
  * an endorsed map TIGHTENS a hot prop out of a marginal bet
  * an UNMAPPED prop model is completely unaffected
  * the RAW numbers are still what gets stored

Pure-function tests — no network, no DB.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import config
from models import scorer

REPO = Path(__file__).resolve().parent.parent

MODEL = "mlb_prop_pitcher_k"
IMPLIED = 0.5238            # a -110 price
ODDS = -110.0


@pytest.fixture(autouse=True)
def _thresholds(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, MODEL, 0.08)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, MODEL, 0.58)
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", config.MODEL_EDGE_THRESHOLDS)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", config.MODEL_PROB_THRESHOLDS)
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set())
    monkeypatch.setattr(scorer, "REQUIRE_DK_PRICE", False)


def _prop(monkeypatch, *, raw_prob, calibrated_to, decide_on_cal=True,
          model_id=MODEL):
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", decide_on_cal)
    monkeypatch.setattr(scorer, "_calibrated",
                        lambda mid, p: calibrated_to if mid == MODEL else p)
    return scorer._make_prop_pick(
        game_id="G1", model_id=model_id, game_date="2026-09-07",
        player_name="Aaron Nola", pick_side="over",
        model_prob=raw_prob, dk_implied_prob=IMPLIED,
        edge=raw_prob - IMPLIED, dk_odds=ODDS, line=5.5,
        bankroll=10000.0, stat_label="Ks", player_id="P1")


# ── the decision ─────────────────────────────────────────────────────────────

def test_a_hot_prop_model_no_longer_fires_the_marginal_bet(monkeypatch):
    """Claims 0.66 (+13.6pp edge, clears 0.58/0.08); worth 0.60 (+7.6pp, does not)."""
    pick = _prop(monkeypatch, raw_prob=0.66, calibrated_to=0.60)
    assert pick["signal_type"] == "NONE"


def test_the_same_prop_WOULD_have_fired_on_the_raw_number(monkeypatch):
    """The counterpart that makes the test above mean something.

    Watched to fail before the fix: with the pre-2026-09-07 body of
    _make_prop_pick this returns BET, which is the bug."""
    pick = _prop(monkeypatch, raw_prob=0.66, calibrated_to=0.60,
                 decide_on_cal=False)
    assert pick["signal_type"] == "BET"


def test_a_genuinely_big_edge_still_fires_after_calibration(monkeypatch):
    pick = _prop(monkeypatch, raw_prob=0.72, calibrated_to=0.68)
    assert pick["signal_type"] == "BET"


def test_an_unmapped_prop_model_is_completely_unaffected(monkeypatch):
    """The property that stops this silently re-cutting every prop at once."""
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, "mlb_prop_pitcher_outs", 0.08)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, "mlb_prop_pitcher_outs", 0.50)
    pick = _prop(monkeypatch, raw_prob=0.66, calibrated_to=0.60,
                 model_id="mlb_prop_pitcher_outs")
    assert pick["signal_type"] == "BET"


def test_the_stored_prop_numbers_remain_RAW(monkeypatch):
    """History has to stay comparable: every past sweep read these columns."""
    pick = _prop(monkeypatch, raw_prob=0.72, calibrated_to=0.68)
    assert pick["model_probability"] == pytest.approx(0.72)
    assert pick["edge"] == pytest.approx(0.72 - IMPLIED, abs=1e-4)


def test_avoid_on_a_prop_is_judged_on_the_calibrated_number_too(monkeypatch):
    """A cold claim calibrates UP, out of the AVOID band, by the same arithmetic."""
    pick = _prop(monkeypatch, raw_prob=0.43, calibrated_to=0.47)
    assert pick["signal_type"] == "NONE"
    assert _prop(monkeypatch, raw_prob=0.43, calibrated_to=0.47,
                 decide_on_cal=False)["signal_type"] == "AVOID"


def test_a_prop_calibration_failure_falls_back_to_raw_rather_than_blocking(monkeypatch):
    """A calibration miss must never be able to stop a pick being written."""
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", True)
    monkeypatch.setattr(scorer, "_calibrated", lambda mid, p: None)
    pick = scorer._make_prop_pick(
        game_id="G1", model_id=MODEL, game_date="2026-09-07",
        player_name="Aaron Nola", pick_side="over", model_prob=0.72,
        dk_implied_prob=IMPLIED, edge=0.72 - IMPLIED, dk_odds=ODDS,
        line=5.5, bankroll=10000.0, stat_label="Ks", player_id="P1")
    assert pick["signal_type"] == "BET"


def test_the_prop_builder_reads_the_flag_at_all():
    """Source tripwire. The bug was not a wrong branch, it was NO branch — so
    the regression to guard is the branch going missing again, which a
    behavioural test on a mapped model would not notice if someone deleted the
    map instead."""
    src = (REPO / "models" / "scorer.py").read_text(encoding="utf-8")
    body = src.split("def _make_prop_pick(")[1].split("\ndef ")[0]
    assert "DECIDE_ON_CALIBRATED_PROB" in body
    assert "_calibrated(" in body


# ── one bet per player ───────────────────────────────────────────────────────

def _bet(model_id, player_id, prob, odds=-110.0, game_id="G1"):
    return {"game_id": game_id, "model_id": model_id, "player_id": player_id,
            "model_probability": prob, "dk_odds": odds, "signal_type": "BET",
            "kelly_fraction": 0.02, "recommended_bet": 200.0,
            "pick_label": f"{player_id} {model_id}"}


@pytest.fixture
def _identity_cal(monkeypatch):
    monkeypatch.setattr(scorer, "_calibrated", lambda mid, p: p)


def test_one_bet_per_pitcher_keeps_the_highest_ev(_identity_cal):
    picks = [_bet("mlb_prop_pitcher_k", "P1", 0.62),
             _bet("mlb_prop_pitcher_hits", "P1", 0.70)]
    out = scorer.dedupe_player_props(picks)
    assert [p["signal_type"] for p in out] == ["NONE", "BET"]
    assert "one bet per player" in out[0]["downgrade_reason"]


def test_the_dedupe_leaves_a_reason_a_later_sweep_can_read(_identity_cal):
    """A capped-away BET that reads as a model declining corrupts the next
    sweep, which grades every NONE (CLAUDE.md 7)."""
    out = scorer.dedupe_player_props(
        [_bet("mlb_prop_pitcher_k", "P1", 0.62),
         _bet("mlb_prop_pitcher_hits", "P1", 0.70)])
    dropped = [p for p in out if p["signal_type"] == "NONE"][0]
    assert dropped["downgrade_reason"]
    assert dropped["recommended_bet"] == 0.0

def test_different_players_and_different_games_never_collide(_identity_cal):
    picks = [_bet("mlb_prop_pitcher_k", "P1", 0.62),
             _bet("mlb_prop_pitcher_hits", "P2", 0.70),
             _bet("mlb_prop_pitcher_hits", "P1", 0.70, game_id="G2")]
    assert all(p["signal_type"] == "BET"
               for p in scorer.dedupe_player_props(picks))


def test_a_standing_bet_blocks_a_later_better_one_rather_than_being_retracted(_identity_cal):
    """CLAUDE.md 1c. The morning's pick is the bet of record; an afternoon pass
    finding a juicier market on the same pitcher does not replace it."""
    out = scorer.dedupe_player_props(
        [_bet("mlb_prop_pitcher_hits", "P1", 0.95)],
        already_bet={("mlb_pitcher", "G1", "P1")})
    assert out[0]["signal_type"] == "NONE"


def test_a_pick_with_no_player_id_never_participates(_identity_cal):
    picks = [_bet("mlb_prop_pitcher_k", None, 0.62),
             _bet("mlb_prop_pitcher_hits", None, 0.70)]
    assert all(p["signal_type"] == "BET"
               for p in scorer.dedupe_player_props(picks))


def test_a_model_outside_every_pool_is_untouched(_identity_cal):
    picks = [_bet("mlb_prop_batter_runs", "B1", 0.62),
             _bet("mlb_prop_batter_walks", "B1", 0.70)]
    assert all(p["signal_type"] == "BET"
               for p in scorer.dedupe_player_props(picks))


def test_the_pool_ranks_on_the_calibrated_number(monkeypatch):
    """Raw EV structurally favours whichever model is most overconfident, and
    the whole point of a pool is to compare models against each other."""
    monkeypatch.setattr(
        scorer, "_calibrated",
        lambda mid, p: 0.52 if mid == "mlb_prop_pitcher_k" else p)
    out = scorer.dedupe_player_props(
        [_bet("mlb_prop_pitcher_k", "P1", 0.80),      # hot: worth 0.52
         _bet("mlb_prop_pitcher_hits", "P1", 0.62)])  # honest
    assert out[0]["signal_type"] == "NONE"
    assert out[1]["signal_type"] == "BET"


# ── the daily cap ────────────────────────────────────────────────────────────

CAPS = {"mlb_prop_pitcher_k": 2}


def test_the_cap_keeps_the_models_best_n_not_the_first_n(_identity_cal):
    picks = [_bet("mlb_prop_pitcher_k", f"P{i}", p)
             for i, p in enumerate([0.60, 0.75, 0.62, 0.80])]
    out = scorer.apply_prop_daily_cap(picks, {}, CAPS)
    kept = [p["player_id"] for p in out if p["signal_type"] == "BET"]
    assert sorted(kept) == ["P1", "P3"]


def test_the_cap_counts_bets_already_standing_today(_identity_cal):
    """So it can never retract one: two already placed, allowance spent."""
    out = scorer.apply_prop_daily_cap(
        [_bet("mlb_prop_pitcher_k", "P9", 0.90)],
        {"mlb_prop_pitcher_k": 2}, CAPS)
    assert out[0]["signal_type"] == "NONE"
    assert "daily cap" in out[0]["downgrade_reason"]


def test_an_uncapped_model_is_untouched(_identity_cal):
    picks = [_bet("mlb_prop_pitcher_outs", f"P{i}", 0.7) for i in range(5)]
    assert all(p["signal_type"] == "BET"
               for p in scorer.apply_prop_daily_cap(picks, {}, CAPS))


def test_no_caps_configured_is_a_no_op(_identity_cal):
    picks = [_bet("mlb_prop_pitcher_k", f"P{i}", 0.7) for i in range(5)]
    assert scorer.apply_prop_daily_cap(picks, {}, {}) == picks


def test_the_interim_cap_covers_the_two_models_that_overshot():
    """config.py's own projections vs what fired: ~5.4/wk against ~52/wk, and
    ~19.8/wk against ~39/wk. The cap comes off when their maps are promoted."""
    assert set(config.PROP_MAX_SIGNALS_PER_DAY) == {
        "mlb_prop_pitcher_k", "mlb_prop_pitcher_hits"}
