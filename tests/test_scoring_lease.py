"""The scoring lease is what a second container can see.

The threading locks in scheduler.py do not cross a Railway overlap.
These tests use a fake connection. They fail if the boot sweep stamps a
daily whose lease is held, or if a timed-out wait is treated as free.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tracking.job_queue import QUEUE_LOCK_KEY
from tracking.scoring_lease import (
    _KEYS,
    acquire,
    drop_live_kinds,
    held,
    wait_for_scoring_lease,
)


class _Timeout(Exception):
    pgcode = "55P03"


class Fake:
    def __init__(self, *, try_got=True, lock_error=None):
        self.sql: list[str] = []
        self.closed = False
        self.try_got = try_got
        self.lock_error = lock_error
        self.commits = 0

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if "pg_advisory_lock" in sql and "try" not in sql and self.lock_error:
            raise self.lock_error
        return self

    def fetchone(self):
        if self.sql and "pg_try_advisory_lock" in self.sql[-1]:
            return (self.try_got,)
        return (1,)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = True


def test_a_dropped_session_logs_the_lease_as_lost():
    src = (
        Path(__file__).resolve().parent.parent / "tracking" / "scoring_lease.py"
    ).read_text(encoding="utf-8")
    assert src.count("scoring lease: LOST") >= 3


def test_the_lease_keys_are_not_the_job_queue_lock():
    assert QUEUE_LOCK_KEY not in _KEYS.values()
    assert len(set(_KEYS.values())) == len(_KEYS)


def test_held_is_false_when_this_session_could_take_the_lock():
    conn = Fake(try_got=True)
    assert held("daily", connect=lambda: conn) is False
    assert any("pg_advisory_unlock" in sql for sql in conn.sql)
    assert conn.closed


def test_held_is_true_when_try_lock_fails():
    conn = Fake(try_got=False)
    assert held("refresh", connect=lambda: conn) is True
    assert not any("pg_advisory_unlock" in sql for sql in conn.sql)
    assert conn.closed


def test_a_timed_out_wait_does_not_count_as_free():
    conn = Fake(lock_error=_Timeout("canceling statement due to lock timeout"))
    assert wait_for_scoring_lease("daily", connect=lambda: conn) is False
    assert conn.closed


def test_a_database_that_cannot_be_opened_does_not_block_the_boot():
    def boom():
        raise RuntimeError("down")

    assert wait_for_scoring_lease("daily", connect=boom) is True
    assert held("daily", connect=boom) is False


def test_acquire_locks_and_release_unlocks():
    conn = Fake()
    lease = acquire("daily", connect=lambda: conn, keepalive_s=60)
    assert lease is not None
    assert any(
        "pg_advisory_lock" in sql and "try" not in sql for sql in conn.sql
    )
    lease.release()
    assert any("pg_advisory_unlock" in sql for sql in conn.sql)
    assert conn.closed
    lease.release()  # second call is a no-op


def test_acquire_returns_none_when_the_lock_times_out():
    conn = Fake(lock_error=_Timeout("lock timeout"))
    assert acquire("daily", connect=lambda: conn) is None
    assert conn.closed


def test_drop_live_kinds_keeps_a_held_daily_out_of_the_sweep(monkeypatch):
    monkeypatch.setattr(
        "tracking.scoring_lease.held", lambda kind, **kwargs: kind == "daily",
    )
    assert drop_live_kinds(["hourly", "evening", "daily"]) == ["hourly", "evening"]


def test_boot_sweep_does_not_abort_a_daily_whose_lease_is_held(monkeypatch):
    import scheduler
    from tracking import run_ledger

    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE pipeline_runs ("
        "run_id TEXT PRIMARY KEY, run_kind TEXT, started_at TEXT, "
        "finished_at TEXT, steps_total INTEGER, steps_failed INTEGER, "
        "failed_steps TEXT, ok BOOLEAN)"
    )
    db.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at) "
        "VALUES ('daily-live', 'daily', '2026-11-05T11:00:00+00:00')"
    )
    db.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at) "
        "VALUES ('evening-dead', 'evening', '2026-11-05T03:50:00+00:00')"
    )
    db.commit()

    class Conn:
        def execute(self, sql, params=None):
            return db.execute(sql, params or ())

        def commit(self):
            db.commit()

        def rollback(self):
            db.rollback()

        def close(self):
            pass

    monkeypatch.setattr(run_ledger, "_BOOT_CUTOFF", None)
    monkeypatch.setattr(run_ledger, "_ensure_table", lambda c: None)
    monkeypatch.setattr(run_ledger, "get_connection", lambda *a, **k: Conn())
    import data.db as dbmod
    monkeypatch.setattr(dbmod, "get_connection", lambda *a, **k: Conn())
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "pipeline")
    monkeypatch.setattr(
        "tracking.scoring_lease.held",
        lambda kind, **kwargs: kind == "daily",
    )

    assert scheduler.abort_orphaned_refresh_runs() == 1
    daily_fin = db.execute(
        "SELECT finished_at FROM pipeline_runs WHERE run_id='daily-live'"
    ).fetchone()[0]
    assert daily_fin is None
    evening_fin, evening_failed = db.execute(
        "SELECT finished_at, failed_steps FROM pipeline_runs "
        "WHERE run_id='evening-dead'"
    ).fetchone()
    assert evening_fin is not None
    assert evening_failed == "aborted"


def test_boot_sweep_aborts_the_daily_when_the_lease_is_free(monkeypatch):
    """The same sweep, with nobody holding the lease, still closes the row.
    A guard that never aborts would also satisfy the test above."""
    import scheduler
    from tracking import run_ledger

    db = sqlite3.connect(":memory:")
    db.execute(
        "CREATE TABLE pipeline_runs ("
        "run_id TEXT PRIMARY KEY, run_kind TEXT, started_at TEXT, "
        "finished_at TEXT, steps_total INTEGER, steps_failed INTEGER, "
        "failed_steps TEXT, ok BOOLEAN)"
    )
    db.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at) "
        "VALUES ('daily-dead', 'daily', '2026-11-05T11:00:00+00:00')"
    )
    db.commit()

    class Conn:
        def execute(self, sql, params=None):
            return db.execute(sql, params or ())

        def commit(self):
            db.commit()

        def rollback(self):
            db.rollback()

        def close(self):
            pass

    monkeypatch.setattr(run_ledger, "_BOOT_CUTOFF", None)
    monkeypatch.setattr(run_ledger, "_ensure_table", lambda c: None)
    monkeypatch.setattr(run_ledger, "get_connection", lambda *a, **k: Conn())
    import data.db as dbmod
    monkeypatch.setattr(dbmod, "get_connection", lambda *a, **k: Conn())
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "pipeline")
    monkeypatch.setattr(
        "tracking.scoring_lease.held", lambda kind, **kwargs: False,
    )

    assert scheduler.abort_orphaned_refresh_runs() == 1
    failed = db.execute(
        "SELECT failed_steps FROM pipeline_runs WHERE run_id='daily-dead'"
    ).fetchone()[0]
    assert failed == "aborted"
