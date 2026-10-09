"""Re-run the refresh pass a deploy killed, instead of waiting for the next :17.

WHY THIS EXISTS
---------------
Measured 2026-09-20. Every merge to master redeploys the `worker`, and Railway
stops the old container whatever it is doing: deployment 17265563 was scoring
NCAAF game lines at 18:23:01 UTC and logged "Stopping Container" at 18:23:03,
three minutes after #796 merged. The hourly pass it was six minutes into never
reached prop scoring. Seven passes in two days ended `failed_steps='aborted'`
with a merge inside their window (09-19 13:17 / 14:17 / 18:17 UTC, 09-20 00:20
/ 13:17 / 17:17 / 18:17), and on 09-20 no pass completed between 16:32 and
19:31 UTC: MLB props had ZERO rows for the day until 19:23, with first pitches
from 17:11.

`tracking.daily_retry` already covers the 6am daily, for the same reason: a
CronTrigger whose fire has passed does not misfire on a fresh scheduler, so the
killed pass is simply lost until the next one. For an hourly pass that is up to
an hour of no scoring, in the afternoon, which is when lineups post.

This module is the decision; `scheduler.catch_up_refresh_pass` calls it at
boot. It only ever replaces a pass that was already scheduled and did not
finish -- it adds no pass of its own.

WHAT IT COSTS
-------------
A catch-up is a full pass and buys odds again: 1,018 Odds API credits left the
ledger in the minute holding the 19:17 UTC pass's odds and prop-odds pulls on
2026-09-20 (955,209 -> 954,191; ~40 of that was the NFL in-play loop). That is
the price of the pass it replaces, not a new line of spend, but it is real:
the cap below bounds a merge-heavy hour. Kill switch: `RUN_REFRESH_RETRY=0`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from loguru import logger

from tracking.daily_retry import ET, Decision, _as_dt

# The :17 passes (hourly 7am-5pm ET, overnight midnight-6am ET) both ledger as
# `hourly`. The evening pass ledgers as `evening` and fires every ten minutes,
# 6:00-11:50pm ET.
#
# Evening used to be excluded: "the next one is never further away than a
# catch-up would take to start." Measured 2026-10-09 22:00-23:20 UTC, that
# wait is the outage. Three merges (#908 22:24 UTC, #909 22:59, #910 23:07)
# each replaced the worker mid-pass. The next tick's start_run then closed
# the open row as failed_steps='aborted' with finished_at equal to that
# tick (22:20→22:30, 23:00→23:10, 23:10→23:20), steps_total NULL. The same
# evening, a pass that actually overran the cadence (22:00, 10.78 min) was
# left alone: no 22:10 row, and it finished ok at 22:10:47. Oct 7 22:00-23:00
# UTC averaged 10.6-10.9 min with zero aborts and half the ticks absent.
# The abort stamp is the next start_run, not a 10-minute kill, and not the
# in-process lock (scheduler._REFRESH_LOCK plus max_instances=1) giving up.
#
# What did not run: health-check. pipeline_log's last dispatch:health-check
# before the streak was 22:58:34; the 23:20 pass wrote the next batch at
# 23:28:56. job_heartbeats.nfl_poll_hourly was re-seeded "registered" at
# 23:10:43, which is scheduler boot, 60s before refresh_catch_up beat at
# 23:11:47 — and that catch-up skipped because this module refused evening.
CATCH_UP_KINDS = frozenset({"hourly", "evening"})
REFRESH_KINDS = frozenset({"hourly", "evening"})
PASS_MINUTE = 17
# Evening cron is hour 18-23 ET, minute */10. Last fire is 23:50 ET.
EVENING_HOUR_START = 18
EVENING_HOUR_END = 23
# Under this, the */10 cron is close enough that starting a second pass
# would only buy odds twice. The in-process lock still collapses a catch-up
# that is still running when the tick arrives into one pass.
EVENING_MIN_LEAD = timedelta(minutes=3)

# Only a pass from this hour is worth replacing; an older orphan belongs to a
# worker that was down, and the cron has the schedule from here.
LOOKBACK = timedelta(minutes=60)

# Inside this many minutes of the next :17 the cron is about to run the same
# pass anyway.
MIN_LEAD_TO_NEXT_PASS = timedelta(minutes=10)

# Interrupted passes inside LOOKBACK, the one being replaced included. A
# container restarting in a loop (or four merges in half an hour, 2026-09-20
# 18:20-18:51 UTC) must not buy odds on every boot.
MAX_INTERRUPTED_IN_LOOKBACK = 2


@dataclass(frozen=True)
class RefreshRun:
    run_kind: str
    started_at: datetime | None
    finished_at: datetime | None
    steps_total: object = None
    failed_steps: str | None = None


def _enabled() -> bool:
    return os.environ.get("RUN_REFRESH_RETRY", "1") not in ("0", "false", "False")


def refresh_run_from_row(row) -> RefreshRun:
    kind, started, finished, steps_total, failed = (list(row) + [None] * 5)[:5]
    return RefreshRun(
        run_kind=str(kind or ""),
        started_at=_as_dt(started),
        finished_at=_as_dt(finished),
        steps_total=steps_total,
        failed_steps=None if failed is None else str(failed),
    )


def interrupted(run: RefreshRun) -> bool:
    """True when the pass never reached its own end.

    Unfinished is an orphan: this is a fresh process, so whatever wrote the
    row is gone. `aborted` is the same orphan after a later `start_run` closed
    it. A pass that FINISHED with failed steps ran its chain and is not this.
    """
    if run.finished_at is None:
        return True
    return run.steps_total is None and "aborted" in (run.failed_steps or "")


def _next_pass(now: datetime) -> datetime:
    nxt = now.replace(minute=PASS_MINUTE, second=0, microsecond=0)
    return nxt if nxt > now else nxt + timedelta(hours=1)


def _next_ten_minutes(now: datetime) -> datetime:
    """The next */10 boundary strictly after `now`, in the same timezone.

    A time that lands on a boundary (19:10:00) advances to the following one.
    Seconds past a boundary (19:10:47) do too: that fire has already happened.
    """
    base = now.replace(second=0, microsecond=0)
    remainder = base.minute % 10
    if remainder == 0:
        return base + timedelta(minutes=10)
    return base + timedelta(minutes=(10 - remainder))


def _in_evening_window(et: datetime) -> bool:
    return EVENING_HOUR_START <= et.hour <= EVENING_HOUR_END


def next_refresh_fire(now: datetime, kind: str) -> datetime:
    """When the cron will next run the same chain this catch-up would run.

    Hourly (and the overnight :17, which ledgers as hourly) is the next :17.
    Evening is the next */10 inside 18:00-23:50 ET; after 23:50 the next
    refresh of this chain is the overnight :17, not tomorrow's 18:00.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if kind != "evening":
        return _next_pass(now)
    et = now.astimezone(ET)
    nxt_et = _next_ten_minutes(et)
    if _in_evening_window(nxt_et):
        return nxt_et.astimezone(timezone.utc)
    return _next_pass(now)


def _min_lead(kind: str) -> timedelta:
    return EVENING_MIN_LEAD if kind == "evening" else MIN_LEAD_TO_NEXT_PASS


def decide_refresh_retry(
    *,
    now: datetime,
    runs: list[RefreshRun],
    in_process_running: bool = False,
    enabled: bool | None = None,
) -> Decision:
    """Pure decision: replace the pass a deploy killed, or leave it to the cron.

    `runs` are refresh rows, oldest first. An empty list is a SKIP, unlike the
    daily: no ledgered pass this hour means there is nothing to replace.
    """
    if enabled is None:
        enabled = _enabled()
    if not enabled:
        return Decision("skip", "disabled by RUN_REFRESH_RETRY")
    if in_process_running:
        return Decision("skip", "a refresh pass is already running in this process")

    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    recent = [r for r in runs
              if r.run_kind in REFRESH_KINDS and r.started_at
              and now - r.started_at <= LOOKBACK]
    if not recent:
        return Decision("skip", "no refresh pass started in the last hour")

    latest = recent[-1]
    if not interrupted(latest):
        return Decision("skip", "the latest refresh pass ran to its end")
    if latest.run_kind not in CATCH_UP_KINDS:
        return Decision(
            "skip", f"a {latest.run_kind} pass was interrupted; not a "
                    "refresh this catch-up replaces")

    lead = next_refresh_fire(now, latest.run_kind) - now
    if lead < _min_lead(latest.run_kind):
        if latest.run_kind == "evening":
            return Decision(
                "skip", f"the next evening tick is "
                        f"{int(lead.total_seconds() // 60)} minute(s) away")
        return Decision(
            "skip", f"the next :{PASS_MINUTE} pass is {int(lead.total_seconds() // 60)} "
                    "minute(s) away")

    broken = sum(1 for r in recent if interrupted(r))
    if broken > MAX_INTERRUPTED_IN_LOOKBACK:
        return Decision(
            "skip", f"{broken} refresh passes were interrupted in the last hour "
                    f"(cap {MAX_INTERRUPTED_IN_LOOKBACK}; not buying odds again)")

    started = latest.started_at.astimezone(timezone.utc).strftime("%H:%M UTC")
    mode = latest.run_kind if latest.run_kind in ("hourly", "evening") else "hourly"
    return Decision(
        "run", f"the {started} {latest.run_kind} pass was interrupted "
               "— the worker was replaced mid-run",
        mode=mode)


def load_recent_refreshes(conn, now: datetime) -> list[RefreshRun] | None:
    """Refresh rows from the last LOOKBACK, `None` when the ledger is unreadable.

    None is a SKIP for the caller, the same rule as the daily: 'cannot read'
    must not become 'start a pass blind'. Filtered in Python so the same code
    runs on the SQLite test ledger (TEXT timestamps, mixed offsets).
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    cutoff = (now.astimezone(timezone.utc) - LOOKBACK - timedelta(minutes=5)).isoformat()
    try:
        rows = conn.execute(
            "SELECT run_kind, started_at, finished_at, steps_total, failed_steps "
            "FROM pipeline_runs "
            "WHERE run_kind IN ('hourly', 'evening') AND started_at >= ? "
            "ORDER BY started_at",
            (cutoff,),
        ).fetchall()
    except Exception as exc:  # noqa: BLE001 — skip, do not start blind
        logger.warning(f"refresh_retry: could not read pipeline_runs ({exc})")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
    return [refresh_run_from_row(r) for r in rows or []]
