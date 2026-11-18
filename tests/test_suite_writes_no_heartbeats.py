"""
No test writes a job check-in row to a real database (#1456).

Every scheduled job writes a check-in row ("I ran") to `job_heartbeats`
(tracking/job_heartbeat.beat), and building the scheduler writes one for each
watched job: "registered" for the ones it schedules, "disabled" for the ones
this service owns but switched off. One `scheduler.build_scheduler()` made 32
connections on 2026-11-18, and 21 calls in the suite build it.

`tests/conftest.py` imports `data.db`, which loads the checkout's `.env`. In
the main checkout that points at production, so a suite run would reset the
silence clock on every watched job and mark the PC's absent jobs as switched
off. In a copy with no `.env`, each connection was a refused localhost dial of
4 s, and a full run had not finished after 14 hours.

So the suite replaces `beat` before any test runs (tests/conftest.py). These
tests hold that in place, and they prove the trap they use still sees the
route the real `beat` takes, so a passing guard cannot be a blind one.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")


def _trap_connections(monkeypatch):
    """Record every attempt to open a database connection, and refuse it.

    Both doors: `data.db.get_connection` (what `beat` uses), and
    `psycopg2.connect`, for any module that bound `get_connection` at import
    time and so would walk past a patch on `data.db`. Never dials.
    """
    import psycopg2

    import data.db

    dialled = []

    def refuse(door):
        def _refuse(*a, **k):
            dialled.append(door)
            raise RuntimeError(f"a test opened a database connection via {door}")
        return _refuse

    monkeypatch.setattr(data.db, "get_connection", refuse("data.db.get_connection"))
    monkeypatch.setattr(psycopg2, "connect", refuse("psycopg2.connect"))
    return dialled


def _build(monkeypatch):
    """Build the worker's scheduler the way the suite's 21 call sites do.

    The role is pinned, because another test reloads the scheduler as the
    in-play service. `seed` and `mark_disabled` are spied on, calling through to
    the real ones, so a zero below cannot come from a build that wrote nothing
    because it registered nothing.
    """
    import scheduler
    from tracking import job_heartbeat as jh

    seeded, disabled = [], []
    real_seed, real_mark_disabled = jh.seed, jh.mark_disabled

    def seed(job_id):
        seeded.append(job_id)
        return real_seed(job_id)

    def mark_disabled(job_id, *a, **k):
        disabled.append(job_id)
        return real_mark_disabled(job_id, *a, **k)

    monkeypatch.setattr(jh, "seed", seed)
    monkeypatch.setattr(jh, "mark_disabled", mark_disabled)
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "pipeline")
    monkeypatch.setattr(scheduler, "RUN_NFL_LIVE", False)
    sched = scheduler.build_scheduler()
    return sched, seeded, disabled


def test_building_the_scheduler_opens_no_database_connection(monkeypatch):
    dialled = _trap_connections(monkeypatch)
    sched, seeded, disabled = _build(monkeypatch)

    # The build did write check-ins: watched jobs were registered and seeded,
    # and at least one watched job was marked switched off.
    assert sched.get_jobs(), "the scheduler registered no jobs"
    assert seeded, "no watched job was seeded, so this test proves nothing"
    assert "nfl_live_worker" in disabled, disabled
    # And none of them reached a database.
    assert dialled == [], (
        f"building the scheduler opened {len(dialled)} database connection(s); "
        "on a checkout with a .env each is a heartbeat row written to that "
        "database (tests/conftest.py should replace tracking.job_heartbeat.beat)")


def _run_a_wrapped_job(sched):
    """Register a do-nothing job through the scheduler's own wrapper and run
    it once. The wrapper writes the job's check-in when the job returns."""
    ran = []
    sched.add_job(lambda: ran.append(1), "interval", minutes=5,
                  id="suite_heartbeat_probe")
    sched.get_job("suite_heartbeat_probe").func()
    assert ran == [1], "the job body did not run, so its check-in was never reached"


def test_a_job_that_runs_in_a_test_opens_no_database_connection(monkeypatch):
    """A test that runs a scheduled job (tests/test_morning_disk.py does) must
    not write that job's check-in row either."""
    dialled = _trap_connections(monkeypatch)
    sched, _, _ = _build(monkeypatch)
    _run_a_wrapped_job(sched)
    assert dialled == [], dialled


def test_the_trap_sees_the_route_the_real_heartbeat_takes(monkeypatch, real_heartbeat):
    """The guard above is only worth something if the trap it sets is on the
    path a real check-in takes. Put the real `beat` back and the same build
    must hit it. If `beat` ever moves to another connection route, this fails
    and the guard has to follow it."""
    dialled = _trap_connections(monkeypatch)
    sched, seeded, disabled = _build(monkeypatch)
    assert len(dialled) == len(seeded) + len(disabled) > 0, (
        len(dialled), len(seeded), len(disabled))
    dialled.clear()
    _run_a_wrapped_job(sched)
    assert dialled == ["data.db.get_connection"], dialled


class _StandInConn:
    def __init__(self):
        self.sql, self.committed, self.closed = [], False, False

    def execute(self, sql, params=()):
        self.sql.append((" ".join(sql.split()), params))
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def rollback(self):
        pass

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


def test_the_real_heartbeat_still_writes_its_row(monkeypatch, real_heartbeat):
    """A test that wants the real `beat` asks for `real_heartbeat` and gives it
    a stand-in database, as here."""
    import data.db
    from tracking import job_heartbeat as jh

    conn = _StandInConn()
    monkeypatch.setattr(data.db, "get_connection", lambda *a, **k: conn)
    jh.seed("job_queue")
    upserts = [p for s, p in conn.sql if s.startswith("INSERT INTO job_heartbeats")]
    assert len(upserts) == 1
    job_id, _, status, detail = upserts[0]
    assert (job_id, status, detail) == ("job_queue", "registered", "scheduled, not yet run")
    assert conn.committed and conn.closed


def test_the_suite_stub_keeps_the_real_source_readable():
    """tests/test_nba_team_total_luck_window.py reads the real `beat`'s source
    to show the heartbeat is that job's only connection. The stub keeps it."""
    import inspect

    from tracking import job_heartbeat as jh

    assert jh.beat.__wrapped__ is not jh.beat
    assert "get_connection()" in inspect.getsource(jh.beat)
