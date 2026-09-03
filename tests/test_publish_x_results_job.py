"""Recovering a missed X recap, on the worker where the credentials are.

WHAT WENT WRONG. The recap fix (#402) merged at 20:42 ET on 2026-09-02 and the
`x_results:2026-09-02` ledger row was deleted a minute later so the corrected
record would post at 6am. The Railway deploy stamp `2026-09-03T00:42Z` was read
as ET; it was still the 2nd, the deploy had not finished, and the next refresh
pass — running the OLD code, with no day-is-over guard — re-posted a partial
8-4 and re-ledgered it. That row blocked the 6am post: Discord published 13-17,
X published nothing.

CLAUDE.md §7's "use ET, never UTC, for today", made in reasoning rather than in
code. The recovery runs as a job because the X credentials live on the worker
(§1b: a handover is a last resort with a reason attached).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import job_queue as jq  # noqa: E402


def test_the_job_type_is_registered_and_validated():
    fn, validator = jq.JOBS["publish_x_results"]
    assert callable(fn) and callable(validator)


@pytest.mark.parametrize("bad", [{}, {"game_date": ""}, {"game_date": "nope"},
                                 {"game_date": "2026/09/02"}])
def test_a_malformed_date_is_refused_before_anything_runs(bad):
    with pytest.raises(ValueError):
        jq.JOBS["publish_x_results"][1](bad)


def test_a_good_date_survives_validation():
    assert jq.JOBS["publish_x_results"][1](
        {"game_date": "2026-09-02", "junk": 1}) == {"game_date": "2026-09-02"}


def test_the_job_does_not_bypass_the_day_is_over_guard():
    """THE SAFETY PROPERTY. Re-posting must not become a way to publish a
    partial mid-slate record — which is the bug the whole exercise was fixing.
    The job clears the ledger and calls the ORDINARY notify_x_results, whose
    guard still refuses a date that is not over.
    """
    src = (Path(__file__).parent.parent / "tracking"
           / "job_queue.py").read_text(encoding="utf-8")
    i = src.index("def _job_publish_x_results(")
    body = src[i:src.index("\ndef ", i + 10)]
    assert "notify_x_results(game_date)" in body, (
        "the job must call the ordinary path, guard included")
    for bypass in ("datetime", "today", "force"):
        assert bypass not in body.split('"""')[-1], (
            f"the job manipulates {bypass} — the guard must be untouched")


def test_the_job_only_clears_its_own_ledger_kind():
    """A DELETE on push_sent that is not tightly scoped can silently un-post
    Discord signals, push notifications and the free pick."""
    src = (Path(__file__).parent.parent / "tracking"
           / "job_queue.py").read_text(encoding="utf-8")
    i = src.index("def _job_publish_x_results(")
    body = src[i:src.index("\ndef ", i + 10)]
    delete = body[body.index("DELETE FROM push_sent"):]
    assert "lock_key = %s" in delete and "kind = 'x_results'" in delete
