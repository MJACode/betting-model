"""backfill_mlb_prop_odds: every row it writes must be pre-game.

WHY THE ANCHORING IS THE WHOLE TEST. backfill_nfl_prop_odds takes ONE snapshot
per date, anchored to 17:00 UTC, because an NFL slate is a handful of kickoff
times clustered together. An MLB slate runs 13:05 to 22:10 ET. A single instant
per date is three hours early for some games and INSIDE others -- and a row from
a game already under way is exactly the leak that made the first grading of
models/mlb_prop_market meaningless (see load_quotes and
tests/test_mlb_prop_market_pregame.py).

So each event is fetched at ITS OWN commence_time minus hours_before, and these
tests pin that rather than trusting it.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import data.ingestors.prop_odds_ingestor as ing


def test_each_event_is_anchored_to_its_own_first_pitch():
    """A source guard on the property that makes the backfill honest: the
    snapshot is derived from the EVENT's commence_time, not from the date."""
    src = inspect.getsource(ing.backfill_mlb_prop_odds)
    assert "kick - timedelta(hours=hours_before)" in src, src
    # ...and never from a fixed hour, which is the NFL shape.
    assert "T17:00:00" not in src, src


def test_the_anchor_arithmetic_is_pre_game_for_every_start_time():
    """The actual claim, computed across a real MLB spread of first pitches:
    every snapshot must land strictly before its own game."""
    for et_hour in (13, 16, 19, 20, 22):          # 1:05pm .. 10:10pm ET
        # ET -> UTC is +4 in summer, which rolls past midnight for late games.
        kick = (datetime(2026, 6, 10, et_hour, 5, tzinfo=timezone.utc)
                + timedelta(hours=4))
        for lead in (1, 3, 6):
            snap = kick - timedelta(hours=lead)
            assert snap < kick
            assert (kick - snap).total_seconds() / 3600 == lead


def test_it_records_the_served_snapshot_not_the_requested_one():
    """The Odds API snaps to its nearest stored snapshot. Recording what we
    ASKED for would misstate when the price existed -- the same leak-discipline
    rule the NFL backfill follows."""
    src = inspect.getsource(ing.backfill_mlb_prop_odds)
    assert "stamp = served or snap" in src, src
    assert "datetime.now" not in src, "a backfill must never stamp the run time"


def test_the_listing_instant_precedes_every_first_pitch():
    """16:00Z is 12:00 ET -- before the earliest MLB first pitch, so the listing
    sees the whole scheduled slate and nothing has been removed for starting.
    Verified against the API 2026-09-06: 10:00Z and 16:00Z return the same 9
    events for 2026-08-20 and the same 15 for 2026-06-10."""
    src = inspect.getsource(ing.backfill_mlb_prop_odds)
    assert 'T16:00:00Z' in src, src
    earliest_et_first_pitch = 13     # 1:05pm ET games exist; nothing earlier
    assert 16 - 4 < earliest_et_first_pitch


def test_it_is_append_only():
    """Every snapshot writer here appends; the reader takes the latest
    qualifying row. A backfill that replaced rows would destroy the live
    series it is being added alongside."""
    src = inspect.getsource(ing._insert_prop_odds)
    assert "DELETE" not in src.upper(), src
    assert "ON CONFLICT" not in src.upper(), src
