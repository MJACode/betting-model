#!/usr/bin/env python
"""Always-on scheduler for the betting pipeline — replaces the GitHub Actions crons.

WHY THIS EXISTS
---------------
The pipeline used to be triggered by three scheduled Actions workflows
(daily_pipeline.yml, refresh_picks.yml, evening_lines.yml). On a private repo that
burned ~10,000 Actions minutes/month against a 2,000 free cap — the evening loop alone
held a paid runner idle ~55 min/night. This process runs the exact same cadence on a
cheap always-on worker (Railway/Render, ~$5/mo flat) instead, so Actions minutes drop
to ~zero.

WHAT IT DOES
------------
Reproduces the three Actions cadences with a real, DST-aware timezone (America/New_York),
which also fixes the "shifts 1 hour in winter (EST)" caveat every old workflow carried:

  * Daily full pipeline   6:00am ET            -> python run_pipeline.py
  * Hourly refresh        :17, 7am-5pm ET      -> bash scripts/refresh_pass.sh
  * Evening 10-min refresh every :00..:50, 6-11pm ET -> bash scripts/refresh_pass.sh

It shells out to the EXISTING entrypoints — it does not re-implement any pipeline logic.
scripts/refresh_pass.sh stays the single source of truth for the refresh step chain, so
behavior is byte-identical to the old Actions runs. Each job uses max_instances=1 +
coalesce=True (the analog of the Actions `concurrency` group): a long-running pass queues
the next tick instead of double-fetching. A failed pass is logged and never kills the
scheduler.

RUN IT
------
  python scheduler.py            # blocks forever; this is the worker's start command

Required env (same secrets as the old GitHub Actions workflows):
  DATABASE_URL, ODDS_API_KEY, DATAGOLF_API_KEY
Optional:
  TZ=America/New_York            # belt-and-suspenders; the scheduler sets its own tz too
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
TIMEZONE = "America/New_York"  # DST-aware — 6am ET is 6am ET year-round.

# FETCH_F5_LIVE=1 mirrors what every workflow set; ensure it's on for subprocesses.
BASE_ENV = {**os.environ, "FETCH_F5_LIVE": os.environ.get("FETCH_F5_LIVE", "1")}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("scheduler")


# ---------------------------------------------------------------------------
# Jobs — each just runs an existing entrypoint as a subprocess.
# ---------------------------------------------------------------------------

def _run(cmd: list[str], label: str) -> None:
    """Run a pipeline entrypoint, logging start/stop. Never raises — a failed run
    must not tear down the long-lived scheduler process."""
    log.info("START %s: %s", label, " ".join(cmd))
    try:
        result = subprocess.run(cmd, cwd=ROOT, env=BASE_ENV, check=False)
        if result.returncode == 0:
            log.info("DONE  %s (exit 0)", label)
        else:
            log.warning("FAIL  %s (exit %s)", label, result.returncode)
    except Exception:  # noqa: BLE001 - keep the scheduler alive no matter what
        log.exception("ERROR %s crashed", label)


def run_daily_pipeline() -> None:
    # Bare invocation == run_pipeline.run_daily_pipeline() (settle, ingest, score,
    # game log, prop scoring, health check).
    _run([sys.executable, "run_pipeline.py"], "daily-pipeline")


def run_refresh_pass() -> None:
    # The single-source-of-truth refresh chain (odds + prop odds + lineups + scoring
    # for every sport, opening-signals, parlay record, push notifications).
    _run(["bash", "scripts/refresh_pass.sh"], "refresh-pass")


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

def build_scheduler() -> BlockingScheduler:
    sched = BlockingScheduler(
        timezone=TIMEZONE,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    # Daily full pipeline — 6:00am ET (was daily_pipeline.yml).
    sched.add_job(
        run_daily_pipeline,
        CronTrigger(hour=6, minute=0, timezone=TIMEZONE),
        id="daily_pipeline",
        name="Daily full pipeline (6:00am ET)",
    )

    # Hourly refresh — :17 past the hour, 7am-5pm ET (was refresh_picks.yml, 11 runs).
    sched.add_job(
        run_refresh_pass,
        CronTrigger(hour="7-17", minute=17, timezone=TIMEZONE),
        id="hourly_refresh",
        name="Hourly refresh (7am-5pm ET, :17)",
    )

    # Evening fast lines — every 10 minutes, 6pm-11pm ET (was evening_lines.yml's
    # runner-holding sleep loop, now just a real */10 cron on an always-on worker).
    sched.add_job(
        run_refresh_pass,
        CronTrigger(hour="18-23", minute="*/10", timezone=TIMEZONE),
        id="evening_refresh",
        name="Evening 10-min refresh (6-11pm ET)",
    )

    return sched


def main() -> None:
    from datetime import datetime

    sched = build_scheduler()
    now = datetime.now(sched.timezone)
    log.info("Betting scheduler starting (timezone=%s). Registered jobs:", TIMEZONE)
    for job in sched.get_jobs():
        # next_run_time isn't populated until the scheduler starts, so compute the
        # next fire directly from the trigger for the startup banner.
        try:
            nxt = job.trigger.get_next_fire_time(None, now)
        except Exception:  # noqa: BLE001
            nxt = "?"
        log.info("  - %s [%s] next: %s", job.id, job.name, nxt)
    log.info("Scheduler running. Ctrl-C to stop.")
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")


if __name__ == "__main__":
    main()
