"""
Market-relative MLB props, and the shared edge maths underneath.

The projection approach is measured to lose here (nine of eleven prop models
negative, and a 185-cell sweep with a 0.055 train-to-test correlation). The
market-relative construction is the one thing in this repo with a blind-tested
positive result. These tests pin the two properties that decide whether the
port is honest rather than flattering:

  * only EQUAL lines are compared -- 5.5 against 6.5 is a different bet, and
    treating that price gap as edge manufactures one out of nothing
  * a market the sharp book does not price is EXCLUDED, not silently traded on
    thin coverage
"""

from __future__ import annotations

import pytest

from models import market_relative as mr
from models import mlb_prop_market as mpm


def _q(line, over, under):
    return {"line": line, "over_price": over, "under_price": under}


# ── the arithmetic ───────────────────────────────────────────────────────────

def test_devig_removes_the_hold_symmetrically():
    o, u = mr.devig(-110, -110)
    assert o == pytest.approx(0.5) and u == pytest.approx(0.5)


def test_devig_reports_one_way_markets_as_none():
    assert mr.devig(-110, None) == (None, None)


def test_implied_handles_both_signs():
    assert mr.implied(-200) == pytest.approx(2/3)
    assert mr.implied(+150) == pytest.approx(0.4)


# ── the honesty property: equal lines only ───────────────────────────────────

def test_a_different_line_is_never_compared():
    """Pinnacle 5.5 vs DK 6.5 is a different proposition. Counting the price
    gap between them as edge is how a +13% result turned out to be a
    measurement artifact."""
    quotes = {
        ("G", "Judge", "batter_total_bases", "pinnacle"):   _q(5.5, -110, -110),
        ("G", "Judge", "batter_total_bases", "draftkings"): _q(6.5, +200, -260),
    }
    bets, diag = mr.find_bets(quotes, "pinnacle", min_edge=0.01)
    assert bets == []
    assert diag["line_mismatch"] == 1
    assert diag["compared"] == 0


def test_an_equal_line_with_a_real_disagreement_is_a_bet():
    quotes = {
        ("G", "Judge", "batter_total_bases", "pinnacle"):   _q(1.5, -110, -110),
        ("G", "Judge", "batter_total_bases", "draftkings"): _q(1.5, +130, -160),
    }
    bets, diag = mr.find_bets(quotes, "pinnacle", min_edge=0.05)
    assert diag["compared"] == 1
    assert [b.side for b in bets] == ["over"]
    assert bets[0].edge > 0.05
    assert bets[0].book == "draftkings"


def test_agreement_produces_no_bet():
    quotes = {
        ("G", "Judge", "batter_total_bases", "pinnacle"):   _q(1.5, -110, -110),
        ("G", "Judge", "batter_total_bases", "draftkings"): _q(1.5, -110, -110),
    }
    bets, _ = mr.find_bets(quotes, "pinnacle", min_edge=0.01)
    assert bets == []


def test_a_prop_the_sharp_book_did_not_price_is_counted_not_traded():
    quotes = {
        ("G", "Soto", "batter_hits", "draftkings"): _q(0.5, +120, -150),
    }
    bets, diag = mr.find_bets(quotes, "pinnacle", min_edge=0.0)
    assert bets == []
    assert diag["no_sharp"] == 1


def test_the_sharp_book_is_never_bet_against_itself():
    quotes = {
        ("G", "Judge", "batter_total_bases", "pinnacle"): _q(1.5, +200, -260),
    }
    bets, _ = mr.find_bets(quotes, "pinnacle", min_edge=0.0)
    assert bets == []


# ── MLB coverage discipline ──────────────────────────────────────────────────

def test_only_markets_pinnacle_actually_prices_are_traded():
    for m in ("batter_hits", "batter_rbis", "batter_walks",
              "pitcher_earned_runs", "pitcher_walks", "batter_stolen_bases"):
        assert m not in mpm.SHARP_MARKETS, (
            f"{m} is quoted by Pinnacle 0% of the time — it cannot be traded "
            f"market-relative")


def test_a_market_under_the_coverage_floor_is_excluded():
    """batter_runs_scored is 2.3% of DK's rows. Trading it would produce a
    handful of comparisons a week and a record that means nothing."""
    assert mpm.SHARP_COVERAGE["batter_runs_scored"] < mpm.MIN_COVERAGE
    assert "batter_runs_scored" not in mpm.SHARP_MARKETS


def test_the_best_covered_market_is_traded():
    assert "batter_total_bases" in mpm.SHARP_MARKETS
    assert mpm.SHARP_COVERAGE["batter_total_bases"] > 0.5


def test_no_default_threshold_is_shipped():
    """The NFL rule's 5pp was pre-committed against a blind season. Nothing
    here is, so a constant in the module would look validated and would not
    be."""
    assert not hasattr(mpm, "MIN_EDGE")
    assert not hasattr(mpm, "DEFAULT_MIN_EDGE")


# ── the NFL model must be unchanged by the extraction ────────────────────────

def test_the_nfl_model_still_exposes_its_own_names():
    from models import nfl_prop_market as npm
    assert npm.SHARP_BOOK == "pinnacle"
    for name in ("MarketBet", "devig", "implied", "find_bets"):
        assert hasattr(npm, name), f"{name} must stay importable from nfl_prop_market"


def test_the_nfl_binding_still_defaults_to_pinnacle():
    """find_bets there takes no sharp_book argument; it must bind Pinnacle."""
    from models import nfl_prop_market as npm
    quotes = {
        ("G", "X", "player_receptions", "pinnacle"):   _q(4.5, -110, -110),
        ("G", "X", "player_receptions", "draftkings"): _q(4.5, +130, -160),
    }
    bets, diag = npm.find_bets(quotes, min_edge=0.05)
    assert diag["compared"] == 1 and len(bets) == 1
