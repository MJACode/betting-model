"""
The opener's ceiling: a gap to Pinnacle no real number has ever shown is a feed
error, and the model does not bet it (mike, 2026-11-24).

The board in these tests is the real one. At 20:56:01Z on 2026-11-24 The Odds
API served BetMGM's PHI @ DAL spread as DAL +5.5 (-110 / -108). One poll
earlier it was DAL -8.5 (-108 / -110), and every other book and Pinnacle stayed
at DAL -8.5 (Hard Rock -9). The card wrote "PHI @ DAL — DAL +5.5" at BetMGM
-110, a 14-point gap, and posted it. mike: "dal +5.5 that doesn't exist in any
way shape or form".
"""

import importlib.util
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
# data_ingest lives only under nfl/. Appended, not prepended: nfl/ also has
# `models` and `scripts` packages that must not shadow the platform's.
if str(ROOT / "nfl") not in sys.path:
    sys.path.append(str(ROOT / "nfl"))

_mspec = importlib.util.spec_from_file_location(
    "nfl_opener_spread_model_ceiling", ROOT / "nfl" / "models" / "opener_spread.py")
opener = importlib.util.module_from_spec(_mspec)
_mspec.loader.exec_module(opener)


def _sched(home="DAL", away="PHI", gid="NFL_2026_12_PHI_DAL"):
    return pd.DataFrame([{
        "game_id": gid, "home_team": home, "away_team": away,
        "matchup": f"{away} @ {home}", "kick_utc": "2026-11-26 21:30:00+00:00",
        "lead_days": 2.02,
    }])


def _both(book, home_point, px_home, px_away, home="DAL", away="PHI", event="ev1"):
    base = {"event_id": event, "home": home, "away": away, "book": book,
            "market": "spreads"}
    return [dict(base, side="home", point=home_point, price=px_home),
            dict(base, side="away", point=-home_point, price=px_away)]


def _board_2026_11_24_2056(mgm_point=5.5, mgm_home=-110, mgm_away=-108):
    """The stored nfl_odds_history quotes at 20:56:01Z, bettable books + Pinnacle."""
    rows = (_both("pinnacle", -8.5, -106, -106)
            + _both("betmgm", mgm_point, mgm_home, mgm_away)
            + _both("draftkings", -8.5, -111, -108)
            + _both("fanduel", -8.5, -110, -110)
            + _both("betrivers", -8.5, -110, -110)
            + _both("williamhill_us", -8.5, -110, -109)
            + _both("fanatics", -8.5, -110, -110)
            + _both("hardrockbet", -9.0, -110, -110))
    return pd.DataFrame(rows)


class TestTheDallasBoard:
    def test_the_phantom_number_is_not_bet(self):
        bets = opener.select_opener_bets(_board_2026_11_24_2056(), _sched())
        assert bets.empty, bets.to_dict("records")

    def test_the_audit_row_says_why_it_declined(self):
        (row,) = opener.evaluate_board(_board_2026_11_24_2056(), _sched())
        assert row["qualifies"] == "0"
        assert "betmgm" in row["reason"] and "ceiling" in row["reason"]
        # The book's main line was not what the gap was measured from, so the
        # row carries the largest gap that IS believable (Hard Rock, 0.5).
        assert row["current_book"] != "betmgm"

    def test_the_same_board_one_poll_earlier_is_not_touched(self):
        # BetMGM's own number a minute before: DAL -8.5, no gap, no bet,
        # and nothing said about a ceiling.
        board = _board_2026_11_24_2056(-8.5, -108, -110)
        assert opener.select_opener_bets(board, _sched()).empty
        (row,) = opener.evaluate_board(board, _sched())
        assert "ceiling" not in row["reason"]


class TestTheCeilingIsAQuoteFilterNotAGameFilter:
    def test_a_believable_second_book_still_bets(self):
        # Pinnacle DAL -8.5; BetMGM the phantom +5.5; FanDuel DAL -6.5, a real
        # 2-point gap. The game is NOT declined because one book glitched.
        board = pd.DataFrame(_both("pinnacle", -8.5, -106, -106)
                             + _both("betmgm", 5.5, -110, -108)
                             + _both("fanduel", -6.5, -110, -110))
        bets = opener.select_opener_bets(board, _sched())
        assert len(bets) == 1
        b = bets.iloc[0]
        assert b.book == "fanduel" and b.dev == 2.0 and b.side_line == -6.5
        (row,) = opener.evaluate_board(board, _sched())
        assert row["qualifies"] == "1" and row["current_book"] == "fanduel"
        assert row["current_line"] == -6.5


class TestWhereTheCeilingSits:
    """Neighbourhood, from the stored quotes (docs/nfl_opener_dev_ceiling.md).

    The largest gap any bettable book has held against Pinnacle two to ten days
    out: 3.5 points in 2021-2025, 4.5 in 2026 (ARI @ SEA, five books agreeing
    after Pinnacle moved). The gaps of 5.5 and more since 2021 are all feed
    glitches: BetMGM TEN @ NYG 2026-09-24 (5.5, three polls), BetRivers HOU @
    TEN 2026-10-07 (14, an alternate line at -770), BetMGM PHI @ DAL today (14).
    """

    def test_the_ceiling_is_five(self):
        assert opener.MAX_DEV == 5.0

    def test_the_largest_real_gap_seen_still_bets(self):
        # ARI @ SEA 2026-11-04: Pinnacle SEA -13, William Hill SEA -8.5.
        board = pd.DataFrame(_both("pinnacle", -13.0, -110, -110, home="SEA", away="ARI")
                             + _both("williamhill_us", -8.5, -110, -110, home="SEA", away="ARI"))
        bets = opener.select_opener_bets(board, _sched("SEA", "ARI", "NFL_2026_09_ARI_SEA"))
        assert len(bets) == 1 and bets.iloc[0].dev == 4.5

    def test_exactly_five_still_bets(self):
        board = pd.DataFrame(_both("pinnacle", -8.5, -106, -106)
                             + _both("betmgm", -3.5, -110, -110))
        bets = opener.select_opener_bets(board, _sched())
        assert len(bets) == 1 and bets.iloc[0].dev == 5.0

    def test_the_smallest_glitch_seen_does_not(self):
        # TEN @ NYG 2026-09-24: Pinnacle NYG -2.5, BetMGM NYG +3.0.
        board = pd.DataFrame(_both("pinnacle", -2.5, -110, -110, home="NYG", away="TEN")
                             + _both("betmgm", 3.0, -110, -110, home="NYG", away="TEN"))
        sched = _sched("NYG", "TEN", "NFL_2026_03_TEN_NYG")
        assert opener.select_opener_bets(board, sched).empty
        (row,) = opener.evaluate_board(board, sched)
        assert row["qualifies"] == "0" and "ceiling" in row["reason"]

    def test_the_age_label_is_untouched(self):
        # Not the fresh-number gate mike rejected on 2026-09-22: a NEW number
        # inside the ceiling still fires at once and still carries its age.
        assert opener.FRESH_MINUTES == 60.0
        assert opener.age_tag(0.0) == "NEW 0m"
