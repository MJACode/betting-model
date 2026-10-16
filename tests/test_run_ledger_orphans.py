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


def _row(db, run_id):
    return db.execute(
        "SELECT finished_at, ok, failed_steps FROM pipeline_runs WHERE run_id=?",
        (run_id,)).fetchone()


def _insert_open(db, run_id, kind, started):
    db.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at) VALUES (?,?,?)",
        (run_id, kind, started))


def test_hourly_start_leaves_a_deploy_killed_evening_open(db, monkeypatch):
    """2026-10-16. Evening 06b9db72 stayed unfinished after the deploy because
    later hourlies only abort hourly rows. This is the hole the boot sweep
    closes; start_run must keep the same-kind scope."""
    _insert_open(db, "06b9db72a43c4323ad5ed84abf00b591", "evening",
                 "2026-10-16T03:50:00.440389+00:00")
    db.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at, finished_at, ok) "
        "VALUES ('hourly-ok','hourly','2026-10-16T11:17:00+00:00',"
        "'2026-10-16T11:29:00+00:00', 1)")
    db.commit()

    rl = _ledger(monkeypatch, _Conn(db))
    new_id = rl.start_run("hourly")

    fin, ok, failed = _row(db, "06b9db72a43c4323ad5ed84abf00b591")
    assert fin is None and ok is None and failed is None
    hourly_fin, hourly_ok, hourly_failed = _row(db, "hourly-ok")
    assert hourly_fin == "2026-10-16T11:29:00+00:00"
    assert hourly_ok == 1 and hourly_failed is None
    assert _row(db, new_id)[0] is None


def test_boot_sweep_closes_the_evening_and_leaves_daily_and_finished_hourly(db, monkeypatch):
    _insert_open(db, "06b9db72a43c4323ad5ed84abf00b591", "evening",
                 "2026-10-16T03:50:00.440389+00:00")
    _insert_open(db, "daily-open", "daily", "2026-10-16T10:00:00+00:00")
    _insert_open(db, "manual-open", "manual", "2026-10-16T10:05:00+00:00")
    db.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at, finished_at, ok) "
        "VALUES ('hourly-ok','hourly','2026-10-16T11:17:00+00:00',"
        "'2026-10-16T11:29:00+00:00', 1)")
    db.commit()

    rl = _ledger(monkeypatch, _Conn(db))
    monkeypatch.setattr(rl, "_BOOT_CUTOFF", None)
    n = rl.abort_prior_refresh_orphans(_Conn(db), started_before="2026-10-16T11:40:00+00:00")
    assert n == 1

    fin, ok, failed = _row(db, "06b9db72a43c4323ad5ed84abf00b591")
    assert fin is not None and not ok and failed == "aborted"
    assert _row(db, "daily-open")[0] is None
    assert _row(db, "manual-open")[0] is None
    hourly_fin, hourly_ok, hourly_failed = _row(db, "hourly-ok")
    assert hourly_fin == "2026-10-16T11:29:00+00:00"
    assert hourly_ok == 1 and hourly_failed is None


def test_a_second_sweep_does_not_abort_the_pass_this_process_started(db, monkeypatch):
    """The cutoff freezes on the first call. start_run of the same kind, then
    a second sweep, must leave the new row open and must not restamp the
    row the first sweep already closed."""
    _insert_open(db, "evening-old", "evening", "2026-10-16T03:50:00.440389+00:00")
    db.commit()
    rl = _ledger(monkeypatch, _Conn(db))
    monkeypatch.setattr(rl, "_BOOT_CUTOFF", None)

    assert rl.abort_prior_refresh_orphans(_Conn(db)) == 1
    first_finish = _row(db, "evening-old")[0]
    assert first_finish is not None

    new_id = rl.start_run("evening")
    assert rl.abort_prior_refresh_orphans(_Conn(db)) == 0

    assert _row(db, "evening-old")[0] == first_finish
    fin, ok, failed = _row(db, new_id)
    assert fin is None and failed is None


def test_an_empty_cutoff_aborts_nothing(db, monkeypatch):
    _insert_open(db, "evening-old", "evening", "2026-10-16T03:50:00+00:00")
    db.commit()
    rl = _ledger(monkeypatch, _Conn(db))
    assert rl.abort_prior_refresh_orphans(_Conn(db), started_before="") == 0
    assert _row(db, "evening-old")[0] is None


def test_sweep_failure_cannot_raise(db, monkeypatch):
    rl = _ledger(monkeypatch, _Conn(db, fail_on_cleanup=True))
    assert rl.abort_prior_refresh_orphans(
        _Conn(db, fail_on_cleanup=True),
        started_before="2099-01-01T00:00:00+00:00") == 0


def test_refresh_kinds_match_the_catch_up_and_exclude_daily():
    from tracking.refresh_retry import REFRESH_KINDS
    from tracking.run_ledger import REFRESH_RUN_KINDS
    assert set(REFRESH_RUN_KINDS) == set(REFRESH_KINDS)
    assert "daily" not in REFRESH_RUN_KINDS
    assert "manual" not in REFRESH_RUN_KINDS


def test_the_scheduler_sweeps_before_it_can_start_a_pass():
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "scheduler.py").read_text(encoding="utf-8")
    main = src.split("def main(")[1]
    call = main.index("\n    abort_orphaned_refresh_runs()\n")
    assert call < main.index("\n        sched.start()\n")
    assert call < main.index("\n        catch_up_refresh_pass,\n")
    body = src.split("def abort_orphaned_refresh_runs(")[1].split("\ndef ")[0]
    assert body.index('owns("hourly_refresh")') < body.index("get_connection")


def test_pipeline_boot_closes_the_evening_and_poller_boot_does_not(db, monkeypatch):
    import scheduler
    from tracking import run_ledger

    _insert_open(db, "06b9db72a43c4323ad5ed84abf00b591", "evening",
                 "2026-10-16T03:50:00.440389+00:00")
    _insert_open(db, "daily-open", "daily", "2026-10-16T10:00:00+00:00")
    _insert_open(db, "hourly-live", "hourly", "2999-01-01T00:00:00+00:00")
    db.commit()

    monkeypatch.setattr(run_ledger, "_BOOT_CUTOFF", None)
    monkeypatch.setattr(run_ledger, "_ensure_table", lambda c: None)
    monkeypatch.setattr(run_ledger, "get_connection", lambda: _Conn(db))
    import data.db as dbmod
    monkeypatch.setattr(dbmod, "get_connection", lambda: _Conn(db))

    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "poller")
    assert scheduler.abort_orphaned_refresh_runs() == 0
    assert _row(db, "06b9db72a43c4323ad5ed84abf00b591")[0] is None

    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "pipeline")
    assert scheduler.abort_orphaned_refresh_runs() == 1
    fin, ok, failed = _row(db, "06b9db72a43c4323ad5ed84abf00b591")
    assert fin is not None and not ok and failed == "aborted"
    assert _row(db, "daily-open")[0] is None
    # Started after the frozen cutoff: a pass this process opened.
    assert _row(db, "hourly-live")[0] is None

    new_id = run_ledger.start_run("evening")
    assert scheduler.abort_orphaned_refresh_runs() == 0
    assert _row(db, new_id)[0] is None
    assert _row(db, "hourly-live")[0] is None


def test_the_zombie_migration_is_one_idempotent_statement():
    from data.view_migrations import ACTIVE_MIGRATIONS, MIGRATIONS_DIR
    name = "abort_deploy_killed_evening_2026_10_16.sql"
    assert name in ACTIVE_MIGRATIONS
    text = (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
    code = "\n".join(ln.split("--", 1)[0] for ln in text.splitlines()).strip()
    assert code.startswith("DO $mig$")
    assert code.endswith("END $mig$;")
    assert code.count("DO $mig$") == 1
    update = code.split("UPDATE pipeline_runs", 1)[1]
    assert "run_id = '06b9db72a43c4323ad5ed84abf00b591'" in update
    assert "run_kind = 'evening'" in update
    assert "finished_at IS NULL" in update
    assert "failed_steps = 'aborted'" in update
    assert "ok = FALSE" in update


def test_hourly_start_does_not_abort_an_open_daily(db, monkeypatch):
    """Kind-scoped orphans. 2026-09-18: the 7:17 hourly closed the still-open
    daily as aborted. That is the right label when the daily process is
    already dead, and the wrong one when a same-day daily retry is still
    running — max_instances=1 is per job, not across daily and hourly."""
    db.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at) "
        "VALUES ('daily-open','daily','2026-09-18T10:00:00+00:00')")
    db.commit()
    _ledger(monkeypatch, _Conn(db)).start_run("hourly")
    fin, failed = db.execute(
        "SELECT finished_at, failed_steps FROM pipeline_runs "
        "WHERE run_id='daily-open'").fetchone()
    assert fin is None, "hourly must not abort a still-open daily"
    assert failed is None
