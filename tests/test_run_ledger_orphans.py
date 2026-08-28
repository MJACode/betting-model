"""start_run closes orphaned runs left by a killed worker.

Regression for a false CRIT observed live on 2026-08-27: two deploys replaced
the container mid-pass, each leaving a pipeline_runs row with finished_at NULL,
and refresh_pass_completion then reported "2 run(s) started >2h ago and never
finished - a pass is hanging" indefinitely. Every deploy added another.
"""
import sqlite3
import pytest


class _Conn:
    """Minimal DBConnection stand-in: ? params, rowcount, commit/close."""

    def __init__(self, db, fail_on_cleanup=False):
        self._db = db
        self._fail = fail_on_cleanup

    def execute(self, sql, params=None):
        if self._fail and "UPDATE pipeline_runs" in sql and "aborted" in sql:
            raise RuntimeError("simulated cleanup failure")
        return self._db.execute(sql, params or ())

    def commit(self):
        self._db.commit()

    def close(self):
        pass


SCHEMA = """
CREATE TABLE pipeline_runs (
  run_id TEXT PRIMARY KEY, run_kind TEXT, started_at TEXT, finished_at TEXT,
  steps_total INTEGER, steps_failed INTEGER, failed_steps TEXT, ok BOOLEAN)
"""


@pytest.fixture
def db():
    d = sqlite3.connect(":memory:")
    d.execute(SCHEMA)
    d.commit()
    return d


def _ledger(monkeypatch, conn):
    from tracking import run_ledger
    monkeypatch.setattr(run_ledger, "get_connection", lambda: conn)
    monkeypatch.setattr(run_ledger, "_ensure_table", lambda c: None)
    return run_ledger


def _open_rows(db):
    return db.execute(
        "SELECT COUNT(*) FROM pipeline_runs WHERE finished_at IS NULL").fetchone()[0]


def test_orphans_are_closed_and_labelled(db, monkeypatch):
    for rid, t in (("o1", "2026-08-27T22:50:00+00:00"),
                   ("o2", "2026-08-27T23:00:00+00:00")):
        db.execute("INSERT INTO pipeline_runs (run_id, run_kind, started_at) "
                   "VALUES (?,?,?)", (rid, "evening", t))
    db.commit()
    assert _open_rows(db) == 2

    rl = _ledger(monkeypatch, _Conn(db))
    new_id = rl.start_run("evening")

    for rid in ("o1", "o2"):
        fin, ok, failed = db.execute(
            "SELECT finished_at, ok, failed_steps FROM pipeline_runs WHERE run_id=?",
            (rid,)).fetchone()
        assert fin is not None
        assert not ok
        assert failed == "aborted"

    # only the run just started is left open
    assert _open_rows(db) == 1
    assert db.execute("SELECT finished_at FROM pipeline_runs WHERE run_id=?",
                      (new_id,)).fetchone()[0] is None


def test_finished_runs_are_never_touched(db, monkeypatch):
    db.execute("INSERT INTO pipeline_runs (run_id, run_kind, started_at, finished_at,"
               " ok, failed_steps) VALUES ('done','evening','2026-08-27T22:40:00+00:00',"
               "'2026-08-27T22:44:00+00:00', 0, 'health-check')")
    db.commit()
    _ledger(monkeypatch, _Conn(db)).start_run("evening")
    fin, failed = db.execute(
        "SELECT finished_at, failed_steps FROM pipeline_runs WHERE run_id='done'").fetchone()
    assert fin == "2026-08-27T22:44:00+00:00"
    assert failed == "health-check"      # its real failure survives


def test_a_genuine_current_hang_is_still_detectable(db, monkeypatch):
    """The point of the check must survive the fix. After cleanup the only row
    that can be open is the pass running right now — which is exactly the case
    refresh_pass_completion's 2h 'stuck' branch exists to catch."""
    rl = _ledger(monkeypatch, _Conn(db))
    rl.start_run("evening")
    stuck = db.execute(
        "SELECT COUNT(*) FROM pipeline_runs WHERE finished_at IS NULL AND started_at < ?",
        ("2999-01-01T00:00:00+00:00",)).fetchone()[0]
    assert stuck == 1


def test_aborted_runs_stay_countable(db, monkeypatch):
    """Aborted is recorded, not erased — a worker dying mid-pass repeatedly is
    still visible, just no longer indistinguishable from a live hang."""
    rl = _ledger(monkeypatch, _Conn(db))
    for _ in range(3):
        rl.start_run("evening")
    assert db.execute(
        "SELECT COUNT(*) FROM pipeline_runs WHERE failed_steps='aborted'").fetchone()[0] == 2
    assert _open_rows(db) == 1


def test_cleanup_failure_cannot_break_the_pass(db, monkeypatch):
    """Observability must never break the thing it observes."""
    rl = _ledger(monkeypatch, _Conn(db, fail_on_cleanup=True))
    run_id = rl.start_run("evening")
    assert run_id
    assert db.execute("SELECT COUNT(*) FROM pipeline_runs WHERE run_id=?",
                      (run_id,)).fetchone()[0] == 1
