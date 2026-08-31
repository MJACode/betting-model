"""
Every step of the refresh pass must record how long it took.

The pass runs 28 steps and takes ~12 minutes, but only 8 step types ever wrote
to pipeline_log -- 2.7 of those 12 minutes. The other nine were invisible, so
"where does the time go" was unanswerable. mike, 2026-08-30: "we absolutely
need to get the 12 minutes down." You cannot cut what you cannot measure.

Two properties matter, and the second is the one that bites:

  * EVERY step is timed, because timing sits at the single dispatch point
    rather than in 28 call sites. The step that gets forgotten is always the
    slow one nobody suspected.
  * Timing can NEVER fail a step. This is §7's "a health check must not gate
    on the thing that breaks" applied to instrumentation: a pass that dies
    because its stopwatch could not reach the database is strictly worse than
    an unmeasured pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

_SRC = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")


def _timed_step():
    import run_pipeline
    return run_pipeline._timed_step


# ── it never breaks the step ──────────────────────────────────────────────────

def test_a_dead_database_does_not_fail_the_step(monkeypatch):
    """The whole point: measuring must not be able to break what it measures."""
    import run_pipeline
    import data.db as db
    monkeypatch.setattr(db, "get_connection",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db")))
    assert run_pipeline._timed_step("odds", lambda: True, "2026-08-30") is True


def test_the_step_result_passes_through_untouched(monkeypatch):
    import run_pipeline
    import data.db as db
    monkeypatch.setattr(db, "get_connection",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db")))
    assert run_pipeline._timed_step("x", lambda: False, "2026-08-30") is False
    assert run_pipeline._timed_step("x", lambda: True, "2026-08-30") is True


def test_a_step_that_raises_still_raises(monkeypatch):
    """
    Swallowing the exception would turn a broken step into a silent one --
    exactly the failure the run ledger was built to end.
    """
    import run_pipeline
    import data.db as db
    monkeypatch.setattr(db, "get_connection",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db")))

    def boom():
        raise ValueError("step exploded")

    with pytest.raises(ValueError, match="step exploded"):
        run_pipeline._timed_step("x", boom, "2026-08-30")


def test_a_step_that_raises_is_still_TIMED(monkeypatch):
    """
    A step that dies after four minutes is exactly the kind we are hunting.
    Recording only successes would hide the worst offenders.
    """
    import run_pipeline
    written = []

    class _Conn:
        def execute(self, sql, params=None):
            written.append(params)
            return self
        def commit(self): pass
        def close(self): pass

    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: _Conn())

    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        run_pipeline._timed_step("slow-step", boom, "2026-08-30")

    assert written, "a failing step recorded no duration"
    row = written[0]
    assert row[1] == "dispatch:slow-step"
    assert row[2] == "error"
    assert row[4] and "ValueError" in row[4], "the error must be recorded"


def test_a_successful_step_records_a_duration(monkeypatch):
    import run_pipeline
    written = []

    class _Conn:
        def execute(self, sql, params=None):
            written.append(params)
            return self
        def commit(self): pass
        def close(self): pass

    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: _Conn())
    run_pipeline._timed_step("odds", lambda: True, "2026-08-30")

    row = written[0]
    assert row[0] == "2026-08-30"
    assert row[1] == "dispatch:odds"
    assert row[2] == "success"
    assert isinstance(row[3], float) and row[3] >= 0


# ── it covers everything ──────────────────────────────────────────────────────

def test_timing_wraps_the_single_dispatch_point():
    """
    28 call sites would be 28 chances to forget one. Pin that the dispatch goes
    through the wrapper, so a step added tomorrow is measured for free.
    """
    assert "_timed_step(args.step, step_fns[args.step], run_date)" in _SRC
    assert "success = step_fns[args.step]()" not in _SRC, (
        "an unwrapped dispatch path would leave steps unmeasured")


def test_the_dispatch_rows_are_distinguishable_from_producer_rows():
    """
    Some steps already log their own row with records_in/out. The dispatch row
    is a SECOND row measuring wall clock, and the two must be separable or the
    per-producer detail is lost in aggregation.
    """
    assert 'f"dispatch:{name}"' in _SRC


def test_every_step_name_in_the_dispatch_table_is_reachable():
    """A step registered but unreachable is dead config that reads as coverage."""
    table = _SRC[_SRC.index("step_fns = {"):_SRC.index("success = _timed_step")]
    names = [ln.split('"')[1] for ln in table.splitlines()
             if ln.strip().startswith('"') and ":" in ln]
    assert len(names) >= 40, f"only {len(names)} steps found — parser drifted"
    assert len(names) == len(set(names)), "duplicate step name in the table"


def test_the_refresh_chain_only_calls_registered_steps():
    """
    A typo in refresh_pass.sh is a step that silently never runs -- and an
    absent producer looks exactly like a quiet market (§7).
    """
    sh = (Path(__file__).parent.parent / "scripts" / "refresh_pass.sh").read_text()
    called = [ln.split()[1] for ln in sh.splitlines()
              if ln.strip().startswith("step ") and len(ln.split()) > 1]
    table = _SRC[_SRC.index("step_fns = {"):_SRC.index("success = _timed_step")]
    for name in called:
        assert f'"{name}":' in table, f"refresh_pass.sh calls unknown step {name!r}"


def test_a_step_that_returns_false_records_a_REASON(monkeypatch):
    """
    Every step_* in this repo catches its own exception and returns False, so
    the interesting failures never raise. The first version of this recorded
    status='error' with error_msg NULL — a failure with no reason.

    It cost a diagnosis the same day it shipped: `lineups` failed on the
    2026-08-30 16:17 pass and the row could not say why, so "is this new, or is
    it 4pm on a Sunday" was unanswerable from the table.
    """
    import run_pipeline
    written = []

    class _Conn:
        def execute(self, sql, params=None):
            written.append(params)
            return self
        def commit(self): pass
        def close(self): pass

    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: _Conn())
    assert run_pipeline._timed_step("lineups", lambda: False, "2026-08-30") is False

    row = written[0]
    assert row[2] == "error"
    assert row[4], "a returned failure must record SOME reason, not NULL"
    assert "returned False" in row[4], (
        "the reason must distinguish a returned failure from a raised one")


def test_a_raised_failure_still_records_the_exception(monkeypatch):
    """The two failure modes must stay distinguishable when reading back."""
    import run_pipeline
    written = []

    class _Conn:
        def execute(self, sql, params=None):
            written.append(params)
            return self
        def commit(self): pass
        def close(self): pass

    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: _Conn())

    def boom():
        raise KeyError("missing_feature")

    with pytest.raises(KeyError):
        run_pipeline._timed_step("scoring", boom, "2026-08-30")
    assert "KeyError" in written[0][4]
    assert "returned False" not in written[0][4]
