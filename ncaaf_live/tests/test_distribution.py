"""
Tests for the Stage 2 distribution, focused on the smoothing change.

The uniform-Laplace low-tail artifact failed the first 2025 gate run (4.02pp
worst coverage with ZERO mean bias), so the shrink-to-mu path gets pinned:
its whole point is that prior mass lands on real football outcomes instead of
being smeared over a 91-point support.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.engine.distribution import (  # noqa: E402
    MAX_REMAINING, ScoreDistribution, mu_bucket, time_bucket)


def _synth(n=30_000, seed=0):
    """Predictions plus actuals drawn around them, football-ish."""
    rng = np.random.default_rng(seed)
    mu_h = rng.uniform(3, 35, n)
    mu_a = rng.uniform(3, 35, n)
    secs = rng.uniform(0, 3600, n)
    y_h = np.clip(np.rint(mu_h + rng.normal(0, 6, n)), 0, MAX_REMAINING)
    y_a = np.clip(np.rint(mu_a + rng.normal(0, 6, n)), 0, MAX_REMAINING)
    return y_h, mu_h, y_a, mu_a, secs


def test_marginals_are_normalised_under_both_smoothings():
    args = _synth()
    for kw in (dict(laplace=0.5), dict(laplace=0.01, shrink_k=150.0)):
        d = ScoreDistribution.fit(*args, **kw)
        assert np.allclose(d.pmf_mu_time.sum(axis=-1), 1.0, atol=1e-9)
        assert np.allclose(d.pmf_mu.sum(axis=-1), 1.0, atol=1e-9)


def test_shrink_moves_prior_mass_off_the_impossible_low_tail():
    """
    THE property that motivated the change. From a high-mu state, remaining
    points near zero are (almost) impossible; uniform Laplace still puts
    pseudo-mass there, shrink-to-mu puts it where the mu-pool actually lands.
    """
    args = _synth()
    uni = ScoreDistribution.fit(*args, laplace=0.5)
    shr = ScoreDistribution.fit(*args, laplace=0.01, shrink_k=150.0)

    # a thin-ish high-mu cell: mass on 0..4 remaining from a mu~30 state
    hi_mu = int(mu_bucket(30.0))
    t = int(time_bucket(1800))
    low_tail_uni = float(uni.pmf_mu_time[0, hi_mu, t, :5].sum())
    low_tail_shr = float(shr.pmf_mu_time[0, hi_mu, t, :5].sum())
    assert low_tail_shr < low_tail_uni, (
        "shrink-to-mu should thin the impossible low tail that uniform "
        "smoothing fattens")


def test_no_support_cell_is_ever_exactly_zero():
    """A zero-probability score is an infinite edge on the alt line that
    lands on it - the reason a token laplace floor survives the change."""
    d = ScoreDistribution.fit(*_synth(), laplace=0.01, shrink_k=150.0)
    assert (d.pmf_mu_time > 0).all()
    assert (d.pmf_mu > 0).all()


def test_shrink_zero_reproduces_the_uniform_fit():
    args = _synth()
    a = ScoreDistribution.fit(*args, laplace=0.5)
    b = ScoreDistribution.fit(*args, laplace=0.5, shrink_k=0.0)
    assert np.allclose(a.pmf_mu_time, b.pmf_mu_time)


def test_shrink_weight_behaves_like_pseudo_rows():
    """As shrink_k grows, cells converge to the mu-only prior."""
    args = _synth()
    small = ScoreDistribution.fit(*args, laplace=0.01, shrink_k=10.0)
    big = ScoreDistribution.fit(*args, laplace=0.01, shrink_k=100_000.0)
    hi_mu, t = int(mu_bucket(20.0)), int(time_bucket(900))
    prior = big.pmf_mu[0, hi_mu]
    gap_big = np.abs(big.pmf_mu_time[0, hi_mu, t] - prior).sum()
    gap_small = np.abs(small.pmf_mu_time[0, hi_mu, t] - prior).sum()
    assert gap_big < gap_small
    assert gap_big < 0.02


def test_final_pmf_offsets_by_current_score():
    d = ScoreDistribution.fit(*_synth(), laplace=0.01, shrink_k=150.0)
    out = d.final_score_pmf(14.0, 10.0, 1200.0, 21, 17)
    assert out["home_score"] == 21 and out["away_score"] == 17
    joint = out["joint_remaining"]
    assert joint.shape == (MAX_REMAINING + 1, MAX_REMAINING + 1)
    assert joint.sum() == pytest.approx(1.0, abs=1e-9)
