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


def test_ufc_poll_uses_the_etag_gate_and_the_daily_run_does_not():
    """The mirror is ~9.8 MB fetched unconditionally, so the hourly caller must
    check before pulling. The 6am run deliberately does not: a broken check
    would make a skipping poll silent, and the daily run is the backstop."""
    src = Path("run_pipeline.py").read_text(encoding="utf-8")
    body = src[src.index("def step_ufc_results("):]
    body = body[:body.index("\ndef ", 1)]
    assert "def step_ufc_results(run_date: str, poll: bool = False)" in body
    assert re.search(r"if poll and mirror_unchanged\(\):\s*\n.*\n\s*return True", body)


def test_mirror_unchanged_is_conservative_when_it_cannot_tell():
    """Any doubt must fetch. Silently skipping a card is the expensive failure;
    an extra download is not."""
    from data.ingestors import ufc_csv_loader as ufc
    head, cached = ufc._mirror_etag, ufc._cached_etag
    try:
        ufc._mirror_etag = lambda: None            # HEAD failed
        ufc._cached_etag = lambda: '"abc"'
        assert ufc.mirror_unchanged() is False
        ufc._mirror_etag = lambda: '"abc"'
        ufc._cached_etag = lambda: None            # nothing cached yet
        assert ufc.mirror_unchanged() is False
        ufc._cached_etag = lambda: '"abc"'         # match
        assert ufc.mirror_unchanged() is True
    finally:
        ufc._mirror_etag, ufc._cached_etag = head, cached


def test_etag_is_recorded_only_after_a_clean_ingest():
    src = Path("data/ingestors/ufc_csv_loader.py").read_text(encoding="utf-8")
    body = src[src.index("def ingest_ufc_results_for_date_csv("):]
    body = body[:body.index("\ndef ", 1)]
    # captured before the download, stored after the DB work completes
    assert body.index("etag = _mirror_etag()") < body.index("_read_csv(\"events\")")
    assert body.index("conn.close()") < body.index("_store_etag(etag)")
