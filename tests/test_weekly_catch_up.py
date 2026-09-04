"""
A weekly cron has a one-week worst-case first run, and the boot catch-up must
cover EVERY weekly job -- not just the one it was written for.

WHY THIS EXISTS
---------------
Measured 2026-09-01. `catch_up_weekly_jobs()` was added on 2026-08-31 because
the Savant refresh landed hours after its own Monday trigger, which would have
fed a four-month-old snapshot into every prop score for another week.

ModelCalibration was added THE SAME DAY, at 18:06 ET, with a Monday 8:30am ET
trigger -- nine and a half hours after that Monday's 8:30. The catch-up written
for exactly this failure did not cover it, because it was a Savant check rather
than a catch-up. The result was measurable: `model_calibration_sweeps` did not
exist in production at all, and the first sweep of every registered model would
not have run until 2026-09-07.

`docs/agents_contract.md` meanwhile described the catch-up in the general form
-- "runs a weekly job immediately at startup if its data is already stale" --
which was true of one job and read as true of all of them. A contract that
overstates its own coverage is how the gap stayed invisible for a week.
"""

from __future__ import annotations

import importlib
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent


@pytest.fixture()
def sched(monkeypatch):
    import scheduler
    importlib.reload(scheduler)
    return scheduler


class _Cursor:
    def __init__(self, row):
        self._row = row

    def fetchone(self):
        return self._row


class _Conn:
    """Answers the two freshness probes and nothing else."""

    def __init__(self, savant_row=("2099-01-01", 2), calib_row=None,
                 calib_raises=False):
        self.savant_row = savant_row
        self.calib_row = calib_row
        self.calib_raises = calib_raises
        self.closed = False
        self.rolled_back = 0

    def execute(self, sql, params=None):
        if "player_savant_stats" in sql:
            return _Cursor(self.savant_row)
        if "model_calibration_sweeps" in sql:
            if self.calib_raises:
                # what psycopg raises for a table that has never been created
                raise RuntimeError('relation "model_calibration_sweeps" does not exist')
            return _Cursor(self.calib_row)
        return _Cursor(None)

    def commit(self):
        pass

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed = True


@pytest.fixture()
def wired(sched, monkeypatch):
    """Runs the catch-up against a fake DB, recording which jobs it fired."""
    import data.db
    import data.db_setup

    monkeypatch.setattr(data.db_setup, "_run_migrations", lambda conn: None)

    fired: list[str] = []
    monkeypatch.setattr(sched, "run_savant_refresh", lambda: fired.append("savant"))
    monkeypatch.setattr(sched, "run_model_calibration", lambda: fired.append("calibration"))

    def _run(conn, **kw):
        monkeypatch.setattr(data.db, "get_connection", lambda *a, **k: conn)
        fired.clear()
        for name, value in kw.items():
            monkeypatch.setattr(sched, name, value)
        sched.catch_up_weekly_jobs()
        return fired

    return _run


# ── ModelCalibration is covered ──────────────────────────────────────────────

def test_a_missing_sweeps_table_counts_as_stale(wired):
    """The loudest possible stale: the agent has never completed a single run.

    This is the exact production state on 2026-09-01 -- `to_regclass` returned
    NULL -- so a catch-up that treats a failed probe as "fresh" would have done
    nothing on precisely the boot that needed it.
    """
    assert "calibration" in wired(_Conn(calib_raises=True))


def test_an_old_sweep_triggers_the_catch_up(wired):
    stale = (date.today() - timedelta(days=30)).isoformat()
    assert "calibration" in wired(_Conn(calib_row=(stale,)))


def test_a_recent_sweep_does_not(wired):
    """The freshness guard is what stops five deploys in an hour re-sweeping
    five times -- and today's five deploys were not hypothetical."""
    assert "calibration" not in wired(_Conn(calib_row=(date.today().isoformat(),)))


def test_a_failed_probe_rolls_back_so_it_does_not_poison_the_connection(wired, sched):
    """psycopg aborts the whole transaction on a missing relation. Without the
    rollback the probe would leave the connection unusable for anything after
    it -- which is the shape of a catch-up that half-runs.

    Both probes, not just the calibration one: the Savant probe runs FIRST, so
    a rollback missing there breaks the probe that follows it.
    """
    conn = _Conn(calib_raises=True)
    wired(conn)
    assert conn.rolled_back >= 1

    class _Boom:
        def __init__(self):
            self.rolled_back = 0

        def execute(self, *a, **k):
            raise RuntimeError("column as_of_date does not exist")

        def rollback(self):
            self.rolled_back += 1

    boom = _Boom()
    sched._savant_is_stale(boom, 2026)
    assert boom.rolled_back >= 1, (
        "the Savant probe runs first — a poisoned transaction here takes the "
        "calibration probe down with it")


# ── the two jobs are independent ─────────────────────────────────────────────

def test_a_fresh_savant_does_not_suppress_the_calibration_catch_up(wired):
    fired = wired(_Conn(savant_row=(date.today().isoformat(), 2),
                        calib_raises=True))
    assert fired == ["calibration"]


def test_a_failing_savant_refresh_does_not_cost_the_calibration_its_catch_up(wired):
    """One weekly job's catch-up failing must not silently cancel the rest."""
    def _boom():
        raise RuntimeError("savant CSV 503")

    fired = wired(_Conn(savant_row=(None, 0), calib_raises=True),
                  run_savant_refresh=_boom)
    assert "calibration" in fired


def test_ownership_is_checked_per_job(wired, sched):
    """Gating the whole catch-up on one job's ownership is what made this a
    Savant check rather than a catch-up."""
    fired = wired(_Conn(savant_row=(None, 0), calib_raises=True),
                  owns=lambda job_id: job_id == "model_calibration")
    assert fired == ["calibration"]


def test_the_call_site_does_not_gate_every_weekly_job_on_savant():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert 'if owns("savant_refresh"):\n        catch_up_weekly_jobs()' not in src, (
        "the catch-up is gated on Savant ownership again — a role that does "
        "not own Savant would skip every other weekly catch-up too")
    assert "catch_up_weekly_jobs()" in src


def test_model_calibration_belongs_to_the_pipeline_service(sched):
    """Two services sweeping the same board would write the same rows twice and
    post the summary twice."""
    assert "model_calibration" in sched._PIPELINE_JOBS


# ── the contract says what is actually true ──────────────────────────────────

def test_the_contract_names_both_weekly_jobs_the_catch_up_covers():
    text = (ROOT / "docs" / "agents_contract.md").read_text(encoding="utf-8")
    block = text[text.index("### Catch-up on boot"):]
    assert "Savant" in block
    assert "ModelCalibration" in block, (
        "the contract described the catch-up in the general form while it "
        "covered exactly one job — which is how the gap stayed invisible")


def test_the_catch_up_creates_the_review_tables_on_boot():
    """
    models/scorer.py reads `model_auto_pauses` on EVERY scoring run, but the
    only thing that created it was a 7:45am cron whose DDL was never committed
    (see tracking/threshold_review.ensure_schema). Boot is the moment that
    reliably follows a deploy, and it is where the column migrations already
    run for the same stated reason: a schema change with no path into
    production is not a schema change.

    Matches the IMPORT rather than the bare identifier — `ensure_schema` also
    appears in the surrounding comment, and a test that matches a name
    appearing in a comment passes with the call deleted. That exact weakness
    was found in this file's own `_run_migrations` test.
    """
    import io
    from pathlib import Path
    src = io.open(Path(__file__).parent.parent / "scheduler.py",
                  encoding="utf-8").read()
    block = src[src.index("def catch_up_weekly_jobs"):]
    block = block[:block.index("\ndef ")]
    assert "from tracking.threshold_review import ensure_schema" in block
    assert "ensure_schema(conn)" in block


def test_the_review_schema_is_not_gated_by_owns():
    """
    auto_paused() is consulted by the scorer wherever it runs, not only on the
    service that owns the review, so gating the table's creation on
    owns("threshold_review") would leave the other service reading a table that
    does not exist there.
    """
    import io
    from pathlib import Path
    src = io.open(Path(__file__).parent.parent / "scheduler.py",
                  encoding="utf-8").read()
    block = src[src.index("def catch_up_weekly_jobs"):]
    block = block[:block.index("\ndef ")]
    before = block[:block.index("ensure_schema(conn)")]
    assert 'owns("threshold_review")' not in before, (
        "the review schema must be created regardless of service role")
