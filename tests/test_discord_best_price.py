"""
Discord publishes where the same bet is cheaper — without moving the decision.

mike, 2026-08-30: "the bet should pick the best line for the bettor, across the
main books, not just DK."

THE DISTINCTION THIS FILE EXISTS TO PROTECT. The models DECIDE on DraftKings
(CLAUDE.md §6): every threshold was swept on DK-implied edge, and a best-of-N
price is systematically ~2pp cheaper in implied probability, so adopting it as
the QUALIFYING price would loosen every cut by that much with nobody deciding
to. This changes where a reader should PLACE the bet, never whether the bet
exists — and a future edit that quietly starts gating on best_odds is the
regression to catch.

Where the money is: measured across 1,569 same-line prop comparisons on
2026-08-30, DK is the best price at the median, but one prop in three has 1-30
cents available elsewhere and one in sixteen has 30+.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from tracking.discord_notifier import better_price_note, _signal_field  # noqa: E402

_SRC = (Path(__file__).parent.parent / "tracking"
        / "discord_notifier.py").read_text(encoding="utf-8")


def _sig(**over):
    s = {"label": "Yankees Over 8.5", "sport": "MLB", "model_id": "mlb_over_under",
         "dk_odds": -110, "kelly": 0.02, "home": "NYY", "away": "BOS"}
    s.update(over)
    return s


# ── when it speaks ────────────────────────────────────────────────────────────

def test_a_strictly_better_book_is_published():
    assert better_price_note(_sig(dk_odds=-120, best_odds=-105,
                                  best_book="fanduel")) == "also `-105` @ FanDuel"


def test_it_works_on_plus_money_too():
    """+175 beats +150; the comparison must be on implied price, not on sign."""
    note = better_price_note(_sig(dk_odds=150, best_odds=175, best_book="pinnacle"))
    assert note == "also `+175` @ Pinnacle"


# ── when it stays silent ──────────────────────────────────────────────────────

def test_the_same_book_is_never_offered_as_an_alternative():
    """
    "also -105 @ DraftKings" beside -110 is noise — it is the same book.

    The best price is recorded across ALL books including DraftKings, so
    best_book == draftkings with best_odds BETTER than the pick's dk_odds is a
    real, common row (the two are captured at different moments). The first
    version of this test used equal prices, so the strictly-better check caught
    it and a mutation removing the same-book guard passed cleanly.
    """
    assert better_price_note(_sig(dk_odds=-110, best_odds=-105,
                                  best_book=config.ODDS_API_BOOKMAKER)) is None
    assert better_price_note(_sig(dk_odds=-110, best_odds=-105,
                                  best_book="DraftKings")) is None, (
        "the book name must be compared case-insensitively")


def test_an_equal_price_elsewhere_is_not_published():
    assert better_price_note(_sig(dk_odds=-110, best_odds=-110,
                                  best_book="fanduel")) is None


def test_a_WORSE_price_is_never_published():
    """
    The failure that would actively mislead: sending a reader to a book that
    pays less.
    """
    assert better_price_note(_sig(dk_odds=-105, best_odds=-120,
                                  best_book="fanduel")) is None


@pytest.mark.parametrize("missing", [
    {"best_odds": None, "best_book": "fanduel"},
    {"best_odds": -105, "best_book": None},
    {"best_odds": -105, "best_book": "   "},
    {},
])
def test_missing_data_is_silent_not_broken(missing):
    """A prop-only or live pick carries no best price; that must not raise."""
    assert better_price_note(_sig(**missing)) is None


def test_an_unpriced_pick_cannot_produce_a_note():
    """No decision price means no comparison to make."""
    assert better_price_note(_sig(dk_odds=None, best_odds=-105,
                                  best_book="fanduel")) is None


# ── it reaches the rendered field ─────────────────────────────────────────────

def test_the_note_appears_in_the_pick_line():
    field = _signal_field(_sig(dk_odds=-120, best_odds=-105, best_book="fanduel"))
    assert "also `-105` @ FanDuel" in field["value"]
    assert "-120" in field["value"], "the decision price must still be shown first"


def test_the_decision_price_is_shown_before_the_alternative():
    """A reader must see what the model priced, then where to shop it."""
    v = _signal_field(_sig(dk_odds=-120, best_odds=-105, best_book="fanduel"))["value"]
    assert v.index("-120") < v.index("also `-105`")


def test_a_pick_with_no_better_book_renders_exactly_as_before():
    field = _signal_field(_sig(best_odds=-110, best_book="draftkings"))
    assert "also" not in field["value"]


# ── the invariant ─────────────────────────────────────────────────────────────

def test_best_odds_never_reaches_the_qualifying_gate():
    """
    §6's tripwire, restated for this feature. The threshold join in
    _new_signals gates on os.* and t.* columns; best_odds is read from the
    picks row for DISPLAY and must never appear in a WHERE clause.
    """
    i = _SRC.index("def _new_signals(")
    j = _SRC.index("\ndef ", i + 10)
    fn = _SRC[i:j]
    # The SQL only. A first version sliced to the end of the function and
    # tripped on the row dict, where "best_odds" is a legitimate output key —
    # a test that fails on correct code teaches people to delete tests.
    sql_start = fn.index('conn.execute("""') + len('conn.execute("""')
    sql = fn[sql_start:fn.index('"""', sql_start)]
    where = sql[sql.index("WHERE"):]
    assert "best_odds" not in where, (
        "best_odds appears in the signal query's WHERE — the BET decision must "
        "stay on DraftKings (§6)")
    # ...and it IS projected out to the caller, or the display half was never
    # wired. Checked against the OUTER select list and the row dict's indices,
    # not against "is the string anywhere before the first WHERE" — that first
    # WHERE belongs to the LATERAL subquery, so the loose version stayed true
    # with the outer projection deleted and a mutation sailed through it.
    assert "pk.best_book, pk.best_odds" in sql, (
        "the outer SELECT must project the best price")
    assert '"best_book": r[14], "best_odds": r[15],' in fn, (
        "the row dict must read the projected columns")


def test_the_live_path_is_untouched():
    """
    Live picks carry no multi-book best price, and the live lane has its own
    staleness story. Adding a shopping tip there would advertise a price we
    never measured.
    """
    i = _SRC.index("def _new_live_signals(")
    j = _SRC.index("\ndef ", i + 10)
    assert "best_odds" not in _SRC[i:j]
