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


def test_a_false_step_fails_the_job(monkeypatch):
    import run_pipeline
    monkeypatch.setattr(run_pipeline, "_timed_step", lambda name, fn, d: False)
    with pytest.raises(RuntimeError):
        jq._job_nba_quarters(run_date="2026-10-30")
    monkeypatch.setattr(run_pipeline, "_timed_step", lambda name, fn, d: True)
    assert jq._job_nba_quarters(run_date="2026-10-30") == {"ok": True, "run_date": "2026-10-30"}
