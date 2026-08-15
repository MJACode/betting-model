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
  * In-play live loop     */10 supervisor, 11am-midnight ET
        -> python -m data.ingestors.live_trigger_orchestrator --loop
        (poller + orchestrator + live scorer; exits when no games are live, the
        supervisor tick relaunches it; disable with RUN_LIVE_LOOP=0)
  * NFL wind-totals card  Thu/Sat/Sun/Mon mornings ET (in season)
        -> python scripts/weekly_wind_card.py, run from the standalone nfl/ package
        (the Section-28 runbook cadence, plus a Monday run so MNF is priced;
        ~5 Odds API credits/week, billed to the existing ODDS_API_KEY unless a
        dedicated THE_ODDS_API_KEY is set; no-ops for free when no games are in
        window; disable with RUN_NFL_WIND_CARD=0)

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
  THE_ODDS_API_KEY               # OPTIONAL override: a dedicated Odds API key for the
                                 # nfl/ wind card. Not needed — the card falls back to
                                 # ODDS_API_KEY (same service, ~5 credits/week). With
                                 # neither set it runs --dry-run (weather only).
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

# In-play (live) betting loop — set RUN_LIVE_LOOP=0 to disable without a redeploy
# of code (kill switch; credit safety inside the loop is LIVE_DAILY_CREDIT_CAP).
RUN_LIVE_LOOP = os.environ.get("RUN_LIVE_LOOP", "1") != "0"

# NFL wind-totals card (the standalone nfl/ package, CLAUDE.md Section 28) — set
# RUN_NFL_WIND_CARD=0 to disable without a redeploy. The card itself exits 0 with
# "No games in window." before any odds call on off-days/off-season, so leaving it
# scheduled year-round costs nothing outside the NFL season.
RUN_NFL_WIND_CARD = os.environ.get("RUN_NFL_WIND_CARD", "1") != "0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("scheduler")


# ---------------------------------------------------------------------------
# Jobs — each just runs an existing entrypoint as a subprocess.
# ---------------------------------------------------------------------------

def _run(cmd: list[str], label: str, cwd: Path | None = None,
         env: dict[str, str] | None = None) -> None:
    """Run a pipeline entrypoint, logging start/stop. Never raises — a failed run
    must not tear down the long-lived scheduler process."""
    log.info("START %s: %s", label, " ".join(cmd))
    try:
        result = subprocess.run(cmd, cwd=cwd or ROOT, env=env or BASE_ENV, check=False)
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


def run_live_loop() -> None:
    # The in-play betting loop (state poller every 15s + trigger orchestrator +
    # live scorer). It EXITS on its own after ~1 min with no active games, so this
    # job acts as a supervisor: the */10 cron relaunches it whenever it isn't
    # running. While a slate is live one invocation runs for hours and
    # max_instances=1 makes the intervening ticks no-ops (APScheduler logs a
    # "maximum number of running instances" warning for each skipped tick —
    # expected, and a useful heartbeat that the loop is alive). Idle attempts
    # cost ~4 DB polls and zero Odds API credits; in-play credit burn is capped
    # by LIVE_DAILY_CREDIT_CAP (config default 1000/day).
    _run(
        [sys.executable, "-m", "data.ingestors.live_trigger_orchestrator", "--loop"],
        "live-loop",
    )


def run_nfl_wind_card(days: int, regions: str = "us") -> None:
    # The Section-28 wind-totals bet card from the standalone nfl/ package. MUST run
    # with cwd=nfl/ — the script reads data/games.csv and writes data/cards/ relative
    # to its package root. It exits 0 before any odds call when no games are in the
    # window, so off-season/off-day runs are free.
    #
    # The nfl/ package (developed externally) reads THE_ODDS_API_KEY — a different
    # env var NAME for the same Odds API service the platform already uses. No new
    # Railway variable is needed: we fall back to the platform's ODDS_API_KEY, whose
    # quota the card barely touches (~5 credits/week in season). Set THE_ODDS_API_KEY
    # in Railway Variables only if you ever want the NFL card on its own key/quota —
    # it takes precedence. With neither set, fall back to --dry-run instead of
    # letting the script SystemExit every week: the weather side of the card still
    # prints to the worker log at 0 credits.
    #
    # The printed card in the Railway log is the deliverable — the CSV the script also
    # writes (nfl/data/cards/) lands on the worker's EPHEMERAL disk and is lost on
    # redeploy. Same for the package's credit ledger (nfl/data/credit_ledger.json):
    # it resets per deploy, which is fine — it's telemetry, not the quota itself.
    cmd = [sys.executable, "scripts/weekly_wind_card.py", "--days", str(days),
           "--regions", regions]
    env = dict(BASE_ENV)
    key = env.get("THE_ODDS_API_KEY") or env.get("ODDS_API_KEY")
    if key:
        env["THE_ODDS_API_KEY"] = key
    else:
        log.warning("Neither THE_ODDS_API_KEY nor ODDS_API_KEY is set — running NFL "
                    "wind card in --dry-run (weather only, no priced card).")
        cmd.append("--dry-run")
    _run(cmd, f"nfl-wind-card-{days}d", cwd=ROOT / "nfl", env=env)


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

    # In-play live betting loop — supervisor ticks every 10 minutes, 11am-11:59pm ET.
    # Window rationale: earliest MLB first pitches are ~12:05pm ET (holiday/getaway
    # day games), and the loop treats a game as active LIVE_PREGAME_BUFFER_MIN (15
    # min) before first pitch, so 11am attempts always beat the first game. A loop
    # started late evening keeps running PAST the window until the last west-coast
    # game ends (~1-2am) — the cron only governs (re)launch attempts, not runtime.
    if RUN_LIVE_LOOP:
        sched.add_job(
            run_live_loop,
            CronTrigger(hour="11-23", minute="*/10", timezone=TIMEZONE),
            id="live_loop",
            name="In-play live loop supervisor (11am-midnight ET, */10)",
        )
    else:
        log.info("RUN_LIVE_LOOP=0 — in-play live loop NOT scheduled.")

    # NFL wind-totals card — the Section-28 runbook cadence (Thu scan / Sat firm /
    # Sun place), plus a Monday-morning run the runbook lacks: Sunday's --days 1
    # window closes before Monday-night kickoff, so without it MNF would never be
    # priced. "Later is better" per the runbook (the edge is vs the close and
    # forecast skill improves), so each run simply re-prices whatever is left in
    # its window. ~5 credits/week in season on THE_ODDS_API_KEY; zero off-season.
    if RUN_NFL_WIND_CARD:
        for dow, hour, days, regions in (
            ("thu", 9, 4, "us"),        # scan the whole slate (incl. TNF tonight)
            ("sat", 9, 2, "us"),        # firm forecast for the Sunday slate
            ("sun", 8, 1, "us,eu"),     # place: shop wider on game morning
            ("mon", 9, 1, "us"),        # cover Monday Night Football
        ):
            sched.add_job(
                run_nfl_wind_card,
                CronTrigger(day_of_week=dow, hour=hour, minute=0, timezone=TIMEZONE),
                args=[days, regions],
                id=f"nfl_wind_card_{dow}",
                name=f"NFL wind card ({dow.capitalize()} {hour}am ET, --days {days})",
            )
    else:
        log.info("RUN_NFL_WIND_CARD=0 — NFL wind card NOT scheduled.")

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
