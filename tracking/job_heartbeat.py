"""Every scheduled job says "I ran", so silence becomes detectable.

WHY THIS EXISTS
---------------
Most of this system is watched by watching its OUTPUT. `odds_dk_lines` catches
a dead pre-game poller because the poller writes odds; `picks_scored_today`
catches a dead scorer. That works whenever a job's job is to write rows.

It does not work for a job whose correct output is often NOTHING. Audited
2026-09-06, three jobs had no check at all:

  * nfl_opener_poll / nfl_poll_hourly — write a pick only when one qualifies,
    so "no picks" is indistinguishable from "no edge". The opener produced its
    first pick ever that day; before then, a permanently broken job and a
    permanently quiet market looked identical.
  * nfl_live_worker — writes its decision log to the Railway volume, not a
    table, so there is nothing queryable to be stale.

And one job had no watcher because it IS the watcher: `failure_alerter`. It
alerts on everything else and nothing alerted on it.

So this records the fact of a RUN, separately from whatever the run produced.
A job that is doing nothing because there is nothing to do still beats; a job
that has died stops beating. Those are the two states that were previously
identical.

HOW IT IS WIRED
---------------
In ONE place — scheduler.py wraps every registered job through `add_job`, so a
new job inherits the heartbeat by existing rather than by someone remembering
to add it. That is the same reasoning the role filter uses there: eleven call
sites is eleven chances to forget one, and the one forgotten is the one that
fails silently.

STALENESS IS DECLARED, NOT INFERRED. A job's cadence lives in its CronTrigger,
which is awkward to introspect and would give a fragile bound anyway (a `*/10`
job legitimately misses ticks when the previous run overruns). `MAX_SILENCE`
below states, per job, how long silence is allowed to last before it means
something. A job with no entry is not watched — deliberately, so that adding a
job cannot fail a deploy, and the list is short enough to read.

NEVER RAISES. A heartbeat that breaks the job it is recording would be worse
than no heartbeat at all.
"""

from __future__ import annotations

from datetime import datetime, timezone

from loguru import logger

from data.ddl_guard import schema_is_current

# How long each job may stay silent before silence is a finding, in minutes.
#
# Set from the job's own cadence with generous headroom, because the cost of a
# false alarm here is the channel being ignored, and the cost of a slow true
# alarm is hours rather than days. Anything not listed is not watched.
MAX_SILENCE: dict = {
    # Minute-cadence NFL opener: 20 minutes is 20 missed ticks.
    "nfl_opener_poll": 20,
    # Hourly, and stands down when no game is inside 10 days -- but it still
    # RUNS and returns, so it still beats. 180 covers a slow tick plus slack.
    "nfl_poll_hourly": 180,
    "nfl_poll_fast": 180,
    # Every 10 minutes, 9am-midnight ET. Off overnight by design, so the bound
    # has to clear the gap: ~9h of silence is legitimate.
    "nfl_live_worker": 700,
    # The watcher. 10-minute cadence; 45 minutes of silence means the thing
    # that reports everything else has stopped reporting.
    "failure_alerter": 45,
    # 15-minute cadence, 24x7, and the last line of defence.
    "heartbeat_watchdog": 45,
    # Every 5 minutes, 24x7.
    "job_queue": 30,
}


def ensure_schema(conn) -> None:
    """Create the table if absent, and DO NOT re-run the DDL once it exists.

    `IF NOT EXISTS` does not make this free. CREATE takes a lock and, more
    importantly, every DDL statement fires Supabase's `pgrst_ddl_watch`, so
    PostgREST answers 503 to the whole app while it rebuilds its schema cache.
    Seven modules once did this on every call and it cost 11.6 hours of
    database time and ~3,600 forced cache reloads (.claude/rules/
    data-integrity.md).

    A heartbeat is written on EVERY tick of EVERY watched job -- the highest
    call rate of anything in this repo -- so it is the worst possible place to
    get this wrong. The repo's own tripwire, tests/test_ddl_guard.py, caught it
    here before it shipped.
    """
    if schema_is_current(conn, "job_heartbeats", columns=("job_id",)):
        return
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_heartbeats (
            job_id     TEXT PRIMARY KEY,
            last_run_at TEXT NOT NULL,
            last_status TEXT,
            detail      TEXT
        )
    """)


def beat(job_id: str, status: str = "ok", detail: str = "") -> None:
    """Record that `job_id` ran. Best-effort; never raises.

    Opens and closes its own connection rather than borrowing one, because the
    caller is the scheduler wrapper and has none. That is one short transaction
    per job run, on the transaction pooler.
    """
    try:
        from data.db import get_connection
        conn = get_connection()
        try:
            ensure_schema(conn)
            conn.execute("""
                INSERT INTO job_heartbeats (job_id, last_run_at, last_status, detail)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET
                    last_run_at = EXCLUDED.last_run_at,
                    last_status = EXCLUDED.last_status,
                    detail      = EXCLUDED.detail
            """, (job_id, datetime.now(timezone.utc).isoformat(), status,
                  (detail or "")[:500]))
            conn.commit()
        finally:
            conn.close()
    except Exception as exc:  # noqa: BLE001 — see the module docstring
        logger.warning(f"heartbeat for {job_id} failed: {exc}")


def seed(job_id: str) -> None:
    """Record a job at REGISTRATION, before it has run.

    Without this, every watched job reports as silent on a fresh deploy until
    its first tick -- up to an hour for the hourly NFL poll and most of a night
    for the in-play worker. A monitor whose first act after every deploy is a
    burst of false alarms trains people to ignore it.

    It also draws the line between "registered and stopped" and "never
    registered", which is what lets a disabled job be silently absent rather
    than permanently alarming.
    """
    beat(job_id, status="registered", detail="scheduled, not yet run")


def stale_jobs(conn, now: datetime | None = None) -> list:
    """[(job_id, minutes_silent, allowed)] for every watched job that is late.

    A job with NO ROW AT ALL is not reported, and that is the important
    subtlety. Two very different things produce no row: a job that is disabled
    on this deployment (RUN_NFL_LIVE=0 and friends never register, so they
    never beat) and a brand-new deploy where nothing has run yet. Alerting on
    either would mean a burst of false alarms every deploy plus a permanent
    alarm for every switched-off job -- and an alerter that cries wolf on boot
    is one nobody reads by the second week.

    Registration is what creates the row: `seed` is called for every job the
    scheduler actually registers, so "has a row but has gone quiet" means
    exactly "was registered and has stopped running", which is the condition
    worth waking someone for.
    """
    now = now or datetime.now(timezone.utc)
    try:
        rows = conn.execute(
            "SELECT job_id, last_run_at FROM job_heartbeats").fetchall()
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"heartbeat read failed: {exc}")
        return []

    seen = {}
    for job_id, raw in rows:
        try:
            parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        seen[job_id] = parsed

    late = []
    for job_id, allowed in sorted(MAX_SILENCE.items()):
        last = seen.get(job_id)
        if last is None:
            continue                      # not registered here — see above
        silent = (now - last).total_seconds() / 60.0
        if silent > allowed:
            late.append((job_id, silent, allowed))
    return late
