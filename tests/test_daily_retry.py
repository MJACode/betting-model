"""Same-day retry of the 6am daily after a mid-run worker restart.

WHY THIS EXISTS
---------------
2026-09-18: daily run_id `b65a709cdf734a15bdf7a5d3c8cf7983` started 6:00am ET,
PR #699 merged ~6:07am ET, Railway replaced the worker mid-run. APScheduler
registered `daily_pipeline` next for tomorrow 6:00am. pipeline_watch reported
the abort and did not re-queue. mlb_bullpen_workload / mlb_team_stats went
STALE — they are written only by the once-daily run.

These tests pin the guards the catch-up must not get wrong:
  aborted today → retry; deploy-kills do not use the failure cap
  a deploy-kill loop stops at 12, and automatic catch-up stops at 22:00 ET
  a finished non-aborted failure → one retry, then stop
  successful today → no retry
  in-progress in this process → no second start
"""

from __future__ import annotations

import inspect
import importlib
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tracking.daily_retry import (
    DAILY_RETRY_CUTOFF_HOUR,
    MAX_DAILY_RUN,
    MAX_DEPLOY_KILLED_STARTS_PER_ET_DAY,
    MAX_NON_ABORTED_FAILURES,
    DailyRun,
    announce_daily_retry,
    assess_daily_completion,
    classify_relaunch,
    daily_pipeline_reclaim_decision,
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


def test_a_deploy_kill_loop_stops_at_the_bound():
    """The lock is the double-run guard. Deploy-kills do not use the
    one-retry failure cap. They stop at 12. 2026-11-04 was four aborted
    starts before 13:30Z; a cap of 4 then skipped the day. 12 covers that
    rate through the afternoon and stops a restart every few minutes."""
    assert MAX_DEPLOY_KILLED_STARTS_PER_ET_DAY == 12

    def _killed(i: int) -> DailyRun:
        return _run(
            started=SIX_AM + timedelta(minutes=i),
            finished=SIX_AM + timedelta(minutes=i, seconds=30),
            ok=False,
            failed="aborted",
        )

    under = [_killed(i) for i in range(MAX_DEPLOY_KILLED_STARTS_PER_ET_DAY - 1)]
    d = decide_daily_retry(now=WATCH_TIME, runs=under)
    assert d.action == "run"
    assert "aborted" in d.reason

    full = [_killed(i) for i in range(MAX_DEPLOY_KILLED_STARTS_PER_ET_DAY)]
    d = decide_daily_retry(now=WATCH_TIME, runs=full)
    assert d.action == "skip"
    assert "deploy-killed" in d.reason
    assert "not started again" in d.reason


def test_four_deploy_kills_on_2026_11_04_still_relaunch():
    """pipeline_runs for 2026-11-04, all run_kind=daily, all aborted.
    Read at 13:34Z: 3d3685c1, 8a44ef65, c1869c15, d5a27075. The cap of 4
    skipped the day. None of them finished a step."""
    specs = (
        ("2026-11-04T11:00:00+00:00", "2026-11-04T11:13:34+00:00"),
        ("2026-11-04T11:13:34+00:00", "2026-11-04T13:01:36+00:00"),
        ("2026-11-04T13:01:40+00:00", "2026-11-04T13:19:13+00:00"),
        ("2026-11-04T13:19:17+00:00", "2026-11-04T13:29:24+00:00"),
    )
    runs = [
        _run(
            started=datetime.fromisoformat(started),
            finished=datetime.fromisoformat(finished),
            ok=False,
            failed="aborted",
        )
        for started, finished in specs
    ]
    now = datetime(2026, 11, 4, 13, 34, tzinfo=timezone.utc)
    d = decide_daily_retry(now=now, runs=runs, in_process_running=False)
    assert d.action == "run"
    assert "aborted" in d.reason


def test_deploy_kills_do_not_relaunch_after_the_cutoff():
    """A restart loop must not run overnight. 22:00 ET still covers a
    fix that deploys in the evening of the killed day."""
    assert DAILY_RETRY_CUTOFF_HOUR == 22
    killed = _run(
        started=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc),
        finished=datetime(2026, 11, 4, 11, 13, tzinfo=timezone.utc),
        ok=False,
        failed="aborted",
    )
    before = datetime(2026, 11, 4, 21, 59, tzinfo=ET)
    after = datetime(2026, 11, 4, 22, 0, tzinfo=ET)
    assert decide_daily_retry(now=before, runs=[killed]).action == "run"
    d = decide_daily_retry(now=after, runs=[killed])
    assert d.action == "skip"
    assert "cutoff" in d.reason


def test_a_missing_daily_after_the_cutoff_waits_until_tomorrow():
    now = datetime(2026, 11, 4, 22, 5, tzinfo=ET)
    d = decide_daily_retry(now=now, runs=[])
    assert d.action == "skip"
    assert "cutoff" in d.reason


def test_a_real_failure_is_retried_once_and_then_stops():
    """An upstream outage before MLB freshness is not a killed worker.
    The scheduled run plus one retry is the failure cap. A third start
    would buy odds again on every boot and at 7:15. An aborted start
    between the two failures does not reset the count, and does not
    consume it. The stop is the one-retry cap, not the deploy-kill bound."""
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
    assert len([first, second]) < MAX_DEPLOY_KILLED_STARTS_PER_ET_DAY

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

    def fetchone(self):
        return self._rows[0] if self._rows else None


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
        head = sql.lstrip().upper()
        # The catch-up waits on the scoring lease before it reads the ledger.
        # That session lock is not the daily query.
        if "PG_ADVISORY" in head or head.startswith("SET ") or head.startswith("SELECT 1"):
            return _Cursor([(True,)])
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


def test_boot_schedules_the_daily_catch_up_without_blocking_the_scheduler():
    """2026-11-04 13:17Z. The hourly (8:17am ET) never ledgered. The last
    hourly was 12:17Z. The 13:01Z boot called the daily catch-up on the
    main thread before sched.start(), and the daily held that thread
    until the 13:19Z deploy. The :17 cron was not registered yet. The
    evening pass uses the same scheduler, so it was blocked the same way
    whenever a boot landed inside a daily. The catch-up is a one-off job."""
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    main = src[src.index("def main"):]
    assert "catch_up_daily_pipeline(source=\"boot\")" not in main
    assert 'id="daily_catch_up"' in main
    assert 'kwargs={"source": "boot"}' in main
    assert main.index("catch_up_weekly_jobs()") < main.index('id="daily_catch_up"')
    start = main.index("\n        sched.start()\n")
    assert main.index('id="daily_catch_up"') < start
    assert main.index('id="refresh_catch_up"') < start
    refresh = src[src.index("def run_refresh_pass"):src.index("def run_savant_refresh")]
    assert "_REFRESH_LOCK.acquire(blocking=False)" in refresh
    assert "_DAILY_LOCK" in refresh
    assert "waiting to score" in refresh


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


def test_the_ops_note_names_which_start_this_is_and_why(monkeypatch):
    """A boot loop has to be visible in the channel. The note says which
    start this attempt is, and whether it is a deploy-kill or a real
    failure. Deploy-kills are not the one-retry cap."""
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
        start_number=5,
        relaunch_kind="deploy-kill",
        deploy_kills=4,
        real_failures=0,
    )
    assert captured["recovery"] is True
    assert "**Start:** 5 today" in captured["detail"]
    assert "**Why:** deploy-kill." in captured["detail"]
    assert "unfinished" in captured["detail"]
    assert "one retry" in captured["detail"]
    assert "do not use the failure cap" in captured["detail"]
    assert "deploy-kills 4" in captured["detail"]
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


def test_catch_up_relaunches_four_deploy_kills(wired):
    """The 2026-11-04 ledger, on the wiring: four aborted rows, nothing
    completed, the next boot starts number 5 and says why."""
    rows = []
    for minute in (0, 8, 16, 24):
        started = (SIX_AM + timedelta(minutes=minute)).astimezone(
            timezone.utc).isoformat()
        finished = (SIX_AM + timedelta(minutes=minute + 2)).astimezone(
            timezone.utc).isoformat()
        rows.append((started, finished, False, "aborted"))
    result, fired = wired(_Conn(rows=rows))
    assert result["status"] == "run"
    assert len(fired) == 1
    assert fired[0]["retry_start_number"] == 5
    assert fired[0]["retry_kind"] == "deploy-kill"
    assert fired[0]["deploy_kills"] == 4
    assert fired[0]["real_failures"] == 0


def test_the_manual_job_runs_one_daily_and_skips_when_the_lock_is_held(
        sched, monkeypatch):
    """worker_jobs daily_pipeline is the kick when the catch-up has
    stopped. It runs run_pipeline.py once. The daily lock is the same
    object the cron holds, so a second start in this process does not
    happen. A skip is not a raised failure: the queue would retry it."""
    from tracking.job_queue import JOBS, _job_daily_pipeline, _validate_daily_pipeline

    assert "daily_pipeline" in JOBS
    assert JOBS["daily_pipeline"][0] is _job_daily_pipeline
    assert _validate_daily_pipeline({}) == {}
    with pytest.raises(ValueError, match="no arguments"):
        _validate_daily_pipeline({"stake": 5})
    declared = (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8")
    assert "daily_pipeline" not in declared

    ran = []
    announced = []
    monkeypatch.setattr(sched, "_run", lambda *a, **k: ran.append(a) or "ok")
    monkeypatch.setattr(sched, "_wait_for_nhl_window", lambda label: True)
    monkeypatch.setattr(
        "tracking.daily_retry.announce_daily_retry",
        lambda *a, **k: announced.append(k) or True,
    )
    started = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        "data.db.get_connection",
        lambda: _Conn(rows=[(started, started, False, "aborted")]),
    )

    out = _job_daily_pipeline()
    assert out["status"] == "ok"
    assert out["start_number"] == 2
    assert len(ran) == 1
    assert ran[0][0][-1] == "run_pipeline.py"
    assert announced[0]["relaunch_kind"] == "manual"
    assert announced[0]["start_number"] == 2
    assert announced[0]["deploy_kills"] == 1
    assert announced[0]["source"] == "worker_jobs"

    ran.clear()
    assert sched._DAILY_LOCK.acquire(blocking=False)
    try:
        skipped = _job_daily_pipeline()
    finally:
        sched._DAILY_LOCK.release()
    assert ran == []
    assert skipped["status"] == "skipped"
    assert "already running" in skipped["reason"]
    assert skipped["start_number"] == 2


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


# ── overlap: a relaunched daily and a refresh both write picks ───────────────

def _quiet_passes(sched, monkeypatch, *, daily_wait=3, refresh_wait=3):
    monkeypatch.setattr(sched, "_WRITER_POLL_S", 0.01)
    monkeypatch.setattr(sched, "_DAILY_WAIT_FOR_REFRESH_S", daily_wait)
    monkeypatch.setattr(sched, "_refresh_wait_for_daily_s", lambda: refresh_wait)
    monkeypatch.setattr(sched, "_wait_for_nhl_window", lambda label: True)
    monkeypatch.setattr(
        "tracking.daily_retry.announce_daily_retry", lambda *a, **k: True,
    )


def _sleep_until_wait(monkeypatch) -> threading.Event:
    """Set when the pass's wait loop actually sleeps, so the assertion
    cannot pass just because the thread has not started yet."""
    entered = threading.Event()
    original = time.sleep

    def spy(seconds):
        if seconds == 0.01:
            entered.set()
        original(seconds)

    monkeypatch.setattr(time, "sleep", spy)
    return entered


def test_refresh_does_not_score_while_the_daily_lock_is_held(sched, monkeypatch):
    """Boot refresh is +60s and the :17 cron keeps firing. Neither may
    enter refresh_pass.sh while the daily still holds its lock."""
    ran = []
    _quiet_passes(sched, monkeypatch)
    entered = _sleep_until_wait(monkeypatch)
    monkeypatch.setattr(sched, "_run", lambda *a, **k: ran.append(a) or "ok")
    assert sched._DAILY_LOCK.acquire(blocking=False)
    thread = threading.Thread(target=sched.run_refresh_pass)
    thread.start()
    try:
        assert entered.wait(2)
        assert ran == []
    finally:
        sched._DAILY_LOCK.release()
    thread.join(2)
    assert not thread.is_alive()
    assert len(ran) == 1
    assert ran[0][0][1] == "scripts/refresh_pass.sh"


def test_daily_does_not_score_while_a_refresh_holds_the_lock(sched, monkeypatch):
    """pipeline_watch at 7:15 starts a daily while the 7:17 hourly may
    already be inside the pass. The daily waits, then scores."""
    import sys
    ran = []
    _quiet_passes(sched, monkeypatch)
    entered = _sleep_until_wait(monkeypatch)
    monkeypatch.setattr(
        sched, "_run", lambda *a, **k: ran.append(a[0]) or "ok",
    )
    assert sched._REFRESH_LOCK.acquire(blocking=False)
    thread = threading.Thread(target=sched.run_daily_pipeline)
    thread.start()
    try:
        assert entered.wait(2)
        assert ran == []
    finally:
        sched._REFRESH_LOCK.release()
    thread.join(2)
    assert not thread.is_alive()
    assert ran == [[sys.executable, "run_pipeline.py"]]


def test_a_daily_and_a_refresh_do_not_score_at_the_same_time(sched, monkeypatch):
    """The post-deploy case: both passes are started together. Their
    subprocesses must not overlap. Concurrent look-ahead deletes empty a
    board; the unique index only drops a second insert."""
    _quiet_passes(sched, monkeypatch, daily_wait=5, refresh_wait=5)
    gate = threading.Lock()
    busy = {"daily": False, "refresh": False}
    overlap = []
    counts = {"daily": 0, "refresh": 0}

    def fake_run(cmd, label, **kw):
        kind = "daily" if label == "daily-pipeline" else "refresh"
        with gate:
            counts[kind] += 1
            other = "refresh" if kind == "daily" else "daily"
            if busy[other]:
                overlap.append(kind)
            busy[kind] = True
        time.sleep(0.12)
        with gate:
            busy[kind] = False
        return "ok"

    monkeypatch.setattr(sched, "_run", fake_run)
    daily = threading.Thread(
        target=lambda: sched.run_daily_pipeline(retry_reason="overlap"),
    )
    refresh = threading.Thread(target=sched.run_refresh_pass)
    daily.start()
    refresh.start()
    daily.join(5)
    refresh.join(5)
    assert not daily.is_alive()
    assert not refresh.is_alive()
    assert overlap == []
    assert counts == {"daily": 1, "refresh": 1}
    assert busy == {"daily": False, "refresh": False}


def test_a_second_refresh_skips_without_waiting_out_the_daily(sched, monkeypatch):
    """Waiting is for the daily. Another refresh in this process still
    returns immediately, which is what keeps two passes from buying odds."""
    _quiet_passes(sched, monkeypatch, refresh_wait=30)
    ran = []
    monkeypatch.setattr(sched, "_run", lambda *a, **k: ran.append("ran") or "ok")
    assert sched._REFRESH_LOCK.acquire(blocking=False)
    try:
        started = time.monotonic()
        sched.run_refresh_pass()
        assert time.monotonic() - started < 0.5
    finally:
        sched._REFRESH_LOCK.release()
    assert ran == []


def test_a_refresh_scores_if_the_daily_lock_never_clears(sched, monkeypatch):
    """A stuck daily must not silence every later hour. Past the wait the
    refresh scores anyway."""
    ran = []
    _quiet_passes(sched, monkeypatch, refresh_wait=0)
    monkeypatch.setattr(sched, "_run", lambda *a, **k: ran.append("ran") or "ok")
    assert sched._DAILY_LOCK.acquire(blocking=False)
    try:
        sched.run_refresh_pass()
    finally:
        sched._DAILY_LOCK.release()
    assert ran == ["ran"]


def test_classify_relaunch_uses_the_latest_start_not_list_order():
    """load_today_dailies orders by started_at. A caller that does not
    still classifies the latest row. runs[-1] would call this a deploy-kill."""
    early_kill = _run(
        started=SIX_AM,
        finished=datetime(2026, 9, 18, 6, 10, tzinfo=ET),
        ok=False, failed="aborted",
    )
    late_real = _run(
        started=datetime(2026, 9, 18, 8, 0, tzinfo=ET),
        finished=datetime(2026, 9, 18, 8, 20, tzinfo=ET),
        ok=False, failed="mlb_stats",
    )
    assert classify_relaunch([late_real, early_kill]) == "real-failure"
    assert classify_relaunch([early_kill, late_real]) == "real-failure"
    src = inspect.getsource(load_today_dailies)
    assert "ORDER BY started_at" in src


# ── reclaim of a deploy-killed manual daily ──────────────────────────────────

class _ReclaimConn:
    """Applies the reclaim UPDATEs. A pending daily_pipeline is what the
    next claim_one would start."""

    def __init__(self, ledger_rows, *, raise_ledger=False):
        self.ledger_rows = list(ledger_rows)
        self.raise_ledger = raise_ledger
        self.jobs = {
            42: {
                "status": "running",
                "job_type": "daily_pipeline",
                "attempts": 1,
                "error": "",
            },
        }
        self.sql: list[str] = []
        self._last = ""
        self._one = None
        self._rows: list = []
        self.rolled_back = 0

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._last = sql
        if self.raise_ledger and "pipeline_runs" in sql:
            raise RuntimeError('relation "pipeline_runs" does not exist')
        if "SELECT job_id FROM worker_jobs" in sql and "daily_pipeline" in sql:
            self._rows = [
                (jid,) for jid, job in self.jobs.items()
                if job["status"] == "running" and job["job_type"] == "daily_pipeline"
            ]
        elif "pipeline_runs" in sql:
            self._rows = list(self.ledger_rows)
        elif "GREATEST" in sql and "status = 'running'" in sql:
            exclude = "job_type <> 'daily_pipeline'" in sql
            self._rows = []
            for jid, job in list(self.jobs.items()):
                if job["status"] != "running":
                    continue
                if exclude and job["job_type"] == "daily_pipeline":
                    continue
                job["status"] = "pending"
                job["attempts"] = max(job["attempts"] - 1, 0)
                self._rows.append((jid,))
        elif (
            "UPDATE worker_jobs" in sql
            and "status = 'failed'" in sql
            and "daily_pipeline" in sql
        ):
            for job in self.jobs.values():
                if job["status"] == "running" and job["job_type"] == "daily_pipeline":
                    job["status"] = "failed"
                    job["error"] = params[0] if params else ""
            self._rows = []
        elif "SET status = 'running'" in sql and "SKIP LOCKED" in sql:
            pending = [jid for jid, job in self.jobs.items() if job["status"] == "pending"]
            self._one = None
            if pending:
                jid = pending[0]
                job = self.jobs[jid]
                job["status"] = "running"
                job["attempts"] += 1
                self._one = (jid, job["job_type"], {}, job["attempts"])
        else:
            self._rows = []
        return self

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        if "RETURNING job_id, job_type" in self._last:
            return self._one
        return None

    def commit(self):
        pass

    def rollback(self):
        self.rolled_back += 1


def _killed_ledger(minute: int):
    started = datetime(2026, 11, 4, 11, minute, tzinfo=timezone.utc).isoformat()
    finished = datetime(2026, 11, 4, 11, minute, 20, tzinfo=timezone.utc).isoformat()
    return (started, finished, False, "aborted")


def _reclaim_then_claim(conn, now):
    from tracking.job_queue import _reclaim_stale, claim_one
    _reclaim_stale(conn, now)
    return claim_one(conn)


def test_the_first_claim_of_a_manual_daily_is_not_the_reclaim_bounds():
    """A pending row is the kick after the catch-up has stopped. The
    bounds apply when a deploy left that row running, not on the first
    claim."""
    from tracking.job_queue import _job_daily_pipeline, _reclaim_stale
    kick = inspect.getsource(_job_daily_pipeline)
    assert "decide_daily_retry" not in kick
    assert "daily_pipeline_reclaim_decision" not in kick
    reclaim = inspect.getsource(_reclaim_stale)
    assert "_refuse_stale_daily_pipeline" in reclaim


def test_reclaim_inside_the_bounds_leaves_the_manual_daily_pending():
    """One deploy-kill, afternoon, kill switch on: the row goes back to
    pending and the next claim would start it. This is the control the
    bound tests have to fail against."""
    conn = _ReclaimConn([_killed_ledger(0)])
    job = _reclaim_then_claim(conn, datetime(2026, 11, 4, 15, 0, tzinfo=ET))
    assert job is not None
    assert job["job_type"] == "daily_pipeline"
    assert conn.jobs[42]["status"] == "running"


def test_reclaim_after_the_deploy_kill_cap_does_not_start_a_daily(monkeypatch):
    started = []
    monkeypatch.setattr(
        "scheduler.run_daily_pipeline",
        lambda **kw: started.append(kw) or "ok",
    )
    rows = [_killed_ledger(i) for i in range(MAX_DEPLOY_KILLED_STARTS_PER_ET_DAY)]
    conn = _ReclaimConn(rows)
    job = _reclaim_then_claim(conn, datetime(2026, 11, 4, 15, 0, tzinfo=ET))
    assert job is None
    assert started == []
    assert conn.jobs[42]["status"] == "failed"
    assert "deploy-killed" in conn.jobs[42]["error"]
    assert "not reclaimed" in conn.jobs[42]["error"]


def test_reclaim_after_the_cutoff_does_not_start_a_daily(monkeypatch):
    started = []
    monkeypatch.setattr(
        "scheduler.run_daily_pipeline",
        lambda **kw: started.append(kw) or "ok",
    )
    conn = _ReclaimConn([_killed_ledger(0)])
    job = _reclaim_then_claim(conn, datetime(2026, 11, 4, 22, 5, tzinfo=ET))
    assert job is None
    assert started == []
    assert conn.jobs[42]["status"] == "failed"
    assert "cutoff" in conn.jobs[42]["error"]


def test_reclaim_with_the_kill_switch_off_does_not_start_a_daily(monkeypatch):
    started = []
    monkeypatch.setenv("RUN_DAILY_RETRY", "0")
    monkeypatch.setattr(
        "scheduler.run_daily_pipeline",
        lambda **kw: started.append(kw) or "ok",
    )
    conn = _ReclaimConn([_killed_ledger(0)])
    job = _reclaim_then_claim(conn, datetime(2026, 11, 4, 15, 0, tzinfo=ET))
    assert job is None
    assert started == []
    assert conn.jobs[42]["status"] == "failed"
    assert "RUN_DAILY_RETRY" in conn.jobs[42]["error"]


def test_reclaim_does_not_start_a_daily_when_the_ledger_is_unreadable():
    conn = _ReclaimConn([_killed_ledger(0)], raise_ledger=True)
    job = _reclaim_then_claim(conn, datetime(2026, 11, 4, 15, 0, tzinfo=ET))
    assert job is None
    assert conn.jobs[42]["status"] == "failed"
    assert "ledger unreadable" in conn.jobs[42]["error"]
    assert conn.rolled_back == 1


def test_the_reclaim_decision_matches_the_catch_up():
    """The queue does not grow a second copy of the bounds."""
    conn = _ReclaimConn([_killed_ledger(0)])
    now = datetime(2026, 11, 4, 22, 5, tzinfo=ET)
    decision = daily_pipeline_reclaim_decision(conn, now)
    assert decision.action == "skip"
    assert decision.reason == decide_daily_retry(
        now=now,
        runs=load_today_dailies(conn, now),
    ).reason
