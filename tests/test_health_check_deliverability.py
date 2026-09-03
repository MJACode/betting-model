"""signal_delivery must not report a failure nobody can fix.

mike: "look at why health-check keeps failing."

It failed on EVERY refresh pass for three days because of ONE row.
`MIN vs DET Under 8.5` was locked into opening_signals at 2026-08-31 19:45 ET
against a 19:41 ET first pitch — four minutes after the game started. It was
never delivered, it can never be delivered now, and the CRIT check counts any
postable signal from the last three days with no discord_signal ledger row. So
it held the check red until it would have aged out of the window on 09-04 —
going quiet because time passed, not because anything was fixed.

A permanent false alarm is how a check stops being read (§7, and the same
reasoning as #401's cadence floor for the pipeline watch).

Detection is deliberately unchanged: a real notifier outage shows up as TODAY's
signals going undelivered past the 90-minute grace, and those are locked
pre-commence by construction.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.system_health import _deliverable  # noqa: E402

START = "2026-08-31T23:41:00+00:00"          # 19:41 ET first pitch


def test_a_signal_locked_after_first_pitch_was_never_deliverable():
    """The exact row that held the check red."""
    assert _deliverable("2026-08-31T19:45:00.093035-04:00", START) is False


def test_a_signal_locked_before_first_pitch_still_counts():
    """The check must keep catching a genuine delivery failure."""
    assert _deliverable("2026-08-31T18:36:00-04:00", START) is True


def test_a_signal_locked_exactly_at_first_pitch_counts():
    """Boundary: at the pitch it was still postable."""
    assert _deliverable("2026-08-31T23:41:00+00:00", START) is True


@pytest.mark.parametrize("locked,commence", [
    (None, START),
    ("2026-08-31T19:45:00-04:00", None),
    ("not a timestamp", START),
    ("2026-08-31T19:45:00-04:00", "not a timestamp"),
])
def test_it_fails_toward_noticing(locked, commence):
    """An unparseable or missing timestamp on EITHER side counts as
    deliverable. The opposite default would let one NULL commence_time silence
    a real outage — a check must not be gated on the thing that breaks (§7)."""
    assert _deliverable(locked, commence) is True


def test_mixed_timestamp_shapes_are_parsed_not_string_compared():
    """These columns are TEXT in mixed shapes ('Z' vs '-04:00' vs naive). A
    string comparison silently keeps the wrong rows (§7) — and here it would
    keep the wrong ones in the flattering direction, hiding the alarm.

    '2026-08-31T19:45:00-04:00' sorts BEFORE '2026-08-31T23:41:00+00:00' as a
    string, so a naive comparison calls this deliverable; parsed, they are the
    same instant plus four minutes and it is not.
    """
    locked = "2026-08-31T19:45:00-04:00"
    assert locked < START, "fixture no longer demonstrates the string trap"
    assert _deliverable(locked, START) is False


def test_the_query_does_not_use_postgres_only_casts():
    """The health checks run against sqlite in tests and Postgres in
    production. A `::timestamptz` cast passes locally against the real database
    and breaks every test in the shim — which is how the first version of this
    fix was caught."""
    src = (Path(__file__).parent.parent / "tracking"
           / "system_health.py").read_text(encoding="utf-8")
    assert "::timestamptz" not in src
