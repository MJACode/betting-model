"""The book sweep must never recommend a book the reader cannot bet at.

WHY (2026-09-08). Asked to re-check the soft-book set, the sweep returned
exactly one INCLUDE: `bovada`. It clears all four statistical clauses on 2,172
bets — and it is offshore, absent from config.BEST_LINE_BOOKMAKERS, and already
ruled out by mike after the opener card put seven qualifying Week-1 bets at
books with no US licence: "no can't bet on these remove them".

The sweep had no way to know that. Its recommendation was to start naming bets
nobody could take, and the only thing between that and production was somebody
happening to remember. That is not a control, so bettability is now clause zero
— asked before any statistics, because no amount of edge rescues a book you
cannot walk up to.

BEST_LINE_BOOKMAKERS, not LINE_SHOP_BOOKMAKERS, is the right list: the second is
deliberately broader because an unbettable book is still a useful price signal.
It just cannot be the side we take.
"""
from __future__ import annotations

import config
from scripts.nfl_prop_book_sweep import soft_verdict

# Comfortably passing stats, so only the bettability clause can decide.
GOOD = {"bets": 2172, "roi_ci": (2.5, 10.8), "roi_pct": 6.69}


def _verdict(book):
    return soft_verdict(GOOD, 0.90, 100, 6.0, 6.0, book=book)


def test_an_unbettable_book_is_excluded_however_good_its_numbers():
    ok, why = _verdict("bovada")
    assert not ok, "bovada clears the statistics and still cannot be bet"
    assert "not bettable" in why


def test_a_bettable_book_still_passes():
    ok, why = _verdict("fanduel")
    assert ok and why == "clears all four"


def test_every_incumbent_soft_book_is_bettable():
    """If this ever fails, the shipped strategy is naming bets that cannot be
    placed — which is the failure the clause exists to prevent, already live."""
    import models.nfl_prop_market as mk

    unbettable = [b for b in mk.SOFT_BOOKS
                  if b not in config.BEST_LINE_BOOKMAKERS]
    assert not unbettable, (
        f"{unbettable} are in SOFT_BOOKS but not BEST_LINE_BOOKMAKERS, so the "
        f"rule can name a bet the reader has no account for")


def test_the_clause_is_not_dead_code():
    """It was, briefly: the first version read the book off the stats dict,
    which has no such key, so it never fired while still printing a verdict."""
    assert _verdict("bovada")[0] is False
    assert _verdict(None)[0] is True, (
        "omitting the book must not silently exclude everything")
