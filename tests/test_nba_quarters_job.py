"""The on-demand nba_quarters worker job runs the daily step's own dispatch."""
from __future__ import annotations

import inspect

import pytest

import tracking.job_queue as jq


def test_the_job_is_on_the_allowlist():
    fn, validate = jq.JOBS["nba_quarters"]
    assert fn is jq._job_nba_quarters
    assert validate({}) == {}
    assert validate({"run_date": "2026-10-30"}) == {"run_date": "2026-10-30"}
    with pytest.raises(ValueError):
        validate({"run_date": "tomorrow"})


def test_it_goes_through_timed_step_and_never_shells_out():
    src = inspect.getsource(jq._job_nba_quarters)
    assert '_timed_step(\n        "nba-quarters"' in src
    assert "subprocess" not in src and "os.system" not in src


def test_a_false_step_is_recorded_once_and_not_requeued(monkeypatch):
    """A step that returns False has already written its pipeline_log error row
    inside _timed_step. Raising from the job puts the row back to pending and
    runs it again, up to MAX_ATTEMPTS. health_check and model_quality return
    {"ok": false} for a non-ok result and the queue records that once."""
    import json

    import run_pipeline

    calls = []

    def timed(name, fn, run_date):
        calls.append((name, run_date))
        return False

    monkeypatch.setattr(run_pipeline, "_timed_step", timed)
    monkeypatch.setattr(jq, "_announce", lambda *a, **k: None)

    assert jq._job_nba_quarters(run_date="2026-10-30") == {
        "ok": False, "run_date": "2026-10-30"}

    class Conn:
        def __init__(self):
            self.writes = []

        def execute(self, sql, params=None):
            self.writes.append((sql, params))
            return self

        def commit(self):
            pass

    conn = Conn()
    out = jq._execute(conn, {
        "job_id": 9,
        "job_type": "nba_quarters",
        "args": {"run_date": "2026-10-30"},
        "attempts": 1,
    })
    assert calls == [("nba-quarters", "2026-10-30"),
                     ("nba-quarters", "2026-10-30")]
    assert out["status"] == "done"
    assert out["result"] == {"ok": False, "run_date": "2026-10-30"}
    assert "final" not in out
    assert len(conn.writes) == 1
    sql, params = conn.writes[0]
    assert "status='done'" in sql
    assert json.loads(params[0]) == {"ok": False, "run_date": "2026-10-30"}
    assert "pending" not in sql

    monkeypatch.setattr(run_pipeline, "_timed_step", lambda name, fn, d: True)
    assert jq._job_nba_quarters(run_date="2026-10-30") == {
        "ok": True, "run_date": "2026-10-30"}
