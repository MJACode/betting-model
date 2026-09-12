"""
Best-line shopping: the price we tell the bettor to take -- and, since
2026-09-09, the price that DECIDES.

Every scored pick records the best price across config.BEST_LINE_BOOKMAKERS and
which book had it. Until 2026-09-09 that was display-only and the BET/AVOID
call, the stake and settlement measured against DraftKings; mike ("we should
remove DK only - we want best lines for us regardless") flipped it: the pick is
re-decided at the best bettable price (models.scorer._requalify_at_best) and
that price is stored as decision_*. The selection rules below are unchanged;
the isolation tests are the INVERSE of what they were, and
tests/test_decide_on_best_price.py carries the requalification itself.

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
    # Was written against pinnacle, which is no longer offered as a price
    # (see test_reference_only_books_are_never_offered_as_a_price). The point
    # of the test is the ABSENT line filter, so any second book makes it.
    rows = [
        ("draftkings", -150, None, None, None, "2026-08-28T18:00:00Z"),
        ("betmgm", -138, None, None, None, "2026-08-28T18:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "MLB_2026-08-28_NYY_BOS", "h2h",
                            "home", None)
    assert best["book"] == "betmgm"


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


# ── the best price DECIDES (2026-09-09), through one code path ───────────────

def test_the_builders_decide_at_draftkings_and_the_stamp_requalifies():
    """
    _make_pick and _make_prop_pick decide at the DraftKings quote through
    _decide / _size, and the stamping step that follows them re-runs THE SAME
    two functions at the best bettable price. A second copy of the rules is how
    the two prices would drift apart.
    """
    src = _source("models/scorer.py")
    for fn in ("def _make_pick(", "def _make_prop_pick("):
        start = src.index(fn)
        body = src[start:src.index("\ndef ", start + 1)]
        assert "_decide(" in body and "_size(" in body, fn
        assert "_decision_fields(" in body, (
            f"{fn} must record which price decided it")
        if fn == "def _make_prop_pick(":
            # 2026-09-12: a proposition DraftKings does not list is scored off
            # the first bettable book that does, so the deciding book there is
            # the line's book and DraftKings only when there is no other.
            assert "_decision_fields(line_book or ODDS_API_BOOKMAKER" in body
            assert '"dk_odds":             None if line_book else dk_odds' in body, (
                "picks.dk_odds must stay NULL when DraftKings never quoted it")
        else:
            assert "_decision_fields(ODDS_API_BOOKMAKER" in body, (
                f"{fn} must record DraftKings as the deciding price until the "
                "best-price re-check says otherwise")
    for fn in ("def _stamp_best_game_prices(", "def _tag_prop("):
        start = src.index(fn)
        body = src[start:src.index("\ndef ", start + 1)]
        assert "_requalify_at_best(" in body, fn


def test_settlement_reads_the_deciding_price():
    """Settlement grades at the price the pick was DECIDED at: the decision
    price since the flip, DraftKings (decision_odds NULL) before it. CLV stays
    DraftKings-to-DraftKings."""
    src = _source("tracking/paper_tracker.py")
    assert src.count("COALESCE(p.decision_odds, p.dk_odds)") == 4, (
        "every settle path (props, UFC, golf, game) grades at the decision price")
    assert "best_odds" not in src, "the settlement price is decision_odds, not the display stamp"
    assert "closing_dk_odds" in src


# ── The price has to be one the bettor can actually take ─────────────────────
# BEST_LINE_BOOKMAKERS answers "where should this be placed?", so a book that
# does not accept US customers is not an answer to it however good its number
# is. Measured 2026-09-02: of 69 pre-game BETs since 08-31 carrying a best
# price, 35 named a book other than DraftKings and 18 of those 35 named
# Pinnacle or Bovada — over half of every "better number" claim, and 26% of all
# bets, pointing at a price that could not be taken.

def test_reference_only_books_are_never_offered_as_a_price():
    for book in ("pinnacle", "bovada"):
        assert book not in config.BEST_LINE_BOOKMAKERS, (
            f"{book} cannot be bet from the US but is offered as the best price")


def test_caesars_is_williamhill_us_and_must_survive_a_book_edit():
    """mike, 2026-09-03, asked to ADD Caesars and REMOVE William Hill in one
    breath. On The Odds API they are the same key: `williamhill_us` is Caesars
    and `caesars` is not a key the endpoint returns (verified against the live
    endpoint the same day). Doing both literally deletes the book that was
    asked for, so this pins the mapping for the next person to edit the list."""
    assert "williamhill_us" in config.BEST_LINE_BOOKMAKERS, (
        "williamhill_us IS Caesars -- removing it removes Caesars")
    assert "caesars" not in config.LINE_SHOP_BOOKMAKERS, (
        "`caesars` is not a key The Odds API returns; use williamhill_us")


def test_a_book_can_only_be_offered_if_it_is_also_fetched():
    """BEST_LINE is filtered out of LINE_SHOP, so a book added to one and not
    the other is either never shopped or never collected. fanatics was added on
    2026-09-03 and needed both."""
    for book in config.BEST_LINE_BOOKMAKERS:
        assert book in config.LINE_SHOP_BOOKMAKERS, (
            f"{book} is offered as a price but never fetched")
        assert book in config.ODDS_API_BOOKMAKERS_PARAM


def test_reference_only_books_are_still_collected():
    """They are excluded from SHOPPING, not from the feed: Pinnacle is the sharp
    de-vig reference SHARP_BOOKMAKERS is built on and Bovada carried the NCAAF
    opener signal. Dropping them from ingest would break both."""
    for book in ("pinnacle", "bovada"):
        assert book in config.LINE_SHOP_BOOKMAKERS
        assert book in config.ODDS_API_BOOKMAKERS_PARAM


def test_an_unbettable_book_does_not_win_the_shop(monkeypatch):
    """The behaviour, not just the config: a better Pinnacle price loses to a
    worse DraftKings one, because the Pinnacle price is not available."""
    rows = [
        ("draftkings", -150, None, None, None, "2026-08-28T18:00:00Z"),
        ("pinnacle", -138, None, None, None, "2026-08-28T18:00:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "MLB_2026-08-28_NYY_BOS", "h2h",
                            "home", None)
    assert best["book"] == "draftkings"


# ── UFC: the same fight exists under two orientations ────────────────────────
# game_id is built from The Odds API's home_team and that assignment is not
# stable between fetches, so odds land on whichever row the feed used. The DK
# read has resolved the sibling since the 2026-08-29 card; best-price lookup did
# not, so line shopping silently gave up on fights five books had priced — and
# it was invisible, because "no quotes" and "no better price" both stamp NULL.

class TwoOrientationConn:
    """Odds exist only on the sibling game_id."""

    def __init__(self, rows, only_for):
        self._rows, self._only_for = rows, only_for
        self.seen = []

    _sql = ""

    def execute(self, sql, params=None):
        self.seen.append(params)
        self._last = params
        self._sql = sql
        return self

    def fetchall(self):
        return self._rows if self._last[0] == self._only_for else []


def test_ufc_h2h_resolves_the_sibling_orientation_and_flips_the_side():
    stored = "UFC_2026-09-05_mario-pinto_ryan-spann"
    asked  = "UFC_2026-09-05_ryan-spann_mario-pinto"
    # On the stored row our fighter is AWAY, so his price is in away_price —
    # the query the fallback issues must select that column.
    rows = [("fanduel", 145, "fd", None, None, "2026-09-05T18:00:00Z")]
    conn = TwoOrientationConn(rows, only_for=stored)
    best = _best_game_price(conn, asked, "h2h", "home", None)
    assert best is not None, "the sibling orientation was never tried"
    assert best["book"] == "fanduel"
    assert conn.seen[0][0] == asked and conn.seen[1][0] == stored
    assert "away_price" in str(conn._sql), (
        "the sibling was read on the same side, so home was priced as away")


def test_ufc_totals_keep_their_side_on_the_sibling():
    """Over/under is orientation-independent — flipping it would report the
    price of the opposite bet."""
    stored = "UFC_2026-09-05_mario-pinto_ryan-spann"
    asked  = "UFC_2026-09-05_ryan-spann_mario-pinto"
    rows = [("fanduel", -110, "fd", 1.5, None, "2026-09-05T18:00:00Z")]
    conn = TwoOrientationConn(rows, only_for=stored)
    best = _best_game_price(conn, asked, "totals", "under", 1.5)
    assert best is not None and best["book"] == "fanduel"
    assert "under_price" in str(conn._sql)


def test_a_non_ufc_game_is_not_looked_up_twice():
    """The fallback must not double every miss for the other seven sports."""
    conn = TwoOrientationConn([], only_for="never")
    assert _best_game_price(conn, "MLB_2026-09-01_NYY_BOS", "h2h",
                            "home", None) is None
    assert len(conn.seen) == 1
