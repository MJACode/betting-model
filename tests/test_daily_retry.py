"""Same-day retry of the 6am daily after a mid-run worker restart.

WHY THIS EXISTS
---------------
2026-09-18: daily run_id `b65a709cdf734a15bdf7a5d3c8cf7983` started 6:00am ET,
PR #699 merged ~6:07am ET, Railway replaced the worker mid-run. APScheduler
registered `daily_pipeline` next for tomorrow 6:00am. pipeline_watch reported
the abort and did not re-queue. mlb_bullpen_workload / mlb_team_stats went
STALE — they are written only by the once-daily run.

These tests pin the four guards the catch-up must not get wrong:
  aborted today → retry
  successful today → no retry
  in-progress in this process → no second start
  already retried today → no third start
"""

from __future__ import annotations

import inspect
import importlib
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tracking.daily_retry import (
    MAX_DAILY_STARTS_PER_ET_DAY,
    DailyRun,
    decide_daily_retry,
    load_today_dailies,
)

ROOT = Path(__file__).parent.parent
ET = ZoneInfo("America/New_York")

# The incident window. Boot catch-up at 6:07am ET; pipeline_watch at 7:15am ET.
INCIDENT_DAY = datetime(2026, 9, 18, 6, 7, tzinfo=ET)
WATCH_TIME = datetime(2026, 9, 18, 7, 15, tzinfo=ET)
BEFORE_SIX = datetime(2026, 9, 18, 5, 55, tzinfo=ET)
SIX_AM = datetime(2026, 9, 18, 6, 0, tzinfo=ET)


def _run(*, started=SIX_AM, finished=None, ok=None, failed=None) -> DailyRun:
    return DailyRun(
        started_at=started, finished_at=finished, ok=ok, failed_steps=failed,
    )


def _aborted() -> DailyRun:
    """The 2026-09-18 ledger after the 7:17 hourly closed the orphan."""
    return _run(
        started=SIX_AM,
        finished=datetime(2026, 9, 18, 7, 17, tzinfo=ET),
        ok=False,
        failed="aborted",
    )


def _ok() -> DailyRun:
    return _run(
        started=SIX_AM,
        finished=datetime(2026, 9, 18, 6, 22, tzinfo=ET),
        ok=True,
        failed=None,
    )


# ── the four guards ──────────────────────────────────────────────────────────

def test_an_aborted_daily_today_is_retried():
    d = decide_daily_retry(now=INCIDENT_DAY, runs=[_aborted()])
    assert d.action == "run"
    assert "aborted" in d.reason


def test_a_successful_daily_today_is_not_retried():
    d = decide_daily_retry(now=INCIDENT_DAY, runs=[_ok()])
    assert d.action == "skip"
    assert "already completed" in d.reason


def test_an_in_progress_daily_does_not_start_a_second():
    """The 6am cron (or a boot retry already in flight) holds _DAILY_LOCK.
    pipeline_watch at 7:15 must not shell out a second run_pipeline.py."""
    unfinished = _run(started=SIX_AM, finished=None)
    d = decide_daily_retry(
        now=WATCH_TIME, runs=[unfinished], in_process_running=True,
    )
    assert d.action == "skip"
    assert "already running" in d.reason


def test_already_retried_today_does_not_start_a_third():
    """Cap is 2: the scheduled 6am start + one automatic retry. A crash-loop
    after the retry must not keep launching full dailies."""
    assert MAX_DAILY_STARTS_PER_ET_DAY == 2
    first = _aborted()
    retry = _run(
        started=datetime(2026, 9, 18, 6, 8, tzinfo=ET),
        finished=datetime(2026, 9, 18, 6, 10, tzinfo=ET),
        ok=False,
        failed="aborted",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[first, retry])
    assert d.action == "skip"
    assert "cap" in d.reason
    assert "third" in d.reason


# ── the 2026-09-18 boot shape: unfinished, process already gone ──────────────

def test_an_orphaned_unfinished_daily_is_retried_on_boot():
    """At 6:07am the new container sees finished_at NULL. That is NOT
    in-progress — Railway replaced the process. Skipping it would recreate
    the incident: wait until tomorrow."""
    orphan = _run(started=SIX_AM, finished=None)
    d = decide_daily_retry(
        now=INCIDENT_DAY, runs=[orphan], in_process_running=False,
    )
    assert d.action == "run"
    assert "unfinished" in d.reason


def test_a_missing_daily_after_6am_is_started():
    """Worker was down across 6:00am. Next cron is tomorrow; start now."""
    d = decide_daily_retry(now=WATCH_TIME, runs=[])
    assert d.action == "run"
    assert "no daily run ledgered" in d.reason


def test_a_missing_daily_before_6am_waits_for_the_cron():
    d = decide_daily_retry(now=BEFORE_SIX, runs=[])
    assert d.action == "skip"
    assert "before today's 6:00am" in d.reason


def test_yesterday_aborted_does_not_trigger_a_retry_before_6am():
    yesterday = _run(
        started=datetime(2026, 9, 17, 6, 0, tzinfo=ET),
        finished=datetime(2026, 9, 17, 6, 7, tzinfo=ET),
        ok=False,
        failed="aborted",
    )
    d = decide_daily_retry(now=BEFORE_SIX, runs=[yesterday])
    assert d.action == "skip"


def test_health_check_only_failure_does_not_re_run_the_daily():
    """MLB freshness steps already wrote. Re-running burns Odds API credits
    and is not the 2026-09-18 gap."""
    run = _run(
        started=SIX_AM,
        finished=datetime(2026, 9, 18, 6, 25, tzinfo=ET),
        ok=False,
        failed="health_check",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[run])
    assert d.action == "skip"
    assert "already completed" in d.reason


def test_a_failed_mlb_stats_step_is_retried():
    run = _run(
        started=SIX_AM,
        finished=datetime(2026, 9, 18, 6, 25, tzinfo=ET),
        ok=False,
        failed="mlb_stats,bullpen,health_check",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[run])
    assert d.action == "run"


def test_kill_switch_skips_even_when_aborted():
    d = decide_daily_retry(now=INCIDENT_DAY, runs=[_aborted()], enabled=False)
    assert d.action == "skip"
    assert "disabled" in d.reason


# ── loader ───────────────────────────────────────────────────────────────────

class _Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows=None, raises=False):
        self.rows = rows or []
        self.raises = raises
        self.rolled_back = 0
        self.closed = False

    def execute(self, sql, params=None):
        if self.raises:
            raise RuntimeError('relation "pipeline_runs" does not exist')
        assert "run_kind = 'daily'" in sql or "run_kind = ?" in sql
        return _Cursor(self.rows)

    def rollback(self):
        self.rolled_back += 1

    def close(self):
        self.closed = True


def test_loader_keeps_only_todays_et_dailies():
    today = SIX_AM.astimezone(timezone.utc).isoformat()
    yesterday = datetime(2026, 9, 17, 6, 0, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    conn = _Conn(rows=[
        (yesterday, yesterday, False, "aborted"),
        (today, None, None, None),
    ])
    got = load_today_dailies(conn, INCIDENT_DAY)
    assert len(got) == 1
    assert got[0].finished_at is None


def test_a_failed_ledger_query_rolls_back_and_does_not_start_blind():
    """A missing table is not 'no daily today'. Starting a full pipeline
    because we cannot read the ledger is the expensive default."""
    conn = _Conn(raises=True)
    assert load_today_dailies(conn, INCIDENT_DAY) is None
    assert conn.rolled_back >= 1
    # decide() on [] after 6am WOULD run — that is the missing-daily path.
    # catch_up must not substitute [] for None; the wiring test below pins it.
    d = decide_daily_retry(now=INCIDENT_DAY, runs=[])
    assert d.action == "run"


# ── scheduler wiring ─────────────────────────────────────────────────────────

@pytest.fixture()
def sched(monkeypatch):
    import scheduler
    importlib.reload(scheduler)
    return scheduler


class _FrozenDatetime(datetime):
    _frozen = INCIDENT_DAY

    @classmethod
    def now(cls, tz=None):
        return cls._frozen.astimezone(tz) if tz else cls._frozen.replace(tzinfo=None)


@pytest.fixture()
def wired(sched, monkeypatch):
    import data.db

    fired: list[dict] = []
    monkeypatch.setattr(sched, "datetime", _FrozenDatetime)
    monkeypatch.setattr(
        sched, "run_daily_pipeline",
        lambda **kw: fired.append(kw),
    )
    monkeypatch.setattr(sched, "owns", lambda job_id: True)

    def _run(conn, **kw):
        monkeypatch.setattr(data.db, "get_connection", lambda *a, **k: conn)
        fired.clear()
        for name, value in kw.items():
            monkeypatch.setattr(sched, name, value)
        return sched.catch_up_daily_pipeline(source="test"), fired

    return _run


def _aborted_row():
    started = SIX_AM.astimezone(timezone.utc).isoformat()
    finished = datetime(2026, 9, 18, 7, 17, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    return (started, finished, False, "aborted")


def _ok_row():
    started = SIX_AM.astimezone(timezone.utc).isoformat()
    finished = datetime(2026, 9, 18, 6, 22, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    return (started, finished, True, None)


def test_catch_up_runs_the_daily_when_today_aborted(wired):
    result, fired = wired(_Conn(rows=[_aborted_row()]))
    assert result["status"] == "run"
    assert len(fired) == 1
    assert "aborted" in fired[0]["retry_reason"]
    assert fired[0]["retry_source"] == "test"


def test_catch_up_does_not_run_when_today_succeeded(wired):
    result, fired = wired(_Conn(rows=[_ok_row()]))
    assert result["status"] == "skipped"
    assert fired == []


def test_catch_up_does_not_run_a_third_start(wired):
    first = _aborted_row()
    retry_started = datetime(2026, 9, 18, 6, 8, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    retry_finished = datetime(2026, 9, 18, 6, 10, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    second = (retry_started, retry_finished, False, "aborted")
    result, fired = wired(_Conn(rows=[first, second]))
    assert result["status"] == "skipped"
    assert fired == []
    assert "cap" in result["reason"]


def test_catch_up_is_a_no_op_when_this_process_already_holds_the_lock(
        wired, sched):
    assert sched._DAILY_LOCK.acquire(blocking=False)
    try:
        result, fired = wired(_Conn(rows=[_aborted_row()]))
    finally:
        sched._DAILY_LOCK.release()
    assert result["status"] == "skipped"
    assert fired == []
    assert "already running" in result["reason"]


def test_catch_up_does_not_start_blind_when_the_ledger_is_unreadable(wired):
    result, fired = wired(_Conn(raises=True))
    assert result["status"] == "skipped"
    assert result["reason"] == "ledger unreadable"
    assert fired == []


def test_catch_up_is_scoped_to_the_pipeline_service(wired):
    result, fired = wired(
        _Conn(rows=[_aborted_row()]),
        owns=lambda job_id: job_id != "daily_pipeline",
    )
    assert result["status"] == "skipped"
    assert fired == []
    assert result["reason"] == "not this service"


def test_run_daily_pipeline_lock_skips_a_second_in_process_start(
        sched, monkeypatch):
    """Behavioral, not a source grep: holding the lock must mean _run is
    never called. A comment that says 'lock' is not a lock."""
    ran = []
    monkeypatch.setattr(sched, "_run", lambda *a, **k: ran.append("ran"))
    assert sched._DAILY_LOCK.acquire(blocking=False)
    try:
        sched.run_daily_pipeline()
    finally:
        sched._DAILY_LOCK.release()
    assert ran == []


def test_boot_calls_the_daily_catch_up():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    main = src[src.index("def main"):]
    assert "catch_up_daily_pipeline(source=\"boot\")" in main, (
        "a CronTrigger whose 6am fire has passed does not misfire on a "
        "fresh scheduler — boot is the 2026-09-18 hole"
    )
    assert main.index("catch_up_weekly_jobs()") < main.index(
        "catch_up_daily_pipeline")


def test_pipeline_watch_requeues_after_it_reports():
    """2026-09-18: watch reported aborted/failed and did not re-queue.
    The retry is AFTER the watch's own try so a watch crash still retries,
    and so a 20-minute daily does not delay the morning Discord post."""
    import scheduler
    src = inspect.getsource(scheduler.run_pipeline_watch)
    assert "catch_up_daily_pipeline(source=\"pipeline_watch\")" in src
    assert src.index('log.exception("ERROR pipeline-watch crashed")') < src.index(
        "catch_up_daily_pipeline")


def test_the_contract_names_the_daily_catch_up():
    text = (ROOT / "docs" / "agents_contract.md").read_text(encoding="utf-8")
    block = text[text.index("### Catch-up on boot"):]
    assert "daily" in block.lower()
    assert "catch_up_daily_pipeline" in block


def test_kill_switch_is_honoured_from_the_env(monkeypatch, wired):
    monkeypatch.setenv("RUN_DAILY_RETRY", "0")
    result, fired = wired(_Conn(rows=[_aborted_row()]))
    assert result["status"] == "skipped"
    assert fired == []
    assert "disabled" in result["reason"]
