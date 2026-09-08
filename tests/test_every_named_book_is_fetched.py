"""Every book we NAME must be a book we FETCH.

THREE INSTANCES IN TWO DAYS, all the same shape and all silent:

  * `fliff` added to nfl_prop_market.SOFT_BOOKS while absent from the pull
    (2026-09-07). Caught only because an existing NFL-specific test happened to
    cover that one pairing.
  * `betonlineag` added as a second sharp reference while absent from the pull
    (2026-09-08). Caught by running the ingestor by hand and reading the counts.
  * backfill_nfl_prop_odds defaulting to a book list containing NEITHER sharp
    reference (2026-09-08). Caught twelve thousand credits into a run.

A book named in one place and fetched in another does not error. The request
succeeds, rows land, counts look healthy, and the board silently shrinks -- so
the failure arrives as "this rule found no edge" rather than as a bug. That is
the most expensive way for this repo to be wrong, and it has now happened three
times, so the guard is general rather than another per-case assertion.

WHAT THIS DOES NOT CHECK: whether the API actually serves a book. That is a
question for the live endpoint and is answered by probing before wiring (as
betonlineag and fliff both were). This checks only that our own declarations
agree with each other, which is the part that has actually gone wrong.
"""
from __future__ import annotations

import pytest

import config


def _param_books(param: str) -> set[str]:
    return {b.strip().lower() for b in param.split(",") if b.strip()}


# (label, the books a model names, the pull that must supply them)
def _cases():
    import models.mlb_prop_market as mlb
    import models.nfl_prop_market as nfl
    import models.wnba_prop_market as wnba
    from data.ingestors.nfl_prop_odds_ingestor import MARKET_BOOKS as NFL_BOOKS

    general = config.ODDS_API_BOOKMAKERS_PARAM

    out = [
        ("nfl soft", nfl.SOFT_BOOKS, NFL_BOOKS),
        ("nfl sharp", nfl.SHARP_BOOKS, NFL_BOOKS),
        ("wnba soft", wnba.SOFT_BOOKS, general),
        ("wnba sharp", (wnba.SHARP_BOOK,), general),
        ("mlb soft", mlb.SOFT_BOOKS, general),
        ("mlb sharp", (mlb.SHARP_BOOK,), general),
    ]
    return out


@pytest.mark.parametrize("label,named,param", _cases(),
                         ids=[c[0] for c in _cases()])
def test_every_named_book_is_in_the_pull_that_serves_it(label, named, param):
    fetched = _param_books(param)
    missing = sorted(b for b in named if b.lower() not in fetched)
    assert not missing, (
        f"{label}: named but never fetched -> {missing}. These produce NO quotes "
        f"and shrink the board without erroring.")


def test_a_sharp_reference_is_never_also_a_soft_book():
    """The reference is the estimate of truth. Betting into it is betting into
    our own number, and §5c's placebo depends on the sets being disjoint."""
    import models.mlb_prop_market as mlb
    import models.nfl_prop_market as nfl
    import models.wnba_prop_market as wnba

    for label, sharp, soft in (
        ("nfl", set(nfl.SHARP_BOOKS), set(nfl.SOFT_BOOKS)),
        ("wnba", {wnba.SHARP_BOOK}, set(wnba.SOFT_BOOKS)),
        ("mlb", {mlb.SHARP_BOOK}, set(mlb.SOFT_BOOKS)),
    ):
        assert not (sharp & soft), f"{label}: {sorted(sharp & soft)} is both"


def test_the_nfl_backfill_defaults_to_the_live_pull():
    """A historical backfill exists to study the rule, so it must buy the board
    the rule reads. It defaulted to a list holding neither sharp reference and
    that cost 12k credits of the wrong data."""
    import inspect

    from data.ingestors.nfl_prop_odds_ingestor import (
        MARKET_BOOKS, backfill_nfl_prop_odds,
    )

    sig = inspect.signature(backfill_nfl_prop_odds)
    assert sig.parameters["books"].default == MARKET_BOOKS


def test_every_bettable_book_can_be_named_to_a_human():
    """A key with no display entry renders as its raw feed name, and
    "hardrockbet" in a channel members pay for reads like a bug."""
    import tracking.discord_notifier as dn
    import tracking.x_publisher as xp

    for book in config.BEST_LINE_BOOKMAKERS:
        assert book in dn._BOOK_NAMES, f"{book}: no Discord display name"
        assert book in xp._BOOK_DISPLAY, f"{book}: no X display name"
