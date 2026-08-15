"""
Tests for the umpire ingestor's self-heal window logic (session 116).

Pure-function tests only — no DB, no MLB Stats API. The heal window is what
fixes the 2026-07-12 → 2026-08-14 freeze: the daily pipeline moved to 6am ET
(before MLB posts officials), so fetching only run_date silently wrote 0 rows
and nothing ever retried a past date.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.umpire_ingestor import _heal_window_lo


class TestHealWindowLo:
    def test_default_trailing_window(self):
        # Table is current (yesterday) → plain 10-day trailing window.
        assert _heal_window_lo("2026-08-14", "2026-08-13") == "2026-08-04"

    def test_long_outage_extends_to_day_after_max(self):
        # The production freeze: MAX(game_date)=2026-07-12 → window reaches
        # back to 7/13 so the whole gap backfills on the first run.
        assert _heal_window_lo("2026-08-14", "2026-07-12") == "2026-07-13"

    def test_empty_table_uses_default_window(self):
        assert _heal_window_lo("2026-08-14", None) == "2026-08-04"

    def test_cap_bounds_pathological_gap(self):
        # A years-old max can't trigger a full-history refetch.
        assert _heal_window_lo("2026-08-14", "2019-04-01") == "2025-08-14"

    def test_max_inside_window_keeps_default(self):
        # Newest row is only 3 days old — the 10-day window already covers it.
        assert _heal_window_lo("2026-08-14", "2026-08-11") == "2026-08-04"

    def test_garbage_max_falls_back_to_default(self):
        assert _heal_window_lo("2026-08-14", "not-a-date") == "2026-08-04"

    def test_timestamp_shaped_max_is_truncated(self):
        # game_date is TEXT — tolerate a full ISO timestamp.
        assert _heal_window_lo("2026-08-14", "2026-07-12T00:00:00") == "2026-07-13"
