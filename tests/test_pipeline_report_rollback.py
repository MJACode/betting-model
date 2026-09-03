"""
One broken section of the report must not break every section after it.

WHY THIS EXISTS
---------------
Measured 2026-09-03, on the pipeline watch's FIRST ever scheduled run. The log:

    WARNING pipeline_watch:_rows - query failed: current transaction is
            aborted, commands ignored until end of transaction block
    INFO    run_watch - 13 finding(s), 12 pass(es), 0 picks, posted=True

"0 picks" on a day when the same query run standalone returns 14 groups.

Two defects, one visible symptom:

  1. `failing_checks` compared `system_health_checks.run_date` -- a TEXT column
     -- against a date, so it raised `operator does not exist: text >= date`
     on every single run. Rule 3 of the watch (health checks CRIT) had
     therefore NEVER worked, and 10 not-OK rows were invisible.

  2. `_rows` caught that error and returned a tidy QUERY FAILED marker WITHOUT
     rolling back. On Postgres a failed statement aborts the transaction, so
     every later statement failed too -- each with its own tidy marker. One
     broken section became six.

This is the same defect #390 fixed in tracking/system_health.py. A second
module had it, which is why the fix is tested here rather than trusted.
"""

from __future__ import annotations

import re
from pathlib import Path

from scripts import pipeline_report as pr

ROOT = Path(__file__).parent.parent


class _Conn:
    """Fails the Nth statement, then behaves like Postgres: everything after
    it raises until someone rolls back."""

    def __init__(self, fail_on=1):
        self.calls = 0
        self.fail_on = fail_on
        self.aborted = False
        self.rollbacks = 0

    def execute(self, sql, params=()):
        self.calls += 1
        if self.calls == self.fail_on:
            self.aborted = True
            raise RuntimeError("operator does not exist: text >= date")
        if self.aborted:
            raise RuntimeError("current transaction is aborted, commands ignored "
                               "until end of transaction block")
        return self

    def fetchall(self):
        return [("ok",)]

    def rollback(self):
        self.rollbacks += 1
        self.aborted = False


def test_a_failed_query_rolls_back():
    conn = _Conn(fail_on=1)
    out = pr._rows(conn, "SELECT 1")
    assert out[0][0] == "QUERY FAILED"
    assert conn.rollbacks == 1, (
        "without the rollback the transaction stays aborted and every later "
        "section fails too")


def test_one_broken_section_does_not_break_the_rest():
    """The whole point. Section 3 of 6 fails; 4, 5 and 6 must still return."""
    conn = _Conn(fail_on=3)
    results = [pr._rows(conn, f"SELECT {i}") for i in range(1, 7)]

    failed = [i for i, r in enumerate(results, 1) if r and r[0][0] == "QUERY FAILED"]
    assert failed == [3], (
        f"expected only section 3 to fail, got {failed} — a missing rollback "
        f"turns one broken section into every section after it")
    assert results[3] == [("ok",)] and results[5] == [("ok",)]


def test_the_health_check_query_does_not_compare_text_to_a_date():
    """`run_date` is TEXT. `run_date >= <date>` raises on Postgres, which is
    how this section returned nothing for its entire life."""
    src = (ROOT / "scripts" / "pipeline_report.py").read_text(encoding="utf-8")
    block = src[src.index('out["failing_checks"]'):src.index('out["api_burn_by_source"]')]
    assert "run_date >=" in block
    assert "to_char(" in block, (
        "compare TEXT to TEXT — both sides are ISO YYYY-MM-DD, which sorts "
        "correctly as text")
    assert not re.search(r"run_date\s*>=\s*\(now\(\)[^)]*\)::date", block), (
        "the text >= date comparison is back")


def test_every_section_is_still_present():
    """A fix that quietly drops a section would pass the tests above."""
    src = (ROOT / "scripts" / "pipeline_report.py").read_text(encoding="utf-8")
    for key in ("slowest_steps", "recent_passes", "failing_checks",
                "api_burn_by_source", "picks_written", "delivery"):
        assert f'"{key}"' in src, f"report lost its {key} section"
