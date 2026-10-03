"""Settle's CLV date scan must not die on the 120s statement timeout.

pipeline_log 119709 (2026-10-03 18:12:46Z), run
dcbf2c7e352443e1bba4ff9b7c6722ce. `dispatch:settle` failed with
`Settlement failed: canceling statement due to statement timeout`.

Postgres cancelled pid 3837081 (sqlstate 57014) on:

    SELECT DISTINCT p.game_date
    FROM picks p
    JOIN games g ON g.game_id = p.game_id
    WHERE p.signal_type = 'BET'
      AND ... clv_captured_at / clv_method ...
    ORDER BY p.game_date
    LIMIT 40

That plan is an index scan of idx_picks_date with the CLV predicates as a
Filter. 22 dates pass the commence_time join, so LIMIT 40 never stops the
scan. The fix is a game_date window (an Index Cond) plus one retry after
ROLLBACK TO SAVEPOINT. The database statement_timeout is not raised.
"""

from __future__ import annotations

import ast
from pathlib import Path

import psycopg2

from tracking import paper_tracker as pt

_TIMEOUT = "canceling statement due to statement timeout"
_ABORTED = (
    "current transaction is aborted, commands ignored until end of "
    "transaction block"
)
_SRC = Path(__file__).parent.parent / "tracking" / "paper_tracker.py"


def _fn(name: str) -> str:
    text = _SRC.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == name)
    return "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])


class _Conn:
    """A failed statement aborts the transaction until ROLLBACK TO SAVEPOINT."""

    def __init__(self, span, windows, timeouts=None, errors=None):
        self.span = span
        self.windows = windows
        self.timeouts_left = dict(timeouts or {})
        self.errors = dict(errors or {})
        self.aborted = False
        self.events: list[tuple] = []
        self.selects: list[str] = []
        self._rows = []

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if self.aborted and not text.startswith("ROLLBACK TO SAVEPOINT"):
            self.events.append(("poisoned", text[:80]))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        if text.startswith("SAVEPOINT"):
            self.events.append(("savepoint",))
            return self
        if text.startswith("RELEASE SAVEPOINT"):
            self.events.append(("release",))
            return self
        if text.startswith("ROLLBACK TO SAVEPOINT"):
            self.aborted = False
            self.events.append(("rollback_to",))
            return self
        if text.startswith("ROLLBACK"):
            self.aborted = False
            self.events.append(("rollback",))
            return self
        self.events.append(("exec", text[:48]))
        if "MIN(game_date)" in text:
            self._rows = [self.span]
            return self
        if "p.game_date >=" in text:
            lo = params[0]
            self.selects.append(lo)
            left = self.timeouts_left.get(lo, 0)
            if left:
                self.timeouts_left[lo] = left - 1
                self.aborted = True
                raise psycopg2.errors.QueryCanceled(_TIMEOUT)
            if lo in self.errors:
                self.aborted = True
                raise psycopg2.errors.SyntaxError(self.errors[lo])
            remaining = params[3]
            self._rows = [(d,) for d in self.windows.get(lo, [])[:remaining]]
            return self
        self._rows = [(1,)]
        return self

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def rollback(self):
        self.aborted = False
        self.events.append(("rollback",))


def _sql() -> str:
    return _fn("_backfill_clv").split("sql = ", 1)[1].split('"""', 2)[1]


def test_the_date_scan_is_bounded_on_game_date():
    """The cancelled statement had no game_date predicate. Each window does."""
    src = _fn("_backfill_clv")
    assert "p.game_date >= %s" in src
    assert "p.game_date < %s" in src
    assert "ORDER BY p.game_date" in src
    assert "LIMIT %s" in src
    assert "statement_timeout" not in src
    assert "session_mode" not in src
    assert "DB_STATEMENT_TIMEOUT_MS" not in _fn("_clv_backfill_dates")
    assert "ROLLBACK TO SAVEPOINT" in _fn("_rollback_clv_savepoint")
    assert "retrying once" in _fn("_clv_attempt")


def test_a_timeout_is_rolled_back_and_retried_once():
    conn = _Conn(
        span=("2026-08-01", "2026-08-01"),
        windows={"2026-08-01": ["2026-08-03"]},
        timeouts={"2026-08-01": 1},
    )
    dates = pt._clv_backfill_dates(conn, _sql())
    assert dates == ["2026-08-03"]
    assert conn.selects == ["2026-08-01", "2026-08-01"]
    assert ("rollback_to",) in conn.events
    assert not any(kind == "poisoned" for kind, *_ in conn.events)
    # The connection still accepts a statement. That is the grading query
    # that used to die with InFailedSqlTransaction.
    conn.execute("SELECT 1")


def test_a_second_timeout_does_not_abort_the_next_statement():
    conn = _Conn(
        span=("2026-08-01", "2026-08-20"),
        windows={
            "2026-08-01": ["2026-08-01"],
            "2026-08-08": ["2026-08-09"],
        },
        timeouts={"2026-08-01": 2},
    )
    dates = pt._clv_backfill_dates(conn, _sql())
    assert dates == []
    # The failed window is not skipped. A later window must not run in its
    # place, or the backfill would fill newer dates and leave the old one.
    assert conn.selects == ["2026-08-01", "2026-08-01"]
    conn.execute("SELECT 1")
    assert not any(kind == "poisoned" for kind, *_ in conn.events)


def test_a_non_timeout_is_not_retried():
    conn = _Conn(
        span=("2026-08-01", "2026-08-01"),
        windows={"2026-08-01": ["2026-08-01"]},
        errors={"2026-08-01": "syntax error at or near"},
    )
    assert pt._clv_backfill_dates(conn, _sql()) == []
    assert conn.selects == ["2026-08-01"]
    conn.execute("SELECT 1")


def test_windows_walk_oldest_first_and_stop_at_the_cap(monkeypatch):
    monkeypatch.setattr(pt, "_CLV_BACKFILL_DATES_PER_RUN", 3)
    monkeypatch.setattr(pt, "_CLV_BACKFILL_WINDOW_DAYS", 7)
    conn = _Conn(
        span=("2026-08-01", "2026-08-20"),
        windows={
            "2026-08-01": ["2026-08-02", "2026-08-04"],
            "2026-08-08": ["2026-08-08", "2026-08-10"],
            "2026-08-15": ["2026-08-16"],
        },
    )
    dates = pt._clv_backfill_dates(conn, _sql())
    assert dates == ["2026-08-02", "2026-08-04", "2026-08-08"]
    assert conn.selects == ["2026-08-01", "2026-08-08"]


def test_settle_still_returns_when_the_scan_times_out(monkeypatch):
    """The scan used to raise out of settle_picks. A double timeout is empty."""
    captured = []
    monkeypatch.setattr(
        pt, "_capture_clv",
        lambda conn, d, at: captured.append(d) or 1,
    )
    conn = _Conn(
        span=("2026-09-01", "2026-09-01"),
        windows={"2026-09-01": ["2026-09-01"]},
        timeouts={"2026-09-01": 2},
    )
    assert pt._backfill_clv(conn, "2026-10-03T14:12:00-04:00") == 0
    assert captured == []
    conn.execute("SELECT 1")


def test_one_date_timeout_does_not_drop_the_next_date(monkeypatch):
    calls = {"n": 0}

    def _capture(conn, d, at):
        calls["n"] += 1
        if d == "2026-08-02" and calls["n"] == 1:
            raise psycopg2.errors.QueryCanceled(_TIMEOUT)
        return 2

    monkeypatch.setattr(pt, "_capture_clv", _capture)
    conn = _Conn(
        span=("2026-08-01", "2026-08-03"),
        windows={"2026-08-01": ["2026-08-02", "2026-08-03"]},
    )
    filled = pt._backfill_clv(conn, "2026-10-03T14:12:00-04:00")
    assert filled == 4
    assert not any(kind == "poisoned" for kind, *_ in conn.events)


def test_query_canceled_with_sqlstate_is_a_timeout():
    """Both shapes count: the message the worker logs, and sqlstate 57014.

    A hand-built psycopg2 error leaves pgcode unset, so the sqlstate branch
    is a stand-in with that attribute. The message branch uses the real class.
    """
    by_message = psycopg2.errors.QueryCanceled(_TIMEOUT)
    assert pt._is_statement_timeout(by_message)

    class _Sqlstate:
        pgcode = "57014"

        def __str__(self):
            return "canceling statement"

    assert pt._is_statement_timeout(_Sqlstate())
    assert not pt._is_statement_timeout(psycopg2.errors.SyntaxError("nope"))
