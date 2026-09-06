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
        window; disable with RUN_NFL_WIND_CARD=0. After each LIVE card run,
        scripts/nfl_wind_publisher.py mirrors the qualifying bets into the
        games + picks tables so they surface in the mobile app.)
  * NFL opener-spread card daily 9:30am ET (in season)
        -> python scripts/daily_opener_card.py from nfl/, then the publisher
        in --opener mode (insert-once lock — opener bets are taken at the
        first qualifying moment and never re-priced; the edge is staleness).
        2 credits/run on the same key; RUN_NFL_WIND_CARD=0 disables both NFL
        card jobs together.

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

from datetime import date, datetime, timedelta

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent
TIMEZONE = "America/New_York"  # DST-aware — 6am ET is 6am ET year-round.

# FETCH_F5_LIVE=1 mirrors what every workflow set; ensure it's on for subprocesses.
# PYTHONPATH carries the repo root into every child process, including the ones
# that run with cwd=nfl/ — without it those cannot `import monitoring` to record
# their own API traffic.
BASE_ENV = {
    **os.environ,
    "FETCH_F5_LIVE": os.environ.get("FETCH_F5_LIVE", "1"),
    "PYTHONPATH": os.pathsep.join(
        [str(ROOT)] + ([os.environ["PYTHONPATH"]] if os.environ.get("PYTHONPATH") else [])
    ),
}

# In-play (live) betting loop — set RUN_LIVE_LOOP=0 to disable without a redeploy
# of code (kill switch; credit safety inside the loop is LIVE_DAILY_CREDIT_CAP).
RUN_LIVE_LOOP = os.environ.get("RUN_LIVE_LOOP", "1") != "0"

# DraftKings' OWN in-play feed (data/ingestors/dk_direct_feed.py).
# DEFAULT OFF. Measured 2026-08-30, it captures 1,890 distinct in-play quotes
# where the aggregator gives 654 on the same games, and prices at ~5s instead of
# a ~67s cache. It writes into `odds` as bookmaker='draftkings' with
# source='dk_direct', so the live scorer picks it up with no code change -- which
# is exactly why it is opt-in rather than on by default: turning it on changes
# what every live MLB model prices against, and that is a decision, not a deploy.
RUN_DK_DIRECT_FEED = os.environ.get("RUN_DK_DIRECT_FEED", "0") != "0"

# Bovada's OWN in-play feed (data/ingestors/bovada_direct_feed.py).
# DEFAULT OFF, but unlike the DK feed this one CAN run here: probed 2026-08-31
# it was the only book of seven that answered the worker (200, 802 KB, no key,
# no impersonation). It is a BEST-LINE source only -- rows are written as
# bookmaker='bovada', so _best_live_price can shop them and _get_live_dk_odds
# structurally cannot see them.
RUN_BOVADA_FEED = os.environ.get("RUN_BOVADA_FEED", "0") != "0"
# NCAAF live gameday loop (ncaaf_live/) — set RUN_NCAAF_LIVE=0 to disable
RUN_NCAAF_LIVE = os.environ.get("RUN_NCAAF_LIVE", "1") != "0"

# NFL wind-totals card (the standalone nfl/ package, docs/sports/nfl.md) — set
# RUN_NFL_WIND_CARD=0 to disable without a redeploy. The card itself exits 0 with
# "No games in window." before any odds call on off-days/off-season, so leaving it
# scheduled year-round costs nothing outside the NFL season.
RUN_NFL_WIND_CARD = os.environ.get("RUN_NFL_WIND_CARD", "1") != "0"

# NFL player-prop market card (models/nfl_prop_market, docs §5c) — the
# de-vig-Pinnacle-bet-the-outlier rule. RUN_NFL_PROP_CARD=0 disables it.
RUN_NFL_PROP_CARD = os.environ.get("RUN_NFL_PROP_CARD", "1") != "0"

# NCAAF player props (data/ingestors/ncaaf_prop_odds_ingestor.py). Matt turned
# these on 2026-09-05 after the probe measured them: ~8.7 credits per event
# against 68 events the feed lists, so ONE FULL PASS IS ~590 CREDITS and the
# three below cost ~1,800 on a Saturday. That is affordable enough that the
# ceiling is coverage, not money -- which is why this is three passes and not
# hourly: the lines are the Stats board's research column, not a model input,
# and nothing measured says a college prop line moves enough between 9am and
# 1pm to be worth 11 more passes.
#
# Scheduled DAILY, not on Saturdays: college football also plays Thursday and
# Friday nights and the odd Tuesday in November. A day with no events costs
# NOTHING -- the ingestor returns before any paid call, and the /events listing
# it reads first is free (measured: credits null).
RUN_NCAAF_PROP_ODDS = os.environ.get("RUN_NCAAF_PROP_ODDS", "0") == "1"

# NFL in-play gameday worker (nfl/live_model). Polls ESPN state every 10s and
# prices the one validated lane, live pass attempts. Set RUN_NFL_LIVE=0 to
# disable without a redeploy. It is PAPER ONLY: the executor records decisions
# to a JSONL audit log and alerts nobody, so a bad tick costs a poll.
RUN_NFL_LIVE = os.environ.get("RUN_NFL_LIVE", "1") != "0"

# Hours before kickoff inside which the prop card polls. 30 brackets BOTH
# measured offsets (T-24h and T-3h) without extrapolating far past them.
#
# The window matters because publishing LOCKS insert-once: a pick taken at an
# offset where the edge is noise is a locked bet, not a discarded one. T-24h and
# T-3h are measured (+4.05% / +0.73%, indistinguishable), and the pair is worth
# polling because only 13% of edges are the same proposition at both — a second
# look roughly doubles distinct bets rather than re-confirming the first.
# Everything beyond that is unmeasured, so the window stops just past T-24h.
NFL_PROP_WINDOW_HOURS = float(os.environ.get("NFL_PROP_WINDOW_HOURS", "30"))

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


def _publish_new_signals(label: str) -> None:
    """Lock and deliver whatever BETs the job that just ran wrote.

    THE RULE (2026-09-05, mike: "when there is a bet from the model, post the
    pick"): a job that WRITES picks publishes them itself. Leaving that to the
    next hourly refresh pass is how a UFC moneyline written 13 minutes before
    its fight was first locked 43 minutes after the opening bell, and so was
    never postable at all.

    In-process, like the watchdog above, because the whole point is that it
    reaches Discord: a subprocess reports failure as an exit code nobody reads.
    `publish_new_signals` guards each surface itself and never raises; the
    try here is for the import.
    """
    try:
        from tracking.signal_publisher import publish_new_signals
        out = publish_new_signals()
        if any(out.values()):
            log.info("publish [%s]: %s", label, out)
    except Exception:  # noqa: BLE001 - publishing must never kill the scheduler
        log.exception("ERROR publish after %s crashed", label)


def run_daily_pipeline() -> None:
    # Bare invocation == run_pipeline.run_daily_pipeline() (settle, ingest, score,
    # game log, prop scoring, health check).
    _run([sys.executable, "run_pipeline.py"], "daily-pipeline")


def run_refresh_pass(mode: str = "hourly") -> None:
    # The single-source-of-truth refresh chain (odds + prop odds + lineups + scoring
    # for every sport, opening-signals, parlay record, push notifications).
    _run(["bash", "scripts/refresh_pass.sh", mode], f"refresh-pass[{mode}]")


def run_savant_refresh() -> None:
    _run([sys.executable, "run_pipeline.py", "--step", "savant"], "savant-refresh")


def run_pipeline_watch() -> None:
    # The pipeline watch. In-process for the same reason as the watchdog and
    # the review: its output is a Discord post, not an exit code.
    #
    # This was a scheduled Claude session (Sentinel) until 2026-09-03. It read
    # the database through the Supabase MCP, and Routine sessions carry no
    # mcp__* entry in their permitted-tool list, so every read raised a
    # permission prompt -- which unattended killed two consecutive runs in
    # REQUIRES_ACTION, and attended just paged a person every morning. The
    # worker already holds DATABASE_URL and the Discord webhook, so it can do
    # the reading without asking anyone.
    try:
        from data.db import get_connection
        from tracking.pipeline_watch import run_watch
        conn = get_connection()
        try:
            result = run_watch(conn)
        finally:
            conn.close()
        log.info("PipelineWatch: %s", result.get("status"))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR pipeline-watch crashed")


def run_model_calibration() -> None:
    # ModelCalibration — the weekly re-measure of every model. In-process for
    # the same reason as the watchdog and the review: its output is a Discord
    # post and a table, not an exit code.
    try:
        from data.db import get_connection
        from tracking.model_calibration_agent import run_agent
        conn = get_connection()
        try:
            result = run_agent(conn)
        finally:
            conn.close()
        log.info("ModelCalibration: %s", result.get("status"))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR model-calibration crashed")


def run_calibration_watch() -> None:
    # The ModelCalibration JUDGEMENT pass. The sweep above writes the rows;
    # this reads them and says what changed. In-process for the same reason as
    # the sweep and the pipeline watch: its output is a Discord post and a
    # push_sent row, not an exit code.
    #
    # It is deliberately a SEPARATE job from run_model_calibration rather than
    # a tail call inside it. A judgement pass that runs inside the job
    # producing its inputs cannot report on a sweep that did not finish -- the
    # same reasoning that keeps the threshold review out of the pipeline.
    try:
        from data.db import get_connection
        from tracking.calibration_watch import run_calibration_watch as _run
        conn = get_connection()
        try:
            result = _run(conn)
        finally:
            conn.close()
        log.info("CalibrationWatch: %s", result.get("status"))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR calibration-watch crashed")


def run_job_queue() -> None:
    # The worker's answer to "why on my machine?". Claims at most one queued job
    # per tick and runs it here, in-process, where DATABASE_URL, ODDS_API_KEY and
    # open egress already are.
    #
    # A retrain runs for an hour. That is fine: APScheduler's default pool is ten
    # threads, so a long job occupies one while every other schedule keeps
    # firing, and max_instances=1 makes the ticks during it no-ops.
    try:
        from data.db import get_connection
        from tracking.job_queue import run_one
        conn = get_connection()
        try:
            result = run_one(conn)
        finally:
            conn.close()
        if result.get("status") != "idle":
            log.info("job queue: %s", result.get("status"))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR job-queue crashed")


def run_threshold_review() -> None:
    # In-process for the same reason as the watchdog: its output is a Discord
    # post and a pause, not an exit code, so an exception here must surface as
    # a scheduler error rather than a subprocess return value nobody reads.
    #
    # It is a no-op on most days by design -- the rule fires at fixed slate-wide
    # milestones (250 settled bets, then 500, ...) rather than continuously,
    # because a pause rule re-evaluated daily eventually fires on noise, which
    # is the same mistake as the sweep it exists to check.
    try:
        from data.db import get_connection
        from tracking.threshold_review import run_review
        conn = get_connection()
        try:
            result = run_review(conn)
        finally:
            conn.close()
        log.info("threshold review: %s", result.get("status"))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR threshold-review crashed")


def run_heartbeat_watchdog() -> None:
    # Called IN-PROCESS rather than through _run's subprocess, deliberately.
    # _run reports failure by logging it, and a log line is exactly the channel
    # that went unread for nine hours on 2026-08-31. The watchdog's whole
    # contract is that it reaches Discord itself, so it is imported and called
    # here where an unexpected exception is visible as a scheduler error rather
    # than an exit code nobody reads.
    try:
        from tracking.heartbeat_watchdog import run_watchdog
        result = run_watchdog()
        log.info("watchdog: %s (notified=%s)", result["status"], result["notified"])
    except Exception:  # noqa: BLE001 - the watchdog must never kill the scheduler
        log.exception("ERROR heartbeat-watchdog crashed")


def run_bovada_feed() -> None:
    # Same supervisor shape as the others: exits after --minutes, the */10 cron
    # relaunches it, max_instances=1 makes intervening ticks no-ops.
    _run(
        [sys.executable, "-m", "data.ingestors.bovada_direct_feed",
         "--minutes", "15"],
        "bovada-feed",
    )


def run_dk_direct_feed() -> None:
    # Same supervisor shape as run_live_loop: the feed exits on its own after
    # --minutes, and the */10 cron relaunches it, so a crash costs one tick
    # rather than the evening. max_instances=1 makes the intervening ticks
    # no-ops while a slate is live.
    _run(
        [sys.executable, "-m", "data.ingestors.dk_direct_feed",
         "--sports", "MLB", "--minutes", "15"],
        "dk-direct-feed",
    )


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


# ── Service role ─────────────────────────────────────────────────────────────
# One image, two services. Until 2026-08-30 the refresh pass, both live loops,
# the NFL worker and the pre-game poller all ran in ONE container, so every
# deploy restarted all of them: on 2026-08-30 four consecutive refresh passes
# died mid-chain that way, and the day's recap sat unposted for five hours as a
# result.
#
# This does NOT exist for throughput. The worker peaks at 1.1GB of 8GB and 1.4
# of 8 CPUs, and every slow step is waiting on a socket — a second machine does
# not make a socket answer faster. It exists to shrink the BLAST RADIUS: a
# deploy to the pipeline should not be able to kill a poller mid-tick.
#
# SERVICE_ROLE is read from the environment so both services deploy the same
# commit. Default "all" preserves today's single-container behaviour exactly,
# so this is inert until the second Railway service actually sets a role —
# a split that half-lands must never leave a job running nowhere.
SERVICE_ROLE = os.environ.get("SERVICE_ROLE", "all").strip().lower()

# Which roles own which jobs. A job with no entry here runs under "all" only.
_PIPELINE_JOBS = {"daily_pipeline", "hourly_refresh", "evening_refresh",
                  "overnight_refresh", "nfl_poll_hourly", "nfl_poll_10min",
                  "savant_refresh", "threshold_review",
                  "model_calibration", "job_queue", "pipeline_watch",
                  "calibration_watch"}
# nfl_live_worker is deliberately NOT here. It writes its decision log to
# DECISION_LOG_DIR on the Railway VOLUME mounted at /data, and a Railway volume
# attaches to exactly one service. Moving the worker to the poller service would
# leave it writing to an empty path -- silently, since the log is append-only
# audit output nothing reads back in real time. A split audit trail is worse
# than a worker that a deploy can restart, so it stays with the volume until
# either the log moves into Supabase (CLAUDE.md §1b lists it as still outside)
# or the poller service gets its own volume.
_POLLER_JOBS = {"pregame_poller", "live_loop", "ncaaf_live_loop",
                "dk_direct_feed", "bovada_feed"}

# Jobs that run on EVERY service, whatever its role. Only the watchdog belongs
# here, and for the one reason that justifies the duplication: a monitor hosted
# inside the thing it monitors cannot report its own container dying. Running it
# on both services means the poller still speaks when the pipeline service is
# down, and vice versa. The cost is at most one duplicate alert during a
# genuine outage, which is the right side of that trade.
_ALWAYS_JOBS = {"heartbeat_watchdog"}


def owns(job_id: str) -> bool:
    """True when THIS service should schedule that job.

    Fails OPEN on an unknown role: a typo in SERVICE_ROLE must leave the
    scheduler running everything, never running nothing. A container that
    silently schedules no jobs is indistinguishable from a quiet market — §7's
    recurring failure mode, and the reason this defaults to "all".
    """
    if job_id in _ALWAYS_JOBS:
        return True
    if SERVICE_ROLE == "pipeline":
        return job_id not in _POLLER_JOBS
    if SERVICE_ROLE in ("poller", "pollers"):
        return job_id in _POLLER_JOBS
    return True


def run_pregame_poller() -> None:
    # The 30-second pre-game line watcher. Same supervisor shape as the live
    # loops: the */10 cron relaunches it if it is not running, and
    # max_instances=1 makes the intervening ticks no-ops while it is.
    #
    # Unlike the live loops this one does NOT exit on its own — unstarted games
    # exist around the clock, which is the whole point (mike, 2026-08-30:
    # "that should be the cadence 24x7"). So in steady state this cron fires
    # once and every later tick is a skipped no-op; the APScheduler "maximum
    # number of running instances" warning is the heartbeat that it is alive.
    #
    # It is stopped by RUN_PREGAME_POLLER=0 in Railway rather than by removing
    # the job, so a runaway can be halted without a deploy. Burn is capped by
    # PREGAME_POLL_DAILY_CREDIT_CAP.
    _run(
        [sys.executable, "-m", "data.ingestors.pregame_line_poller"],
        "pregame-poller",
    )


def run_nfl_live_worker() -> None:
    # Supervisor for the NFL in-play worker, exactly the shape run_live_loop
    # uses: the worker polls ESPN every POLL_STATE_SEC (10s) and exits on its
    # own when no game is live, so this cron relaunches it rather than keeping
    # a process parked. max_instances=1 makes the ticks during a live slate
    # no-ops, and APScheduler's "maximum number of running instances" warning
    # is the heartbeat that it is still running.
    #
    # Idle ticks are FREE: with no live game the worker reaches no hunt state
    # and never calls the odds API. Credit burn while a slate is live is capped
    # by the CreditMeter inside the worker.
    #
    # MUST run with cwd=nfl/ — the package resolves data/ relative to its own
    # root, and the decision log defaults onto that path.
    _run(
        [sys.executable, "-m", "live_model.workers.gameday"],
        "nfl-live",
        cwd=str(Path(__file__).parent / "nfl"),
        env={**BASE_ENV,
             "THE_ODDS_API_KEY": os.environ.get("THE_ODDS_API_KEY")
             or os.environ.get("ODDS_API_KEY", "")},
    )


def run_ncaaf_live_loop() -> None:
    # The NCAAF live gameday loop (ncaaf_live/gameday.py) under the same
    # supervisor pattern as the MLB live loop: it EXITS itself after ~30 idle
    # minutes with nothing live, so the */10 cron just relaunches it; during a
    # slate one invocation runs for hours and max_instances=1 skips the
    # intervening ticks. On the worker, site.api.espn.com is 403-blocked, so
    # --source cfbd pins the CFBD /scoreboard state feed (keyed, reachable —
    # the same host the weekly NCAAF step already uses). Idle invocations cost
    # one CFBD call and zero Odds API credits -- true only since the loop learned
    # to exit immediately when no kickoff is near. It previously polled for a
    # full 30 idle minutes before exiting and this supervisor relaunched it, so
    # it billed CFBD at ~86% duty cycle 11am-midnight whether or not anything
    # was live. Live burn is ~4 credits/min, session-capped inside the loop.
    _run(
        [sys.executable, "-m", "ncaaf_live.gameday", "--source", "cfbd"],
        "ncaaf-live-loop",
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
    # Mirror the card into the app (games + picks tables) — LIVE runs only.
    # A dry-run card has no prices and writes no CSV, so the publisher is
    # skipped without a key. Since 2026-08-22 the wind publisher is INSERT-ONCE
    # like the opener: a locked pick is never re-priced or removed, and a
    # forecast that later collapses is flagged by scripts.nfl_pick_monitor
    # rather than deleting the bet.
    if key:
        _run([sys.executable, "-m", "scripts.nfl_wind_publisher"], "nfl-wind-publish")


NFL_POLL_HORIZON_DAYS = 10.0   # start watching this far out
NFL_FAST_WINDOW_HOURS = float(os.environ.get("NFL_FAST_WINDOW_HOURS", "24"))
# Inside this many hours to kickoff, poll every 10 minutes instead of hourly.
#
# 3 -> 24 on 2026-09-05 (Matt). The 10-minute tier was meant to cover the
# run-up to kickoff and only reached T-3h, so T-24h..T-3h -- the window the
# opener rule actually fires in, and where the wind forecast firms up --
# resolved at one tick an hour. Cost is ~6 credits a tick (wind us,eu +
# opener us,eu), so the extra 126 ticks a kickoff-day are ~750 credits
# against a 4.71M balance and a ~46-76k/day burn: immaterial.


def _nfl_lead_hours() -> float | None:
    """Hours to the next NFL kickoff, or None if nothing is scheduled ahead."""
    import csv as _csv
    from datetime import datetime as _dt, timezone as _tz
    from zoneinfo import ZoneInfo as _ZI
    path = ROOT / "nfl" / "data" / "games.csv"
    if not path.exists():
        return None
    now = _dt.now(_tz.utc)
    best = None
    try:
        with path.open(newline="", encoding="utf-8") as fh:
            for row in _csv.DictReader(fh):
                day, tod = row.get("gameday"), row.get("gametime")
                if not day or not tod:
                    continue
                try:
                    kick = _dt.fromisoformat(f"{day} {tod}").replace(
                        tzinfo=_ZI("America/New_York")).astimezone(_tz.utc)
                except ValueError:
                    continue
                lead = (kick - now).total_seconds() / 3600.0
                if lead > 0 and (best is None or lead < best):
                    best = lead
    except OSError:
        return None
    return best


def run_nfl_poll(fast: bool = False) -> None:
    """
    One NFL poll tick: both models, then publish, then record history.

    CADENCE (set 2026-08-22): watch from 10 days out, hourly, and every 10
    minutes once a kickoff is inside 3 hours. The two jobs are mutually
    exclusive — the hourly one stands down inside the fast window so a tick is
    never paid for twice.

    Firing stays inside each model's VALIDATED window. Polling early does not
    mean betting early: at 10 days out Pinnacle has not posted (it arrives
    ~T-6.5), so the opener has nothing to compare against, and wind does not
    fire past `wind_totals.MAX_FIRE_LEAD`. Watching from T-10 buys the first
    fireable moment, not an earlier bet.

    That was an ASPIRATION in this comment and not true in the code between
    2026-09-05 and 2026-09-06: nothing gated wind firing, so the `--days` handed
    to the card below -- the poll horizon, 10 -- was the firing window too, and
    all five Week 1 picks locked at leads of 7.2 to 8.7 days. The gate now lives
    in the model where every caller gets it, not in this argument.

    Cost is ~4 credits a tick (2 markets x 2 regions), and zero when no game is
    inside the horizon, which is most of the year.
    """
    lead = _nfl_lead_hours()
    if lead is None or lead > NFL_POLL_HORIZON_DAYS * 24:
        return                                  # nothing within the horizon: free
    inside_fast = lead <= NFL_FAST_WINDOW_HOURS
    if fast != inside_fast:
        return                                  # the other job owns this tick

    label = "fast" if fast else "hourly"
    log.info("NFL poll (%s): next kickoff in %.1fh", label, lead)
    run_nfl_wind_card(int(NFL_POLL_HORIZON_DAYS), "us,eu")
    run_nfl_opener_card()
    # Record what the models thought of every game this tick, and flag any
    # locked pick whose conditions have changed. Never re-prices anything.
    _run([sys.executable, "-m", "scripts.nfl_pick_monitor"], "nfl-pick-monitor")
    # PUBLISH WHAT THE CARD JUST WROTE. Same reason as the pre-game poller
    # (2026-09-05): a writer outside the refresh pass used to leave its picks
    # sitting until the next :17 pass captured them, and inside the 3-hour fast
    # window that lag can outlast the kickoff the pick was for. Idempotent and
    # non-raising, so an extra call on a tick that wrote nothing is three cheap
    # reads.
    _publish_new_signals("nfl-poll")


def run_ncaaf_prop_odds() -> None:
    """One college prop pass: the scoped slate, every book, standard + alternate.

    A clean no-op off-season and on days with no games -- the ingestor lists
    events first (a free call) and returns before spending anything.
    """
    _run([sys.executable, "-m", "data.ingestors.ncaaf_prop_odds_ingestor"],
         "ncaaf-prop-odds")


def run_nfl_prop_card() -> None:
    """
    One prop-card tick: fetch the board, price it, publish what qualifies.

    Runs HOURLY inside NFL_PROP_WINDOW_HOURS and returns free otherwise, which
    is most of the year. Deliberately not on the 10-minute fast job the game
    lines use: a prop pull is ~61 credits per event against 2-4 for a game-line
    tick, and nothing measured says sub-hourly resolution finds more.

    Every extra tick can only ADD picks — publishing is insert-once per
    proposition — so a locked pick is never re-priced at a number the market has
    since corrected. The offset each pick was taken at is recoverable from
    created_at against game_time, so the season measures which offsets paid
    rather than leaving it to the T-24h/T-3h sample.
    """
    lead = _nfl_lead_hours()
    if lead is None or lead > NFL_PROP_WINDOW_HOURS:
        return
    log.info("NFL prop card: next kickoff in %.1fh", lead)
    # --days 2, not the card's 8-day default: --fetch prices every event in the
    # window at ~61 credits each, and the card only acts inside T-30h anyway, so
    # a wider window would re-buy Thursday's board on every Sunday tick.
    _run([sys.executable, "-m", "scripts.nfl_prop_market_card",
          "--days", "2", "--fetch", "--publish"], "nfl-prop-card")
    # As above: the card's `--publish` writes the PICK. Getting that pick onto
    # the app and into Discord is this call, and waiting for the next refresh
    # pass to do it is what lost a UFC bet on 2026-09-05.
    _publish_new_signals("nfl-prop-card")


def run_nfl_opener_card() -> None:
    # The daily opener-spread card (nfl/scripts/daily_opener_card.py) — the
    # OTHER validated NFL rule: in the T-7..T-2 window, bet the side Pinnacle
    # favours at a soft book's stale number when it deviates >= 1.0 points.
    # Runs DAILY (the live approximation of "first qualifying moment"; the
    # number corrects only ~4.8%/day so daily resolution loses little). The
    # publisher's insert-once lock means later runs can only ADD games, never
    # re-price one — the opposite of the wind card's delete+replace, because
    # this edge IS staleness. 2 credits/run (us,eu spreads); free off-season
    # and the card itself no-ops politely when the key is absent.
    env = dict(BASE_ENV)
    key = env.get("THE_ODDS_API_KEY") or env.get("ODDS_API_KEY")
    if key:
        env["THE_ODDS_API_KEY"] = key
    _run([sys.executable, "scripts/daily_opener_card.py"],
         "nfl-opener-card", cwd=ROOT / "nfl", env=env)
    if key:
        _run([sys.executable, "-m", "scripts.nfl_wind_publisher", "--opener"],
             "nfl-opener-publish")


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

def _savant_is_stale(conn, season: int) -> tuple[bool, object, int]:
    """STALE IS THE DEFAULT. The probe is allowed to fail; the work is two CSV
    requests and an idempotent upsert, so "I cannot tell" must mean "do it",
    never "skip it". Failing the other way is what a health check gated on the
    thing that breaks looks like (§7), and it is exactly how this function did
    nothing on its first run.
    """
    try:
        row = conn.execute("""
            SELECT MAX(as_of_date), COUNT(DISTINCT player_type)
            FROM player_savant_stats WHERE season = %s
        """, (season,)).fetchone()
        newest, kinds = (row or (None, 0))
        stale = (newest is None or (kinds or 0) < 2
                 or str(newest) < (date.today() - timedelta(days=8)).isoformat())
        return stale, newest, (kinds or 0)
    except Exception as exc:  # noqa: BLE001 — see above
        log.warning("catch-up: Savant freshness probe failed (%s) — "
                    "treating Savant as stale", exc)
        try:
            conn.rollback()   # a failed probe poisons the transaction in psycopg
        except Exception:  # noqa: BLE001
            pass
        return True, None, 0


def _model_calibration_is_stale(conn) -> tuple[bool, object]:
    """Same default, same reason.

    The sweep's own table is the freshness signal: it writes one row per model
    per run_date, so MAX(run_date) is exactly "when did ModelCalibration last
    see the board". A MISSING table is the loudest possible stale — it means the
    agent has never completed a single run — and that is not hypothetical: the
    weekly cron landed at 18:06 ET on Monday 2026-08-31, nine and a half hours
    after that Monday's 8:30 trigger, so `model_calibration_sweeps` did not
    exist and the first sweep of every model would have waited until 2026-09-07.

    That is the *same week*, the *same boot*, and the *same failure* the Savant
    catch-up above was written for, in a function that only knew how to catch up
    Savant. A catch-up that covers one weekly job is a catch-up that will be
    wrong again the next time one is added.
    """
    try:
        row = conn.execute(
            "SELECT MAX(run_date) FROM model_calibration_sweeps").fetchone()
        newest = (row or (None,))[0]
        stale = (newest is None
                 or str(newest) < (date.today() - timedelta(days=8)).isoformat())
        return stale, newest
    except Exception as exc:  # noqa: BLE001 — a missing table lands here too
        log.warning("catch-up: ModelCalibration freshness probe failed (%s) — "
                    "treating the sweep as stale", exc)
        try:
            conn.rollback()   # a failed probe poisons the transaction in psycopg
        except Exception:  # noqa: BLE001
            pass
        return True, None


def catch_up_weekly_jobs() -> None:
    """Run any weekly job NOW if its data is already stale.

    A weekly cron has a one-week worst-case first run, and this repo has been
    bitten by exactly that TWICE IN ONE WEEK:

      * the Savant refresh was added on 2026-08-31 with a Monday 5:30am trigger,
        hours AFTER that Monday's 5:30 had passed -- so the 2026 pitcher snapshot
        (last pulled 2026-05-13) and the entirely absent 2026 batter snapshot
        would have stayed stale for another seven days, silently feeding every
        prop score.
      * ModelCalibration was added the SAME DAY at 18:06 ET with a Monday 8:30am
        trigger, and the catch-up written for the first case did not cover it.

    So this is deliberately a LOOP over weekly jobs rather than a Savant check
    with a second one bolted on: the next weekly job to be added inherits the
    catch-up by appearing in the list, instead of by someone remembering.

    Boot is the right moment: a deploy is the one event that reliably follows a
    change to what these jobs do. Guarded by a freshness check so a container
    that restarts five times in an hour does not pull five times, and scoped by
    `owns()` so two services do not double the work for one result.

    Best-effort throughout: a catch-up that raises would stop the scheduler from
    starting, which trades a stale feature for no picks at all.
    """
    try:
        from data.db import get_connection
        conn = get_connection()
        try:
            # Column migrations FIRST. _run_migrations is idempotent and cheap,
            # and it only ever ran inside setup_database() -- i.e. at first-time
            # setup -- so every column added to _MIGRATIONS since then has been
            # missing in production. That is not hypothetical: the very first
            # run of this catch-up crashed on `as_of_date` not existing, and the
            # Savant upsert it was about to trigger would have failed the same
            # way, because the INSERT names that column. Same reasoning as
            # data/view_migrations: a schema change with no path into production
            # is not a schema change.
            try:
                from data.db_setup import _run_migrations
                _run_migrations(conn)
                conn.commit()
            except Exception:  # noqa: BLE001 — a failed migration must not stop the check
                log.exception("catch-up: column migrations failed (continuing)")
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass

            # The 250-bet review's two tables, for exactly the reason stated
            # above: a schema change with no path into production is not a
            # schema change.
            #
            # threshold_review.ensure_schema has created both tables on every
            # 7:45am run since 2026-08-31 and NEITHER existed. The connection is
            # autocommit=False and run_review returns at `not_due` on every day
            # the slate is under the next 250-bet milestone -- every day so far
            # -- so the CREATE TABLEs were discarded when the caller closed the
            # connection. That is fixed at source (ensure_schema now commits),
            # but the cron only reaches it once a day, while models/scorer.py
            # reads model_auto_pauses on EVERY scoring run and has been logging
            # `relation "model_auto_pauses" does not exist` for days.
            #
            # Deliberately NOT gated by owns(): auto_paused() is consulted by
            # the scorer wherever it runs, not only on the service that owns the
            # review. Idempotent and internally gated by ddl_guard, so a
            # container that restarts repeatedly does not re-fire the DDL.
            try:
                from tracking.threshold_review import ensure_schema
                ensure_schema(conn)
            except Exception:  # noqa: BLE001 — must not stop the scheduler
                log.exception("catch-up: threshold-review schema failed (continuing)")
                try:
                    conn.rollback()
                except Exception:  # noqa: BLE001
                    pass

            season = datetime.now().year
            savant_stale, newest, kinds = _savant_is_stale(conn, season)
            calib_stale, last_sweep = _model_calibration_is_stale(conn)
        finally:
            conn.close()

        # Each job is run OUTSIDE the probe connection, and each is guarded
        # independently: one weekly job failing its catch-up must not cost the
        # other one its own.
        if owns("savant_refresh"):
            if savant_stale:
                log.info("catch-up: Savant for %s is stale (newest=%s, player_types=%s)"
                         " — refreshing now rather than waiting for Monday",
                         season, newest, kinds)
                try:
                    run_savant_refresh()
                except Exception:  # noqa: BLE001
                    log.exception("catch-up: Savant refresh failed")
            else:
                log.info("catch-up: Savant is fresh (newest=%s)", newest)

        if owns("model_calibration"):
            if calib_stale:
                log.info("catch-up: ModelCalibration last swept %s — sweeping now "
                         "rather than waiting for Monday", last_sweep or "never")
                # run_model_calibration already swallows everything it can raise,
                # but it opens its own connection and that can fail first.
                try:
                    run_model_calibration()
                except Exception:  # noqa: BLE001
                    log.exception("catch-up: ModelCalibration failed")
            else:
                log.info("catch-up: ModelCalibration is fresh (last sweep=%s)",
                         last_sweep)
    except Exception:  # noqa: BLE001 — never block startup
        log.exception("catch-up check failed (scheduler continues)")


def build_scheduler() -> BlockingScheduler:
    sched = BlockingScheduler(
        timezone=TIMEZONE,
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 300},
    )

    # Role filtering happens HERE, by wrapping add_job once, rather than at the
    # eleven call sites below. Eleven `if owns(...)` guards would be eleven
    # chances to forget one, and the job that gets forgotten runs in BOTH
    # services or NEITHER — a double-fetch of a metered API, or a job that
    # silently stops existing. Neither announces itself.
    _add = sched.add_job

    def _add_job(func, trigger=None, *args, **kwargs):
        jid = kwargs.get("id")
        if jid and not owns(jid):
            log.info(f"SERVICE_ROLE={SERVICE_ROLE} — skipping job {jid}")
            return None
        return _add(func, trigger, *args, **kwargs)

    sched.add_job = _add_job

    # Daily full pipeline — 6:00am ET (was daily_pipeline.yml).
    sched.add_job(
        run_daily_pipeline,
        CronTrigger(hour=6, minute=0, timezone=TIMEZONE),
        id="daily_pipeline",
        name="Daily full pipeline (6:00am ET)",
    )

    # Heartbeat watchdog — every 15 minutes, around the clock.
    #
    # 24x7 because the outage it exists for started at ~10pm ET and the first
    # human eyes on it were the next morning. A watch that keeps office hours
    # would have found this at exactly the same time nobody did.
    #
    # 15 minutes is chosen against what it is watching, not picked round: the
    # evening refresh ticks every 10 minutes, so a quarter-hour cadence cannot
    # miss more than two ticks before it speaks, and the re-notify throttle in
    # the watchdog keeps a long outage to one message every six hours.
    sched.add_job(
        run_heartbeat_watchdog,
        CronTrigger(minute="*/15", timezone=TIMEZONE),
        id="heartbeat_watchdog",
        name="Heartbeat watchdog (every 15 min, 24x7)",
    )

    # Worker job queue — every 5 minutes.
    #
    # Exists because four times in one session work was handed back as "run this
    # on your machine" when the worker already held every credential it needed.
    # A row in worker_jobs is now the way to ask for a retrain, a paid backfill,
    # or any other long job, and the answer arrives in Discord rather than in
    # someone's terminal.
    #
    # Five minutes rather than one: nothing here is latency-sensitive, and a
    # tighter poll would spend a connection every minute to find an empty queue
    # on all but a handful of ticks a week.
    sched.add_job(
        run_job_queue,
        CronTrigger(minute="*/5", timezone=TIMEZONE),
        id="job_queue",
        name="Worker job queue (every 5 min)",
    )

    # Pipeline watch — 7:15am ET daily, the slot the Sentinel agent used.
    #
    # After the 6am pipeline and before the 8am backlog run, so the morning
    # report describes a completed pass rather than one in flight.
    #
    # It reports EVERY run, clean or not. A watch that only speaks when it has
    # news is indistinguishable from one that has stopped -- which is how the
    # agent version failed twice without anyone noticing.
    sched.add_job(
        run_pipeline_watch,
        CronTrigger(hour=7, minute=15, timezone=TIMEZONE),
        id="pipeline_watch",
        name="Pipeline watch (daily 7:15am ET)",
    )

    # ModelCalibration — every Monday 8:30am ET, after the 6am pipeline has
    # settled the weekend and the 5:30am Savant pull has landed.
    #
    # Weekly and unconditional. Every threshold in this repo decays, and every
    # time one has, it was found by a person noticing a bad number: f5 was
    # -9.3% for a month before a -195 pick raised the question, and runline
    # stopped producing picks for six weeks in silence. A sweep that runs only
    # when someone is suspicious finds problems at the speed of suspicion.
    #
    # It changes nothing on its own -- thresholds, pauses and promotions are
    # model updates and need a person (CLAUDE.md 1b). Its job is to make the
    # decision unavoidable, not to make it.
    sched.add_job(
        run_model_calibration,
        CronTrigger(day_of_week="mon", hour=8, minute=30, timezone=TIMEZONE),
        id="model_calibration",
        name="ModelCalibration (weekly, Mon 8:30am ET)",
    )

    # The judgement half, 30 minutes after the sweep it reads. The gap is the
    # point: the sweep refits calibrations and analyses ~22 models, and a
    # judgement pass that started at the same minute would read last week's
    # rows and report "nothing changed" against a sweep still running.
    #
    # Every rule it applies is a DELTA. Measured 2026-09-03 before it shipped:
    # 13 of the 22 models in the sweep carry a standing "RE-CUT to ..."
    # verdict, so a rule that reported every RE-CUT would post thirteen
    # identical findings every Monday forever. A false alarm that never stops
    # is how a channel becomes unreadable, which is silence by another route.
    sched.add_job(
        run_calibration_watch,
        CronTrigger(day_of_week="mon", hour=9, minute=0, timezone=TIMEZONE),
        id="calibration_watch",
        name="Calibration watch — judgement pass (weekly, Mon 9:00am ET)",
    )

    # Pre-registered threshold review — daily at 7:45am ET, after the pipeline
    # has settled the previous day's results.
    #
    # Daily CADENCE, milestone TRIGGER: it looks every morning but only acts
    # when the slate crosses the next 250 settled bets since the cuts shipped.
    # That separation is the point -- the schedule must not become the thing
    # that decides, or the rule degenerates into "check until it fails once".
    #
    # 7:45 rather than during the pipeline: a review that runs inside the job
    # producing its inputs cannot report on a pipeline that did not finish,
    # which is §7's health-check-gated-on-the-thing-that-breaks.
    sched.add_job(
        run_threshold_review,
        CronTrigger(hour=7, minute=45, timezone=TIMEZONE),
        id="threshold_review",
        name="Threshold review (daily 7:45am ET, acts every 250 settled bets)",
    )

    # Baseball Savant refresh — Mondays 5:30am ET, before the 6am pipeline.
    #
    # It had NO schedule until 2026-08-31. The ingestor existed as a manual
    # script, so the 2026 pitcher snapshot was still the one taken on
    # 2026-05-13 -- four months stale and feeding every live pitcher-prop score
    # -- and 2026 batter Savant had never been pulled at all, so every batter
    # prop in the season was quietly falling back to 2025 numbers.
    #
    # Weekly, not daily: these are season-to-date aggregates over hundreds of
    # plate appearances, so a single day moves them marginally, and the pull is
    # two CSV requests. Before the 6am pipeline so the day's scoring sees the
    # fresh numbers rather than last week's.
    sched.add_job(
        run_savant_refresh,
        CronTrigger(day_of_week="mon", hour=5, minute=30, timezone=TIMEZONE),
        id="savant_refresh",
        name="Baseball Savant refresh (Mon 5:30am ET)",
    )

    # Hourly refresh — :17 past the hour, 7am-5pm ET (was refresh_picks.yml, 11 runs).
    sched.add_job(
        run_refresh_pass,
        CronTrigger(hour="7-17", minute=17, timezone=TIMEZONE),
        id="hourly_refresh",
        name="Hourly refresh (7am-5pm ET, :17)",
    )

    # Overnight refresh — :17, midnight-6am ET.
    #
    # Nothing ran in this window at all. A line that opened at 2am was not seen
    # until the 6am pipeline, which is when the board was ALSO frozen for the
    # day, so an opener that appeared overnight was priced hours after it
    # posted. That is the wrong end of the CLV trade: the opening number is the
    # one worth having, and the NFL opener rule is built entirely on being
    # early to it.
    #
    # Same pass as every other hour -- it re-reads odds and re-scores, and with
    # the pick lock now keyed on BETs (not on games) an overnight cross is a
    # real pick rather than a row that freezes the game before the market has
    # woken up.
    #
    # The 6am daily pipeline is unchanged and still does the day's heavy work:
    # settle, stats, backfills, results. This only adds market polling.
    sched.add_job(
        run_refresh_pass,
        CronTrigger(hour="0-5", minute=17, timezone=TIMEZONE),
        id="overnight_refresh",
        name="Overnight refresh (12-6am ET, :17)",
    )

    # Evening fast lines — every 10 minutes, 6pm-11pm ET (was evening_lines.yml's
    # runner-holding sleep loop, now just a real */10 cron on an always-on worker).
    sched.add_job(
        run_refresh_pass,
        CronTrigger(hour="18-23", minute="*/10", timezone=TIMEZONE),
        kwargs={"mode": "evening"},
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

    if RUN_BOVADA_FEED:
        sched.add_job(
            run_bovada_feed,
            CronTrigger(hour="11-23", minute="*/10", timezone=TIMEZONE),
            id="bovada_feed",
            name="Bovada direct in-play feed supervisor (11am-midnight ET)",
        )
    else:
        log.info("RUN_BOVADA_FEED=0 — bovada direct feed NOT scheduled.")

    if RUN_DK_DIRECT_FEED:
        sched.add_job(
            run_dk_direct_feed,
            CronTrigger(hour="11-23", minute="*/10", timezone=TIMEZONE),
            id="dk_direct_feed",
            name="DraftKings direct in-play feed supervisor (11am-midnight ET)",
        )
    else:
        log.info("RUN_DK_DIRECT_FEED=0 — DK direct feed NOT scheduled.")

    if RUN_NCAAF_LIVE:
        sched.add_job(
            run_ncaaf_live_loop,
            CronTrigger(hour="11-23", minute="*/10", timezone=TIMEZONE),
            id="ncaaf_live_loop",
            name="NCAAF live gameday loop supervisor (11am-midnight ET, */10)",
        )
    else:
        log.info("RUN_NCAAF_LIVE=0 — NCAAF live loop NOT scheduled.")

    # The pre-game line watcher (data/ingestors/pregame_line_poller.py).
    # Registered unconditionally so the kill switch lives in ONE place —
    # RUN_PREGAME_POLLER, read by the loop itself — rather than being split
    # between a scheduler condition and an env var. A switch in two places is a
    # switch nobody trusts, and this one has to be usable from Railway during
    # an incident without a deploy.
    sched.add_job(
        run_pregame_poller,
        CronTrigger(minute="*/10", timezone=TIMEZONE),
        id="pregame_poller",
        name="Pre-game line poller (30s, 24x7)",
        max_instances=1,
    )

    # NFL wind-totals card — the Section-28 runbook cadence (Thu scan / Sat firm /
    # Sun place), plus a Monday-morning run the runbook lacks: Sunday's --days 1
    # window closes before Monday-night kickoff, so without it MNF would never be
    # priced. "Later is better" per the runbook (the edge is vs the close and
    # forecast skill improves), so each run simply re-prices whatever is left in
    # its window. ~5 credits/week in season on THE_ODDS_API_KEY; zero off-season.
    if RUN_NFL_WIND_CARD:
        # NFL POLLING (2026-08-22). Replaces the fixed Thu/Sat/Sun/Mon wind
        # card and the daily 9:30am opener card. Both models are now polled on
        # one cadence: hourly from 10 days out, every 10 minutes once a kickoff
        # is inside 3 hours. run_nfl_poll() stands each job down when the other
        # owns the tick, and returns free when no game is inside the horizon —
        # so this stays scheduled year-round and costs nothing off-season.
        #
        # The point of polling this densely is the LOCK: the first moment a bet
        # qualifies it is written and timestamped, and it can never be
        # re-priced. Every later tick records whether the conditions still hold
        # (nfl_pick_status_history) without touching the bet.
        sched.add_job(
            run_nfl_poll,
            CronTrigger(minute=0, timezone=TIMEZONE),
            kwargs={"fast": False},
            id="nfl_poll_hourly",
            name="NFL poll (hourly, 10-day horizon)",
            max_instances=1, coalesce=True, misfire_grace_time=600,
        )
        sched.add_job(
            run_nfl_poll,
            CronTrigger(minute="*/10", timezone=TIMEZONE),
            kwargs={"fast": True},
            id="nfl_poll_fast",
            name="NFL poll (every 10 min inside 3h of kickoff)",
            max_instances=1, coalesce=True, misfire_grace_time=120,
        )
    else:
        log.info("RUN_NFL_WIND_CARD=0 — NFL polling NOT scheduled.")

    # NFL in-play worker. Sundays run 1pm to 1am ET, but Thursday, Saturday,
    # Monday and international kickoffs all fall outside a Sunday-only window,
    # so the supervisor ticks every day. An idle tick reaches no hunt state and
    # spends nothing, which is what makes a year-round schedule affordable.
    if RUN_NFL_LIVE:
        sched.add_job(
            run_nfl_live_worker,
            CronTrigger(hour="9-23", minute="*/10", timezone=TIMEZONE),
            id="nfl_live_worker",
            name="NFL in-play worker supervisor (9am-midnight ET, */10)",
            max_instances=1, coalesce=True, misfire_grace_time=300,
        )
    else:
        log.info("RUN_NFL_LIVE=0 — NFL in-play worker NOT scheduled.")

    if RUN_NFL_PROP_CARD:
        sched.add_job(
            run_nfl_prop_card,
            CronTrigger(minute=25, timezone=TIMEZONE),
            id="nfl_prop_card",
            name=f"NFL prop card (hourly inside T-{NFL_PROP_WINDOW_HOURS:g}h)",
        )
    else:
        log.info("RUN_NFL_PROP_CARD=0 — NFL prop card NOT scheduled.")

    if RUN_NCAAF_PROP_ODDS:
        # 9am / 1pm / 6pm ET: one fresh number before each of the day's kick
        # waves (noon, 3:30, 7pm, and the 6pm pass carries the late window).
        # Minute 35 keeps it clear of the :17 refresh pass and the :25 prop card.
        sched.add_job(
            run_ncaaf_prop_odds,
            CronTrigger(hour="9,13,18", minute=35, timezone=TIMEZONE),
            id="ncaaf_prop_odds",
            name="NCAAF player props (9am/1pm/6pm ET)",
            max_instances=1, coalesce=True, misfire_grace_time=1800,
        )
    else:
        log.info("RUN_NCAAF_PROP_ODDS=0 — NCAAF player props NOT scheduled.")

    return sched


def main() -> None:
    from datetime import datetime

    # Telemetry first: the probe records the scheduler's own HTTP traffic, and
    # the dashboard thread serves it. Both are best-effort by construction —
    # neither can raise into the scheduler, and RUN_MONITOR=0 disables the
    # server (PIPELINE_TELEMETRY=0 disables recording everywhere).
    try:
        from monitoring.probe import install as _install_probe
        from monitoring.server import serve_in_thread as _serve_monitor
        _install_probe("scheduler")
        srv = _serve_monitor()
        if srv is not None:
            log.info("Monitor dashboard on http://%s:%s/",
                     srv.server_address[0], srv.server_address[1])
    except Exception:  # noqa: BLE001
        log.exception("Monitoring failed to start (pipeline continues)")

    sched = build_scheduler()

    # Before the first cron fires: run any weekly job whose data is already
    # stale. Ownership is checked per job INSIDE the catch-up rather than here:
    # gating the whole thing on savant_refresh meant a role that did not own
    # Savant silently skipped every other weekly catch-up too, and adding a
    # second weekly job is exactly when that stops being a no-op.
    catch_up_weekly_jobs()

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
