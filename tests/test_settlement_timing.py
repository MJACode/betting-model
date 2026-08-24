"""
Guards for running settlement on an hourly cadence rather than once a day.

Both behaviours here fail SILENTLY if they regress — a wrong CLV number looks
like a real one, and a half-ingested game log looks like a complete one — so
they are pinned rather than left to review.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tracking.paper_tracker import _as_utc


NOW = datetime(2026, 8, 23, 23, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize("stored", [
    "2026-08-23T22:00:00Z",          # both forms are present in production:
    "2026-08-23T22:00:00+00:00",     # 3 rows vs 997 as of 2026-08-23
    "2026-08-23T18:00:00-04:00",     # same instant, local offset
])
def test_started_games_are_recognised_in_every_stored_format(stored):
    assert _as_utc(stored) <= NOW


@pytest.mark.parametrize("stored", [
    "2026-08-24T01:00:00Z",
    "2026-08-24T01:00:00+00:00",
])
def test_future_kickoffs_are_not_treated_as_started(stored):
    assert _as_utc(stored) > NOW


def test_z_and_offset_forms_are_the_same_instant_but_not_the_same_string():
    """The reason this is parsed rather than compared as TEXT.

    commence_time is stored in both forms. These two are the SAME moment, yet
    'Z' (0x5A) sorts after '+' (0x2B), so a `commence_time <= now` done in SQL
    puts them on opposite sides of the boundary. Once parsed they are equal, as
    they should be.
    """
    z, offset = "2026-08-23T22:00:00Z", "2026-08-23T22:00:00+00:00"
    assert z > offset                          # the trap: unequal as strings
    assert _as_utc(z) == _as_utc(offset)       # correct once parsed


@pytest.mark.parametrize("bad", [None, "", "garbage", "2026-13-45"])
def test_unparseable_timestamps_yield_none_rather_than_a_guess(bad):
    assert _as_utc(bad) is None


def test_capture_clv_requires_the_game_to_have_started():
    """Source-level: the guard must stay in the loop, not drift out of it."""
    src = Path("tracking/paper_tracker.py").read_text(encoding="utf-8")
    body = src[src.index("def _capture_clv("):]
    body = body[:body.index("\ndef ", 1)]
    assert "_as_utc(commence_time)" in body
    assert re.search(r"if ct is None or ct > now_utc:\s*\n\s*continue", body)


def test_game_log_skips_per_game_not_per_date():
    """A date-level skip strands every game that was not yet final on the first
    call of the evening — including for the next morning's run, which would then
    also see rows and skip."""
    src = Path("data/ingestors/mlb_stats_ingestor.py").read_text(encoding="utf-8")
    body = src[src.index("def ingest_game_log_for_date("):]
    body = body[:body.index("\ndef ", 1)]
    assert "SELECT DISTINCT game_id FROM player_game_log" in body
    assert "if game_id in done_game_ids:" in body
    assert "if existing > 0:" not in body
