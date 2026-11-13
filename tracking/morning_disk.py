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

The daily still runs at 06:00. It is the morning's one full writer. From
05:40 to 07:15 ET a refresh does not start while it holds its lock (outside
that window a refresh runs beside a daily as before), and the daily waits for
a refresh already inside its chain. In the same window the other heavy ticks
share one lane, so they run one at a time instead of as a pile; the jobs that
decide real-money picks in that window (DECIDING_JOBS) are not in the lane.
Kalshi snapshots and the api_call_log prune do not start in that window;
Kalshi has a 07:20 and 07:25 catch-up so the hour is still recorded, and the
prune runs on the next flush after the window, one session at a time. A tick
the gate turns away beats its heartbeat as "skipped", not "ok".

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

# Disk-heavy ticks that still have to run in the window and neither decide a
# real-money pick in it nor capture the prices one decides on. One at a time.
# The every-minute planning reads are not in this set: they are one indexed
# read when idle.
LANE_JOBS = frozenset({
    "ncaab_injury_feed",
    "ncaab_spread_card",
    "ncaab_moneyline_card",
    "ncaaf_moneyline_card",
    "nfl_schedule_refresh",
    "nba_prop_window",
})

# Jobs that decide real-money picks inside 05:40-07:15 ET, or capture the
# prices those decisions are made on. The lane is a non-blocking try, so a
# tick that lost it was skipped, not queued, and the game would be decided
# at a later look. They run as they did before the lane. Measured
# 2026-11-13 on the last 21 days (decision ledgers and picks, read-only):
#   ncaab_total_card     1 decision, 2026-11-13 06:18 ET (East Texas A&M at
#                        Portland, below the cut), on a quote stored 06:14.
#                        Decides at DraftKings' first posted total.
#   ncaabw_total_card    the same first-posted-total rule; its ledger starts
#                        2026-11-10, so 21 days cannot be measured yet.
#   ncaab_odds_capture   stores the first posts both NCAAB first-post rules
#                        decide on. The first-post moneyline (every minute,
#                        never in the lane) wrote 44 decisions in the window
#                        on 41 games, each on a first post stored in it. It
#                        shared its minute with the injury feed and the NBA
#                        prop window, so it competed for the lane every tick.
#   ncaabw_odds_capture  the same, for the women's totals card.
#   nfl_prop_card        1 decision, 2026-11-01 06:27 ET (nfl_prop_rec_yards,
#                        written by the 06:25 tick's prop scoring step).
#   nfl_opener_poll,     1 decision, 2026-11-13 06:00 ET (nfl_opener_spread,
#   nfl_poll_hourly,     SF at DAL). The opener races Pinnacle's first post;
#   nfl_poll_fast        the polls price the opener and wind cards.
# The cards still in LANE_JOBS wrote no decision in the window in those 21
# days: the NCAAB spread and moneyline cards decide only in the 15:00Z hour,
# the NCAAF moneyline card in the 14:00Z hour, and the NBA prop window 45-57
# minutes before a tip (158 decisions, none in the window).
DECIDING_JOBS = frozenset({
    "ncaab_total_card",
    "ncaabw_total_card",
    "ncaab_odds_capture",
    "ncaabw_odds_capture",
    "nfl_prop_card",
    "nfl_opener_poll",
    "nfl_poll_hourly",
    "nfl_poll_fast",
})

# The 06:00 daily can outlast the window (finished dailies ran 23.8-47.5
# minutes from 2026-10-15 to 11-03, and a retried one starts later), so the
# research recorders and the job queue also wait while it holds its lock.
# Only in the morning: a catch-up daily may run until 22:00 ET
# (tracking/daily_retry.py), and one in the evening must not hold the job
# queue or drop the Kalshi record of live games for its whole run.
DAILY_BUSY_DEFER_END_MIN = 12 * 60


def now_et() -> datetime:
    """The scheduler's clock for this gate. A function so a test can move it."""
    return datetime.now(ET)


def in_morning_window(now: datetime) -> bool:
    """True from 05:40 ET inclusive through 07:15 ET exclusive."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    local = now.astimezone(ET)
    minutes = local.hour * 60 + local.minute
    return WINDOW_START_MIN <= minutes < WINDOW_END_MIN


def _minutes_et(now: datetime) -> int:
    if now.tzinfo is None:
        now = now.replace(tzinfo=ET)
    local = now.astimezone(ET)
    return local.hour * 60 + local.minute


def refresh_yields_to_daily(now: datetime, daily_busy: bool) -> bool:
    """True when a refresh pass should stand down for the daily.

    Only inside the morning window. Outside it a refresh runs beside a
    daily as it always did: a catch-up daily can run until 22:00 ET, and the
    18:00-23:00 passes carry the odds, scoring and push for live games.
    """
    return daily_busy and in_morning_window(now)


def _defer_for_daily(now: datetime, daily_busy: bool) -> bool:
    return daily_busy and _minutes_et(now) < DAILY_BUSY_DEFER_END_MIN


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
        if job_id in DEFER_JOBS and (in_morning_window(now)
                                     or _defer_for_daily(now, daily_busy)):
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
        now=now if now is not None else now_et(),
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
    if in_morning_window(now if now is not None else now_et()):
        return "wait"
    try:
        row = conn.execute(
            "SELECT pg_try_advisory_lock(?)", (API_LOG_PRUNE_LOCK,),
        ).fetchone()
    except Exception:                                          # noqa: BLE001
        # The SELECT may have opened a transaction and then failed. Close it
        # before the caller prunes on this same connection.
        try:
            conn.rollback()
        except Exception:                                      # noqa: BLE001
            pass
        return "run"
    if row and row[0]:
        return "run"
    # Not acquired. The SELECT is still an open transaction on the writer's
    # connection, which is reused for inserts and may not write again for an
    # hour. Commit it so the connection is not left idle in a transaction.
    try:
        conn.commit()
    except Exception:                                          # noqa: BLE001
        try:
            conn.rollback()
        except Exception:                                      # noqa: BLE001
            pass
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
