"""Yardline parse from the CFBD situation string.

Kept out of test_serve.py so PR CI can run these without importing
LiveEngine (and lightgbm). The engine fixture in that file is why a
whole-file subset entry failed pytest-subset on #770.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# Every distinct situation string the loop stored on the first slate it kept
# them (2026-09-19, ncaaf_live_states.raw_state), with the possession the feed
# reported beside it: (string, home, away, possession, yards to goal).
_REAL_SITUATIONS = [
    ("4th & 7 at CCU 47", "Delaware", "Coastal Carolina", "away", 53),
    ("2nd & 14 at ARK 36", "Arkansas", "Georgia", "away", 36),
    ("2nd & 10 at BGSU 18", "Iowa State", "Bowling Green", "away", 82),
    ("1st & 10 at ASU 31", "Kansas", "Arizona State", "away", 69),
    ("1st & 10 at MER 31", "Georgia Tech", "Mercer", "home", 31),
    ("4th & 3 at UNC 5", "Clemson", "North Carolina", "home", 5),
    ("4th & 10 at AKR 14", "Minnesota", "Akron", "away", 86),
    ("1st & 10 at UNT 44", "Texas State", "North Texas", "home", 44),
    ("2nd & 8 at EMU 27", "Wisconsin", "Eastern Michigan", "away", 73),
    ("1st & 17 at NCSU 8", "Vanderbilt", "NC State", "away", 92),
    ("2nd & 3 at ME 22", "Boston College", "Maine", "away", 78),
    ("2nd & 4 at ILL 41", "Illinois", "Southern Illinois", "home", 59),
]


def _cfbd_game(status="in_progress", period=2, clock="8:00", hp=14, ap=10,
               possession="home", situation="2nd & 7 at TCU 48",
               home_id=2628, away_id=153):
    return {"status": status, "period": period, "clock": clock,
            "possession": possession, "situation": situation,
            "homeTeam": {"id": home_id, "name": "TCU Horned Frogs",
                         "points": hp},
            "awayTeam": {"id": away_id, "name": "North Carolina Tar Heels",
                         "points": ap}}


_IDS = {2628: "TCU", 153: "North Carolina"}


@pytest.mark.parametrize("text,home,away,poss,want", _REAL_SITUATIONS)
def test_cfbd_yardline_from_every_stored_situation(text, home, away, poss, want):
    """The training column is CFBD's yardsToGoal: distance to the opponent's
    end zone for the offense. The ball on the named team's own side is 100
    minus the yard; on the other team's side it is the yard."""
    from ncaaf_live.feeds.cfbd_scoreboard import _parse_yardline
    assert _parse_yardline(text, home, away, poss) == want


def test_cfbd_yardline_refuses_rather_than_guesses():
    from ncaaf_live.feeds.cfbd_scoreboard import _parse_yardline
    # Unknown possession: the side of the field has no meaning.
    assert _parse_yardline("1st & 10 at UNT 44", "Texas State", "North Texas", None) is None
    # Fits both schools (Michigan / Michigan State): refuse.
    assert _parse_yardline("1st & 10 at MICH 30", "Michigan", "Michigan State", "home") is None
    # Fits neither.
    assert _parse_yardline("1st & 10 at XYZ 30", "Delaware", "Coastal Carolina", "home") is None
    # Midfield is midfield whoever has it; a bare "at 50" is not a shape we know.
    assert _parse_yardline("1st & 10 at CCU 50", "Delaware", "Coastal Carolina", "home") == 50
    assert _parse_yardline("1st & 10 at 50", "Delaware", "Coastal Carolina", "home") is None
    # Any other shape.
    assert _parse_yardline("Kickoff", "Delaware", "Coastal Carolina", "home") is None
    assert _parse_yardline(None, "Delaware", "Coastal Carolina", "home") is None


def test_cfbd_state_carries_the_yardline_and_the_raw_situation():
    from ncaaf_live.feeds.cfbd_scoreboard import extract_live_states_cfbd
    g = _cfbd_game()
    g["situation"] = "3rd & 7 at TCU 25"
    g["possession"] = "home"                 # TCU is home in the fixture
    st = extract_live_states_cfbd([g], _IDS)[0]
    assert st["situation"] == "3rd & 7 at TCU 25"
    assert st["yardline_100"] == 75         # own 25 -> 75 to go
