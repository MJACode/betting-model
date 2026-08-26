"""
Regression tests for the NCAAF snapshot look-ahead leak.

Root cause (found 2026-08-25): CFBD restarts week numbering for the
postseason, so every bowl and playoff game is season_type='postseason',
week=1. The snapshot builder filtered completed games with `week < wk`, which
therefore admitted the ENTIRE postseason into every in-season snapshot from
week 2 onward -- putting January playoff results into September features.

Measured impact before the fix: 32.7% of 40,194 snapshots (2014-2025) carried
look-ahead, stable at 30-36% in every season. Ohio State's 2024-09-04 snapshot
reported games_played=5 against a true count of 1.

The fix filters on DATE. These tests pin that, and specifically pin that the
OLD week-based logic would have failed -- so the test cannot pass vacuously if
someone reintroduces a week filter.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.cfbd_ingestor import _completed_before  # noqa: E402


def _ohio_state_2024() -> list[dict]:
    """The real shape that exposed the bug — regular weeks plus 4 playoff games."""
    return [
        {"team": "Ohio State", "week": 1, "season_type": "regular",
         "game_date": "2024-08-31", "points": 52},
        {"team": "Ohio State", "week": 2, "season_type": "regular",
         "game_date": "2024-09-07", "points": 56},
        {"team": "Ohio State", "week": 4, "season_type": "regular",
         "game_date": "2024-09-21", "points": 49},
        # All four playoff games carry week=1 in CFBD's numbering.
        {"team": "Ohio State", "week": 1, "season_type": "postseason",
         "game_date": "2024-12-22", "points": 42},
        {"team": "Ohio State", "week": 1, "season_type": "postseason",
         "game_date": "2025-01-01", "points": 41},
        {"team": "Ohio State", "week": 1, "season_type": "postseason",
         "game_date": "2025-01-11", "points": 28},
        {"team": "Ohio State", "week": 1, "season_type": "postseason",
         "game_date": "2025-01-21", "points": 34},
    ]


def test_postseason_excluded_from_early_season_snapshot():
    """The exact production failure: a Sept snapshot must see ONE game, not five."""
    rows = _completed_before(_ohio_state_2024(), "2024-09-04")
    assert len(rows) == 1, (
        f"snapshot dated 2024-09-04 saw {len(rows)} games; Ohio State had "
        "played exactly one by then (Aug 31 vs Akron)")
    assert rows[0]["game_date"] == "2024-08-31"


def test_the_old_week_filter_would_have_failed_this():
    """
    Control. If this assertion ever stops holding, the fixture no longer
    reproduces the bug and the test above proves nothing.
    """
    wk = 2                                   # snapshot for week 2
    old_logic = [r for r in _ohio_state_2024()
                 if r.get("week") is not None and r["week"] < wk]
    assert len(old_logic) == 5, (
        "the week-based filter should admit the Aug 31 opener plus all four "
        "postseason week-1 games — that is the bug being regressed")


def test_end_of_regular_season_snapshot_excludes_playoffs():
    """A December snapshot sees the regular season but not the playoff run."""
    rows = _completed_before(_ohio_state_2024(), "2024-12-13")
    assert len(rows) == 3, "should see the 3 regular-season games, no playoffs"
    assert all(r["season_type"] == "regular" for r in rows)


def test_boundary_is_strict():
    """A game played ON the as_of date is not yet completed information."""
    rows = [{"game_date": "2024-09-07", "week": 2}]
    assert _completed_before(rows, "2024-09-07") == []
    assert len(_completed_before(rows, "2024-09-08")) == 1


def test_missing_or_malformed_dates_are_dropped_not_admitted():
    """Unknown timing must fail CLOSED — never silently included."""
    rows = [
        {"game_date": None, "week": 1},
        {"week": 1},
        {"game_date": "", "week": 1},
        {"game_date": "2024-08-31", "week": 1},
    ]
    got = _completed_before(rows, "2024-09-04")
    assert len(got) == 1 and got[0]["game_date"] == "2024-08-31"


def test_datetime_like_values_are_handled():
    """The column can come back as a timestamp string; the [:10] cut must work."""
    rows = [{"game_date": "2024-08-31 19:30:00", "week": 1}]
    assert len(_completed_before(rows, "2024-09-04")) == 1
    assert _completed_before(rows, "2024-08-31") == []


def test_empty_input():
    assert _completed_before([], "2024-09-04") == []
