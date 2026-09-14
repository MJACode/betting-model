"""No-vig CLV arithmetic — the OddsShopper contract.

Production `picks.clv_pct` used raw `american_to_implied_prob` on a single
DraftKings close (tracking/paper_tracker._capture_clv, through 2026-09-14).
That is the number the vig flatters. These tests pin the honest formula
BEFORE it is wired into capture, and they were watched failing against the
old one-sided helper.

    python -m pytest -q tests/test_clv_math.py
"""
from __future__ import annotations

import pytest

from models.market_relative import implied
from tracking.clv_math import (
    CLV_METHOD_NO_VIG,
    CLV_METHOD_ONE_WAY,
    CLV_METHOD_ZERO_VIG,
    ZERO_VIG_BOOKS,
    close_book_candidates,
    fair_close_probability,
    implied_to_american,
    other_side_prices,
    price_clv_pct,
)


# ── OddsShopper worked example ───────────────────────────────────────────────

def test_oddsshopper_dodgers_no_vig_close():
    """Bet Dodgers −130; close −150 / +135 → fair ≈ 58.5% ≈ −141, not raw −150.

    Source: https://www.oddsshopper.com/articles/betting-101/closing-line-value-explained
    (updated 2026-06-05). Their write-up rounds 58.5%; we pin the exact
    multiplicative de-vig and the rounded pp the capture path stores.
    """
    fair, method = fair_close_probability(-150, [+135], book="draftkings")
    assert method == CLV_METHOD_NO_VIG
    padres = 100.0 / 235.0
    assert fair == pytest.approx(0.60 / (0.60 + padres))
    assert fair == pytest.approx(0.58505, abs=5e-5)
    assert implied_to_american(fair) == -141

    clv, method = price_clv_pct(-130, -150, [+135], book="draftkings")
    assert method == CLV_METHOD_NO_VIG
    bet = 130.0 / 230.0
    assert clv == round((fair - bet) * 100, 2)
    assert clv == pytest.approx(1.98, abs=0.01)


def test_raw_close_flatters_the_dodgers_example():
    """The bug: one-sided implied on −150 reports ~+3.48pp; no-vig is ~+1.98."""
    raw = round((implied(-150) - implied(-130)) * 100, 2)
    no_vig, _ = price_clv_pct(-130, -150, [+135], book="pinnacle")
    assert raw == pytest.approx(3.48, abs=0.01)
    assert no_vig == pytest.approx(1.98, abs=0.01)
    assert no_vig < raw


# ── Two-way multiplicative de-vig ────────────────────────────────────────────

def test_a_fair_market_devigs_to_a_coin_flip():
    fair, method = fair_close_probability(-110, [-110], book="draftkings")
    assert method == CLV_METHOD_NO_VIG
    assert fair == pytest.approx(0.5)


def test_vig_widening_at_close_is_not_clv():
    """Both sides going −110 → −115 is more hold, not a move toward us.

    Raw one-sided implied on our −115 close reads as +1.11pp of 'CLV'. The
    fair number did not move. This is the trap OddsShopper names.

    Close-only de-vig (no lock two-way) vs raw bet is −2.38pp — juice you
    paid, not a beat. De-vigging both two-ways is exactly 0.
    """
    raw = round((implied(-115) - implied(-110)) * 100, 2)
    assert raw == pytest.approx(1.11, abs=0.01)
    close_only, method = price_clv_pct(-110, -115, [-115], book="draftkings")
    assert method == CLV_METHOD_NO_VIG
    assert close_only < 0
    assert close_only != raw
    clv, method = price_clv_pct(
        -110, -115, [-115], book="draftkings", bet_other_prices=[-110])
    assert method == CLV_METHOD_NO_VIG
    assert clv == 0.0


def test_a_real_price_move_still_grades_positive():
    """−110 in, close −150 / +130: the market DID move; no-vig stays positive."""
    clv, method = price_clv_pct(-110, -150, [+130], book="pinnacle")
    assert method == CLV_METHOD_NO_VIG
    assert clv > 0


def test_three_way_devigs_all_three_sides():
    """NHL regulation: home / away / draw. Dropping draw would steal its mass."""
    fair, method = fair_close_probability(-150, [+180, +400], book="draftkings")
    assert method == CLV_METHOD_NO_VIG
    h, a, d = implied(-150), implied(+180), implied(+400)
    assert fair == pytest.approx(h / (h + a + d))
    two_way, _ = fair_close_probability(-150, [+180], book="draftkings")
    assert fair != pytest.approx(two_way)


# ── Zero-vig books must not be de-vigged ─────────────────────────────────────

def test_kalshi_is_not_devigged():
    """Kalshi is already no-vig. De-vigging −150/+135 would pull 60% down to
    58.5% and manufacture a sportsbook hold the exchange does not take."""
    fair, method = fair_close_probability(-150, [+135], book="kalshi")
    assert method == CLV_METHOD_ZERO_VIG
    assert fair == pytest.approx(implied(-150))
    clv, _ = price_clv_pct(-130, -150, [+135], book="kalshi")
    raw = round((implied(-150) - implied(-130)) * 100, 2)
    assert clv == raw


def test_polymarket_is_in_the_zero_vig_set():
    assert "polymarket" in ZERO_VIG_BOOKS
    fair, method = fair_close_probability(-150, [+135], book="polymarket")
    assert method == CLV_METHOD_ZERO_VIG
    assert fair == pytest.approx(implied(-150))


# ── One-way / thin ───────────────────────────────────────────────────────────

def test_a_one_way_market_is_not_silently_devigged():
    """Anytime TD and other one-sided quotes have no second side. Returning
    the raw implied as if it were fair would bake the juice into CLV."""
    fair, method = fair_close_probability(-200, [None], book="draftkings")
    assert method == CLV_METHOD_ONE_WAY
    assert fair == pytest.approx(implied(-200))
    _, method2 = fair_close_probability(-200, [], book="draftkings")
    assert method2 == CLV_METHOD_ONE_WAY


# ── Same-line vs moved-line is the caller's job, but the other-side helper
#    has to find the opposite American so capture can de-vig. ───────────────

def test_other_side_prices_for_totals_and_h2h():
    tot = {"over_price": -110, "under_price": -110, "total_line": 44.5}
    assert other_side_prices(tot, "over") == [-110]
    assert other_side_prices(tot, "under") == [-110]
    h2h = {"home_price": -150, "away_price": +130}
    assert other_side_prices(h2h, "home") == [+130]
    assert other_side_prices(h2h, "away") == [-150]


def test_other_side_prices_include_draw_on_a_three_way():
    row = {"home_price": -150, "away_price": +180, "draw_price": +400}
    assert other_side_prices(row, "home") == [+180, +400]
    assert other_side_prices(row, "draw") == [-150, +180]


# ── Sharp book preference ────────────────────────────────────────────────────

def test_pinnacle_is_tried_before_the_pick_book():
    assert close_book_candidates("draftkings") == ["pinnacle", "draftkings"]
    assert close_book_candidates("fanduel") == ["pinnacle", "fanduel"]
    assert close_book_candidates("pinnacle") == ["pinnacle"]
