"""No test reaches a real database (#1396, #1455, #1456).

Two separate guards, both installed by tests/conftest.py:

1. Heartbeats write nothing. Building the scheduler registers every watched
   job, and each registration calls tracking/job_heartbeat.beat, which opens
   one database connection. Measured 2026-11-18 on mike's PC: about 32 per
   build. With the main checkout's .env each one wrote a heartbeat row to
   production. With no .env each one dialled localhost:5432 and took 4.1 s to
   be refused, so one scheduler-building test took about 130 s. conftest stubs
   `beat`; a test of the heartbeat itself opts out with
   `@pytest.mark.real_heartbeat`.

2. A database that is not on this machine is refused (tests/_db_guard.py).
   Anything a test does that dials psycopg2 at a host off this machine fails
   at once, without dialling, and the run's summary counts it. That covers the
   other callers #1396 found (the pick grader, the in-play push notifier, the
   scorer's paused-model check) and whatever comes next.

Every simulated remote host here ends in `.invalid`, a name that can never
resolve, so not even a broken guard can reach a real server from this file.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

FAR = "db.guard-test.invalid"


def _record_dials(monkeypatch) -> list:
    """Replace the dial underneath psycopg2.connect with a recorder.

    psycopg2.connect builds the DSN and then calls psycopg2._connect, the C
    function that opens the socket. A DSN that reaches the recorder is one the
    guard let through; one that never arrives was refused before any dial.
    """
    import psycopg2
    dials = []

    def _connect(dsn, connection_factory=None, **kwasync):
        dials.append(dsn)
        raise psycopg2.OperationalError("recorded by the test, not dialled")

    monkeypatch.setattr(psycopg2, "_connect", _connect)
    return dials


@pytest.fixture
def expected_refusals():
    """Drop the refusals a test here asks for, so the run's count is only of
    real ones."""
    from tests import _db_guard
    already = len(_db_guard.REFUSED)
    yield
    del _db_guard.REFUSED[already:]


# ── 1. Building the scheduler ─────────────────────────────────────────────────

def test_building_the_scheduler_opens_no_database_connection(monkeypatch):
    """The test that would have caught #1455 and #1456.

    Counted at psycopg2.connect, the lowest point every route goes through.
    The recorder raises at once, so if the stub is missing this fails in
    seconds rather than spending 4 s per connection. It asserts on the count:
    `beat` swallows every error, so waiting for a raise would pass with the
    bug still there. DATABASE_URL is set to a host that cannot resolve so
    get_connection gets as far as dialling instead of stopping at "not set".
    """
    import psycopg2
    import scheduler
    monkeypatch.setenv("DATABASE_URL", f"postgresql://u:p@{FAR}:6543/postgres")
    dials = []

    def connect(*args, **kwargs):
        dials.append(1)
        raise psycopg2.OperationalError("a test opened a database connection")

    monkeypatch.setattr(psycopg2, "connect", connect)
    sched = scheduler.build_scheduler()
    assert sched.get_jobs(), "the scheduler built no jobs, so this proves nothing"
    assert dials == [], (
        f"building the scheduler opened {len(dials)} database connection(s); "
        "tests/conftest.py stubs tracking.job_heartbeat.beat so it opens none")


def test_a_heartbeat_inside_a_test_writes_nothing(monkeypatch):
    from data import db
    from tracking import job_heartbeat
    opened = []
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: opened.append(1))
    job_heartbeat.beat("job_queue")
    job_heartbeat.seed("job_queue")
    job_heartbeat.mark_disabled("job_queue")
    assert opened == []


def test_the_stub_still_shows_the_real_source():
    """tests/test_nba_team_total_luck_window.py reads beat's source to check it
    opens a connection per tick. The stub is wrapped, so that still reads the
    real function."""
    import inspect
    from tracking import job_heartbeat
    assert "get_connection()" in inspect.getsource(job_heartbeat.beat)


def test_the_scorers_pause_check_opens_no_connection(monkeypatch):
    """models.scorer reads the leftover auto-pause list once per process. With
    no list cached, the first test in a run to score a pick opened a
    connection for it (#1396); conftest now holds the cache at empty."""
    import psycopg2
    import models.scorer as sc
    monkeypatch.setenv("DATABASE_URL", f"postgresql://u:p@{FAR}:6543/postgres")
    dials = []

    def connect(*args, **kwargs):
        dials.append(1)
        raise psycopg2.OperationalError("a test opened a database connection")

    monkeypatch.setattr(psycopg2, "connect", connect)
    assert sc._auto_paused_models() == set()
    assert dials == []


class _FakeConn:
    def __init__(self):
        self.sql, self.committed, self.closed = [], False, False

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


@pytest.mark.real_heartbeat
def test_a_test_of_the_heartbeat_itself_runs_the_real_code(monkeypatch):
    """The opt-out: a test marked real_heartbeat gets the real `beat`."""
    from data import db
    from tracking import job_heartbeat
    conn = _FakeConn()
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: conn)
    monkeypatch.setattr(job_heartbeat, "schema_is_current", lambda *a, **k: True)
    job_heartbeat.seed("job_queue")
    writes = [p for s, p in conn.sql if "INSERT INTO job_heartbeats" in s]
    assert len(writes) == 1
    assert writes[0][0] == "job_queue" and writes[0][2] == "registered"
    assert conn.committed and conn.closed


# ── 2. A database off this machine is refused ─────────────────────────────────

@pytest.mark.parametrize("args, kwargs", [
    ((f"postgresql://u:p@{FAR}:6543/postgres",), {}),
    ((f"host={FAR} port=6543 dbname=postgres user=u",), {}),
    # a keyword host overrides a local one in the DSN, as libpq does
    (("postgresql://u:p@localhost/db",), {"host": FAR}),
    ((), {"host": FAR, "dbname": "postgres"}),
    # one local host in a list does not make the others local
    ((f"postgresql://u:p@localhost,{FAR}/db",), {}),
    (("hostaddr=203.0.113.5 dbname=postgres",), {}),
    # a service file can point anywhere, so it is refused
    (("service=prod",), {}),
])
def test_a_database_off_this_machine_is_refused_without_dialling(
        monkeypatch, expected_refusals, args, kwargs):
    import psycopg2
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)
    dials = _record_dials(monkeypatch)
    with pytest.raises(psycopg2.OperationalError, match="not on this machine"):
        psycopg2.connect(*args, **kwargs)
    assert dials == [], "the guard let a dial through to a host off this machine"


def test_a_host_named_only_in_pghost_is_refused(monkeypatch, expected_refusals):
    """libpq reads PGHOST when the DSN names no host."""
    import psycopg2
    monkeypatch.setenv("PGHOST", FAR)
    dials = _record_dials(monkeypatch)
    with pytest.raises(psycopg2.OperationalError, match="not on this machine"):
        psycopg2.connect("dbname=postgres user=u")
    assert dials == []


@pytest.mark.parametrize("dsn", [
    "postgresql://user:pass@localhost/db",       # the 64 test files' default
    "host=127.0.0.1 port=5433 dbname=postgres user=postgres",  # tests/_pg.py
    "host=::1 port=5433 dbname=postgres",
    "postgresql:///db",                          # no host: the local socket
    "host=/tmp dbname=postgres",                 # a socket directory
])
def test_a_database_on_this_machine_still_gets_through(monkeypatch, dsn):
    """The scratch Postgres in tests/_pg.py listens on 127.0.0.1 and is named
    in libpq's key=value form. #1396's first guard did not read that form and
    blocked it, which errored 153 tests."""
    import psycopg2
    monkeypatch.delenv("PGHOST", raising=False)
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    dials = _record_dials(monkeypatch)
    with pytest.raises(psycopg2.OperationalError, match="recorded by the test"):
        psycopg2.connect(dsn)
    assert len(dials) == 1


def test_a_refusal_is_counted_for_the_run_summary(monkeypatch, expected_refusals):
    import psycopg2
    from tests import _db_guard
    _record_dials(monkeypatch)
    before = len(_db_guard.REFUSED)
    with pytest.raises(psycopg2.OperationalError):
        psycopg2.connect(f"postgresql://u:p@{FAR}/postgres")
    assert len(_db_guard.REFUSED) == before + 1
    test, hosts = _db_guard.REFUSED[-1]
    assert "test_a_refusal_is_counted_for_the_run_summary" in test
    assert hosts == [FAR]


def test_the_guard_is_installed_before_any_project_module_is_imported():
    """conftest imports monitoring.probe, which imports config and data.db.
    The guard has to be in place first, as the Odds API refusal is."""
    src = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    guard = src.index("_db_guard.install()")
    first_project_import = src.index("from monitoring import probe")
    assert guard < first_project_import
