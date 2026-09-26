"""A contended scored-pick refresh must finish, and must not poison the pool.

Evening pipeline_run ce9699a2719847338d7328398098421a, pipeline_log 99603
(2026-09-26 00:26:48Z):

    dispatch:refresh-outcomes  error  121.237s
    step returned False — ✗ Scored-pick outcomes refresh failed:
    canceling statement due to statement timeout

Postgres logged the statement at 00:24:46.914Z and cancelled it at
00:26:46.914Z — the database statement_timeout of 120000 ms, to the
millisecond. log_lock_waits was on and no lock-wait line was logged.
pg_stat_statements (stats_reset 2026-04-04) has 978 completed runs of
the same REFRESH, mean 5602.5 ms, max 57715.8 ms. The plan is a seq
scan of picks plus index lookups; the unique index is valid.

The longer cap has to be a session GUC on a session-mode connection.
REFRESH CONCURRENTLY cannot run inside a transaction, so SET LOCAL
cannot cover it, and SET on the transaction pooler sticks to the
backend that happened to draw it.
"""

from __future__ import annotations

import inspect

import psycopg2

import run_pipeline as rp


_ABORTED = (
    "current transaction is aborted, commands ignored until end of "
    "transaction block"
)
_TIMEOUT = "canceling statement due to statement timeout"


class _Raw:
    def __init__(self):
        self.autocommit = False


class _Conn:
    """Postgres-shaped: a failed statement aborts the transaction until
    rollback(). Records autocommit at each execute."""

    def __init__(self, *, timeouts=0, other_error=None):
        self._conn = _Raw()
        self.timeouts_left = timeouts
        self.other_error = other_error
        self.aborted = False
        self.sql: list[str] = []
        self.events: list[tuple] = []
        self.rollbacks = 0
        self.closed = False

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if self.aborted:
            self.events.append(("poisoned", text[:80]))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.sql.append(text)
        self.events.append(("exec", text, self._conn.autocommit))
        if text.startswith("REFRESH MATERIALIZED VIEW"):
            if self.other_error is not None:
                self.aborted = True
                raise self.other_error
            if self.timeouts_left > 0:
                self.timeouts_left -= 1
                self.aborted = True
                raise psycopg2.errors.QueryCanceled(_TIMEOUT)
        return self

    def rollback(self):
        self.rollbacks += 1
        self.aborted = False
        self.events.append(("rollback",))

    def close(self):
        self.closed = True


def _factory(conn):
    def factory(*_args, **kwargs):
        conn.opened_with = kwargs
        return conn
    return factory


def _refreshes(conn):
    return [s for s in conn.sql if s.startswith("REFRESH MATERIALIZED VIEW")]


def test_timeout_constant_is_above_the_database_default_and_bounded():
    """120000 is the configuration-file statement_timeout measured
    2026-09-26. The cap is this connection's, and it stays a cap."""
    assert rp._OUTCOMES_REFRESH_TIMEOUT_MS > 120_000
    assert rp._OUTCOMES_REFRESH_TIMEOUT_MS == 300_000
    assert rp._OUTCOMES_REFRESH_ATTEMPTS == 2
    assert "CONCURRENTLY" in rp._OUTCOMES_REFRESH_SQL


def test_the_step_uses_a_session_connection_not_the_process_timeout():
    src = inspect.getsource(rp.step_refresh_outcomes)
    assert "get_connection(session_mode=True)" in src
    assert "DB_STATEMENT_TIMEOUT_MS" not in src
    ready = inspect.getsource(rp._ready_outcomes_session)
    assert "SET LOCAL" not in ready.split('"""', 2)[-1]


def test_a_statement_timeout_is_retried_after_rollback(monkeypatch):
    conn = _Conn(timeouts=1)
    monkeypatch.setattr("data.db.get_connection", _factory(conn))

    assert rp.step_refresh_outcomes("2026-09-25") is True

    assert conn.opened_with == {"session_mode": True}
    assert conn.closed
    refreshes = _refreshes(conn)
    assert refreshes == [rp._OUTCOMES_REFRESH_SQL, rp._OUTCOMES_REFRESH_SQL]
    assert conn.sql.count(rp._OUTCOMES_ANALYZE_SQL) == 1
    assert conn.sql[-1] == "RESET statement_timeout"
    sets = [s for s in conn.sql if s.startswith("SET ")]
    assert sets == [
        "SET statement_timeout = 300000",
        "SET statement_timeout = 300000",
    ]
    assert all("SET LOCAL" not in s for s in conn.sql)
    refresh_events = [e for e in conn.events if e[0] == "exec" and e[1].startswith("REFRESH")]
    assert all(e[2] is True for e in refresh_events)
    # The second REFRESH must follow a rollback. Without it the fake
    # raises InFailedSqlTransaction and the step returns False.
    first = next(i for i, e in enumerate(conn.events)
                 if e[0] == "exec" and e[1].startswith("REFRESH"))
    second = next(i for i, e in enumerate(conn.events)
                  if i > first and e[0] == "exec" and e[1].startswith("REFRESH"))
    assert any(e[0] == "rollback" for e in conn.events[first:second])
    assert not any(e[0] == "poisoned" for e in conn.events)


def test_a_non_timeout_is_not_retried(monkeypatch):
    conn = _Conn(other_error=psycopg2.Error("relation does not exist"))
    monkeypatch.setattr("data.db.get_connection", _factory(conn))

    assert rp.step_refresh_outcomes("2026-09-25") is False

    assert len(_refreshes(conn)) == 1
    assert rp._OUTCOMES_ANALYZE_SQL not in conn.sql
    assert conn.closed
    assert conn.sql[-1] == "RESET statement_timeout"


def test_two_timeouts_return_false_and_still_close(monkeypatch):
    conn = _Conn(timeouts=5)
    monkeypatch.setattr("data.db.get_connection", _factory(conn))

    assert rp.step_refresh_outcomes("2026-09-25") is False

    assert len(_refreshes(conn)) == 2
    assert rp._OUTCOMES_ANALYZE_SQL not in conn.sql
    assert conn.closed
    assert conn.rollbacks >= 1
    assert conn.sql[-1] == "RESET statement_timeout"
