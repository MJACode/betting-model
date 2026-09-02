"""
NCAAF has to be VISIBLE before it can be bet.

Two failures on 2026-08-29 sat behind one symptom — an empty NCAAF board:

  1. `ncaaf_spread_premium` was registered, trained, and added to
     config.MODELS, but never to FEATURE_MAP. score_game resolves
     FEATURE_MAP[model_id] BEFORE it looks at the artifact, so the KeyError
     escaped run_scorer and killed game-level scoring for EVERY sport for a
     whole day. MLB, WNBA, NHL and UFC picks all stopped; the health check
     said `scoring` was failing but the board just looked quiet.

  2. Even with that fixed, both NCAAF rules answered a game they would not bet
     with `return []` — no row, so the game never appeared at all. A user
     cannot tell "the model is watching and has no view" from "the pipeline is
     broken", and neither could we.

These tests pin the fixes: every registered model has features, and a declined
rule still produces a row that is forced to NONE.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from features.feature_engine import FEATURE_MAP  # noqa: E402
from models.scorer import _days_until, _opener_rule  # noqa: E402

_SRC = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
    encoding="utf-8")


# ── the crash ─────────────────────────────────────────────────────────────────

def test_every_registered_model_has_a_feature_map_entry():
    """
    The generic form of the 2026-08-29 outage. A model in MODELS with no
    FEATURE_MAP entry does not degrade — it raises out of run_scorer and takes
    every other sport's game picks down with it.
    """
    missing = sorted(set(config.MODELS) - set(FEATURE_MAP))
    assert not missing, (
        f"models registered without features: {missing} — score_game will "
        f"raise KeyError and abort scoring for ALL sports")


def test_the_premium_tier_shares_the_spread_features():
    """It is the same rule on the same market, only a disjoint |dev| band."""
    assert FEATURE_MAP["ncaaf_spread_premium"] == FEATURE_MAP["ncaaf_spread"]


# ── the opener rule's decline paths ───────────────────────────────────────────

_ARTIFACT = {
    "kind": "cross_book_opener",
    "sharp_book": "bovada",
    "d_threshold": 1.0,
    "model_prob": 0.5810,
    "max_skew_min": 90.0,
}


def _patch(monkeypatch, *, cur, soft, sharp):
    import models.scorer as sc
    monkeypatch.setattr(sc, "_get_dk_odds", lambda *a, **k: cur)

    def _open(conn, game_id, market, bookmaker):
        return soft if bookmaker == sc.ODDS_API_BOOKMAKER else sharp
    monkeypatch.setattr(sc, "_opening_line", _open)


def _line(spread, at="2026-08-26T07:00:00Z"):
    return {"spread_home": spread, "total_line": None, "home_price": -110,
            "away_price": -110, "snapshot_at": at}


def test_no_current_dk_line_writes_nothing(monkeypatch):
    """Nothing to price and nothing to display."""
    _patch(monkeypatch, cur=None, soft=_line(-3.0), sharp=_line(-4.5))
    assert _opener_rule(None, "g", "ncaaf_spread", "spreads", _ARTIFACT) == (
        None, None, None)


def test_missing_sharp_opener_is_a_no_signal_row(monkeypatch):
    _patch(monkeypatch, cur=_line(-3.0), soft=_line(-3.0), sharp=None)
    home, away, reason = _opener_rule(None, "g", "ncaaf_spread", "spreads", _ARTIFACT)
    assert (home, away) == (0.5, 0.5)
    assert reason and "opener" in reason


def test_the_real_four_day_capture_skew_is_a_no_signal_row(monkeypatch):
    """
    Week 1's actual condition: every game was first polled 2026-08-22, before
    Bovada was ingested. The rule must decline — but the game still shows.
    """
    _patch(monkeypatch,
           cur=_line(-3.0),
           soft=_line(-3.0, "2026-08-22T07:00:00Z"),
           sharp=_line(-4.5, "2026-08-26T07:00:00Z"))
    home, away, reason = _opener_rule(None, "g", "ncaaf_spread", "spreads", _ARTIFACT)
    assert (home, away) == (0.5, 0.5)
    assert "simultaneous" in reason


def test_dk_off_its_opener_is_a_no_signal_row(monkeypatch):
    """The stale number is gone, so the edge is gone — but the line still shows."""
    _patch(monkeypatch, cur=_line(-2.5), soft=_line(-3.0), sharp=_line(-4.5))
    home, away, reason = _opener_rule(None, "g", "ncaaf_spread", "spreads", _ARTIFACT)
    assert (home, away) == (0.5, 0.5)
    assert "moved" in reason


def test_books_agreeing_is_a_no_signal_row(monkeypatch):
    _patch(monkeypatch, cur=_line(-3.0), soft=_line(-3.0), sharp=_line(-3.5))
    home, away, reason = _opener_rule(None, "g", "ncaaf_spread", "spreads", _ARTIFACT)
    assert (home, away) == (0.5, 0.5)
    assert "agree" in reason


def test_the_rule_fires_on_the_side_the_sharp_book_favours(monkeypatch):
    """
    dev = soft(-3.0) - sharp(-4.5) = +1.5 > 0 → sharp favours HOME, so the
    home side carries the validated probability.
    """
    _patch(monkeypatch, cur=_line(-3.0), soft=_line(-3.0), sharp=_line(-4.5))
    home, away, reason = _opener_rule(None, "g", "ncaaf_spread", "spreads", _ARTIFACT)
    assert reason is None
    assert home == pytest.approx(0.5810)
    assert away == pytest.approx(0.4190)


def test_a_fired_pick_clears_its_own_probability_floor(monkeypatch):
    """A qualifying pick must not then be filtered out by the config floor."""
    _patch(monkeypatch, cur=_line(-3.0), soft=_line(-3.0), sharp=_line(-4.5))
    home, _, _ = _opener_rule(None, "g", "ncaaf_spread", "spreads", _ARTIFACT)
    assert home >= config.MODEL_PROB_THRESHOLDS["ncaaf_spread"]


def test_the_band_ceiling_writes_nothing(monkeypatch):
    """The sibling tier is betting this exact side — do not contradict it."""
    art = dict(_ARTIFACT, d_threshold_max=2.5)
    _patch(monkeypatch, cur=_line(-3.0), soft=_line(-3.0), sharp=_line(-6.0))
    assert _opener_rule(None, "g", "ncaaf_spread", "spreads", art) == (
        None, None, None)


def test_the_premium_band_takes_exactly_what_the_standard_band_declined(monkeypatch):
    """The two tiers must partition the range, never overlap it."""
    std = dict(_ARTIFACT, d_threshold=1.0, d_threshold_max=2.5)
    prem = dict(_ARTIFACT, d_threshold=2.5, model_prob=0.6047)
    _patch(monkeypatch, cur=_line(-3.0), soft=_line(-3.0), sharp=_line(-6.0))
    assert _opener_rule(None, "g", "ncaaf_spread", "spreads", std)[0] is None
    assert _opener_rule(None, "g", "ncaaf_spread_premium", "spreads", prem)[0] \
        == pytest.approx(0.6047)


# ── lead arithmetic ───────────────────────────────────────────────────────────

def test_days_until_is_none_without_a_kickoff_time():
    """Unknown lead must never be read as "kicks off now"."""
    assert _days_until(None) is None
    assert _days_until("garbage") is None


def test_days_until_is_positive_for_a_future_kickoff():
    from datetime import datetime, timedelta, timezone
    soon = (datetime.now(timezone.utc) + timedelta(days=3)).isoformat()
    assert _days_until(soon) == pytest.approx(3.0, abs=0.01)


# ── the wiring, at source level ───────────────────────────────────────────────

def test_a_declined_rule_can_never_leak_a_signal():
    """
    Forcing NONE explicitly, rather than trusting the prob/edge thresholds to
    suppress it. The totals ECDF is asymmetric (OOS residual mean -0.62), so an
    inside-the-gate game can still hand the UNDER side a probability above the
    0.65 floor — which would fire a BET the walk-forward never validated.
    """
    i = _SRC.index("\n    if no_signal:\n        for p in picks:")
    block = _SRC[i:i + 400]
    assert 'p["signal_type"]     = "NONE"' in block
    assert 'p["kelly_fraction"]  = 0.0' in block
    assert 'p["recommended_bet"] = 0.0' in block
    assert i < _SRC.index("        _insert_picks(conn, picks)"), (
        "the downgrade must happen BEFORE the row is written")


def test_a_no_signal_row_does_not_lock_an_ncaaf_game_for_the_week():
    """
    NCAAF is scored across a week, so the lock has to mean "a signal is
    locked", not "this game has been looked at". Freezing a NONE row would
    mean the totals rule — game-day by design — could never fire at all.

    This was an NCAAF-only carve-out until 2026-08-30, when it became the
    general rule (mike: "once a pick crosses a threshold, it's picked"). The
    property is unchanged and is now guaranteed for every sport, so the check
    moved from the sport clause to the signal clause — asserting the old
    carve-out would now fail on a codebase that is MORE correct.
    """
    i = _SRC.index("locked_pairs: set[tuple] = set()")
    q = _SRC[i:_SRC.index("locked_pairs.add(", i)]
    assert "p.signal_type = 'BET'" in q
    # And the no-signal rows must still be cleared, or they duplicate per pass.
    assert "signal_type != 'BET'" in _SRC


def test_one_model_cannot_take_down_every_sport():
    i = _SRC.index("                try:\n                    picks = score_game(")
    block = _SRC[i:i + 700]
    assert "model_failures.append" in block
    assert "continue" in block
    # ...but the step must still fail, or the outage goes silent.
    assert "raise RuntimeError(" in _SRC
    assert _SRC.index("conn.commit()\n\n        # Committed first") < _SRC.index(
        "raise RuntimeError("), "surviving picks must be committed before the raise"


# ── the look-ahead's cost, not its behaviour ──────────────────────────────────

def test_unpriced_ncaaf_games_are_skipped_before_the_feature_build():
    """
    The 7-day window holds a whole Saturday slate — 155 look-ahead games on
    2026-08-29, of which DK priced 73. Every NCAAF model returns early without
    a DK line, so the other 82 cost a feature build plus four models' worth of
    round trips to produce nothing. Scoring ran ~10 minutes before this.

    The skip must sit BEFORE the sport dispatch, or it saves nothing.
    """
    skip = _SRC.index("            if game_id in ncaaf_unpriced:")
    assert skip < _SRC.index('elif sport == "NCAAF":'), (
        "the skip must precede the feature build to be worth anything")


def test_the_price_prefilter_can_only_ever_skip_ncaaf():
    """A cost filter that reached another sport would be a behaviour change."""
    i = _SRC.index("        ncaaf_unpriced: set = set()")
    block = _SRC[i:i + 1600]
    assert 'if g[1] == "NCAAF" and g[0] not in priced' in block, (
        "only NCAAF games may enter the skip set")
    assert "sport = 'NCAAF'" in block


def test_the_price_prefilter_fails_open():
    """
    A filter that cannot be built must never empty the board — the failure
    mode is paying the old cost, never showing nothing.
    """
    i = _SRC.index("        ncaaf_unpriced: set = set()")
    block = _SRC[i:i + 1600]
    assert "except Exception as exc:" in block
    assert "ncaaf_unpriced = set()" in block.split("except Exception as exc:")[1]
