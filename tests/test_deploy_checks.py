"""Scheduled verification: a named check, run on the worker at a chosen time,
announced to the ops channel. Session 280 (2026-09-11), mike: "Schedule run to
confirm these things and alert me."

What is pinned: a job can name only a registered check; the claim honours
`run_after`; a declared job carries its time through; and a failing check
raises so the queue's failure card is the alert.
"""
from __future__ import annotations

import json

import pytest

from tracking import deploy_checks as dc
from tracking import job_queue as q


class _Conn:
    def __init__(self, rows):
        self.rows = list(rows)
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        return self

    def fetchone(self):
        return self.rows.pop(0) if self.rows else None

    def commit(self):
        pass


def test_every_check_is_read_only():
    """Every statement a check executes starts with SELECT."""
    import inspect
    import re
    for name, fn in dc.CHECKS.items():
        src = inspect.getsource(fn)
        stmts = re.findall(r'execute\(\s*"""\s*(\w+)', src)
        assert stmts, f"{name} executes nothing?"
        assert all(v.upper() == "SELECT" for v in stmts), (name, stmts)


def test_a_job_can_only_name_a_registered_check():
    with pytest.raises(ValueError):
        q.enqueue(_Conn([]), "verify_checks", {"checks": ["not_a_check"]})
    with pytest.raises(ValueError):
        q.enqueue(_Conn([]), "verify_checks", {"checks": []})


def test_the_claim_waits_for_run_after():
    conn = _Conn([])
    q.claim_one(conn)
    claim_sql = [s for s, _ in conn.sql if "SET status = 'running'" in s][0]
    assert "run_after IS NULL OR run_after <= NOW()" in claim_sql


def test_enqueue_rejects_a_naive_run_after():
    with pytest.raises(ValueError):
        q.enqueue(_Conn([]), "verify_checks", {"checks": ["ncaaf_paused_avoid_gone"]},
                  run_after="2026-09-12T10:45:00")


def test_enqueue_stores_run_after(monkeypatch):
    monkeypatch.setattr(q, "ensure_schema", lambda conn: None)
    conn = _Conn([(7,)])
    q.enqueue(conn, "verify_checks", {"checks": ["ncaaf_paused_avoid_gone"]},
              run_after="2026-09-12T10:45:00Z", dedupe_key="k")
    sql, params = [x for x in conn.sql if "INSERT INTO worker_jobs" in x[0]][0]
    assert "run_after" in sql
    assert params[-1].startswith("2026-09-12T10:45:00")


def test_a_declared_job_carries_its_run_after(monkeypatch, tmp_path):
    seen = {}

    def _enqueue(conn, job_type, args, requested_by, note, dedupe_key, run_after=None):
        seen.update(job_type=job_type, run_after=run_after)
        return 1

    monkeypatch.setattr(q, "enqueue", _enqueue)
    f = tmp_path / "declared.json"
    f.write_text(json.dumps([{"key": "k", "job_type": "verify_checks",
                              "run_after": "2026-09-12T02:20:00+00:00",
                              "args": {"checks": ["kalshi_game_snapshot_fresh"]}}]),
                 encoding="utf-8")
    q.sync_declared_jobs(_Conn([]), path=f)
    assert seen == {"job_type": "verify_checks", "run_after": "2026-09-12T02:20:00+00:00"}


def test_the_two_session_280_checks_are_declared():
    declared = json.loads(q.DECLARED_JOBS_FILE.read_text(encoding="utf-8"))
    mine = {e["key"]: e for e in declared if e.get("job_type") == "verify_checks"}
    assert "verify-280-paused-avoid-2026-09-12" in mine
    assert "verify-280-kalshi-snapshot-2026-09-12" in mine
    for e in mine.values():
        assert e["run_after"].endswith("+00:00")
        q.JOBS["verify_checks"][1](e["args"])          # validates


def test_a_failing_check_raises_so_the_queue_announces_it(monkeypatch):
    monkeypatch.setitem(dc.CHECKS, "always_fails", lambda conn: (False, "nope"))
    monkeypatch.setitem(dc.CHECKS, "always_ok", lambda conn: (True, "fine"))
    with pytest.raises(RuntimeError, match="always_fails: nope"):
        dc.run_checks(None, ["always_ok", "always_fails"])
    out = dc.run_checks(None, ["always_ok"])
    assert out["verdict"] == "PASS" and out["checks"]["always_ok"]["ok"]
