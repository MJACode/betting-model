"""Same-day retry of the 6am ET daily after a mid-run worker restart.

WHY THIS EXISTS
---------------
Observed 2026-09-18. The daily full pipeline started at 6:00am ET
(`pipeline_runs` run_id `b65a709cdf734a15bdf7a5d3c8cf7983`, run_kind=`daily`).
At ~6:07am ET PR #699 merged and Railway replaced the `worker` container
mid-run. APScheduler then registered `daily_pipeline` next for *tomorrow*
6:00am ET — a CronTrigger whose fire has passed does not misfire on a fresh
scheduler. The orphaned row stayed `finished_at` NULL until the 7:17am ET
hourly called `start_run`, which closed it as `ok=false`,
`failed_steps='aborted'` (finished_at ~11:17 UTC).

`pipeline_watch` (7:15am ET) reported the aborted pass and did not re-queue.
`mlb_bullpen_workload` and `mlb_team_stats` are written ONLY by the once-daily
run (Steps 0d/3/3b/5c); hourlies never touch them. The 8:28am ET health check
went STALE, and live MLB models scored on yesterday's features until the next
calendar day's 6am.

A weekly job already has a boot catch-up (`catch_up_weekly_jobs`) for the same
shape of miss. The daily did not, because a daily cron's worst-case miss was
assumed to be "until tomorrow" — which is exactly what happened, and is too
long for tables that only get written once a day.

This module is the decision. Scheduler boot and `run_pipeline_watch` both call
it; the 6am cron is unchanged. A dead run is retried again the same
America/New_York day until one daily finishes the MLB freshness steps, a
daily is actually running in this process, or the crash-loop ceiling is hit.
Kill switch: `RUN_DAILY_RETRY=0`.

2026-11-04: the 6:00am ET daily (run 3d3685c194b949d69243f13a1d3c52e7) was
aborted at 11:13:34Z by the deploy of 1934d8b. The catch-up started
8a44ef65d4364828af08e025aa292a51 at that same second. Deploys at 11:39Z and
12:02Z killed that retry and left its row unfinished. The two-start cap then
treated the open row as the retry already spent, so no later boot relaunched
it. There is no SIGTERM handler that closes the ledger; a row stays
unfinished until a later same-kind start or the boot sweep stamps it aborted.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

from loguru import logger

ET = ZoneInfo("America/New_York")

# The scheduled daily. Catch-up must not fire before this, or a 5:55am deploy
# would start the pipeline that the 6:00am cron is about to start.
DAILY_HOUR = 6
DAILY_MINUTE = 0

# Longest finished daily from 2026-10-15 through 2026-11-03 was 47.5 minutes
# (pipeline_runs 16c6612cbcf54ca8b922c6959b7825b6, 54 steps). The 2026-11-01
# through 2026-11-03 runs were 37.6, 41.5 and 39.5 minutes (58–61 steps).
# A row still open past this is not a live pass of that shape.
MAX_DAILY_RUN = timedelta(minutes=75)

# Crash-loop ceiling, not the double-run guard. The in-process lock is what
# stops two dailies in one process. This stops a container that dies inside
# the daily and boots again all day. 2 was the 2026-11-04 hole: the 6:00am
# start and its one automatic retry were both killed by deploys, and every
# later boot saw two ledgered starts and refused another while the retry's
# row was still unfinished.
MAX_DAILY_STARTS_PER_ET_DAY = 8

# Steps that write the daily-only MLB freshness tables (health-check names
# `mlb_bullpen_workload` / `mlb_team_stats` / `mlb_player_game_log` /
# `umpires`). A finished daily whose failures are only later steps (typically
# `health_check`) already completed the ingest we would be retrying for, so a
# full re-run would only burn Odds API credits. Hyphen and underscore forms
# both appear in failed_steps depending on the writer.
MLB_FRESHNESS_STEPS = frozenset({
    "mlb_stats", "mlb-stats",
    "bullpen",
    "game_log", "game-log",
    "umpires",
})


@dataclass(frozen=True)
class DailyRun:
    started_at: datetime | None
    finished_at: datetime | None
    ok: object = None
    failed_steps: str | None = None


@dataclass(frozen=True)
class Decision:
    action: str  # "run" | "skip"
    reason: str


def _enabled() -> bool:
    return os.environ.get("RUN_DAILY_RETRY", "1") not in ("0", "false", "False")


def _as_dt(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _truthy_ok(value) -> bool:
    if value is True or value == 1:
        return True
    if isinstance(value, str) and value.strip().lower() in {"t", "true", "1"}:
        return True
    return False


def _et_day(dt: datetime) -> date:
    return dt.astimezone(ET).date()


def daily_run_from_row(row) -> DailyRun:
    """Coerce a pipeline_runs row (tuple or sequence) into a DailyRun."""
    started, finished, ok, failed = (list(row) + [None] * 4)[:4]
    return DailyRun(
        started_at=_as_dt(started),
        finished_at=_as_dt(finished),
        ok=ok,
        failed_steps=None if failed is None else str(failed),
    )


def completed_mlb_freshness(run: DailyRun) -> bool:
    """True when this daily finished AND wrote the once-daily MLB tables.

    Unfinished and `aborted` are incomplete: the worker died before those
    steps, or we cannot tell. A later-step failure (health_check, scoring, …)
    is complete for this purpose — re-running the whole daily would not
    un-stale bullpen / team_stats because they already landed.
    """
    if run.finished_at is None:
        return False
    if _truthy_ok(run.ok):
        return True
    failed = {s.strip() for s in (run.failed_steps or "").split(",") if s.strip()}
    if not failed or "aborted" in failed:
        return False
    return failed.isdisjoint(MLB_FRESHNESS_STEPS)


def decide_daily_retry(
    *,
    now: datetime,
    runs: list[DailyRun],
    in_process_running: bool = False,
    enabled: bool | None = None,
) -> Decision:
    """Pure decision: run today's daily once more, or skip.

    `runs` are already `run_kind='daily'` rows; this filters to the ET day of
    `now`. Callers that cannot see the ledger pass `runs=[]`, which after 6am
    ET is a missing daily and therefore a run — the same default as a worker
    that was down for the 6am cron.
    """
    if enabled is None:
        enabled = _enabled()
    if not enabled:
        return Decision("skip", "disabled by RUN_DAILY_RETRY")

    now_et = now.astimezone(ET) if now.tzinfo else now.replace(tzinfo=ET)
    today = now_et.date()
    scheduled = now_et.replace(
        hour=DAILY_HOUR, minute=DAILY_MINUTE, second=0, microsecond=0,
    )
    if now_et < scheduled:
        return Decision(
            "skip",
            f"before today's 6:00am ET daily ({today.isoformat()})",
        )

    if in_process_running:
        return Decision("skip", "daily pipeline already running in this process")

    todays = [r for r in runs if r.started_at and _et_day(r.started_at) == today]

    if any(completed_mlb_freshness(r) for r in todays):
        return Decision(
            "skip",
            "today's daily already completed MLB freshness steps",
        )

    if len(todays) >= MAX_DAILY_STARTS_PER_ET_DAY:
        return Decision(
            "skip",
            f"already started {len(todays)} dailies today "
            f"(cap {MAX_DAILY_STARTS_PER_ET_DAY}; not starting another)",
        )

    if not todays:
        return Decision(
            "run",
            f"no daily run ledgered for {today.isoformat()} after 6:00am ET",
        )

    latest = todays[-1]
    if latest.finished_at is None:
        return Decision(
            "run",
            "today's daily is unfinished and this process is not running it",
        )
    failed = latest.failed_steps or "unknown"
    return Decision(
        "run",
        f"today's daily did not complete MLB freshness steps "
        f"(failed_steps={failed})",
    )


def load_today_dailies(conn, now: datetime) -> list[DailyRun] | None:
    """Today's daily rows, `[]` when none, `None` when the ledger is unreadable.

    Fetches a 36h window and filters to the ET calendar day in Python so the
    same code runs against SQLite tests (no timestamptz) and Postgres. A
    failed query returns None so the caller SKIPS rather than treating
    'cannot read' as 'no daily today' and starting a full pipeline blind —
    unlike the weekly catch-up, where a missing table is itself the stale
    signal. Rollback on failure so a poisoned transaction cannot sink the
    caller (bug #390).
    """
    cutoff = (now.astimezone(timezone.utc) - timedelta(hours=36)).isoformat()
    try:
        rows = conn.execute(
            "SELECT started_at, finished_at, ok, failed_steps "
            "FROM pipeline_runs "
            "WHERE run_kind = 'daily' AND started_at >= ? "
            "ORDER BY started_at",
            (cutoff,),
        ).fetchall()
    except Exception as exc:  # noqa: BLE001 — skip, do not start blind
        logger.warning(f"daily_retry: could not read pipeline_runs ({exc})")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None
    today = now.astimezone(ET).date() if now.tzinfo else now.replace(tzinfo=ET).date()
    out = []
    for row in rows or []:
        run = daily_run_from_row(row)
        if run.started_at and _et_day(run.started_at) == today:
            out.append(run)
    return out


def announce_daily_retry(reason: str, *, source: str) -> bool:
    """Ops-channel note. Failure to post must not block the retry itself."""
    from tracking.watch_util import post_ops_alert

    detail = (
        f"**Source:** `{source}`\n"
        f"**Reason:** {reason}\n\n"
        "The 6:00am ET daily is the only writer of `mlb_bullpen_workload` / "
        "`mlb_team_stats`. After a mid-run deploy APScheduler's next fire is "
        "tomorrow 6:00am, which leaves live MLB models on stale features "
        "until then (2026-09-18, run `b65a709cdf734a15bdf7a5d3c8cf7983`, "
        "failed_steps=`aborted`). This is the same-day retry. A deploy that "
        "kills the retry starts it again (2026-11-04, runs "
        "`3d3685c194b949d69243f13a1d3c52e7` and "
        "`8a44ef65d4364828af08e025aa292a51`). The in-process lock stops a "
        "second daily in this process; the crash-loop ceiling stops a "
        f"container that restarts all day ({MAX_DAILY_STARTS_PER_ET_DAY} "
        "starts)."
    )
    try:
        return post_ops_alert(
            "Same-day daily pipeline retry",
            detail,
            recovery=True,
        )
    except Exception:  # noqa: BLE001 — the retry is the point; the note is not
        logger.exception("daily_retry: ops note failed (retry continues)")
        return False


def _minutes(delta: timedelta) -> int:
    return int(delta.total_seconds() // 60)


def assess_daily_completion(
    now: datetime, runs: list[DailyRun],
) -> tuple[str, str]:
    """Health-check view of today's daily. Status is OK, STALE or SKIPPED.

    An unfinished daily older than ``MAX_DAILY_RUN`` is STALE at any hour:
    that is the 2026-11-04 row ``8a44ef65d4364828af08e025aa292a51``, still
    open 81 minutes later while hourlies were completing. ``refresh_pass_completion``
    only counts an unfinished row after 2 hours, and only when the latest
    finished pass is inside 90 minutes, so a killed daily under that age
    stays green beside a healthy hourly.

    A daily that finished the MLB freshness steps is OK. Before 6:00am ET,
    and until ``MAX_DAILY_RUN`` after 6:00am when nothing has finished and
    nothing is open past the max, the check skips — the run is not late yet.
    """
    now_et = now.astimezone(ET) if now.tzinfo else now.replace(tzinfo=ET)
    if now.tzinfo is None:
        now = now_et
    today = now_et.date()
    scheduled = now_et.replace(
        hour=DAILY_HOUR, minute=DAILY_MINUTE, second=0, microsecond=0,
    )
    deadline = scheduled + MAX_DAILY_RUN
    max_min = _minutes(MAX_DAILY_RUN)

    open_runs = [r for r in runs if r.started_at and r.finished_at is None]
    stale_open = [r for r in open_runs if now - r.started_at >= MAX_DAILY_RUN]
    fresh_open = [r for r in open_runs if now - r.started_at < MAX_DAILY_RUN]
    todays = [r for r in runs if r.started_at and _et_day(r.started_at) == today]

    if stale_open:
        oldest = min(stale_open, key=lambda r: r.started_at)
        started = oldest.started_at.astimezone(timezone.utc).strftime("%H:%M UTC")
        return (
            "STALE",
            f"daily started {started} never finished "
            f"({_minutes(now - oldest.started_at)} min, max {max_min}) "
            f"— a killed worker leaves finished_at NULL",
        )

    if any(completed_mlb_freshness(r) for r in todays):
        return ("OK", f"today's daily completed ({today.isoformat()})")

    if now_et < scheduled:
        return (
            "SKIPPED",
            f"before today's 6:00am ET daily ({today.isoformat()})",
        )

    if fresh_open:
        age = _minutes(now - fresh_open[-1].started_at)
        return ("OK", f"daily in progress, started {age} min ago")

    if now_et < deadline:
        return (
            "SKIPPED",
            f"no finished daily yet for {today.isoformat()}; "
            f"the 6:00am run has until {deadline.strftime('%H:%M')} ET",
        )

    return (
        "STALE",
        f"no successful daily for {today.isoformat()} "
        f"and none is still inside {max_min} min",
    )
