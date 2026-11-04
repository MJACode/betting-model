"""Same-day retry of the 6am daily after a mid-run worker restart.

WHY THIS EXISTS
---------------
2026-09-18: daily run_id `b65a709cdf734a15bdf7a5d3c8cf7983` started 6:00am ET,
PR #699 merged ~6:07am ET, Railway replaced the worker mid-run. APScheduler
registered `daily_pipeline` next for tomorrow 6:00am. pipeline_watch reported
the abort and did not re-queue. mlb_bullpen_workload / mlb_team_stats went
STALE — they are written only by the once-daily run.

These tests pin the guards the catch-up must not get wrong:
  aborted today → retry, until 4 ledgered starts
  a finished non-aborted failure → one retry, then stop
  successful today → no retry
  in-progress in this process → no second start
"""

from __future__ import annotations

import inspect
import importlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tracking.daily_retry import (
    MAX_DAILY_RUN,
    MAX_DAILY_STARTS_PER_ET_DAY,
    MAX_NON_ABORTED_FAILURES,
    DailyRun,
    announce_daily_retry,
    assess_daily_completion,
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


def test_a_killed_retry_is_started_again():
    """2026-11-04. The 6:00am ET daily was aborted at 11:13Z, the catch-up
    started a second daily at that second, and later deploys killed the
    retry. Two dead starts are not a finished daily."""
    first = _run(
        started=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc),
        finished=datetime(2026, 11, 4, 11, 13, 34, tzinfo=timezone.utc),
        ok=False,
        failed="aborted",
    )
    orphan = _run(
        started=datetime(2026, 11, 4, 11, 13, 34, tzinfo=timezone.utc),
        finished=None,
    )
    now = datetime(2026, 11, 4, 12, 34, tzinfo=timezone.utc)
    d = decide_daily_retry(
        now=now, runs=[first, orphan], in_process_running=False,
    )
    assert d.action == "run"
    assert "unfinished" in d.reason


def test_two_aborted_dailies_with_no_success_are_retried():
    """The boot sweep stamps the open retry aborted before the decision.
    That must still relaunch: nothing today completed."""
    first = _aborted()
    retry = _run(
        started=datetime(2026, 9, 18, 6, 13, tzinfo=ET),
        finished=datetime(2026, 9, 18, 7, 2, tzinfo=ET),
        ok=False,
        failed="aborted",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[first, retry])
    assert d.action == "run"
    assert "aborted" in d.reason


def test_a_crash_loop_stops_at_the_ceiling():
    """The lock is the double-run guard. Aborted relaunches stop at 4.
    Three killed starts still relaunch — 2026-11-04 was two, and a busy
    merge morning killed the retry again. The fourth does not. 8 would
    buy odds on every boot of that morning."""
    assert MAX_DAILY_STARTS_PER_ET_DAY == 4

    def _killed(i: int) -> DailyRun:
        return _run(
            started=SIX_AM + timedelta(minutes=5 * i),
            finished=SIX_AM + timedelta(minutes=5 * i + 1),
            ok=False,
            failed="aborted",
        )

    under = [_killed(i) for i in range(MAX_DAILY_STARTS_PER_ET_DAY - 1)]
    d = decide_daily_retry(now=WATCH_TIME, runs=under)
    assert d.action == "run"
    assert "aborted" in d.reason

    full = [_killed(i) for i in range(MAX_DAILY_STARTS_PER_ET_DAY)]
    d = decide_daily_retry(now=WATCH_TIME, runs=full)
    assert d.action == "skip"
    assert "cap" in d.reason
    assert "another" in d.reason


def test_a_real_failure_is_retried_once_and_then_stops():
    """An upstream outage before MLB freshness is not a killed worker.
    The scheduled run plus one retry is the old cap. A third start would
    buy odds again on every boot and at 7:15. An aborted start between
    the two failures does not reset the count, and the stop is the
    one-retry cap, not the ceiling of 4."""
    assert MAX_NON_ABORTED_FAILURES == 2
    first = _run(
        started=SIX_AM,
        finished=datetime(2026, 9, 18, 6, 20, tzinfo=ET),
        ok=False,
        failed="mlb_stats,bullpen",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[first])
    assert d.action == "run"

    second = _run(
        started=datetime(2026, 9, 18, 6, 40, tzinfo=ET),
        finished=datetime(2026, 9, 18, 6, 55, tzinfo=ET),
        ok=False,
        failed="mlb_stats",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[first, second])
    assert d.action == "skip"
    assert "one retry" in d.reason
    assert len([first, second]) < MAX_DAILY_STARTS_PER_ET_DAY

    killed = _run(
        started=datetime(2026, 9, 18, 6, 25, tzinfo=ET),
        finished=datetime(2026, 9, 18, 6, 26, tzinfo=ET),
        ok=False,
        failed="aborted",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[first, killed, second])
    assert d.action == "skip"
    assert "one retry" in d.reason


def test_an_aborted_retry_after_a_real_failure_is_relaunched():
    """The one retry was killed before it could fail a step. That is
    aborted, which relaunches until the ceiling."""
    failed = _run(
        started=SIX_AM,
        finished=datetime(2026, 9, 18, 6, 20, tzinfo=ET),
        ok=False,
        failed="mlb_stats",
    )
    killed = _run(
        started=datetime(2026, 9, 18, 6, 25, tzinfo=ET),
        finished=datetime(2026, 9, 18, 6, 26, tzinfo=ET),
        ok=False,
        failed="aborted",
    )
    d = decide_daily_retry(now=WATCH_TIME, runs=[failed, killed])
    assert d.action == "run"
    assert "aborted" in d.reason


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
        self.rowcount = 0

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows=None, raises=False):
        self.rows = rows or []
        self.raises = raises
        self.rolled_back = 0
        self.closed = False
        self.commits = 0
        self.sqls: list[str] = []

    def execute(self, sql, params=None):
        self.sqls.append(sql)
        if self.raises and "SELECT" in sql.upper():
            raise RuntimeError('relation "pipeline_runs" does not exist')
        if "SELECT" in sql.upper():
            assert "run_kind = 'daily'" in sql or "run_kind = ?" in sql
        return _Cursor(self.rows)

    def commit(self):
        self.commits += 1

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
    assert fired[0]["retry_start_number"] == 2


def test_catch_up_does_not_run_when_today_succeeded(wired):
    result, fired = wired(_Conn(rows=[_ok_row()]))
    assert result["status"] == "skipped"
    assert fired == []


def test_catch_up_relaunches_when_both_starts_were_aborted(wired):
    """2026-11-04 after the boot sweep: the retry is aborted too, and
    nothing today completed. The old two-start cap skipped this."""
    first = _aborted_row()
    retry_started = datetime(2026, 9, 18, 6, 8, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    retry_finished = datetime(2026, 9, 18, 6, 10, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    second = (retry_started, retry_finished, False, "aborted")
    conn = _Conn(rows=[first, second])
    result, fired = wired(conn)
    assert result["status"] == "run"
    assert len(fired) == 1
    assert fired[0]["retry_start_number"] == 3
    assert any("UPDATE pipeline_runs" in sql for sql in conn.sqls)


def test_catch_up_relaunches_an_unfinished_retry(wired):
    """The open row itself, before the sweep's stamp is what the decision
    sees if the stamp failed. Still a run: this process is not in it."""
    first = _aborted_row()
    retry_started = datetime(2026, 9, 18, 6, 8, tzinfo=ET).astimezone(
        timezone.utc).isoformat()
    second = (retry_started, None, None, None)
    result, fired = wired(_Conn(rows=[first, second]))
    assert result["status"] == "run"
    assert len(fired) == 1
    assert fired[0]["retry_start_number"] == 3
    assert "unfinished" in fired[0]["retry_reason"]


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


def test_the_ops_note_names_which_start_this_is(monkeypatch):
    """A boot loop has to be visible in the channel before it hits the
    ceiling. The note says which start this attempt is."""
    captured: dict = {}

    def _capture(title, detail, *, recovery=False, post=None):
        captured["title"] = title
        captured["detail"] = detail
        captured["recovery"] = recovery
        return True

    monkeypatch.setattr("tracking.watch_util.post_ops_alert", _capture)
    assert announce_daily_retry(
        "today's daily is unfinished and this process is not running it",
        source="boot",
        start_number=3,
    )
    assert captured["recovery"] is True
    assert "**Start:** 3 of 4 today" in captured["detail"]
    assert "one retry" in captured["detail"]
    assert "boot" in captured["detail"]


def test_kill_switch_is_honoured_from_the_env(monkeypatch, wired):
    monkeypatch.setenv("RUN_DAILY_RETRY", "0")
    result, fired = wired(_Conn(rows=[_aborted_row()]))
    assert result["status"] == "skipped"
    assert fired == []
    assert "disabled" in result["reason"]


# ── health: the 2026-11-04 open daily ────────────────────────────────────────

def test_an_unfinished_daily_past_the_max_is_stale():
    """12:34Z on 2026-11-04. The retry had been open 81 minutes. Hourlies
    were finishing, so the 2h stuck check had not fired."""
    assert MAX_DAILY_RUN == timedelta(minutes=75)
    started = datetime(2026, 11, 4, 11, 13, 34, tzinfo=timezone.utc)
    # 12:34:34Z is 81 minutes after 11:13:34Z. At 12:34:00Z the age is 80.
    now = datetime(2026, 11, 4, 12, 34, 34, tzinfo=timezone.utc)
    status, detail = assess_daily_completion(
        now, [DailyRun(started_at=started, finished_at=None)],
    )
    assert status == "STALE"
    assert "never finished" in detail
    assert "81" in detail


def test_two_aborted_dailies_and_no_open_row_are_stale_after_the_deadline():
    now = datetime(2026, 11, 4, 12, 34, tzinfo=timezone.utc)
    runs = [
        DailyRun(
            started_at=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc),
            finished_at=datetime(2026, 11, 4, 11, 13, tzinfo=timezone.utc),
            ok=False, failed_steps="aborted",
        ),
        DailyRun(
            started_at=datetime(2026, 11, 4, 11, 13, tzinfo=timezone.utc),
            finished_at=datetime(2026, 11, 4, 12, 2, tzinfo=timezone.utc),
            ok=False, failed_steps="aborted",
        ),
    ]
    status, detail = assess_daily_completion(now, runs)
    assert status == "STALE"
    assert "no successful daily" in detail


def test_a_daily_still_inside_the_max_is_in_progress():
    started = datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc)
    now = datetime(2026, 11, 4, 11, 30, tzinfo=timezone.utc)
    status, detail = assess_daily_completion(
        now, [DailyRun(started_at=started, finished_at=None)],
    )
    assert status == "OK"
    assert "in progress" in detail


def test_no_daily_before_the_deadline_is_not_a_failure():
    now = datetime(2026, 11, 4, 11, 20, tzinfo=timezone.utc)
    status, _detail = assess_daily_completion(now, [])
    assert status == "SKIPPED"


def test_a_daily_that_finished_its_freshness_steps_is_ok():
    now = datetime(2026, 11, 4, 16, 0, tzinfo=timezone.utc)
    run = DailyRun(
        started_at=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc),
        finished_at=datetime(2026, 11, 4, 11, 40, tzinfo=timezone.utc),
        ok=False,
        failed_steps="health_check",
    )
    status, detail = assess_daily_completion(now, [run])
    assert status == "OK"
    assert "completed" in detail
