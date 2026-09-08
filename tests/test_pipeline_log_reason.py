"""
pipeline_log carries the step's own reason (2026-09-08).

Every `step_*` catches its exception, logs it and returns False, so the
dispatcher only ever saw a False and wrote "see the step's own log for the
reason". The step's own log is a container that has usually been redeployed
by the time anyone reads the table: on 2026-09-08 `health-check` had failed
18 times in three days and `lineups` 14, and the table could not say why for
a single one of them. mike: "I also want to know about the failures in the
ops log ... and the plan to rectify."

The dispatcher now captures the last ERROR line the step emits and stores it
in pipeline_log.error_msg. Watched failing before the fix: error_msg was the
fixed sentence, whatever the step had logged.
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class _Conn:
    def __init__(self, sink):
        self.sink = sink

    def execute(self, sql, params=None):
        self.sink.append((sql, params))

    def commit(self):
        pass

    def close(self):
        pass


def _capture(monkeypatch):
    rows: list = []
    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: _Conn(rows))
    return rows


def test_a_false_step_records_the_last_error_it_logged(monkeypatch):
    rows = _capture(monkeypatch)
    import run_pipeline

    def step():
        logger.error("✗ Lineups failed: EMAXCONNSESSION from the pooler")
        return False

    ok = run_pipeline._timed_step("lineups", step, "2026-09-08")
    assert ok is False
    sql, params = rows[-1]
    assert "INSERT INTO pipeline_log" in sql
    assert params[1] == "dispatch:lineups" and params[2] == "error"
    assert "EMAXCONNSESSION" in params[-1], params[-1]
    assert "see the step's own log" not in params[-1]


def test_a_false_step_that_logged_nothing_still_says_so(monkeypatch):
    rows = _capture(monkeypatch)
    import run_pipeline
    ok = run_pipeline._timed_step("quiet", lambda: False, "2026-09-08")
    assert ok is False
    assert rows[-1][1][-1] == "step returned False"


def test_the_sink_is_removed_after_the_step(monkeypatch):
    rows = _capture(monkeypatch)
    import run_pipeline
    run_pipeline._timed_step("a", lambda: True, "2026-09-08")
    # A later error, outside any step, must not leak into the next step's row.
    logger.error("stray error between steps")
    run_pipeline._timed_step("b", lambda: False, "2026-09-08")
    assert rows[-1][1][-1] == "step returned False"


def test_a_raising_step_still_records_the_exception(monkeypatch):
    rows = _capture(monkeypatch)
    import run_pipeline
    import pytest

    def boom():
        raise RuntimeError("kaboom")

    with pytest.raises(RuntimeError):
        run_pipeline._timed_step("boom", boom, "2026-09-08")
    assert rows[-1][1][2] == "error" and "RuntimeError: kaboom" in rows[-1][1][-1]
