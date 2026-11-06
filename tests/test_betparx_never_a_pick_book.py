"""betPARX is never the book a pick is decided at or a member is sent to.

mike, 2026-11-06: *"global rule. remove betparx from sports books for
recommeding betting lines in picks only niche avaialble in a few states"*.
betPARX ships one app per state (Maryland, Pennsylvania, New Jersey --
mobile/src/lib/sportsbookLinks.ts), so a pick that names it sends most members
to a book they cannot open. 60 BETs had been decided there by that day, 53 of
them in the 30 days before.

The rule is about RECOMMENDING, not about data: betPARX stays in the fetch, so
its quotes keep arriving for the consensus models that read every book.

Every surface is covered here because each one carries its own copy of "which
books may a pick name": config's two lists, the NFL cards' standalone fallback,
the NBA in-play fetch, the app's mirror, and the scorer's shop itself.
"""
from __future__ import annotations

import os
from pathlib import Path

import config
from models.scorer import _best_game_price, _best_prop_price

REPO = Path(__file__).resolve().parent.parent
BOOK = "betparx"


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

def test_betparx_is_a_state_limited_book():
    assert BOOK in config.STATE_LIMITED_BOOKMAKERS


def test_no_pick_is_decided_or_shopped_at_betparx():
    assert BOOK not in config.BEST_LINE_BOOKMAKERS
    assert BOOK not in config.BETTABLE_BOOKS
    assert BOOK not in config.LIVE_FEED_BOOKMAKERS


def test_betparx_is_still_fetched():
    """Removed from picks, not from the data: the NCAAB consensus models take
    a median over every book, betPARX included, and a book dropped from the
    fetch returns no quotes rather than an error."""
    assert BOOK in config.LINE_SHOP_BOOKMAKERS
    assert BOOK in config.ODDS_API_BOOKMAKERS_PARAM


def test_an_environment_override_cannot_put_betparx_back():
    """The espnbet exclusion is one env var to reverse. This one is a rule, so
    an override of either list -- including the empty exclude list that means
    "shop every book" -- still leaves betPARX out. Run in a fresh interpreter:
    reloading config in this one would hand every other test a second copy."""
    import json
    import subprocess
    import sys
    env = {**os.environ,
           "BEST_LINE_EXCLUDE_BOOKMAKERS": "",
           "BEST_LINE_BOOKMAKERS": "draftkings,betparx,fanduel",
           "BETTABLE_BOOKS": "draftkings,betparx",
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

def test_a_better_betparx_game_price_does_not_win_the_shop():
    rows = [
        ("draftkings", -150, None, None, None, "2026-11-06T15:00:00Z"),
        (BOOK, -120, None, None, None, "2026-11-06T15:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "NBA_2026-11-06_BOS_NYK", "h2h", "home", None)
    assert best is not None and best["book"] == "draftkings"


def test_a_better_betparx_prop_price_does_not_win_the_shop():
    rows = [   # bookmaker, over price, over link, line, snapshot_at
        ("draftkings", -115, None, 5.5, "2026-11-06T15:00:00Z"),
        (BOOK, +120, None, 5.5, "2026-11-06T15:00:00Z"),
    ]
    best = _best_prop_price(FakeConn(rows), "NBA_2026-11-06_BOS_NYK", "Jayson Tatum",
                            "player_rebounds", "over", 5.5)
    assert best is not None and best["book"] == "draftkings"


# ── the other copies of the list ─────────────────────────────────────────────

def test_the_nfl_cards_never_bet_at_betparx(monkeypatch):
    """nfl/data_ingest/books.py runs standalone with no repo config, so it
    carries a literal fallback; all three of its paths must leave betPARX out."""
    from nfl.data_ingest import books
    assert BOOK not in books.BETTABLE_FALLBACK.split(",")
    assert BOOK not in books.bettable_books()
    monkeypatch.setenv("BETTABLE_BOOKS", "draftkings,betparx")
    assert books.bettable_books() == {"draftkings"}
    assert set(books.STATE_LIMITED) == set(config.STATE_LIMITED_BOOKMAKERS)


def test_the_nba_in_play_fetch_keeps_collecting_betparx():
    """feed_books() was built from the deciding list, so removing betPARX from
    that list would have silently stopped FETCHING it too. It stays in the pull
    (the bill is per ten books named, and the list is still under ten)."""
    from data.ingestors.nba_live_feed import feed_books
    books = feed_books()
    assert BOOK in books and len(books) <= 10


def test_the_app_never_offers_betparx():
    """mobile/src/lib/markets.ts mirrors config.BEST_LINE_EXCLUDE_BOOKMAKERS;
    the picker, the line chips, the lines board and the parlay shop all read
    the list it derives."""
    src = _source("mobile/src/lib/markets.ts")
    start = src.index("export const REFERENCE_ONLY_BOOKS")
    line = src[start:src.index("\n", start)]
    assert "'betparx'" in line, line


def test_the_rule_is_in_the_always_loaded_file():
    """Which book a pick may name is asked in chat and in SQL without opening
    config.py, so the rule has to be where every session reads it."""
    text = _source("CLAUDE.md")
    assert "betPARX" in text and "never the book a pick" in text
