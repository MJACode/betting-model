"""Line CLV — the measure that survives a moved line.

CLV was a price comparison and only a price comparison, so a pick whose number
moved by close was skipped outright: ~55% of settled pre-game bets went
unmeasured, and `closing_line` was only ever written when it EQUALLED
`scored_line`. That second consequence is the one users saw. The app's Closing
Line Value card gates its "Line 44.5 -> 46.5" row on
`scored_line !== closing_line`, so the row could never render — the number we
gave them versus the number the market closed at was structurally invisible.

`_line_clv_pts` is the measure that IS valid across a moved line: how far the
number itself travelled toward our side. Positive is always good for the pick,
in every market and on either side. The signs are the load-bearing part —
`scored_line` is HOME-relative for spreads (CLAUDE.md §4), and getting that
backwards has produced a wrong threshold twice.
"""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


def _load():
    """Import paper_tracker's helper without dragging in the DB layer."""
    sys.modules.setdefault("dotenv",
                           types.SimpleNamespace(load_dotenv=lambda *a, **k: None))
    spec = importlib.util.spec_from_file_location(
        "paper_tracker_for_line_clv", ROOT / "tracking" / "paper_tracker.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


line_clv = _load()._line_clv_pts


# ── Totals: the over wants a HIGHER close, the under a LOWER one ─────────────

def test_an_over_taken_below_the_close_beat_it():
    # Over 44.5 closing 46.5: we needed two fewer points than the market did.
    assert line_clv("totals", None, "over", 44.5, 46.5) == 2.0


def test_an_over_taken_above_the_close_lost_to_it():
    assert line_clv("totals", None, "over", 46.5, 44.5) == -2.0


def test_an_under_taken_above_the_close_beat_it():
    # Under 46.5 closing 44.5: we could give up two more points than the market.
    assert line_clv("totals", None, "under", 46.5, 44.5) == 2.0


def test_an_under_taken_below_the_close_lost_to_it():
    assert line_clv("totals", None, "under", 44.5, 46.5) == -2.0


# ── Spreads: scored_line and closing_line are both the HOME number ───────────

def test_a_home_favourite_laying_fewer_points_than_the_close_beat_it():
    # Home -3.5 closing -5.5. Getting the same team two points cheaper is value,
    # and the HOME number FELL to do it — the sign trap this repo has hit twice.
    assert line_clv("spreads", None, "home", -3.5, -5.5) == 2.0


def test_a_home_pick_whose_number_shortened_lost_to_the_close():
    assert line_clv("spreads", None, "home", -5.5, -3.5) == -2.0


def test_an_away_dog_taking_more_points_than_the_close_beat_it():
    # Stored home-relative: -3.5 -> -5.5 means the away side went +3.5 -> +5.5.
    # We took +5.5 and it closed +3.5, so we hold the better number.
    assert line_clv("spreads", None, "away", -5.5, -3.5) == 2.0


def test_an_away_pick_whose_number_shrank_lost_to_the_close():
    assert line_clv("spreads", None, "away", -3.5, -5.5) == -2.0


def test_the_home_and_away_sides_are_exact_mirrors():
    """Both sides of one game cannot beat the close."""
    for scored, closing in [(-3.5, -5.5), (2.5, 7.0), (0.0, -1.0)]:
        h = line_clv("spreads", None, "home", scored, closing)
        a = line_clv("spreads", None, "away", scored, closing)
        assert h == pytest.approx(-a)


# ── Props use the same over/under orientation as totals ─────────────────────

def test_a_prop_over_is_oriented_like_a_total():
    assert line_clv("player_points", "player_points", "over", 18.5, 20.5) == 2.0


def test_a_prop_under_is_oriented_like_a_total():
    assert line_clv("player_points", "player_points", "under", 20.5, 18.5) == 2.0


def test_the_prop_market_flag_wins_over_the_market_string():
    """A prop market key carries neither 'totals' nor 'spreads' in its name, so
    the prop flag has to be what orients it."""
    assert line_clv("batter_hits", "batter_hits", "over", 0.5, 1.5) == 1.0


# ── Nothing to measure ──────────────────────────────────────────────────────

def test_moneyline_has_no_line_to_move():
    assert line_clv("h2h", None, "home", None, None) is None


def test_a_missing_close_is_not_a_zero():
    """Reporting "the line held" for a close we never captured would publish a
    beat-the-close verdict on no evidence."""
    assert line_clv("totals", None, "over", 44.5, None) is None
    assert line_clv("totals", None, "over", None, 46.5) is None


def test_a_line_that_held_is_exactly_zero_not_none():
    """0.0 and None mean different things: measured-and-flat vs unmeasurable."""
    assert line_clv("totals", None, "over", 44.5, 44.5) == 0.0


def test_a_side_that_cannot_be_oriented_returns_none_rather_than_guessing():
    """'draw' on a 3-way market has no line, and a guess here would invert a
    verdict rather than omit it."""
    assert line_clv("spreads", None, "draw", -3.5, -5.5) is None
    assert line_clv("totals", None, "home", 44.5, 46.5) is None


# ── The sign convention agrees with the app's movement chip ─────────────────

def test_the_signs_are_the_negation_of_the_apps_entry_frame():
    """markets.ts computeMovement asks "is the entry available NOW worse than
    what we locked?" and this asks "did the close prove our number good?" — the
    same delta, negated. Any drift between them puts a red chip on a pick the
    CLV card calls a win.

    computeMovement (mobile/src/lib/markets.ts):
      spreads: home hurt when delta < 0, away hurt when delta > 0
      totals:  under hurt when delta < 0, over  hurt when delta > 0
    """
    cases = [
        ("spreads", "home",  -3.5, -5.5),   # delta -2 -> entry worse now
        ("spreads", "away",  -5.5, -3.5),   # delta +2 -> entry worse now
        ("totals",  "under", 46.5, 44.5),   # delta -2 -> entry worse now
        ("totals",  "over",  44.5, 46.5),   # delta +2 -> entry worse now
    ]
    for market, side, scored, closing in cases:
        # Every case above is one the app would flag as "moved against you if
        # you bet it now" — which is exactly a pick that BEAT the close.
        assert line_clv(market, None, side, scored, closing) > 0
