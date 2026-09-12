"""
Two row-level defects found on the NCAAF board, 2026-09-10 (session 280), both
in shared scorer code and therefore every sport's:

  1. A PAUSED model still wrote AVOID rows. `_is_paused` only downgraded a BET,
     so `ncaaf_moneyline` -- paused because every edge cell lost at real
     prices -- had 80 AVOID rows on the Today/Signals board, which does not
     check `paused` (useTodayPicks drops game-over, retired and VOID only).
     A paused model is paused: neither side of it is a signal.

  2. A declined rule's "watching" NONE row carried NO reason. score_game's
     `no_signal` forced signal_type to NONE by hand and never wrote the
     reason anywhere -- 0 of 1,012 non-BET NCAAF rows this season carried
     `downgrade_reason`, while docs/sports/ncaaf.md said every one did.

Both now route through `_downgrade`, which persists the reason in its own
column. These tests were watched to fail before the fix.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from models import scorer  # noqa: E402

MODEL = "mlb_moneyline"
PROP_MODEL = "mlb_prop_pitcher_k"
IMPLIED = 0.55


@pytest.fixture(autouse=True)
def _thresholds(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, MODEL, 0.05)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, MODEL, 0.55)
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, PROP_MODEL, 0.05)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, PROP_MODEL, 0.55)
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", config.MODEL_EDGE_THRESHOLDS)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", config.MODEL_PROB_THRESHOLDS)
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set())
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", False)
    monkeypatch.setattr(scorer, "REQUIRE_DK_PRICE", False)


def _game_pick(monkeypatch, *, prob):
    return scorer._make_pick(
        game_id="G1", model_id=MODEL, sport="MLB", game_date="2026-09-10",
        pick_side="home", pick_label="x", model_prob=prob,
        dk_implied_prob=IMPLIED, edge=prob - IMPLIED, dk_odds=-120.0,
        bankroll=10000.0, features={})


def _prop_pick(monkeypatch, *, prob):
    return scorer._make_prop_pick(
        game_id="G1", model_id=PROP_MODEL, game_date="2026-09-10",
        player_name="Aaron Nola", pick_side="over", model_prob=prob,
        dk_implied_prob=IMPLIED, edge=prob - IMPLIED, dk_odds=-120.0,
        line=5.5, bankroll=10000.0, stat_label="Ks", player_id="P1")


# ── 1. a paused model emits no signal on EITHER side ─────────────────────────

def test_unpaused_model_still_writes_avoid(monkeypatch):
    """Control: the AVOID side is untouched for a live model."""
    p = _game_pick(monkeypatch, prob=0.40)
    assert p["signal_type"] == "AVOID"
    assert p.get("downgrade_reason") is None


def test_paused_game_model_avoid_becomes_none_with_reason(monkeypatch):
    monkeypatch.setattr(scorer, "PAUSED_MODELS", {MODEL})
    p = _game_pick(monkeypatch, prob=0.40)
    assert p["signal_type"] == "NONE"
    assert p["downgrade_reason"] == "model paused"


def test_paused_game_model_bet_becomes_none_with_reason(monkeypatch):
    monkeypatch.setattr(scorer, "PAUSED_MODELS", {MODEL})
    p = _game_pick(monkeypatch, prob=0.70)
    assert p["signal_type"] == "NONE"
    assert p["downgrade_reason"] == "model paused"
    assert p["recommended_bet"] == 0.0


def test_paused_prop_model_avoid_becomes_none_with_reason(monkeypatch):
    monkeypatch.setattr(scorer, "PAUSED_MODELS", {PROP_MODEL})
    p = _prop_pick(monkeypatch, prob=0.40)
    assert p["signal_type"] == "NONE"
    assert p["downgrade_reason"] == "model paused"


def test_auto_paused_counts_as_paused(monkeypatch):
    """The threshold review's pause list goes through the same branch."""
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: {MODEL})
    p = _game_pick(monkeypatch, prob=0.40)
    assert p["signal_type"] == "NONE"
    assert p["downgrade_reason"] == "model paused"


# ── 2. a declined rule's row says why ────────────────────────────────────────

def test_no_signal_rows_persist_the_reason():
    picks = [
        {"signal_type": "BET", "kelly_fraction": 0.03, "recommended_bet": 250.0},
        {"signal_type": "AVOID", "kelly_fraction": 0.0, "recommended_bet": 0.0},
    ]
    out = scorer._apply_no_signal(picks, "openers not captured simultaneously")
    assert [p["signal_type"] for p in out] == ["NONE", "NONE"]
    assert all(p["downgrade_reason"] == "openers not captured simultaneously"
               for p in out)
    assert all(p["kelly_fraction"] == 0.0 and p["recommended_bet"] == 0.0
               for p in out)


def test_score_game_routes_no_signal_through_the_helper():
    """Source tripwire: the bug was a hand-written NONE with no reason column,
    so the regression to guard is the helper going missing again."""
    src = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
        encoding="utf-8")
    body = src.split("def score_game(")[1].split("\ndef ")[0]
    assert "_apply_no_signal(picks, no_signal)" in body
