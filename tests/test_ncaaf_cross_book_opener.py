"""
Tests for the NCAAF cross-book opener rule.

The rule backs the side a SHARP book's opener favours, at a SOFT book's stale
number. Its whole validity rests on a condition the backtest could not check,
because CFBD ships no timestamps: that both openers were observable at the
SAME MOMENT. If the sharp book's number is merely recorded later, `dev`
measures elapsed line movement and the "edge" is an artefact.

So the scorer enforces three preconditions, and these tests pin them. Removing
any one turns a validated rule into a plausible-looking way to lose money:

  1. simultaneity  -- the two openers within max_skew_min
  2. still gettable -- DK's CURRENT spread still equals its opening spread
  3. the gate      -- |dev| >= d_threshold

Concretely: every NCAAF game in the odds table was first polled 2026-08-22,
before Bovada was ingested. Those games are ~4 days of skew apart and MUST be
declined.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.scorer import _minutes_apart, OPENER_MAX_SKEW_MIN  # noqa: E402
from scripts.ncaaf_search.register_opener import (  # noqa: E402
    build_artifact, GATE_RECORDS, SHARP_BOOK)

_SRC = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
    encoding="utf-8")


def _branch() -> str:
    i = _SRC.index('kind") == "cross_book_opener"')
    return _SRC[i:i + 5000]


# ── skew arithmetic ───────────────────────────────────────────────────────────

def test_identical_timestamps_are_zero_apart():
    assert _minutes_apart("2026-08-26T07:00:00", "2026-08-26T07:00:00") == 0.0


def test_the_real_production_skew_is_rejected():
    """
    Every NCAAF game was first polled 2026-08-22; Bovada arrives 2026-08-26.
    That is 5,760 minutes -- far beyond any sane tolerance.
    """
    skew = _minutes_apart("2026-08-22T07:00:00", "2026-08-26T07:00:00")
    assert skew == pytest.approx(5760.0)
    assert skew > OPENER_MAX_SKEW_MIN, (
        "the 4-day capture gap must fail the simultaneity check")


def test_one_refresh_pass_late_is_tolerated():
    """A book appearing one ~60min pass late is still the same opening market."""
    assert _minutes_apart("2026-08-26T07:00:00", "2026-08-26T08:00:00") <= OPENER_MAX_SKEW_MIN


def test_unparseable_timestamps_fail_closed():
    """Unknown timing must never be treated as simultaneous."""
    assert _minutes_apart("garbage", "2026-08-26T07:00:00") is None
    assert _minutes_apart(None, "2026-08-26T07:00:00") is None


def test_timezone_suffixes_do_not_crash():
    assert _minutes_apart("2026-08-26T07:00:00Z", "2026-08-26T07:30:00Z") == pytest.approx(30.0)


# ── the three preconditions, in the scorer ────────────────────────────────────

def test_simultaneity_is_enforced():
    b = _branch()
    assert "max_skew" in b and "_minutes_apart" in b
    assert "skew is None or skew > max_skew" in b, (
        "the rule must decline when the two openers were not captured together")


def test_still_gettable_is_enforced():
    """
    If DK has already moved off its opener, the number the backtest bet no
    longer exists. Betting the CURRENT line instead would be a different,
    unvalidated rule.
    """
    b = _branch()
    assert 'float(cur["spread_home"]) != float(soft_open["spread_home"])' in b


def test_gate_is_enforced_and_read_from_the_artifact():
    b = _branch()
    assert "abs(dev) < gate" in b
    assert 'artifact.get("d_threshold")' in b


def test_every_precondition_failure_returns_no_pick():
    """Each guard must `return []`, never fall through to a degraded pick."""
    b = _branch()
    # opener missing, skew too large, DK moved, gate not cleared
    assert b.count("return []") >= 4


def test_soft_book_is_draftkings_so_the_dk_only_invariant_holds():
    """
    We bet at the SOFT book's number, so the soft book must be the book we
    price against. If the soft book were anything else the pick's price would
    not be DK's and the platform-wide invariant would break.
    """
    b = _branch()
    assert "ODDS_API_BOOKMAKER" in b
    assert build_artifact()["soft_book"] == "draftkings"


def test_dev_sign_maps_to_the_side_the_sharp_book_favours():
    """
    dev = soft_home_line - sharp_home_line. dev > 0 means the soft book's home
    number is more generous, i.e. the sharp book implicitly favours HOME.
    Inverting this backs the wrong side on every pick.
    """
    b = _branch()
    assert "dev > 0" in b
    assert 'soft_open["spread_home"]) - float(sharp_open["spread_home"])' in b


# ── the artifact ──────────────────────────────────────────────────────────────

def test_artifact_shape():
    a = build_artifact()
    assert a["kind"] == "cross_book_opener"
    assert a["model"] is None, "a deterministic rule must not carry a fitted model"
    assert a["feature_cols"] == []
    assert a["market"] == "spreads"
    assert a["sharp_book"] == SHARP_BOOK
    assert a["soft_book"] == "draftkings"


def test_flat_probability_matches_the_validated_record():
    for gate, rec in GATE_RECORDS.items():
        a = build_artifact(gate)
        assert a["model_prob"] == rec["win_rate"], (
            "model_prob must be the pooled validated win rate at that gate, "
            "not an invented number")
        assert a["d_threshold"] == gate


def test_unknown_gate_is_refused():
    with pytest.raises(SystemExit):
        build_artifact(4.75)


def test_flat_prob_clears_the_configured_floor():
    """A qualifying pick must not then be filtered out by the prob threshold."""
    import config
    floor = config.MODEL_PROB_THRESHOLDS["ncaaf_spread"]
    assert build_artifact()["model_prob"] > floor, (
        f"validated prob {build_artifact()['model_prob']} does not clear "
        f"the configured floor {floor} — every pick would be suppressed")
