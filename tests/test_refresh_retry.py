"""The refresh pass a deploy killed is replaced at boot (tracking/refresh_retry).

2026-09-20: a merge to master stopped the worker six minutes into the 18:17 UTC
hourly pass ("Stopping Container", 18:23:03) and the next pass was an hour
away. Seven passes in two days ended that way and MLB props had no rows until
19:23 UTC on a slate that started at 17:11.

Each `run` case below is a SKIP without the module, so these fail on a
scheduler that leaves the killed pass to the next cron.
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from tracking.refresh_retry import (
    RefreshRun, decide_refresh_retry, interrupted, load_recent_refreshes,
)

REPO = Path(__file__).resolve().parent.parent
UTC = timezone.utc
# 18:24 UTC: the boot after #796's deploy killed the 18:17 pass.
NOW = datetime(2026, 9, 20, 18, 24, tzinfo=UTC)


def _run(kind="hourly", started=NOW - timedelta(minutes=7), finished=None,
         steps_total=None, failed=None):
    return RefreshRun(kind, started, finished, steps_total, failed)


def _done(started):
    return _run(started=started, finished=started + timedelta(minutes=12),
                steps_total=36)


def _decide(runs, now=NOW, **kw):
    return decide_refresh_retry(now=now, runs=runs, enabled=True, **kw)


def test_the_pass_the_deploy_killed_is_replaced():
    d = _decide([_done(NOW - timedelta(minutes=67)), _run()])
    assert d.action == "run" and "18:17 UTC hourly pass was interrupted" in d.reason


def test_a_row_the_next_start_run_already_closed_as_aborted_is_the_same_orphan():
    closed = _run(finished=NOW - timedelta(minutes=1), failed="aborted")
    assert interrupted(closed)
    assert _decide([closed]).action == "run"


def test_a_pass_that_finished_with_failed_steps_ran_its_chain():
    ran = _run(finished=NOW - timedelta(minutes=1), steps_total=36,
               failed="health-check")
    assert not interrupted(ran)
    assert _decide([ran]).action == "skip"


def test_a_redeploy_between_passes_replaces_nothing():
    assert _decide([_done(NOW - timedelta(minutes=7))]).action == "skip"
    assert _decide([]).action == "skip"


def test_an_orphan_older_than_the_hour_is_the_crons_business():
    old = _run(started=NOW - timedelta(minutes=95))
    assert _decide([old]).action == "skip"


def test_the_cron_is_about_to_run_the_same_pass():
    # 19:09 UTC: the 18:17 pass died, and 19:17 is eight minutes away.
    now = datetime(2026, 9, 20, 19, 9, tzinfo=UTC)
    d = _decide([_run(started=now - timedelta(minutes=52))], now=now)
    assert d.action == "skip" and "8 minute(s) away" in d.reason


def test_an_evening_pass_is_never_replaced():
    d = _decide([_run(kind="evening", started=NOW - timedelta(minutes=3))])
    assert d.action == "skip" and "ten minutes" in d.reason


def test_a_restart_loop_does_not_buy_odds_on_every_boot():
    # Four merges in half an hour, 2026-09-20 18:20-18:51 UTC.
    runs = [_run(started=NOW - timedelta(minutes=m)) for m in (40, 25, 7)]
    d = _decide(runs)
    assert d.action == "skip" and "not buying odds again" in d.reason
    assert _decide(runs[1:]).action == "run"          # two is inside the cap


def test_the_kill_switch_and_the_in_process_guard():
    assert decide_refresh_retry(now=NOW, runs=[_run()], enabled=False).action == "skip"
    assert _decide([_run()], in_process_running=True).action == "skip"


def test_the_ledger_is_read_as_stored_and_an_unreadable_one_is_none():
    conn = sqlite3.connect(":memory:")
    assert load_recent_refreshes(conn, NOW) is None       # no table: never start blind
    conn.execute("CREATE TABLE pipeline_runs (run_kind TEXT, started_at TEXT, "
                 "finished_at TEXT, steps_total INTEGER, failed_steps TEXT)")
    conn.executemany("INSERT INTO pipeline_runs VALUES (?,?,?,?,?)", [
        ("daily",  "2026-09-20T18:00:00+00:00", None, None, None),
        ("hourly", "2026-09-20T16:17:00.428436+00:00", None, None, None),
        ("hourly", "2026-09-20T17:17:00.460341+00:00",
         "2026-09-20T18:17:00.398838+00:00", None, "aborted"),
        ("hourly", "2026-09-20T18:17:00.430037+00:00", None, None, None),
    ])
    runs = load_recent_refreshes(conn, NOW)
    assert [r.started_at.hour for r in runs] == [18]      # the hour's window only
    assert _decide(runs).action == "run"


def test_the_scheduler_runs_one_pass_at_a_time_and_asks_at_boot():
    """Source tripwire: the catch-up is a boot JOB (a call in main() would hold
    the live loops behind a 12-minute pass), and the cron and the catch-up
    share a lock so neither buys odds while the other is running."""
    src = (REPO / "scheduler.py").read_text(encoding="utf-8")
    body = src.split("def run_refresh_pass(")[1].split("\ndef ")[0]
    assert "_REFRESH_LOCK.acquire(blocking=False)" in body
    main = src.split("def main(")[1]
    assert "catch_up_refresh_pass" in main and '"date"' in main
    catch_up = src.split("def catch_up_refresh_pass(")[1].split("\ndef ")[0]
    assert "decide_refresh_retry" in catch_up and "run_refresh_pass()" in catch_up


# ── a step that swallowed its own failures ───────────────────────────────────

def test_a_failed_view_migration_fails_the_step(monkeypatch):
    """Found the same day: two view migrations raised on every pass in every
    log still held (from 2026-09-19 12:17 UTC; the cause dates from 09-12),
    the runner logged them and carried on, and the step reported
    "31/33 applied" as a success -- so the ledger, the failure alerter and the
    pipeline watch all saw a clean pass."""
    import data.view_migrations as vm
    import run_pipeline
    total = len(vm.ACTIVE_MIGRATIONS)
    monkeypatch.setattr(vm, "apply_view_migrations", lambda: total - 2)
    assert run_pipeline.step_apply_view_migrations("2026-09-21") is False
    monkeypatch.setattr(vm, "apply_view_migrations", lambda: total)
    assert run_pipeline.step_apply_view_migrations("2026-09-21") is True
