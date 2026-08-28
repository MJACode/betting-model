"""
Engine invariants: the score distribution, the markets derived from it, and
the anchor blend.

These are PROPERTIES, not regression fixtures. A number that changes when the
model is retrained is not worth pinning; a marginal that stops summing to one
means every price downstream is wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.engine.distribution import (  # noqa: E402
    MU_CENTRES, N_MU, SUPPORT, gaussian_copula_joint, mu_bucket, time_bucket,
)
from live_model.engine.pricing import (  # noqa: E402
    anchor_to_market, american_to_decimal, american_to_prob, devig_power,
    margin_pmf, price_moneyline, price_second_half, price_spread,
    price_team_total, price_total, total_pmf,
)


def _pmf(points, probs):
    p = np.zeros(len(SUPPORT))
    for pt, pr in zip(points, probs):
        p[pt] = pr
    return p / p.sum()


@pytest.fixture
def dist_out():
    """A lumpy remaining-points distribution with real 3 and 7 point atoms."""
    ph = _pmf([0, 3, 7, 10, 14, 17, 21], [.15, .15, .20, .15, .15, .10, .10])
    pa = _pmf([0, 3, 7, 10, 14], [.20, .20, .25, .20, .15])
    return {"joint_remaining": np.outer(ph, pa), "support": SUPPORT,
            "home_score": 21, "away_score": 17, "rho": 0.0}


# ------------------------------------------------------------------ copula
@pytest.mark.parametrize("rho", [0.0, 0.06, -0.07, 0.4, -0.4, 0.9, -0.9])
def test_copula_preserves_both_marginals_exactly(rho):
    """
    The coupling must not move the total or the moneyline. If it does, the
    anchor blend is silently undone every time a price is computed.
    """
    pa = _pmf([0, 3, 7, 10, 14, 21], [.3, .2, .2, .1, .1, .1])
    pb = _pmf([0, 7, 14, 17], [.4, .3, .2, .1])
    j = gaussian_copula_joint(pa, pb, rho)
    assert j.sum() == pytest.approx(1.0, abs=1e-9)
    assert np.abs(j.sum(axis=1) - pa).max() < 1e-9
    assert np.abs(j.sum(axis=0) - pb).max() < 1e-9


def test_copula_covariance_takes_the_sign_of_rho():
    pa = _pmf([0, 7, 14], [.3, .4, .3])
    pb = _pmf([0, 7, 14], [.3, .4, .3])
    def cov(r):
        j = gaussian_copula_joint(pa, pb, r)
        return (j * np.outer(SUPPORT, SUPPORT)).sum() - \
               (j.sum(1) * SUPPORT).sum() * (j.sum(0) * SUPPORT).sum()
    assert cov(0.5) > 0.5
    assert cov(-0.5) < -0.5
    assert abs(cov(0.0)) < 1e-9


def test_buckets_are_monotone_and_bounded():
    assert [int(time_bucket(s)) for s in (0, 119, 121, 3600)] == [0, 0, 1, 6]
    assert int(mu_bucket(0.0)) == 0
    assert int(mu_bucket(1e6)) == N_MU - 1
    assert list(MU_CENTRES) == sorted(MU_CENTRES)


# ----------------------------------------------------------------- pricing
def test_every_market_is_a_proper_distribution(dist_out):
    assert sum(price_moneyline(dist_out).values()) == pytest.approx(1.0)
    assert sum(price_spread(dist_out, -3.5).values()) == pytest.approx(1.0)
    assert sum(price_total(dist_out, 47.5).values()) == pytest.approx(1.0)
    assert sum(price_team_total(dist_out, "home", 27.5).values()) == pytest.approx(1.0)


def test_integer_lines_carry_push_mass_and_half_points_do_not(dist_out):
    assert price_spread(dist_out, -4.0)["push"] > 0
    assert price_spread(dist_out, -3.5)["push"] == 0.0
    assert price_total(dist_out, 48.0)["push"] > 0
    assert price_total(dist_out, 47.5)["push"] == 0.0


def test_a_tie_is_a_moneyline_push_not_a_win_for_either_side(dist_out):
    ml = price_moneyline(dist_out)
    assert ml["push"] > 0
    assert ml["home"] + ml["away"] < 1.0


def test_prices_are_monotone_in_the_line(dist_out):
    """A higher total must be harder to go over. Not automatic once a copula
    and a discrete grid are involved, and a violation would mean an alternate
    line could be priced as a free bet against its own main line."""
    # The tolerance is for float noise only: summing a 71x71 grid in a
    # different order produces differences around 1e-16, which is not a
    # monotonicity failure and must not be reported as one.
    eps = 1e-12
    overs = [price_total(dist_out, ln)["over"] for ln in np.arange(35.5, 60.5, 1.0)]
    assert all(a >= b - eps for a, b in zip(overs, overs[1:]))
    covers = [price_spread(dist_out, s)["home"] for s in np.arange(-14.5, 14.5, 1.0)]
    assert all(a <= b + eps for a, b in zip(covers, covers[1:]))


def test_second_half_at_halftime_is_exactly_the_remaining_distribution(dist_out):
    """At halftime, second half points and remaining points are the same
    quantity. If these ever disagree, the highest value lane in the system is
    quoting a number inconsistent with its own full game total."""
    half = price_second_half(dist_out, "totals_h2", 20.5,
                             dist_out["home_score"], dist_out["away_score"])
    direct = price_total({**dist_out, "home_score": 0, "away_score": 0}, 20.5)
    assert half["over"] == pytest.approx(direct["over"])


def test_second_half_after_halftime_nets_out_points_already_scored(dist_out):
    """Priced in the third quarter, the second half market must count the
    points scored since halftime and not double count them."""
    later = price_second_half(dist_out, "totals_h2", 20.5,
                              half_home_score=14, half_away_score=10)
    at_half = price_second_half(dist_out, "totals_h2", 20.5,
                                half_home_score=21, half_away_score=17)
    assert later["over"] > at_half["over"]


def test_margin_and_total_pmfs_agree_with_the_joint(dist_out):
    j = dist_out["joint_remaining"]
    mv, mp = margin_pmf(j, 4)
    tv, tp = total_pmf(j, 38)
    assert mp.sum() == pytest.approx(1.0)
    assert tp.sum() == pytest.approx(1.0)
    exp_h = (j.sum(1) * SUPPORT).sum()
    exp_a = (j.sum(0) * SUPPORT).sum()
    assert (mv * mp).sum() == pytest.approx(exp_h - exp_a + 4, abs=1e-6)
    assert (tv * tp).sum() == pytest.approx(exp_h + exp_a + 38, abs=1e-6)


# ------------------------------------------------------------------- devig
def test_devig_of_a_fair_market_is_a_coin_flip():
    a, b = devig_power(-110, -110)
    assert a == pytest.approx(0.5, abs=1e-6)
    assert a + b == pytest.approx(1.0)


def test_devig_removes_hold_from_a_lopsided_moneyline():
    raw = american_to_prob(-600) + american_to_prob(425)
    assert raw > 1.0                       # the book's hold
    a, b = devig_power(-600, 425)
    assert a + b == pytest.approx(1.0)
    assert a < american_to_prob(-600)      # the favourite is shaded down


def test_american_odds_convert_across_the_sign_flip():
    assert american_to_decimal(100) == pytest.approx(2.0)
    assert american_to_decimal(-110) == pytest.approx(1.909, abs=1e-3)
    assert american_to_prob(-110) > american_to_prob(110)


# ------------------------------------------------------------------ anchor
def test_anchor_moves_the_model_onto_the_market_moneyline(dist_out):
    """
    Constraint 4: the live main line is truth. If anchoring does not actually
    land on the market number, every derivative edge is contaminated by our
    disagreement with the sharpest price on the board.
    """
    for target in (0.35, 0.5, 0.75, 0.9):
        out = anchor_to_market(dist_out, market_home_wp=target)
        assert price_moneyline(out)["home"] == pytest.approx(target, abs=0.01)


def test_anchor_moves_the_model_onto_the_market_total(dist_out):
    for target in (44.0, 52.0, 58.0):
        out = anchor_to_market(dist_out, market_total=target)
        tv, tp = total_pmf(out["joint_remaining"],
                           out["home_score"] + out["away_score"])
        assert (tv * tp).sum() == pytest.approx(target, abs=0.5)


def test_anchoring_leaves_a_proper_distribution(dist_out):
    out = anchor_to_market(dist_out, market_home_wp=0.7, market_total=50.0)
    assert out["joint_remaining"].sum() == pytest.approx(1.0)
    assert (out["joint_remaining"] >= 0).all()
    assert out["anchored"] is True
