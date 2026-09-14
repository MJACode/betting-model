"""A named candidate map is promoted on the worker, not by the nightly fit.

2026-09-14: mlb_prop_batter_runs was +11.1pp overconfident at the probability
the 09-07 promoted map had stamped. The candidate that morning helped AND
transferred. Promotion is a model update (CLAUDE.md 1b), so it cannot live in
`run_calibration_fit`; it is a job type, requested by name, reviewed in git.
"""
from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parents[1]


def test_promote_calibration_is_a_registered_job_type():
    assert "promote_calibration" in jq.JOBS


def test_the_runner_calls_promote_not_the_nightly_fit():
    fn, _ = jq.JOBS["promote_calibration"]
    src = inspect.getsource(fn)
    assert "promote(" in src
    assert "run_calibration_fit" not in src
    assert "PAUSED_MODELS" not in src


def test_models_must_be_a_non_empty_known_list():
    _, validate = jq.JOBS["promote_calibration"]
    with pytest.raises(ValueError):
        validate({})
    with pytest.raises(ValueError):
        validate({"models": []})
    with pytest.raises(ValueError):
        validate({"models": ["not_a_model"]})
    with pytest.raises(ValueError):
        validate({"models": ["mlb_prop_batter_runs", "mlb_prop_batter_runs"]})


def test_the_validator_drops_unknown_args():
    _, validate = jq.JOBS["promote_calibration"]
    assert validate({"models": ["mlb_prop_batter_runs"], "command": "rm"}) == {
        "models": ["mlb_prop_batter_runs"]}


def test_the_declared_batter_runs_job_is_present_and_valid():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    match = [e for e in entries if e["key"] == "promote-batter-runs-map-2026-09-14"]
    assert match, "declared_jobs.json missing the batter_runs re-promote"
    job = match[0]
    assert job["job_type"] == "promote_calibration"
    assert job["requested_by"] == "mike"
    assert job["args"]["models"] == ["mlb_prop_batter_runs"]
    # pitcher_er is the other CRIT model and must NOT ride along
    assert "mlb_prop_pitcher_er" not in job["args"]["models"]
    _, validate = jq.JOBS["promote_calibration"]
    validate(job["args"])


def test_a_refused_model_rolls_back_and_raises(monkeypatch):
    """A skip looking like success is how a stale map stays on the decision
    path with a green queue card."""

    class _Conn:
        def __init__(self):
            self.committed = False
            self.rolled_back = False

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            self.committed = True

        def close(self):
            pass

    conn = _Conn()
    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: conn)
    import models.probability_calibration as pc
    monkeypatch.setattr(pc, "promote", lambda c, models: [])
    with pytest.raises(RuntimeError, match="refused"):
        jq._job_promote_calibration(models=["mlb_prop_batter_runs"])
    assert conn.rolled_back and not conn.committed


def test_a_successful_promote_commits(monkeypatch):
    class _Conn:
        def __init__(self):
            self.committed = False

        def rollback(self):
            pass

        def commit(self):
            self.committed = True

        def close(self):
            pass

    conn = _Conn()
    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: conn)
    import models.probability_calibration as pc
    monkeypatch.setattr(pc, "promote",
                        lambda c, models: list(models))
    out = jq._job_promote_calibration(models=["mlb_prop_batter_runs"])
    assert out == {"promoted": ["mlb_prop_batter_runs"]}
    assert conn.committed
