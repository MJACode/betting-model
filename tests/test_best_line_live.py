"""Line shopping for LIVE picks: the data was already paid for and thrown away.

Measured 2026-08-30: 0 of 107 August live BETs carried a best price, while six
non-DK books had in-play rows for the same games in the same poll batch. The
pre-game half has worked since 08-29 (100% coverage); the live half was never
wired.

Most of these pin REFUSALS, because the one way line shopping can make a pick
WORSE is by preferring a book that stopped updating -- a frozen book wins a
naive max() precisely BECAUSE it froze.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import config
from models.scorer import (_best_live_price, _live_quote_is_on_offer,
                           _tag_live)

ROOT = Path(__file__).parent.parent


def _ts(age_sec: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=age_sec)).isoformat()


class _FakeConn:
    """execute().fetchall(), the shape data.db.DBConnection exposes."""

    def __init__(self, rows):
        self._rows = rows
        self.sql = None

    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchall(self):
        return self._rows


# columns: bookmaker, price, link, total_line, spread_home, snapshot_at
def _row(book, price, line=8.5, age=5, link="u"):
    return (book, price, link, line, None, _ts(age))


# -- it finds the better price ------------------------------------------------

def test_it_picks_the_best_price_across_books_at_the_same_line():
    conn = _FakeConn([_row("draftkings", -115), _row("fanduel", -105),
                      _row("betmgm", -110)])
    best = _best_live_price(conn, "G", "totals", "over", 8.5)
    assert best["book"] == "fanduel" and best["odds"] == -105


def test_it_reads_in_play_rows_not_pregame_ones():
    """The pre-game sibling excludes in_play on purpose; this one requires it."""
    conn = _FakeConn([_row("draftkings", -110)])
    _best_live_price(conn, "G", "totals", "over", 8.5)
    assert "snapshot_type = 'in_play'" in conn.sql


def test_plus_money_beats_minus_money():
    conn = _FakeConn([_row("draftkings", -110), _row("bovada", 105)])
    assert _best_live_price(conn, "G", "totals", "over", 8.5)["odds"] == 105


# -- the refusals -------------------------------------------------------------

def test_a_book_on_a_different_line_is_not_a_better_price():
    """CLAUDE.md 1c: Over 9.0 at -105 is not a better price on Over 8.5, it is
    a different bet."""
    conn = _FakeConn([_row("draftkings", -115, line=8.5),
                      _row("fanduel", -101, line=9.5)])
    best = _best_live_price(conn, "G", "totals", "over", 8.5)
    assert best["book"] == "draftkings", "the 9.5 quote is a different bet"


def test_a_frozen_book_cannot_win_by_having_stopped_updating():
    """THE failure mode this guard exists for. A book that froze 5 minutes ago
    still shows its old, better number -- and a naive max() would take it."""
    conn = _FakeConn([_row("draftkings", -115, age=5),
                      _row("betmgm", +130, age=400)])
    best = _best_live_price(conn, "G", "totals", "over", 8.5)
    assert best["book"] == "draftkings", "a stale +130 is not on offer"


def test_freshness_is_bounded_by_the_live_odds_knob():
    assert _live_quote_is_on_offer(_ts(config.LIVE_ODDS_MAX_AGE_SEC - 5))
    assert not _live_quote_is_on_offer(_ts(config.LIVE_ODDS_MAX_AGE_SEC + 30))


def test_the_age_gate_is_the_value_that_was_actually_decided():
    """30s, mike, 2026-08-30 -- REAFFIRMED, not a reversion.

    The identical value was rolled back on 2026-08-29 because it sits below
    DK's 47s median republish and declines ~60% of passes. That concern was put
    to him twice with the numbers and he chose 30 anyway: fewer live bets, in
    exchange for the ones taken being priced at a line that is on the board.

    This test exists so the 2026-08-29 note cannot be read later as grounds for
    quietly restoring 60/90. That argument has been heard and decided; changing
    it needs a new decision, not a rediscovery of the old one.
    """
    assert config.LIVE_ODDS_MAX_AGE_SEC == 30


def test_a_timestamp_it_cannot_parse_fails_OPEN():
    """These columns are TEXT in mixed shapes. A parse failure must not silently
    delete a book from the comparison."""
    assert _live_quote_is_on_offer(None)
    assert _live_quote_is_on_offer("not-a-date")


def test_the_Z_suffix_shape_parses():
    """'Z' vs '+00:00' is the section 7 trap; a string compare keeps stale rows."""
    stamp = (datetime.now(timezone.utc) - timedelta(seconds=5)
             ).strftime("%Y-%m-%dT%H:%M:%SZ")
    assert _live_quote_is_on_offer(stamp)


def test_a_book_with_no_price_is_skipped():
    conn = _FakeConn([_row("draftkings", None), _row("fanduel", -108)])
    assert _best_live_price(conn, "G", "totals", "over", 8.5)["book"] == "fanduel"


def test_no_quotes_at_all_is_none_not_a_crash():
    assert _best_live_price(_FakeConn([]), "G", "totals", "over", 8.5) is None


def test_an_unknown_side_returns_none():
    """UFC 'decision' and similar are not two-way markets."""
    assert _best_live_price(_FakeConn([_row("draftkings", -110)]),
                            "G", "h2h", "decision", None) is None


# -- wiring -------------------------------------------------------------------

def test_tag_live_uses_a_private_key_that_the_insert_strips():
    p = _tag_live({"pick_side": "over"}, ("G", "totals"))
    assert p["_live_ctx"] == ("G", "totals")
    src = (ROOT / "models/scorer.py").read_text(encoding="utf-8")
    assert 'p.pop("_live_ctx", None)' in src, "an unstripped key breaks the INSERT"


def test_both_live_loops_actually_CALL_the_tag():
    """CLAUDE.md 1b: one stamp, both sports -- not two implementations.

    Asserts the CALL, not the import. The first version of this test checked
    only that the name appeared in the file, and it passed with the NCAAF call
    replaced by `pass` -- a test that passes without the fix is not a test.
    """
    mlb = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    assert "_tag_live(p, (game_id, market))" in mlb

    ncaaf = (ROOT / "ncaaf_live/gameday.py").read_text(encoding="utf-8")
    assert "_tag_live(p, (game_id, mkt))" in ncaaf, (
        "NCAAF live picks would be written with no best price")


def test_the_ncaaf_market_map_agrees_with_the_registry():
    """gameday declares its markets locally (its _write_picks runs under a
    stubbed config in the notify tests). This is what stops that copy drifting
    from config.LIVE_MODELS, which is the real source."""
    from ncaaf_live.gameday import LIVE_MODEL_MARKETS
    for model_id, market in LIVE_MODEL_MARKETS.items():
        assert config.LIVE_MODELS[model_id][1] == market, (
            f"{model_id}: gameday says {market}, the registry disagrees")


def test_the_live_decision_path_never_reads_the_best_price():
    """The models decide on DraftKings ONLY (CLAUDE.md 6). Best-of-N runs ~2pp
    cheaper in implied probability, so letting it qualify a bet would loosen
    every live cut by that much with nobody deciding to."""
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    body = src[src.index("def _score_live_model"):src.index("    return [_tag_live")]
    for forbidden in ("best_odds", "best_edge", "best_implied_prob", "best_book"):
        assert forbidden not in body, (
            f"{forbidden} must not reach the live signal/edge/Kelly path")


def test_the_tag_happens_after_the_decision():
    """Tagging inside the scoring loop would put a cross-book price in scope
    while the BET/AVOID call is still being made."""
    src = (ROOT / "models/live_scorer.py").read_text(encoding="utf-8")
    assert src.index("_tag_live(p, (game_id, market))") > src.index("picks.append(pick)")
