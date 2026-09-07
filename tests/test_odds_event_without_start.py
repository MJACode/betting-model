"""
An Odds API event with no parseable start never becomes a games row.

Three MLB games rows exist with commence_time NULL -- MLB_2026-04-16_NYM_LAD,
MLB_2026-04-17_SEA_SD, MLB_2026-04-17_COL_HOU -- all written by the pulls of
2026-04-15 11:55Z and 2026-04-16 00:49Z, each a West Coast night game filed a
SECOND time under its UTC date beside the real ET-dated row. The scorer priced
the NYM@LAD duplicate off its stale snapshot and wrote a BET (pick 661) on a
game the Stats API never scheduled; nothing could ever settle it. The code
that wrote them predates the surviving git history, so the exact April path
is unknowable. What the parser can guarantee now is that an event it cannot
date is dropped with a warning rather than filed under the snapshot's date
with no start time -- a row that is unpublishable and unsettleable.

The first test fails on the pre-fix parser, which files the dateless event
under the snapshot's day.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.odds_ingestor import _process_events  # noqa: E402


def _event(commence, eid="abc"):
    return {
        "id": eid,
        "commence_time": commence,
        "home_team": "Los Angeles Dodgers",
        "away_team": "New York Mets",
        "bookmakers": [{
            "key": "draftkings",
            "markets": [{"key": "totals", "outcomes": [
                {"name": "Over", "price": -110, "point": 7.5},
                {"name": "Under", "price": -110, "point": 7.5},
            ]}],
        }],
    }


SNAP = "2026-04-15T20:49:00-04:00"


def test_an_event_without_a_parseable_start_is_dropped():
    games, odds = _process_events([_event("")], "MLB", "open", SNAP)
    assert games == [] and odds == []


def test_a_garbage_start_is_dropped_too():
    games, odds = _process_events([_event("not a time")], "MLB", "open", SNAP)
    assert games == [] and odds == []


def test_a_dated_event_still_lands_on_its_eastern_date():
    """10:11pm ET on the 15th is 02:11Z on the 16th; the row is the 15th's."""
    games, odds = _process_events([_event("2026-04-16T02:11:00Z")], "MLB", "open", SNAP)
    assert [g["game_id"] for g in games] == ["MLB_2026-04-15_NYM_LAD"]
    assert games[0]["commence_time"] == "2026-04-16T02:11:00+00:00"
    assert len(odds) == 1 and odds[0]["game_id"] == "MLB_2026-04-15_NYM_LAD"


def test_a_bad_event_does_not_take_its_neighbours_with_it():
    games, _odds = _process_events(
        [_event(""), _event("2026-04-16T02:11:00Z", eid="def")], "MLB", "open", SNAP)
    assert [g["game_id"] for g in games] == ["MLB_2026-04-15_NYM_LAD"]
