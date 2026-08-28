"""
Best-line shopping: the price we tell the bettor to take.

Every scored pick records the best price across config.BEST_LINE_BOOKMAKERS and
which book had it. The load-bearing property is that this is DISPLAY + BET
information only — it must never reach the BET/AVOID decision, the edge, the
Kelly stake, settlement or CLV, all of which still measure against DraftKings.
Best-of-N pricing runs ~2pp cheaper in implied probability than DraftKings
(measured 2026-08-28 over 92 MLB games), so letting it qualify picks would
loosen every threshold in section 17 by that much without anyone deciding to.

Pure-function / static-source tests — no network, no DB.
"""

from pathlib import Path

import config
from models.scorer import (
    _best_fields,
    _best_game_price,
    _best_of,
    _best_prop_price,
    _same_line,
    _tag_prop,
)

REPO = Path(__file__).resolve().parent.parent


def _source(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


class FakeConn:
    """Returns canned rows for the single query the helper issues."""

    def __init__(self, rows):
        self._rows = rows
        self.params = None

    def execute(self, sql, params=None):
        self.params = params
        self._sql = sql
        return self

    def fetchall(self):
        return self._rows


# ── selection ────────────────────────────────────────────────────────────────

def test_best_of_picks_the_highest_payout_across_the_sign_flip():
    best = _best_of([
        {"book": "draftkings", "odds": -110, "link": None},
        {"book": "fanduel", "odds": 105, "link": None},
        {"book": "betmgm", "odds": -105, "link": None},
    ])
    assert best["book"] == "fanduel"


def test_best_of_ties_keep_the_first_book_offered():
    """Config order puts DraftKings first, so a tie leaves the quote on the
    book the model actually scored against."""
    best = _best_of([
        {"book": "draftkings", "odds": -110, "link": None},
        {"book": "fanduel", "odds": -110, "link": None},
    ])
    assert best["book"] == "draftkings"


def test_best_of_ignores_books_with_no_price():
    best = _best_of([
        {"book": "draftkings", "odds": None, "link": None},
        {"book": "fanduel", "odds": -130, "link": None},
    ])
    assert best["book"] == "fanduel"


def test_best_of_returns_none_when_nothing_is_priced():
    assert _best_of([{"book": "fanduel", "odds": None, "link": None}]) is None
    assert _best_of([]) is None


# ── the same bet, or a different one ─────────────────────────────────────────

def test_a_better_price_at_a_different_total_is_not_the_same_bet():
    """Over 9.0 at +100 does not beat Over 8.5 at -110 — it is a different
    proposition. Only quotes at the pick's own line may win."""
    rows = [
        ("draftkings", -110, "dk-link", 8.5, None, "2026-08-28T18:00:00Z"),
        ("fanduel", 100, "fd-link", 9.0, None, "2026-08-28T18:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "MLB_2026-08-28_NYY_BOS", "totals",
                            "over", 8.5)
    assert best["book"] == "draftkings"


def test_a_better_price_at_the_same_total_wins():
    rows = [
        ("draftkings", -110, "dk-link", 8.5, None, "2026-08-28T18:00:00Z"),
        ("fanduel", 100, "fd-link", 8.5, None, "2026-08-28T18:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "MLB_2026-08-28_NYY_BOS", "totals",
                            "over", 8.5)
    assert best["book"] == "fanduel"
    assert best["link"] == "fd-link"


def test_moneyline_has_no_line_to_match():
    rows = [
        ("draftkings", -150, None, None, None, "2026-08-28T18:00:00Z"),
        ("pinnacle", -138, None, None, None, "2026-08-28T18:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "MLB_2026-08-28_NYY_BOS", "h2h",
                            "home", None)
    assert best["book"] == "pinnacle"


def test_only_the_newest_snapshot_per_book_counts():
    """A stale row must not win on a price the book has since moved off."""
    rows = [  # query returns newest-first
        ("fanduel", -120, None, None, None, "2026-08-28T18:00:00Z"),
        ("fanduel", 140, None, None, None, "2026-08-28T09:00:00Z"),
        ("draftkings", -115, None, None, None, "2026-08-28T18:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "MLB_2026-08-28_NYY_BOS", "h2h",
                            "home", None)
    assert best["book"] == "draftkings"


def test_unknown_pick_side_has_no_best_price():
    assert _best_game_price(FakeConn([]), "g", "h2h", "nonsense", None) is None


def test_prop_best_price_matches_on_the_line():
    rows = [
        ("draftkings", -140, "dk", 5.5),
        ("fanduel", -105, "fd", 6.5),   # different line — different bet
        ("betmgm", -125, "mgm", 5.5),
    ]
    best = _best_prop_price(FakeConn(rows), "g", "Blake Snell",
                            "pitcher_strikeouts", "over", 5.5)
    assert best["book"] == "betmgm"


def test_prop_best_price_ignores_sides_with_no_market():
    assert _best_prop_price(FakeConn([]), "g", "p", "m", "home", 5.5) is None


def test_query_asks_only_for_the_configured_books():
    conn = FakeConn([])
    _best_game_price(conn, "g", "h2h", "home", None)
    assert list(conn.params[2:]) == config.BEST_LINE_BOOKMAKERS


def test_in_play_prices_are_excluded_from_best_line():
    conn = FakeConn([])
    _best_game_price(conn, "g", "h2h", "home", None)
    assert "snapshot_type != 'in_play'" in conn._sql


# ── the stamped columns ──────────────────────────────────────────────────────

def test_best_fields_report_the_edge_at_the_price_offered():
    fields = _best_fields({"book": "fanduel", "odds": 100, "link": "l"}, 0.60)
    assert fields["best_book"] == "fanduel"
    assert fields["best_odds"] == 100
    assert fields["best_implied_prob"] == 0.5
    assert fields["best_edge"] == 0.10
    assert fields["best_bet_link"] == "l"


def test_best_fields_are_all_null_when_no_book_priced_the_side():
    fields = _best_fields(None, 0.60)
    assert set(fields.values()) == {None}


def test_same_line_treats_both_missing_as_the_same_and_one_missing_as_not():
    assert _same_line(None, None)
    assert _same_line(8.5, 8.5)
    assert not _same_line(8.5, None)
    assert not _same_line(None, 8.5)
    assert not _same_line(8.5, 9.0)


def test_tag_prop_survives_a_none_pick():
    assert _tag_prop(None, ("g", "p", "m")) is None


# ── isolation: best price must never decide a bet ────────────────────────────

def test_the_deciding_functions_never_see_a_best_price():
    """
    _make_pick and _make_prop_pick classify BET/AVOID/NONE and size the stake.
    Neither takes best-price data, and the stamping happens after they return —
    which is what keeps the pick set identical to the DK-calibrated thresholds.
    """
    src = _source("models/scorer.py")
    for fn in ("def _make_pick(", "def _make_prop_pick("):
        start = src.index(fn)
        body = src[start:src.index("\ndef ", start + 1)]
        assert "best_" not in body, (
            f"{fn} references a best-price field — the BET/AVOID call, edge and "
            "Kelly stake must stay measured against DraftKings"
        )


def test_settlement_and_clv_never_read_a_best_price():
    """Settlement grades at the price the pick was measured at. If P&L ever
    moves to the best price, edge and thresholds must move with it."""
    assert "best_odds" not in _source("tracking/paper_tracker.py")


def test_draftkings_is_in_the_best_line_book_set():
    """DraftKings must always be a candidate, or a pick could be stamped with a
    price strictly worse than the one it was scored against."""
    assert config.ODDS_API_BOOKMAKER in config.BEST_LINE_BOOKMAKERS
