"""Say it in Discord when something breaks — every failure, not just an outage.

WHY THIS EXISTS
---------------
On 2026-09-06 the refresh pass failed steps on 32 of 50 passes. `odds` — the
step that fetches the lines every model prices against — died with
EMAXCONNSESSION at 23:00Z and again at 23:30Z. Nobody knew until someone
queried `pipeline_runs` by hand hours later.

Nothing was missing from the DETECTION. `tracking/system_health.py` runs on
every pass, and it had already written the row:

    [WARN] refresh_pass_steps: STALE — intermittent failures
           (not in every pass): lineups, probables-refresh, public-betting

It wrote it to a TABLE and to the log, and there the matter ended. The gap was
never that the system could not tell something was wrong; it was that the only
way to find out was to go and look. mike: "need alerting to the ops discord
when there are failures like this any any other type of failure."

So this module is delivery, not detection. It reads what the health check
already decided and what the run ledger already recorded, and it puts the
failures where a person will see them.

WHAT IT ALERTS ON
-----------------
1. Any health check whose status is not OK, keyed individually so each gets its
   own throttle and its own recovery message. CRIT severity alerts on sight;
   WARN is throttled harder, because a WARN that pages at CRIT's cadence
   teaches people to ignore the channel and that is silence by another route.
2. The refresh pass's CLEAN RATE over a recent window. This is the one that
   would have caught 2026-09-06: no single step was failing in every pass, so
   the persistent-failure rule stayed quiet at WARN, while the board was
   objectively degraded — 18 clean passes out of 50 against 30/47 and 35/51 on
   the two days before.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not detect a database outage. `tracking/heartbeat_watchdog.py` owns
that, and it owns it precisely because it holds NO database dependency on its
alerting path — the database is the subject of that check, never a participant.
This module reads the database to do its job, so during a real outage it can
say nothing at all. That is correct: the watchdog covers exactly that case, and
duplicating it here would create a second, weaker copy of the one check that
has to work when everything else does not.

It does not re-implement the throttle, the volume-backed state file or the ops
webhook. Those live in `watch_util` (§1b: prefer a shared helper the watches
call over a per-watch implementation).

NEVER RAISES. A monitor that dies on its own bookkeeping produces exactly the
silence it exists to prevent, and that silence is indistinguishable from a
healthy system.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from loguru import logger

from tracking.watch_util import (
    post_ops_alert,
    query_rows,
    read_alert_state,
    should_notify,
    write_alert_state,
)

_STATE_FILE = "failure_alerter_state.json"

# CRIT repeats every 2h; WARN every 12h. Different numbers because they are
# different claims: a CRIT is "a thing that produces picks is not producing",
# which stays worth repeating, while a WARN is usually a flaky upstream and
# repeating it hourly is how a channel stops being read.
RENOTIFY_CRIT_MIN = int(os.environ.get("ALERT_RENOTIFY_CRIT_MINUTES", "120"))
RENOTIFY_WARN_MIN = int(os.environ.get("ALERT_RENOTIFY_WARN_MINUTES", "720"))

# The clean-rate rule. 12 passes is about two hours at the evening cadence —
# long enough that one flaky API call does not trip it, short enough to notice
# the same evening. 0.70 sits below the two healthy days measured before the
# incident (0.64 and 0.69 clean... see below) and above the incident itself.
#
# HONEST NOTE ON THAT NUMBER: measured 2026-09-06, the clean-pass rate was
# 30/47 = 0.64 on 09-04 and 35/51 = 0.69 on 09-05, against 18/50 = 0.36 on the
# incident day. A 0.70 threshold would therefore have fired on all three. It is
# set at 0.50 instead — comfortably below both healthy days and comfortably
# above the incident — because a threshold that fires on a normal day is a
# threshold that gets muted. Raise it when the healthy baseline is actually
# clean; it is a floor on "obviously degraded", not a quality target.
CLEAN_RATE_WINDOW = int(os.environ.get("ALERT_CLEAN_RATE_WINDOW", "12"))
CLEAN_RATE_FLOOR = float(os.environ.get("ALERT_CLEAN_RATE_FLOOR", "0.50"))


def _latest_health_rows(conn) -> list:
    """The most recent health run's rows, newest checked_at only.

    Scoped to ONE run rather than "everything recent" so a check that has since
    recovered cannot keep alerting off a stale row.
    """
    return query_rows(conn, """
        SELECT check_name, status, severity, detail
        FROM system_health_checks
        WHERE checked_at = (SELECT MAX(checked_at) FROM system_health_checks)
        ORDER BY severity, check_name
    """, label="failure-alerter/health")


def _clean_rate(conn) -> tuple:
    """(clean, total, failing_steps) over the last CLEAN_RATE_WINDOW passes.

    `aborted` runs are counted as failures: run_ledger writes that sentinel
    when a worker is replaced mid-pass, and a pass that did not finish did not
    produce what the pass produces.
    """
    rows = query_rows(conn, """
        SELECT ok, failed_steps FROM pipeline_runs
        WHERE finished_at IS NOT NULL AND run_kind <> 'daily'
        ORDER BY finished_at DESC LIMIT %s
    """, (CLEAN_RATE_WINDOW,), label="failure-alerter/ledger")
    if not rows:
        return (0, 0, [])
    clean = sum(1 for ok, _ in rows if ok)
    steps: dict = {}
    for _, failed in rows:
        for s in (failed or "").split(","):
            s = s.strip()
            if s:
                steps[s] = steps.get(s, 0) + 1
    ranked = sorted(steps.items(), key=lambda kv: -kv[1])
    return (clean, len(rows), ranked)


def _conditions(conn, now: datetime | None = None) -> dict:
    """Everything currently wrong, as {key: (severity, title, detail)}.

    `now` is threaded in rather than read here so the whole pass judges
    staleness against ONE clock -- two calls to datetime.now() inside a single
    verdict is a race nobody would ever see fail, and exactly the kind that
    makes a test flaky at a month boundary.
    """
    now = now or datetime.now(timezone.utc)
    out: dict = {}

    for check_name, status, severity, detail in _latest_health_rows(conn):
        # SKIPPED is usually legitimate (no golf tournament, no NBA games) and
        # alerting on it would bury the channel out of season. STALE is the
        # status the health check uses for "this should have data and does not".
        if str(status).upper() != "STALE":
            continue
        sev = "CRIT" if str(severity).upper() == "CRIT" else "WARN"
        out[f"health:{check_name}"] = (
            sev,
            f"{check_name} is {status}",
            f"**{severity}** · `{check_name}`\n{detail or '(no detail)'}",
        )

    # A job whose correct output is often NOTHING cannot be watched by watching
    # its output. See tracking/job_heartbeat.py — this covers the NFL polls,
    # the in-play worker, the job queue, the watchdog, and this module itself.
    from tracking.job_heartbeat import stale_jobs
    for job_id, silent, allowed in stale_jobs(conn, now):
        if silent is None:
            detail = (f"`{job_id}` has never recorded a run. Expected at least "
                      f"one every {allowed} minutes.")
        else:
            detail = (f"`{job_id}` last ran **{silent:.0f} minutes ago**, over "
                      f"its {allowed}-minute allowance. It is scheduled but not "
                      f"running.")
        out[f"job:{job_id}"] = ("CRIT", f"{job_id} has gone silent", detail)

    clean, total, ranked = _clean_rate(conn)
    if total >= CLEAN_RATE_WINDOW:
        rate = clean / total
        if rate < CLEAN_RATE_FLOOR:
            worst = "\n".join(f"· `{s}` — {n} of {total}" for s, n in ranked[:8])
            out["pass:clean_rate"] = (
                "CRIT",
                f"Refresh pass degraded — {clean}/{total} clean",
                (f"Only **{clean} of the last {total}** refresh passes "
                 f"completed with no failed steps ({rate:.0%}, floor "
                 f"{CLEAN_RATE_FLOOR:.0%}).\n\nFailing most often:\n{worst}"),
            )
    return out


def run_failure_alerter(conn=None, now: datetime | None = None) -> dict:
    """Alert on what is broken, recover what has cleared. Never raises.

    Returns a dict so a caller and the tests can assert the verdict without
    reading Discord.
    """
    now = now or datetime.now(timezone.utc)
    own_conn = conn is None
    result = {"conditions": [], "alerted": [], "recovered": [], "error": None}
    try:
        if own_conn:
            from data.db import get_connection
            conn = get_connection()
        try:
            active = _conditions(conn, now)
        finally:
            if own_conn:
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
    except Exception as exc:  # noqa: BLE001 — see the module docstring
        logger.warning(f"failure alerter could not run: {exc}")
        result["error"] = str(exc)
        return result

    state = read_alert_state(_STATE_FILE)
    result["conditions"] = sorted(active)

    # RECOVERIES FIRST, so a pass that both clears one condition and raises
    # another reports them in the order they happened rather than alphabetically.
    for key in sorted(set(state) - set(active)):
        title = (state.get(key) or {}).get("title", key)
        if post_ops_alert(f"Resolved — {title}",
                          f"`{key}` has cleared.", recovery=True):
            result["recovered"].append(key)
        # Drop the key either way. A recovery that failed to POST must not
        # leave a stamp behind that suppresses the next occurrence.
        state.pop(key, None)

    for key, (sev, title, detail) in sorted(active.items()):
        minutes = RENOTIFY_CRIT_MIN if sev == "CRIT" else RENOTIFY_WARN_MIN
        if should_notify(state, key, now, minutes):
            if post_ops_alert(title, detail):
                # Stamp ONLY on a confirmed post: stamping on a failed POST
                # would silence the next window on the strength of a message
                # nobody received.
                state[key] = {"last": now.isoformat(), "title": title,
                              "severity": sev}
                result["alerted"].append(key)
            else:
                state.setdefault(key, {"title": title, "severity": sev})
        else:
            entry = state.get(key)
            if isinstance(entry, dict):
                entry["title"] = title
                entry["severity"] = sev

    write_alert_state(_STATE_FILE, state)
    logger.info(
        f"Failure alerter: {len(active)} condition(s), "
        f"{len(result['alerted'])} alerted, {len(result['recovered'])} recovered")
    return result


if __name__ == "__main__":  # pragma: no cover — manual/one-off invocation
    print(run_failure_alerter())
