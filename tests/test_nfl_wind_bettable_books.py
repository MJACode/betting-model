"""The wind card must quote a book the reader can actually walk up to.

`attach_odds` sorted the whole totals feed by total then price and took the top
row, and the feed carries plenty of books nobody here holds. Measured on the
Week-1 board (2026-09-06), three of the five picks this model had locked named
gtbets, lowvig and onexbet. mike: "no can't bet on these remove them."

§1c makes a written pick permanent, so those three cannot be retracted. This is
about the next one.

The opener card got the identical filter hours earlier, from the identical
shared list (CLAUDE.md §1b: a change to how one model operates is assessed
against all of them). The tests below therefore check two things — that the
wind card filters, and that the two cards are reading the SAME list, because
two cards disagreeing about which books exist is the bug rather than the fix.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
NFL_ROOT = ROOT / "nfl"
sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="module")
def books():
    spec = importlib.util.spec_from_file_location(
        "nfl_books_mod", NFL_ROOT / "data_ingest" / "books.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def card():
    """The wind card, loaded the way the scheduler runs it (cwd=nfl/)."""
    sys.path.insert(0, str(NFL_ROOT))
    try:
        spec = importlib.util.spec_from_file_location(
            "nfl_weekly_wind_card", NFL_ROOT / "scripts" / "weekly_wind_card.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        yield mod
    finally:
        sys.path.remove(str(NFL_ROOT))


class TestTheListIsShared:
    def test_the_wind_card_uses_the_shared_bettable_list(self, card, books):
        assert card.bettable_books() == books.bettable_books()

    def test_the_opener_reads_the_same_list(self, books):
        sys.path.insert(0, str(NFL_ROOT))
        try:
            spec = importlib.util.spec_from_file_location(
                "nfl_opener_for_books", NFL_ROOT / "models" / "opener_spread.py")
            opener = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(opener)
            assert opener._bettable_books() == books.bettable_books()
        finally:
            sys.path.remove(str(NFL_ROOT))

    def test_the_books_that_produced_the_bad_picks_are_out(self, books):
        # The three that actually appear on locked wind picks, plus the two
        # that appeared on the opener board the same morning.
        for bad in ("gtbets", "lowvig", "onexbet", "betus", "coolbet"):
            assert bad not in books.bettable_books(), bad

    def test_draftkings_is_in(self, books):
        # The book every model decides on (§6). If it ever left this list the
        # cards would go silent, so pin it.
        assert "draftkings" in books.bettable_books()

    def test_the_fallback_matches_the_platform_config(self, books):
        # The literal exists for standalone runs where `import config` finds
        # nothing. A copy that drifts is a copy that lies.
        import config
        assert {b.strip() for b in books.BETTABLE_FALLBACK.split(",")} \
            == set(config.BETTABLE_BOOKS)

    def test_the_env_override_wins(self, books, monkeypatch):
        monkeypatch.setenv("BETTABLE_BOOKS", "fanduel , DraftKings ")
        assert books.bettable_books() == {"fanduel", "draftkings"}

    def test_the_list_is_read_per_call_not_frozen_at_import(self, books,
                                                            monkeypatch):
        # The cards are long-lived under the scheduler. A value captured at
        # import would ignore a Railway change until the next deploy.
        before = books.bettable_books()
        monkeypatch.setenv("BETTABLE_BOOKS", "betmgm")
        assert books.bettable_books() == {"betmgm"}
        monkeypatch.delenv("BETTABLE_BOOKS")
        assert books.bettable_books() == before


class TestTheCardFilters:
    def test_attach_odds_drops_unbettable_books_before_choosing(self, card,
                                                                monkeypatch):
        """THE ORDERING TRAP, and why the filter runs before the sort.

        The card takes the highest total, then the best price at it. An
        unbettable book quoting a HIGHER total wins that sort outright — so a
        filter applied after the choice would reject the pick and return
        nothing, silently losing the FanDuel quote that was always there.
        """
        # onexbet hangs the higher total (48.5) and would win the sort;
        # fanduel is the best bettable quote at 47.5.
        feed = pd.DataFrame([
            _quote("onexbet", "Under", 48.5, -108),
            _quote("onexbet", "Over", 48.5, -112),
            _quote("fanduel", "Under", 47.5, -105),
            _quote("fanduel", "Over", 47.5, -115),
        ])
        out = _attach(card, monkeypatch, feed)
        assert out.best_book.iloc[0] == "fanduel"
        assert float(out.best_total.iloc[0]) == 47.5
        assert int(out.best_under_px.iloc[0]) == -105

    def test_a_game_only_unbettable_books_quote_gets_no_price(self, card,
                                                              monkeypatch):
        # Not a bet at a worse number — no bet. The model skips a row with no
        # best_under_px, which is the correct "we could not have played this".
        feed = pd.DataFrame([
            _quote("onexbet", "Under", 48.5, -108),
            _quote("onexbet", "Over", 48.5, -112),
        ])
        out = _attach(card, monkeypatch, feed)
        assert pd.isna(out.best_under_px.iloc[0])
        assert pd.isna(out.best_book.iloc[0])

    def test_n_books_counts_only_bettable_ones(self, card, monkeypatch):
        # n_books is shown on the card as "how much of a market is this".
        # Counting venues we cannot use would overstate it.
        feed = pd.DataFrame([
            _quote("onexbet", "Under", 48.5, -108),
            _quote("fanduel", "Under", 47.5, -105),
            _quote("betmgm", "Under", 47.5, -108),
        ])
        out = _attach(card, monkeypatch, feed)
        assert int(out.n_books.iloc[0]) == 2

    def test_defective_books_are_still_excluded(self, card, monkeypatch):
        # The sign-flip screen is independent of bettability and must survive.
        feed = pd.DataFrame([
            _quote("betsson", "Under", 60.5, +200),
            _quote("fanduel", "Under", 47.5, -105),
            _quote("fanduel", "Over", 47.5, -115),
        ])
        out = _attach(card, monkeypatch, feed)
        assert out.best_book.iloc[0] == "fanduel"


# ── helpers ───────────────────────────────────────────────────────────────────

def _quote(book, side, point, price):
    return {"book": book, "market": "totals", "side": side, "point": point,
            "price": price, "home": "BUF", "away": "NYJ",
            "commence_time": "2026-09-13T17:00:00Z"}


def _attach(card, monkeypatch, feed: pd.DataFrame) -> pd.DataFrame:
    """Run attach_odds against a canned feed, with the network stubbed out."""
    monkeypatch.setenv("THE_ODDS_API_KEY", "test-key")

    class _Res:
        cost = 0
        payload = {}

    class _Client:
        def __init__(self, *a, **k):
            pass

        def live_odds(self, *a, **k):
            return _Res()

    import sys as _sys
    odds_api = type(_sys)("data_ingest.odds_api")
    odds_api.OddsAPIClient = _Client
    odds_api.ledger_status = lambda: {}
    parse = type(_sys)("data_ingest.parse")
    parse.snapshot_to_frame = lambda payload, kind: feed.copy()
    monkeypatch.setitem(_sys.modules, "data_ingest.odds_api", odds_api)
    monkeypatch.setitem(_sys.modules, "data_ingest.parse", parse)

    games = pd.DataFrame([{
        "game_id": "2026_02_NYJ_BUF", "home_team": "BUF", "away_team": "NYJ",
        "matchup": "NYJ @ BUF",
    }])
    return card.attach_odds(games, regions="us", dry_run=False)
