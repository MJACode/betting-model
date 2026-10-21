"""
The odds feed bills every GROUP OF TEN named sportsbooks as one region.

Measured 2026-09-20 on one NHL moneyline call: the fourteen names this repo had
requested since 2026-09-03 cost 2 credits; the first ten cost 1. Every odds,
prop and in-play fetch paid double for eighteen days — about 140,000 credits a
day, on course to run the month dry two days before the first NHL game.

An eleventh name anywhere brings that back, silently. These count the names.
"""
from __future__ import annotations

import config

GROUP = 10


def _names(param: str) -> list[str]:
    return [b for b in param.split(",") if b.strip()]


def test_the_shared_list_is_one_group():
    assert len(config.LINE_SHOP_BOOKMAKERS) <= GROUP, config.LINE_SHOP_BOOKMAKERS
    assert len(_names(config.ODDS_API_BOOKMAKERS_PARAM)) <= GROUP


def test_the_history_pull_is_one_group():
    assert len(config.ODDS_HISTORY_BOOKMAKERS) <= GROUP


def test_the_nfl_prop_pull_is_one_group_with_both_references_in_it():
    from data.ingestors.nfl_prop_odds_ingestor import MARKET_BOOKS
    names = _names(MARKET_BOOKS)
    assert len(names) == len(set(names)) <= GROUP, names
    assert {"pinnacle", "betonlineag", "draftkings"} <= set(names)


def test_every_book_the_nfl_prop_model_bets_at_is_actually_fetched():
    """A soft book the pull never requests returns no quotes, not an error."""
    from data.ingestors.nfl_prop_odds_ingestor import MARKET_BOOKS
    from models.nfl_prop_market import SOFT_BOOKS
    assert set(SOFT_BOOKS) <= set(_names(MARKET_BOOKS))


def test_the_sharp_reference_survived_the_cut():
    assert "pinnacle" in config.LINE_SHOP_BOOKMAKERS
    assert "draftkings" in config.LINE_SHOP_BOOKMAKERS
