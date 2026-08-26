"""
Sign-convention and probability tests for the NCAAF totals regression.

The failure mode these exist to catch is silent and total: the spread model's
disagreement ADDS the market number (spreads are stored home-relative and a
cover is `margin + spread_home > 0`), while the totals model SUBTRACTS it
(totals are absolute and the over wins on `actual > line`). Copying the spread
branch without flipping that sign inverts every single pick while still
producing plausible-looking probabilities and a full board of bets.

There is no way to notice that from aggregate metrics until money is lost, so
it is pinned here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.ncaaf_feature_engine import (  # noqa: E402
    total_over_prob, margin_cover_prob)


# residuals = sorted OOS (actual - predicted); symmetric around zero
_RESID = sorted([-14.0, -9.0, -5.0, -2.0, 0.0, 2.0, 5.0, 9.0, 14.0])


# ── the sign convention ───────────────────────────────────────────────────────

def test_model_above_the_line_favours_the_over():
    """predicted_total > line  ->  disagreement > 0  ->  P(over) > 0.5."""
    p = total_over_prob(_RESID, +8.0)
    assert p > 0.5, f"model 8 points above the line gave P(over)={p:.3f}"


def test_model_below_the_line_favours_the_under():
    """predicted_total < line  ->  disagreement < 0  ->  P(over) < 0.5."""
    p = total_over_prob(_RESID, -8.0)
    assert p < 0.5, f"model 8 points below the line gave P(over)={p:.3f}"


def test_probability_is_monotone_in_the_disagreement():
    """More disagreement above the line can only mean more over-confidence."""
    probs = [total_over_prob(_RESID, d) for d in (-12, -6, -1, 0, 1, 6, 12)]
    assert probs == sorted(probs), f"not monotone: {probs}"


def test_symmetric_residuals_give_symmetric_probabilities():
    hi = total_over_prob(_RESID, +6.0)
    lo = total_over_prob(_RESID, -6.0)
    assert hi + lo == pytest.approx(1.0, abs=1e-9), (
        "with symmetric residuals, P(over|+d) and P(over|-d) must sum to 1")


def test_scorer_branch_computes_disagreement_by_SUBTRACTING_the_line():
    """
    Guards the scorer itself, not just the helper. If someone copies the
    spread branch (`pred + line`) into the totals branch this fails.
    """
    src = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
        encoding="utf-8")
    i = src.index('kind") == "total_regression"')
    block = src[i:i + 2000]
    assert "pred_total - float(t_odds[\"total_line\"])" in block, (
        "totals disagreement must SUBTRACT the line; adding it (the spread "
        "convention) inverts every pick")
    assert "total_over_prob" in block


def test_spread_and_totals_helpers_are_not_interchangeable():
    """
    Same ECDF shape, opposite meaning of the input. A caller that swaps them
    would still get a number in [0,1] — this documents that they are distinct
    and both are exercised.
    """
    assert margin_cover_prob(_RESID, 8.0) == pytest.approx(
        total_over_prob(_RESID, 8.0))  # same math...
    # ...but the CALLERS build `disagreement` with opposite signs, which is
    # where the distinction lives. See the scorer test above.


# ── robustness ────────────────────────────────────────────────────────────────

def test_no_residuals_returns_one_half_not_a_confident_bet():
    assert total_over_prob([], 20.0) == 0.5
    assert total_over_prob(None, -20.0) == 0.5


def test_extremes_are_clamped_away_from_certainty():
    """An empty ECDF tail is a sample artefact, never a 0% or 100% claim."""
    assert total_over_prob(_RESID, 999.0) <= 0.99
    assert total_over_prob(_RESID, -999.0) >= 0.01


def test_zero_disagreement_is_near_a_coin_flip():
    p = total_over_prob(_RESID, 0.0)
    assert 0.35 < p < 0.65, f"agreeing with the market should be ~0.5, got {p:.3f}"


def test_artifact_kind_is_routed_by_the_scorer():
    """The scorer must branch on kind, not on model_id."""
    src = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
        encoding="utf-8")
    assert 'artifact.get("kind") == "total_regression"' in src
    assert 'artifact.get("kind") == "margin_regression"' in src


def test_no_dk_total_means_skip_not_prob_only():
    """
    A totals pick with no market number has nothing to disagree with. The
    branch must return [] rather than invent a prob-only pick.
    """
    src = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
        encoding="utf-8")
    i = src.index('kind") == "total_regression"')
    block = src[i:i + 1200]
    assert 'total_line") is None' in block
    assert "return []" in block


# ── the symmetric gate (added after the asymmetry was caught pre-launch) ──────

def test_scorer_enforces_the_symmetric_gate_not_just_a_prob_floor():
    """
    The walk-forward validated |disagreement| >= 8.0 SYMMETRICALLY. Because the
    OOS residuals are not centred (mean -0.62), a lone probability floor
    implies an asymmetric gate: +8 gives P(over)=0.650 while -8 gives
    P(under)=0.710, so an under pick would fire around -5 -- a looser rule than
    anything tested. The scorer must therefore check the gate directly.
    """
    src = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
        encoding="utf-8")
    i = src.index('kind") == "total_regression"')
    block = src[i:i + 3000]
    assert 'abs(disagreement) < gate' in block, (
        "the symmetric gate is not enforced; a prob floor alone ships an "
        "asymmetric, partly-unvalidated rule")
    assert 'd_threshold' in block, "gate must come from the artifact, not a constant"


def test_gate_is_read_from_the_artifact_so_a_refit_can_change_it():
    src = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
        encoding="utf-8")
    i = src.index('kind") == "total_regression"')
    block = src[i:i + 3000]
    assert 'artifact.get("d_threshold")' in block


def test_asymmetry_is_real_and_would_have_bitten():
    """
    Guards the premise. If residuals ever become symmetric this test should be
    revisited -- but with the shipped artifact the asymmetry is material.
    """
    resid = sorted([-14.0, -9.0, -5.0, -2.0, -0.6, 1.0, 4.0, 8.0, 13.0])  # skewed
    over_at_plus = total_over_prob(resid, +8.0)
    under_at_minus = 1.0 - total_over_prob(resid, -8.0)
    assert abs(over_at_plus - under_at_minus) > 0.02, (
        "fixture no longer reproduces the asymmetry this guard exists for")
