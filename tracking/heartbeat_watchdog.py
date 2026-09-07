"""
Heartbeat watchdog — the check that survives the database going away.

WHY THIS EXISTS
---------------
On 2026-08-31 the Railway services' DATABASE_URL stopped authenticating
against the Supabase session pooler at ~02:00 UTC. Every scheduled job kept
running and every one of them failed the same way; no picks were written for
the day, and neither the Discord results recap nor the X post went out. The
outage was silent for more than nine hours and was found by a person noticing
an empty board.

Nothing caught it, and the reason is structural rather than an oversight:

  * ``tracking/system_health.py`` runs INSIDE the refresh pass and reads its
    inputs over the same connection. When the database is the failure it does
    not report CRIT — it does not run at all ("System health check failed to
    run"), which is CLAUDE.md §7's "a health check must not gate on the thing
    that breaks", exactly.
  * ``push_sent``, ``pipeline_runs`` and the health-check results are all
    tables. An alert that has to be written down before it can be noticed
    cannot describe a database that refuses writes.
  * Sentinel runs once a day at 7:15am ET, so its worst-case detection lag is
    24 hours. A daily watch is a review, not a smoke alarm.

So this module deliberately holds NO database dependency on its alerting path.
It reaches Discord over plain HTTP, and it keeps its own de-duplication state
on the filesystem. The database is the SUBJECT of the check, never a
participant in it.

WHAT IT CHECKS
--------------
1. ``db_unreachable`` — can we open a connection at all? This is the one that
   would have caught 2026-08-31, and it is first because every other check is
   meaningless while it fails.
2. ``pipeline_stalled`` — with a connection in hand, how old is the newest
   ``pipeline_runs`` row? Catches the other shape of the same outage: the
   scheduler process dying, or every pass aborting, while the database itself
   is perfectly healthy.

Both are reported through one code path so a recovery message is emitted for
whichever one fired.

WHAT IT DOES NOT COVER
----------------------
A watchdog hosted inside the thing it watches cannot report its own death. If
the container is gone, so is this. That gap is narrowed by scheduling the job
under EVERY service role (see ``_ALWAYS_JOBS`` in scheduler.py) so the poller
service still speaks when the pipeline service is down and vice versa, but it
is not closed: losing both containers at once is still silent here, and
closing that properly needs an off-platform pinger. Said plainly rather than
papered over, because a monitor whose limits are undocumented gets trusted for
things it does not do.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

import config

# _post carries the 429 handling and the never-raises contract this needs, and
# duplicating it would give the watchdog its own untested retry path. Importing
# the module is safe on a dead database: it imports get_connection as a name
# and opens nothing at import time.
from tracking.discord_notifier import _post
from tracking.watch_util import (
    COLOR_ALERT as _COLOR_ALERT,
    COLOR_RECOVERY as _COLOR_RECOVERY,
    alert_state_path,
    post_ops_alert,
    read_alert_state,
    should_notify,
    write_alert_state,
)

_STATE_FILENAME = "heartbeat_watchdog_state.json"

def _state_path() -> Path:
    """Where this watchdog's de-duplication state lives."""
    return alert_state_path(_STATE_FILENAME)


def _read_state() -> dict:
    return read_alert_state(_STATE_FILENAME)


def _write_state(state: dict) -> None:
    write_alert_state(_STATE_FILENAME, state)


def _should_notify(state: dict, key: str, now: datetime) -> bool:
    """True when this condition is new, or has gone unrepeated long enough.

    The repeat exists so a long outage stays visible without burying the
    channel: at the 15-minute cadence an un-throttled 9-hour break posts about
    36 identical messages.
    """
    return should_notify(state, key, now, config.WATCHDOG_RENOTIFY_MINUTES)


def _alert(title: str, detail: str, *, recovery: bool = False) -> bool:
    """Post one watchdog message. Returns True only on a CONFIRMED post.

    `_post` is passed EXPLICITLY rather than resolved inside the helper, so
    this module's name stays the seam the tests patch.
    """
    return post_ops_alert(title, detail, recovery=recovery, post=_post)


def _newest_run_age_minutes(conn, now: datetime) -> float | None:
    """Minutes since the newest pipeline_runs row started, or None if empty.

    started_at is TEXT in mixed shapes here, so it is parsed rather than
    compared as a string (§7: "parse timestamps before comparing them").
    """
    cur = conn.execute("SELECT MAX(started_at) FROM pipeline_runs")
    row = cur.fetchone()
    raw = row[0] if row else None
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        logger.warning(f"Watchdog could not parse pipeline_runs.started_at: {raw!r}")
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return (now - parsed).total_seconds() / 60.0


def _alerter_is_silent(conn, now: datetime) -> bool:
    """True when the failure alerter has stopped recording runs.

    Best-effort and FAILS QUIET: an unreadable heartbeat table must not raise a
    second alarm on top of whatever is already wrong. The database being
    unreachable is already `db_unreachable`, which is checked first.
    """
    try:
        from tracking.job_heartbeat import stale_jobs
        return any(job_id == "failure_alerter"
                   for job_id, _, _ in stale_jobs(conn, now))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Watchdog could not read the alerter heartbeat: {exc}")
        return False


def run_watchdog(now: datetime | None = None) -> dict:
    """Run both checks, alert on what is wrong, and report what it found.

    Returns a dict so a caller (and the tests) can assert on the verdict
    without reading Discord: ``status`` is "ok", "db_unreachable" or
    "pipeline_stalled"; ``notified`` says whether a message was CONFIRMED
    delivered on this pass.
    """
    now = now or datetime.now(timezone.utc)
    state = _read_state()
    status = "ok"
    detail = ""

    try:
        # Imported here, not at module scope, purely for symmetry with the
        # failure it is testing: the import itself is cheap and safe, but
        # keeping the connection attempt inside the try makes the shape of
        # this function match what it claims to check.
        from data.db import get_connection
        conn = get_connection()
    except Exception as exc:  # noqa: BLE001 — ANY failure to connect is the alert
        status = "db_unreachable"
        detail = (
            f"Cannot open a database connection.\n```{str(exc).strip()[:1200]}```\n"
            "Every scheduled job that touches Postgres is failing while this "
            "holds: no picks are being written, and no results recap or X post "
            "can be produced."
        )
    else:
        try:
            age = _newest_run_age_minutes(conn, now)
            if age is not None and age > config.WATCHDOG_STALE_MINUTES:
                status = "pipeline_stalled"
                detail = (
                    f"The database is reachable, but the newest `pipeline_runs` "
                    f"row started **{age:.0f} minutes ago** — over the "
                    f"{config.WATCHDOG_STALE_MINUTES}-minute limit. The scheduler "
                    "is not completing passes."
                )
            elif _alerter_is_silent(conn, now):
                # WHO WATCHES THE WATCHER. tracking/failure_alerter.py reports
                # every other failure to the ops channel, and reports on its own
                # heartbeat too -- which is worth exactly nothing when it is the
                # thing that has died. So the check lives HERE, in the one
                # component that runs on both services, on its own schedule, and
                # keeps no dependency on the alerter being alive.
                #
                # Ranked BELOW pipeline_stalled on purpose: if passes have
                # stopped, that is the finding, and a silent alerter is a
                # symptom of it rather than a second incident.
                status = "alerter_silent"
                detail = (
                    "The database is reachable and passes are completing, but "
                    "`failure_alerter` has not recorded a run inside its "
                    "allowance. **Every other failure alert is therefore off** "
                    "— the channel being quiet no longer means anything."
                )
        finally:
            # The watchdog runs every 15 minutes forever; a leaked connection
            # here would exhaust the pooler and manufacture the outage it is
            # supposed to detect.
            try:
                conn.close()
            except Exception:  # noqa: BLE001 — closing must never mask the verdict
                pass

    notified = False
    if status == "ok":
        # Recover only from a condition that actually alerted, so a healthy
        # boot does not announce a recovery from nothing.
        if state.get("active"):
            was = state["active"]
            notified = _alert(
                "Pipeline recovered",
                f"`{was}` has cleared. The database is reachable and the "
                "scheduler is completing passes again.",
                recovery=True,
            )
            # Clear the throttle stamps as well as the active flag. Leaving a
            # stamp behind would suppress the alert if the same condition
            # returned within the re-notify window — a flapping outage must
            # alert on every new occurrence, not once every six hours.
            state = {}
            _write_state(state)
        logger.info("Watchdog: OK")
        return {"status": status, "notified": notified, "detail": detail}

    logger.error(f"Watchdog: {status} — {detail}")
    if _should_notify(state, f"last_{status}", now):
        notified = _alert(f"Pipeline down — {status.replace('_', ' ')}", detail)
        if notified:
            # Only stamp the throttle on a CONFIRMED post. Stamping on a failed
            # POST would silence the next six hours on the strength of a
            # message nobody received.
            state[f"last_{status}"] = now.isoformat()
    state["active"] = status
    _write_state(state)
    return {"status": status, "notified": notified, "detail": detail}


if __name__ == "__main__":  # pragma: no cover — manual/one-off invocation
    print(json.dumps(run_watchdog(), indent=2))
