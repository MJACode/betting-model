"""Standard CLV arithmetic.

Primary: raw price taken vs that same book's raw close. Neither side is
de-vigged. Percent is taken_decimal / close_decimal − 1. Probability points
are close implied − taken implied.

Secondary: raw taken vs a power-de-vigged close (Pinnacle in production).
De-vigging the price we took is the bug this replaces: it inflated CLV and,
on pick 2387645, flipped the sign of the market-edge number.

    python -m pytest -q tests/test_clv_math.py tests/test_clv_standard_v2.py
"""
from __future__ import annotations

import pytest

from models.market_relative import implied
from tracking.clv_math import (
    CLV_METHOD_STANDARD,
    CLV_METHOD_ZERO_VIG,
    DEVIG_POWER,
    DEVIG_POWER_3WAY,
    PEDIGREE_CLV_METHODS,
    ZERO_VIG_BOOKS,
    american_to_decimal,
    close_book_candidates,
    implied_to_american,
    market_edge_clv,
    other_side_prices,
    power_fair,
    same_book_clv,
)


def test_primary_is_raw_on_both_sides_and_reports_percent_and_pp():
    """−120 taken, −145 close. The close is shorter, so we beat it.

    taken implied 120/220, close implied 145/245.
    percent = (1 + 100/120) / (1 + 100/145) − 1.
    """
    pct, pp = same_book_clv(-120, -145)
    taken_p = 120.0 / 220.0
    close_p = 145.0 / 245.0
    taken_d = 1.0 + 100.0 / 120.0
    close_d = 1.0 + 100.0 / 145.0
    assert pct == round((taken_d / close_d - 1.0) * 100.0, 2)
    assert pp == round((close_p - taken_p) * 100.0, 2)
    assert pct == pytest.approx(8.50, abs=0.01)
    assert pp == pytest.approx(4.64, abs=0.01)
    assert pct > 0 and pp > 0


def test_a_worse_close_is_negative_and_equal_prices_are_zero():
    pct, pp = same_book_clv(-140, -120)
    assert pct < 0 and pp < 0
    assert same_book_clv(-160, -160) == (0.0, 0.0)


def test_primary_does_not_move_when_the_other_side_changes():
    """Vig on the other side is not our CLV. The primary sees one price."""
    assert same_book_clv(-110, -110) == (0.0, 0.0)


def test_devigging_the_taken_price_is_not_what_primary_does():
    """−110/−110 taken, close −115/−115. Raw close implied rises, so primary
    is positive: we hold −110 and the same book is now −115. De-vigging BOTH
    two-ways reports exactly 0, which hides the price we actually got."""
    pct, pp = same_book_clv(-110, -115)
    assert pct > 0 and pp > 0
    fair = power_fair([-115, -115])
    assert fair[0] == pytest.approx(0.5)
    # The old both-sides de-vig: fair close 0.5 − fair bet 0.5 = 0.
    assert round((0.5 - 0.5) * 100, 2) == 0.0
    assert pp != 0.0


def test_power_devig_of_a_balanced_market_is_a_coin_flip():
    fair = power_fair([-110, -110])
    assert fair[0] == pytest.approx(0.5)
    assert fair[1] == pytest.approx(0.5)


def test_market_edge_devigs_only_the_close():
    """OddsShopper's Dodgers: bet −130, close −150 / +135.

    Their write-up de-vigs the close multiplicatively and leaves the bet
    raw, and quotes +1.98pp (fair ≈ −141). Power de-vig is the method we
    store: +2.31pp, fair −143. Raw one-sided is +3.48pp. All three leave
    the bet raw; none of them de-vigs the price we took.
    """
    pct, pp, method = market_edge_clv(-130, -150, [135], book="pinnacle")
    assert method == DEVIG_POWER
    raw_pp = (implied(-150) - implied(-130)) * 100
    assert raw_pp == pytest.approx(3.48, abs=0.02)
    assert pp < raw_pp
    assert pp == pytest.approx(2.31, abs=0.02)
    taken_d = american_to_decimal(-130)
    fair = power_fair([-150, 135])[0]
    assert pct == round((taken_d * fair - 1.0) * 100.0, 2)
    assert pct == pytest.approx(4.08, abs=0.02)
    assert implied_to_american(fair) == -143


def test_three_way_power_uses_all_three_sides():
    """NHL regulation. Dropping the draw would hand its mass to the other two."""
    three = power_fair([-150, 180, 400])
    two = power_fair([-150, 180])
    assert three is not None and two is not None
    assert abs(sum(three) - 1.0) < 1e-9
    assert three[0] != pytest.approx(two[0])
    _pct, _pp, method = market_edge_clv(-150, -150, [180, 400], book="pinnacle")
    assert method == DEVIG_POWER_3WAY


def test_a_one_way_close_is_not_de_vigged():
    assert power_fair([-200]) is None
    assert market_edge_clv(-200, -200, [None], book="pinnacle") == (None, None, None)
    assert market_edge_clv(-200, -200, [], book="pinnacle") == (None, None, None)


def test_kalshi_close_is_not_de_vigged():
    assert "kalshi" in ZERO_VIG_BOOKS
    pct, pp, method = market_edge_clv(-130, -150, [135], book="kalshi")
    assert method == CLV_METHOD_ZERO_VIG
    assert pp == round((implied(-150) - implied(-130)) * 100, 2)
    assert pct == round((american_to_decimal(-130) * implied(-150) - 1) * 100, 2)


def test_polymarket_is_in_the_zero_vig_set():
    assert "polymarket" in ZERO_VIG_BOOKS


def test_other_side_prices_include_the_draw_on_a_three_way():
    row = {"home_price": -150, "away_price": 180, "draw_price": 400}
    assert other_side_prices(row, "home") == [180, 400]
    assert other_side_prices(row, "draw") == [-150, 180]
    tot = {"over_price": -110, "under_price": -105}
    assert other_side_prices(tot, "under") == [-110]


def test_sharp_close_books_do_not_fall_back_to_the_pick_book():
    assert close_book_candidates("draftkings") == ["pinnacle"]
    assert close_book_candidates("fanduel") == ["pinnacle"]
    assert close_book_candidates("pinnacle") == ["pinnacle"]


def test_pedigree_is_only_the_standard_method():
    assert PEDIGREE_CLV_METHODS == frozenset({CLV_METHOD_STANDARD})
    assert "no_vig" not in PEDIGREE_CLV_METHODS
    assert "zero_vig" not in PEDIGREE_CLV_METHODS
