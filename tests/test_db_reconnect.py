"""
The connection wrapper survives a dropped server connection (2026-09-08).

On 2026-09-08 01:30:57Z the pooler dropped every client at once. The worker's
scoring pass and a local dry run both died with "server closed the connection
unexpectedly"; every later statement on the same object failed with
"connection already closed"; and the pass's failure row was never written
because the handler that writes it used the dead connection. mike: "why do
you just stop work when database drops connection, globally we need to add
auto retry to pick up where we left off."

The rule these pin:
  * a lost connection with NO uncommitted writes is invisible — the wrapper
    reconnects and re-runs the one statement;
  * a lost connection WITH uncommitted writes raises ConnectionLost (the
    wrapper has reconnected; the caller re-runs its unit of work);
  * a statement_timeout (SQLSTATE 57014) is NOT a lost connection and is
    never retried — a re-issued 120s DELETE is the wrong reflex;
  * rollback() on a dead connection reconnects and does not raise, which is
    what lets an error handler write its record;
  * a wrapper with no url (tests, hand-built) cannot reconnect and re-raises.

Watched failing on the pre-fix wrapper: every case below raised the bare
InterfaceError / OperationalError straight through.
"""
from __future__ import annotations

import sys
from pathlib import Path

import psycopg2
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import data.db as db  # noqa: E402


class _Cursor:
    def __init__(self, conn):
        self._c = conn
        self.rows = [("ok",)]

    def execute(self, sql, params=None):
        self._c.executed.append(sql)
        if self._c.fail_next:
            exc = self._c.fail_next
            self._c.fail_next = None
            if isinstance(exc, (psycopg2.InterfaceError,)) or getattr(exc, "kills", False):
                self._c.closed = 2
            raise exc

    def fetchone(self):
        return self.rows[0]

    def fetchall(self):
        return list(self.rows)

    def close(self):
        pass


class _Conn:
    """A stand-in for psycopg2's connection: records statements, can be told
    to fail the next statement, and reports `closed` like the real thing."""

    def __init__(self, name="c0"):
        self.name = name
        self.closed = 0
        self.executed: list[str] = []
        self.fail_next = None
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        if self.closed:
            raise psycopg2.InterfaceError("connection already closed")
        return _Cursor(self)

    def commit(self):
        if self.closed:
            raise psycopg2.InterfaceError("connection already closed")
        self.commits += 1

    def rollback(self):
        if self.closed:
            raise psycopg2.InterfaceError("connection already closed")
        self.rollbacks += 1

    def close(self):
        self.closed = 1


def _lost():
    exc = psycopg2.OperationalError(
        "server closed the connection unexpectedly\n\tThis probably means "
        "the server terminated abnormally")
    exc.kills = True
    return exc


def _timeout():
    exc = psycopg2.errors.QueryCanceled("canceling statement due to statement timeout")
    return exc


@pytest.fixture
def wrapper(monkeypatch):
    opened: list[_Conn] = []

    def fake_open(url, options=None):
        c = _Conn(f"c{len(opened) + 1}")
        opened.append(c)
        return c

    monkeypatch.setattr(db, "_open", fake_open)
    monkeypatch.setattr(db.time, "sleep", lambda s: None)
    first = _Conn("c0")
    w = db.DBConnection(first, url="postgresql://x")
    return w, first, opened


def test_a_read_on_a_lost_connection_reconnects_and_retries(wrapper):
    w, first, opened = wrapper
    first.fail_next = _lost()
    row = w.execute("SELECT 1").fetchone()
    assert row == ("ok",)
    assert len(opened) == 1, "exactly one reconnect"
    assert opened[0].executed == ["SELECT 1"], "the statement was re-run on the new connection"
    assert w._conn is opened[0]


def test_a_lost_connection_with_uncommitted_writes_raises_connection_lost(wrapper):
    w, first, opened = wrapper
    w.execute("INSERT INTO t VALUES (1)")           # dirty
    first.fail_next = _lost()
    with pytest.raises(db.ConnectionLost):
        w.execute("INSERT INTO t VALUES (2)")
    assert len(opened) == 1, "it still reconnected, so the object is usable"
    assert w._conn is opened[0]
    assert opened[0].executed == [], "nothing was silently replayed"
    assert w._dirty is False, "the lost transaction is gone; the new one is clean"


def test_a_committed_transaction_is_clean_again(wrapper):
    w, first, opened = wrapper
    w.execute("INSERT INTO t VALUES (1)")
    w.commit()
    first.fail_next = _lost()
    w.execute("SELECT 1")                            # retried, not raised
    assert len(opened) == 1


def test_commit_on_a_dead_connection_raises_when_writes_were_pending(wrapper):
    w, first, opened = wrapper
    w.execute("INSERT INTO t VALUES (1)")
    first.closed = 2
    with pytest.raises(db.ConnectionLost):
        w.commit()
    assert len(opened) == 1


def test_rollback_on_a_dead_connection_reconnects_and_does_not_raise(wrapper):
    w, first, opened = wrapper
    w.execute("INSERT INTO t VALUES (1)")
    first.closed = 2
    w.rollback()                                     # no raise
    assert len(opened) == 1 and w._conn is opened[0]
    # ...and the handler can now write its record on the same object.
    w.execute("INSERT INTO pipeline_log VALUES ('error')")
    w.commit()
    assert opened[0].commits == 1


def test_a_statement_timeout_is_not_a_lost_connection(wrapper):
    w, first, opened = wrapper
    first.fail_next = _timeout()
    with pytest.raises(psycopg2.errors.QueryCanceled):
        w.execute("DELETE FROM picks WHERE 1=1")
    assert opened == [], "a timed-out statement must never be re-issued on a fresh connection"
    assert w._conn is first


def test_a_wrapper_without_a_url_cannot_reconnect_and_re_raises(monkeypatch):
    first = _Conn()
    w = db.DBConnection(first)                       # url=None, the test/hand-built shape
    first.fail_next = _lost()
    with pytest.raises(psycopg2.OperationalError) as ei:
        w.execute("SELECT 1")
    assert not isinstance(ei.value, db.ConnectionLost)


def test_connection_lost_classification():
    assert db.connection_lost(psycopg2.InterfaceError("connection already closed"))
    assert db.connection_lost(_lost())
    assert not db.connection_lost(_timeout())
    # pgcode is read-only on psycopg2 exceptions, so the driver's own classes
    # stand in for the SQLSTATEs: 57P01 admin_shutdown, 08006 connection_failure,
    # 57014 query_canceled.
    assert db.connection_lost(psycopg2.errors.AdminShutdown("x"))
    assert db.connection_lost(psycopg2.errors.ConnectionFailure("x"))
    assert not db.connection_lost(psycopg2.errors.QueryCanceled("x"))
    assert not db.connection_lost(psycopg2.OperationalError("some other operational error"))
    assert not db.connection_lost(ValueError("nope"))


def test_write_classification_is_conservative():
    assert not db._is_write("SELECT 1")
    assert not db._is_write("  select 1")
    assert not db._is_write("WITH a AS (SELECT 1) SELECT * FROM a")
    assert db._is_write("WITH a AS (SELECT 1) INSERT INTO t SELECT * FROM a")
    assert db._is_write("DELETE FROM picks")
    assert db._is_write("SET LOCAL lock_timeout = '10s'")
    assert db._is_write("do $$ begin end $$")


def test_the_factory_hands_the_wrapper_its_url(monkeypatch):
    seen = {}

    def fake_open(url, options=None):
        seen["url"] = url
        return _Conn()

    monkeypatch.setattr(db, "_open", fake_open)
    w = db._connect("postgresql://u:p@h:6543/d")
    assert w._url == "postgresql://u:p@h:6543/d" == seen["url"]
