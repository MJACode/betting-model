"""Keep the morning Picks read off a saturated disk.

2026-11-12, about 05:50–07:03 ET. Postgres disk IO on project vvprgnrmzeekokzkrkfu
was saturated. Queries that are normally milliseconds (`games`, `odds`,
`system_health_checks`) ran 10–99s, and `v_latest_dk_odds` — what the Picks
board waits on for its first paint — took about 14.5s. The app, the worker,
the pollers and prop-probe were up. The overlap on the pipeline scheduler:

- the 05:17 ET overnight refresh (a full odds and scoring pass) could still
  be running when the 06:00 daily started; the two locks did not exclude
  each other
- Kalshi ladder and game-market inserts at :40 and :45 (about 12–18s each),
  on the same minutes as the five-minute odds jobs
- each long-lived process's hourly `api_call_log` prune (a rollup plus one
  unbounded delete; one of them ran about 67s)
- NCAAB/NCAABW odds capture, the NCAAF and NCAAB cards, and the NFL polls
  that read `games` and write `nfl_odds_history`, all free to start together

The daily still runs at 06:00. It is the morning's one full writer. A refresh
does not start while it holds its lock, and the daily waits for a refresh
already inside its chain. From 05:40 to 07:15 ET the other heavy ticks share
one lane, so they run one at a time instead of as a pile. Kalshi snapshots
and the api_call_log prune do not start in that window; Kalshi has a 07:20
and 07:25 catch-up so the hour is still recorded, and the prune runs on the
next flush after the window, one session at a time.

No migration. The lane is in-process. The prune lock is a session advisory
lock, the same mechanism as the scoring lease, and it needs no new table.
"""

from __future__ import annotations

import threading
from datetime import datetime
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")

# Inclusive start, exclusive end, minutes from midnight ET.
# 05:40 covers the first statement timeouts on 2026-11-12. 07:15 is after
# the 07:03 tail, and before the 07:17 hourly refresh.
WINDOW_START_MIN = 5 * 60 + 40
WINDOW_END_MIN = 7 * 60 + 15

# Next to the publish locks (812_090_601–604). Not a scoring-lease key and
# not job_queue.QUEUE_LOCK_KEY. An advisory lock has no namespace but the
# number, so this one is only the api_call_log prune.
API_LOG_PRUNE_LOCK = 812_090_605

# Research recorders. A tick inside the window, or while the daily still
# holds its lock, does not insert. The 07:20 / 07:25 jobs are the catch-up.
MAINTENANCE_JOBS = frozenset({
    "kalshi_ladders",
    "kalshi_game_markets",
    "kalshi_ladders_morning",
    "kalshi_game_markets_morning",
})

# Nothing in the queue is latency-sensitive (the job's own comment). A
# backfill started at 06:00 would sit on the disk next to the daily.
DEFER_JOBS = MAINTENANCE_JOBS | frozenset({"job_queue"})

# Disk-heavy ticks that still have to run in the window (odds capture, the
# cards, the NFL polls). One at a time. The every-minute planning reads are
# not in this set: they are one indexed read when idle, and putting them
# here would let them take the lane from the capture.
LANE_JOBS = frozenset({
    "ncaab_odds_capture",
    "ncaabw_odds_capture",
    "ncaab_injury_feed",
    "ncaab_total_card",
    "ncaabw_total_card",
    "ncaab_spread_card",
    "ncaab_moneyline_card",
    "ncaaf_moneyline_card",
    "nfl_poll_hourly",
    "nfl_poll_fast",
    "nfl_opener_poll",
    "nfl_schedule_refresh",
    "nfl_prop_card",
    "nba_prop_window",
})


def in_morning_window(now: datetime) -> bool:
    """True from 05:40 ET inclusive through 07:15 ET exclusive."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    local = now.astimezone(ET)
    minutes = local.hour * 60 + local.minute
    return WINDOW_START_MIN <= minutes < WINDOW_END_MIN


class Decision:
    """Whether this tick may touch the database, and how to let the lane go."""

    def __init__(self, admitted: bool, reason: str, release):
        self.admitted = admitted
        self.reason = reason
        self._release = release
        self._open = True

    def release(self) -> None:
        if self._open:
            self._open = False
            self._release()


def _noop() -> None:
    return None


class MorningDisk:
    """One heavy tick at a time inside the morning window."""

    def __init__(self):
        self._lane = threading.BoundedSemaphore(1)

    def admit(self, job_id: str, *, now: datetime, daily_busy: bool = False) -> Decision:
        if job_id in DEFER_JOBS and (in_morning_window(now) or daily_busy):
            why = ("morning disk window" if in_morning_window(now)
                   else "daily pipeline still running")
            return Decision(False, f"deferred — {why}", _noop)
        if job_id not in LANE_JOBS or not in_morning_window(now):
            return Decision(True, "", _noop)
        if self._lane.acquire(blocking=False):
            return Decision(True, "", self._lane.release)
        return Decision(False, "deferred — morning disk lane full", _noop)


GATE = MorningDisk()


def admit(job_id: str, *, now: datetime | None = None,
          daily_busy: bool = False) -> Decision:
    """The scheduler's gate. `now` defaults to the current ET minute."""
    return GATE.admit(
        job_id,
        now=now if now is not None else datetime.now(ET),
        daily_busy=daily_busy,
    )


def begin_api_log_prune(conn, now: datetime | None = None) -> str:
    """'wait', 'skip', or 'run'.

    'wait' — inside the morning window. The caller must not advance its
    hourly clock, so the next flush tries again as soon as the window opens.
    'skip' — another session is already deleting the same aged-out rows.
    Advance the clock. One prune an hour is enough; every long-lived process
    used to do its own.
    'run' — this session holds API_LOG_PRUNE_LOCK, or the lock could not be
    asked (fail open, same as the publish lock: a prune that never runs lets
    the table grow). Call end_api_log_prune when the delete returns.
    """
    if in_morning_window(now if now is not None else datetime.now(ET)):
        return "wait"
    try:
        row = conn.execute(
            "SELECT pg_try_advisory_lock(?)", (API_LOG_PRUNE_LOCK,),
        ).fetchone()
    except Exception:                                          # noqa: BLE001
        return "run"
    if row and row[0]:
        return "run"
    return "skip"


def end_api_log_prune(conn) -> None:
    """Release the prune lock. A session that fail-opened never held it."""
    try:
        conn.execute(
            "SELECT pg_advisory_unlock(?)", (API_LOG_PRUNE_LOCK,),
        )
        conn.commit()
    except Exception:                                          # noqa: BLE001
        try:
            conn.rollback()
        except Exception:                                      # noqa: BLE001
            pass
