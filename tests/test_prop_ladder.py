"""The ladder interpolator: it must refuse more often than it guesses.

This is the piece that turns Kalshi's strike ladder into a fair probability at
an arbitrary line, which is how the 63,676 propositions discarded on line
mismatch become priceable. Everything here is about the ways an interpolator
can be confidently wrong rather than obviously broken.
"""
from __future__ import annotations

import math

import pytest

from models.prop_ladder import Ladder, Rung, from_kalshi

# Dak Prescott, passing yards, mid-prices measured off Kalshi 2026-09-08.
DAK = [(174.5, .80, .87), (199.5, .76, .81), (224.5, .60, .70),
       (249.5, .45, .57), (274.5, .31, .42), (299.5, .17, .28),
       (324.5, .09, .19), (349.5, .07, .12)]


def _ladder(rows):
    return Ladder([Rung(s, b, a) for s, b, a in rows])


def test_a_quoted_strike_returns_its_own_mid():
    lad = _ladder(DAK)
    assert lad.p_over(249.5) == pytest.approx(0.51, abs=1e-9)


def test_an_unquoted_line_interpolates_between_its_neighbours():
    """The whole point: 252.5 is not on the ladder and must still be priced."""
    lad = _ladder(DAK)
    p = lad.p_over(252.5)
    assert p is not None
    # Strictly between the 249.5 and 274.5 mids, and nearer the former.
    assert 0.365 < p < 0.510
    assert p > 0.45, "3 yards into a 25-yard gap should barely move the price"


def test_it_refuses_to_extrapolate_past_the_quoted_strikes():
    """Beyond the ladder the tail shape is exactly what nobody has priced."""
    lad = _ladder(DAK)
    assert lad.p_over(100.0) is None
    assert lad.p_over(500.0) is None


def test_probability_is_non_increasing_across_the_whole_range():
    lad = _ladder(DAK)
    xs = [174.5 + i * 2.5 for i in range(71)]
    ps = [lad.p_over(x) for x in xs]
    assert all(p is not None for p in ps)
    assert all(a >= b - 1e-9 for a, b in zip(ps, ps[1:])), "survival must fall"


def test_crossed_quotes_are_repaired_not_trusted():
    """A stale rung can print ABOVE a lower strike, which is impossible. The
    first version of this interpolated straight through and produced a fair
    value that was wrong without looking wrong."""
    rows = [(200.0, .70, .74), (225.0, .78, .82), (250.0, .40, .44)]
    lad = _ladder(rows)
    assert lad.repaired, "the 225 rung is above the 200 rung and must be fixed"
    ps = [lad.p_over(x) for x in (200.0, 225.0, 250.0)]
    assert all(a >= b - 1e-9 for a, b in zip(ps, ps[1:]))
    # PAVA POOLS the offending pair (mean of .72 and .80) rather than deleting
    # either quote -- which of the two is the stale one is precisely what we do
    # not know, so the repair splits the difference instead of guessing.
    assert lad.p_over(200.0) == pytest.approx(0.76, abs=1e-6)
    assert lad.p_over(225.0) == pytest.approx(0.76, abs=1e-6)


def test_a_clean_ladder_is_not_reported_as_repaired():
    assert not _ladder(DAK).repaired


def test_wide_and_one_sided_rungs_are_dropped():
    """bid 0.00 against ask 0.11 is not a market, and the deep tails of every
    real ladder look like that."""
    rows = DAK + [(399.5, 0.00, 0.11)]
    lad = _ladder(rows)
    assert 399.5 not in lad.strikes
    assert lad.p_over(399.5) is None


def test_too_few_usable_rungs_is_unusable_rather_than_wrong():
    lad = _ladder([(200.0, .50, .54), (225.0, .40, .44)])
    assert not lad.usable
    assert lad.p_over(210.0) is None


def test_the_implied_median_is_where_the_market_prices_a_coin_flip():
    """A book's LINE sits at the median; a projection model produces a MEAN, and
    yardage is right-skewed. Exposing the market's median is what lets the two be
    compared on the same quantity."""
    lad = _ladder(DAK)
    med = lad.implied_median()
    assert med is not None
    assert 249.5 <= med <= 274.5, med


def test_duplicate_strikes_keep_the_tighter_quote():
    lad = _ladder([(200.0, .60, .80), (200.0, .69, .71), (225.0, .50, .52),
                   (250.0, .40, .42)])
    assert lad.strikes.count(200.0) == 1
    assert lad.p_over(200.0) == pytest.approx(0.70, abs=1e-9)


def test_from_kalshi_reads_the_dollars_fields():
    """The API renamed prices to `*_dollars`. Reading `yes_bid`/`yes_ask`
    returns nothing and looks exactly like an empty market -- which is how the
    first probe concluded Kalshi had no two-sided prop board when every single
    market had one."""
    markets = [
        {"floor_strike": 199.5, "yes_bid_dollars": "0.76", "yes_ask_dollars": "0.81"},
        {"floor_strike": 224.5, "yes_bid_dollars": "0.60", "yes_ask_dollars": "0.70"},
        {"floor_strike": 249.5, "yes_bid_dollars": "0.45", "yes_ask_dollars": "0.57"},
        {"floor_strike": 274.5, "yes_bid": 0.31, "yes_ask": 0.42},   # old names
    ]
    lad = from_kalshi(markets)
    assert lad.strikes == [199.5, 224.5, 249.5]
    assert lad.usable
    assert lad.p_over(210.0) is not None


def test_interpolation_stays_a_probability_across_a_wide_gap():
    """The reason for logit space, stated correctly.

    An earlier version of this test asserted logit reads ABOVE the straight line
    near the floor. That is false -- between .20 and .03 the logit curve is
    convex and sits BELOW it -- and the assertion was mine, not the market's.
    What logit actually guarantees is that no interpolation can leave (0, 1),
    however wide the gap or steep the fall, which linear interpolation does not.
    """
    lad = _ladder([(300.0, .18, .22), (400.0, .02, .04)])
    lad.min_rungs = 2
    xs = [300.0 + i for i in range(0, 101, 5)]
    ps = [lad.p_over(x) for x in xs]
    assert all(p is not None and 0.0 < p < 1.0 for p in ps)
    assert all(a >= b - 1e-12 for a, b in zip(ps, ps[1:]))
    assert ps[0] == pytest.approx(0.20, abs=1e-9)
    assert ps[-1] == pytest.approx(0.03, abs=1e-9)
