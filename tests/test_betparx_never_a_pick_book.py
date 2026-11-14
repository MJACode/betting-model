"""betPARX and Hard Rock are never the book a pick is decided at or a member is
sent to.

mike, 2026-11-06: *"global rule. remove betparx from sports books for
recommeding betting lines in picks only niche avaialble in a few states"*.
betPARX ships one app per state (Maryland, Pennsylvania, New Jersey --
mobile/src/lib/sportsbookLinks.ts), so a pick that names it sends most members
to a book they cannot open. 60 BETs had been decided there by that day, 53 of
them in the 30 days before.

mike, 2026-11-13: *"Hard rock needs to be removed from the basis of picks as
the best line. We can't bet this in Massachusetts"*. Hard Rock Bet is live in
ten states, none of them Massachusetts. It had decided 154 of the 685 BETs
written in the 30 days before, more than any other book.

The rule is about RECOMMENDING, not about data: both stay in the fetch, so
their quotes keep arriving for the consensus models that read every book.

Every surface is covered here because each one carries its own copy of "which
books may a pick name": config's two lists, the NFL cards' standalone fallback,
the NBA in-play fetch, the app's mirror, and the scorer's shop itself. Each
test runs once per book, so a book added to config.STATE_LIMITED_BOOKMAKERS
without its copies fails here.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

import config
from models.scorer import _best_game_price, _best_prop_price

REPO = Path(__file__).resolve().parent.parent
BOOKS = ("betparx", "hardrockbet")
each_book = pytest.mark.parametrize("book", BOOKS)


def _source(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


class FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self._rows


# ── config: the two deciding lists ───────────────────────────────────────────

def test_the_state_limited_books_are_exactly_these():
    """A book added to the set must be added to BOOKS here, so every test
    below covers it."""
    assert config.STATE_LIMITED_BOOKMAKERS == set(BOOKS)


@each_book
def test_no_pick_is_decided_or_shopped_at_the_book(book):
    assert book not in config.BEST_LINE_BOOKMAKERS
    assert book not in config.BETTABLE_BOOKS
    assert book not in config.LIVE_FEED_BOOKMAKERS


@each_book
def test_the_book_is_still_fetched(book):
    """Removed from picks, not from the data: the NCAAB and NCAAF consensus
    models take a median over every book, both of these included, and a book
    dropped from the fetch returns no quotes rather than an error."""
    assert book in config.LINE_SHOP_BOOKMAKERS
    assert book in config.ODDS_API_BOOKMAKERS_PARAM


@each_book
def test_an_environment_override_cannot_put_the_book_back(book):
    """The espnbet exclusion is one env var to reverse. This one is a rule, so
    an override of either list -- including the empty exclude list that means
    "shop every book" -- still leaves the book out. Run in a fresh interpreter:
    reloading config in this one would hand every other test a second copy."""
    import json
    import subprocess
    import sys
    env = {**os.environ,
           "BEST_LINE_EXCLUDE_BOOKMAKERS": "",
           "BEST_LINE_BOOKMAKERS": f"draftkings,{book},fanduel",
           "BETTABLE_BOOKS": f"draftkings,{book}",
           "PYTHONIOENCODING": "utf-8"}
    out = subprocess.run(
        [sys.executable, "-c",
         "import json, config; print(json.dumps([config.BEST_LINE_BOOKMAKERS, "
         "config.BETTABLE_BOOKS]))"],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    best_line, bettable = json.loads(out.stdout.strip().splitlines()[-1])
    assert best_line == ["draftkings", "fanduel"]
    assert bettable == ["draftkings"]


# ── the scorer's shop: the behaviour, not just the list ──────────────────────

@each_book
def test_a_better_game_price_at_the_book_does_not_win_the_shop(book):
    rows = [
        ("draftkings", -150, None, None, None, "2026-11-06T15:00:00Z"),
        (book, -120, None, None, None, "2026-11-06T15:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "NBA_2026-11-06_BOS_NYK", "h2h", "home", None)
    assert best is not None and best["book"] == "draftkings"


@each_book
def test_a_better_prop_price_at_the_book_does_not_win_the_shop(book):
    rows = [   # bookmaker, over price, over link, line, snapshot_at
        ("draftkings", -115, None, 5.5, "2026-11-06T15:00:00Z"),
        (book, +120, None, 5.5, "2026-11-06T15:00:00Z"),
    ]
    best = _best_prop_price(FakeConn(rows), "NBA_2026-11-06_BOS_NYK", "Jayson Tatum",
                            "player_rebounds", "over", 5.5)
    assert best is not None and best["book"] == "draftkings"


# ── the other copies of the list ─────────────────────────────────────────────

@each_book
def test_the_nfl_cards_never_bet_at_the_book(book, monkeypatch):
    """nfl/data_ingest/books.py runs standalone with no repo config, so it
    carries a literal fallback; all three of its paths must leave the book out."""
    from nfl.data_ingest import books
    assert book not in books.BETTABLE_FALLBACK.split(",")
    assert book not in books.bettable_books()
    monkeypatch.setenv("BETTABLE_BOOKS", f"draftkings,{book}")
    assert books.bettable_books() == {"draftkings"}
    assert set(books.STATE_LIMITED) == set(config.STATE_LIMITED_BOOKMAKERS)


@each_book
def test_the_nba_in_play_fetch_keeps_collecting_the_book(book):
    """feed_books() was built from the deciding list, so removing a book from
    that list would have silently stopped FETCHING it too. It stays in the pull
    (the bill is per ten books named, and the list is still under ten)."""
    from data.ingestors.nba_live_feed import feed_books
    books = feed_books()
    assert book in books and len(books) <= 10


@each_book
def test_the_app_never_offers_the_book(book):
    """mobile/src/lib/markets.ts mirrors config.BEST_LINE_EXCLUDE_BOOKMAKERS;
    the picker, the line chips, the lines board and the parlay shop all read
    the list it derives."""
    src = _source("mobile/src/lib/markets.ts")
    start = src.index("export const REFERENCE_ONLY_BOOKS")
    line = src[start:src.index("\n", start)]
    assert f"'{book}'" in line, line


def test_the_nfl_prop_model_never_bets_hard_rock_and_still_fetches_it():
    """nfl_prop_market names its own betting books (SOFT_BOOKS), and the NCAAF
    prop pull builds its fetch from that module, so leaving SOFT_BOOKS must
    not drop Hard Rock's NCAAF quotes."""
    import models.nfl_prop_market as mk
    assert not set(mk.SOFT_BOOKS) & config.STATE_LIMITED_BOOKMAKERS
    assert "hardrockbet" in mk.FETCHED_NOT_BET
    src = _source("data/ingestors/ncaaf_prop_odds_ingestor.py")
    assert "_mk.FETCHED_NOT_BET" in src


def test_the_rule_is_in_the_always_loaded_file():
    """Which book a pick may name is asked in chat and in SQL without opening
    config.py, so the rule has to be where every session reads it."""
    text = _source("CLAUDE.md")
    assert "betPARX" in text and "Hard Rock" in text and "never the book a pick" in text
