"""One-shot worker job that drains the CLV no-vig rewrite.

#729 already revisits `clv_method='raw_one_sided'` on each settle, 40 dates
per run. There is no `settle` job_type, so history would take many scheduled
settles. This job opens the ordinary `get_connection()` path and loops
`paper_tracker._backfill_clv` until a pass fills 0 (or 40 passes).
"""
from __future__ import annotations

import inspect
import json
import sys
import types
from pathlib import Path

import pytest

import tracking.job_queue as jq

ROOT = Path(__file__).resolve().parents[1]
DECLARED_KEY = "clv-no-vig-backfill-2026-09-14"


def test_clv_backfill_is_a_registered_job_type():
    assert "clv_backfill" in jq.JOBS
    assert "settle" not in jq.JOBS


def test_the_runner_opens_get_connection_and_calls_backfill_clv():
    """Same DB path as the other jobs. Do not invent a second connection."""
    fn, _ = jq.JOBS["clv_backfill"]
    src = inspect.getsource(fn)
    assert "from data.db import get_connection" in src
    assert "get_connection()" in src
    assert "_backfill_clv(" in src
    assert "PAUSED_MODELS" not in src
    assert "ACTION_THRESHOLDS" not in src


def test_empty_args_mean_forty_passes():
    _, validate = jq.JOBS["clv_backfill"]
    assert validate({}) == {"max_passes": 40}
    assert validate({"max_passes": None}) == {"max_passes": 40}
    assert validate({"max_passes": ""}) == {"max_passes": 40}
    assert validate({"max_passes": 7, "command": "rm"}) == {"max_passes": 7}


def test_max_passes_is_bounded():
    _, validate = jq.JOBS["clv_backfill"]
    with pytest.raises(ValueError, match="max_passes"):
        validate({"max_passes": 0})
    with pytest.raises(ValueError, match="max_passes"):
        validate({"max_passes": 41})


def test_the_declared_key_is_present_and_valid():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(
        encoding="utf-8"))
    match = [e for e in entries if e["key"] == DECLARED_KEY]
    assert match, f"declared_jobs.json missing {DECLARED_KEY}"
    job = match[0]
    assert job["job_type"] == "clv_backfill"
    assert job["requested_by"] == "mike"
    _, validate = jq.JOBS["clv_backfill"]
    validate(job.get("args") or {})


class _Conn:
    def __init__(self):
        self.commits = 0
        self.closed = False

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed = True


def _stub_backfill(monkeypatch, fn):
    """The job imports paper_tracker inside the runner. Stub the module so
    the test does not load models.scorer (scipy) just to call a function
    we are replacing anyway."""
    fake = types.ModuleType("tracking.paper_tracker")
    fake._backfill_clv = fn
    monkeypatch.setitem(sys.modules, "tracking.paper_tracker", fake)


def test_loops_until_a_pass_fills_nothing(monkeypatch):
    conn = _Conn()
    calls: list[str] = []

    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: conn)

    def fake_backfill(c, now_iso):
        assert c is conn
        calls.append(now_iso)
        return 5 if len(calls) < 3 else 0

    _stub_backfill(monkeypatch, fake_backfill)
    out = jq._job_clv_backfill(max_passes=40)
    assert out["stopped"] == "empty"
    assert out["passes"] == 3
    assert out["filled_per_pass"] == [5, 5, 0]
    assert out["filled"] == 10
    assert conn.commits == 3
    assert conn.closed
    assert len(calls) == 3
    assert all(calls[0] == t for t in calls)


def test_hard_cap_stops_a_nonempty_queue(monkeypatch):
    conn = _Conn()
    import data.db
    monkeypatch.setattr(data.db, "get_connection", lambda: conn)
    _stub_backfill(monkeypatch, lambda c, now: 2)
    out = jq._job_clv_backfill(max_passes=4)
    assert out["stopped"] == "cap"
    assert out["passes"] == 4
    assert out["filled_per_pass"] == [2, 2, 2, 2]
    assert out["filled"] == 8
    assert conn.commits == 4
    assert conn.closed
