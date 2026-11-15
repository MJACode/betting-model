"""A restarted container relaunches its in-play loops at boot (#1359).

WHY THIS FILE EXISTS

Each in-play loop runs under a supervisor job that only fires inside its
window: college football and MLB 11:00-23:50 ET, every 10 minutes. On
2026-11-14 a merge restarted the in-play service at 23:59:17 ET. North Dakota
State at Hawai'i was in the 2nd quarter, and the new container's first college
football tick was 11:00 ET the next morning, so the second half had no in-play
model. Inside a window a restart still left up to 10 minutes uncovered.

The fix gives each supervisor's own job a first run shortly after boot. It is
the same job, not a second one, so max_instances=1 still stops a second copy
of a loop that is already running. After the boot run the job returns to its
own schedule. Every loop exits by itself when nothing is live, so a boot run
with no game on costs one idle check.
"""

from __future__ import annotations

import os
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

ET = ZoneInfo("America/New_York")
# The restart that left the Hawai'i game without its in-play model.
RESTART = datetime(2026, 11, 14, 23, 59, 17, tzinfo=ET)


@pytest.fixture
def pollers(monkeypatch):
    """The scheduler module as the in-play service sees it, with no database."""
    import scheduler
    from tracking import job_heartbeat as jh
    for fn in ("seed", "beat", "mark_disabled"):
        monkeypatch.setattr(jh, fn, lambda *a, **k: None)
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "pollers")
    return scheduler


def test_main_gives_every_in_play_loop_a_run_just_after_boot(pollers, monkeypatch):
    """main() itself, the path a deploy runs, up to sched.start()."""
    scheduler = pollers
    from apscheduler.schedulers.blocking import BlockingScheduler

    captured = {}
    monkeypatch.setattr(BlockingScheduler, "start", lambda self, *a, **k: captured.setdefault("s", self))
    monkeypatch.setattr(scheduler, "catch_up_weekly_jobs", lambda: None)
    monkeypatch.setattr(scheduler, "abort_orphaned_refresh_runs", lambda: None)
    monkeypatch.setattr(scheduler.signal, "signal", lambda *a, **k: None)
    import monitoring.probe
    import monitoring.server
    monkeypatch.setattr(monitoring.probe, "install", lambda *a, **k: None)
    monkeypatch.setattr(monitoring.server, "serve_in_thread", lambda *a, **k: None)

    before = datetime.now(ET)
    scheduler.main()
    sched = captured["s"]

    present = [jid for jid in scheduler.BOOT_RELAUNCH_JOBS if sched.get_job(jid)]
    assert "ncaaf_live_loop" in present and "nba_live" in present, present
    for jid in present:
        job = sched.get_job(jid)
        # A pending cron job has no next_run_time until the scheduler starts:
        # without the fix it would get its next cron fire, 11:00 ET overnight.
        assert hasattr(job, "next_run_time"), f"{jid} has no boot run"
        lead = (job.next_run_time - before).total_seconds()
        assert 50 <= lead <= 120, (jid, job.next_run_time, before)


def test_a_restart_at_2359_relaunches_college_football_within_two_minutes(pollers):
    scheduler = pollers
    sched = scheduler.build_scheduler()
    runs = scheduler.schedule_boot_relaunch(sched, RESTART)

    first = runs["ncaaf_live_loop"]
    assert first - RESTART <= timedelta(minutes=2), first
    # Before the fix the first college football tick was 11:00 the next day.
    job = sched.get_job("ncaaf_live_loop")
    assert job.trigger.get_next_fire_time(None, RESTART) == datetime(2026, 11, 15, 11, 0, tzinfo=ET)
    # After the boot run the job is back on its own schedule.
    assert job.trigger.get_next_fire_time(first, first) == datetime(2026, 11, 15, 11, 0, tzinfo=ET)
    nba = sched.get_job("nba_live")
    assert nba.trigger.get_next_fire_time(runs["nba_live"], runs["nba_live"]) == \
        datetime(2026, 11, 15, 0, 10, tzinfo=ET)


def test_no_two_loops_start_in_the_same_second(pollers):
    scheduler = pollers
    sched = scheduler.build_scheduler()
    runs = scheduler.schedule_boot_relaunch(sched, RESTART)
    assert len(set(runs.values())) == len(runs)
    # Past the moment the old container's loops stopped (the same second the
    # new one started, on 2026-11-14), so two copies of a loop do not overlap.
    assert min(runs.values()) - RESTART >= timedelta(seconds=60)


def test_the_price_feeds_are_not_relaunched(pollers):
    # They run their full --minutes whether or not a game is live, so a boot
    # run at 04:40 ET would poll for 15 minutes with nothing on.
    assert "dk_direct_feed" not in pollers.BOOT_RELAUNCH_JOBS
    assert "bovada_feed" not in pollers.BOOT_RELAUNCH_JOBS


def test_the_worker_relaunches_none_of_the_in_play_service_loops(monkeypatch):
    import scheduler
    from tracking import job_heartbeat as jh
    for fn in ("seed", "beat", "mark_disabled"):
        monkeypatch.setattr(jh, fn, lambda *a, **k: None)
    monkeypatch.setattr(scheduler, "SERVICE_ROLE", "pipeline")
    sched = scheduler.build_scheduler()
    runs = scheduler.schedule_boot_relaunch(sched, RESTART)
    assert not set(runs) & scheduler._POLLER_JOBS, runs


def test_a_real_scheduler_runs_each_loop_once_at_boot(pollers, monkeypatch):
    """The real APScheduler, the real heartbeat wrapper, stub loops."""
    scheduler = pollers
    calls: dict[str, int] = {}
    lock = threading.Lock()

    def stub(name):
        def _f(*a, **k):
            with lock:
                calls[name] = calls.get(name, 0) + 1
        return _f

    for fn in ("run_live_loop", "run_ncaaf_live_loop", "run_nfl_live_worker",
               "run_nfl_live_leader", "run_nba_live", "run_ncaab_live",
               "run_ncaabw_live", "run_euroleague_live", "run_pregame_poller",
               "run_live_scoreboard", "run_heartbeat_watchdog",
               "run_dk_direct_feed", "run_bovada_feed"):
        monkeypatch.setattr(scheduler, fn, stub(fn))

    sched = scheduler.build_scheduler()
    now = datetime.now(ET)
    runs = scheduler.schedule_boot_relaunch(sched, now, delay_s=1, stagger_s=0.2)
    expected = {
        "live_loop": "run_live_loop", "ncaaf_live_loop": "run_ncaaf_live_loop",
        "nfl_live_worker": "run_nfl_live_worker", "nfl_live_leader": "run_nfl_live_leader",
        "nba_live": "run_nba_live", "ncaab_live": "run_ncaab_live",
        "ncaabw_live": "run_ncaabw_live", "euroleague_live": "run_euroleague_live",
        "pregame_poller": "run_pregame_poller",
    }
    want = {expected[j] for j in runs}
    assert "run_ncaaf_live_loop" in want

    t = threading.Thread(target=sched.start, daemon=True)
    t.start()
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with lock:
                if want <= set(calls):
                    break
            time.sleep(0.1)
        time.sleep(0.5)
        with lock:
            got = dict(calls)
        for fn in want:
            assert got.get(fn) == 1, (fn, got)
        # Each job is back on its own cron, not left firing again at boot.
        after = datetime.now(ET)
        for jid in runs:
            job = sched.get_job(jid)
            nxt = job.trigger.get_next_fire_time(runs[jid], after)
            assert job.next_run_time == nxt, (jid, job.next_run_time, nxt)
    finally:
        sched.shutdown(wait=False)
