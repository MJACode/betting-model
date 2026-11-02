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
  * NBA prop window       every 5 min, 24x7     -> run_nba_prop_window
  * NBA totals window     every minute, 24x7    -> run_nba_total_luck_window
        (scripts/nba_total_luck_window.py: the NBA board fetched, and the
        nba_total_luck card run, when an undecided game is 61-66 minutes
        from tip; scripts/nba_team_total_luck_window.py: one team-total call
        per game, and the nba_team_total_luck card run, when an undecided
        game is 45-56 minutes from tip, and the closing team totals of its bet
        games 12-25 minutes out; scripts/nba_first_half_total_luck_window.py:
        the same for the first half's total and nba_first_half_total_luck. One
        planning read for all three, scripts/nba_pregame_window.py; a tick with
        nothing due makes no API call)
        (scripts/nba_prop_window.py: props for exactly the NBA games 40-62
        minutes from tip and not yet decided, then the nba_prop_market card,
        the closing snapshot for bet games 12-25 minutes out, and publish.
        Returns without an API call when no game is in either range. mike,
        2026-10-16: "we're not leaving our games" -- the hourly passes put no
        look 45-57 minutes before any tip at or before 6pm ET.)
  * NHL goalie window     every 5 min, 11:00-23:55 ET -> run_nhl_goalie_window
        (scripts/nhl_goalie_window.py: no NHL model bets until both starting
        goalies are confirmed, mike 2026-10-20; the goalie poll for today's
        games, then, for any game whose matchup has just become known, one
        NHL odds fetch and the NHL deciders. Nothing while a refresh pass or
        the daily run is in progress. A day with no NHL game makes no call.)
  * NCAAB odds capture    every 5 min, 24x7     -> run_ncaab_odds_capture
        (scripts/ncaab_odds_capture.py: the college basketball board, one
        bulk call, stored only where a price or line moved against
        latest_odds, so the hour an opener appeared, and at which book, is
        known to five minutes. No call when no NCAAB game tips within 36
        hours; RUN_NCAAB_ODDS_CAPTURE=0 stops it. Writes no picks.)
  * NCAAB injury feed     every 5 min, 24x7     -> run_ncaab_injury_feed
        (scripts/ncaab_injury_feed.py: RotoWire's public injury JSON about
        every 10 minutes, every 5 while a game tips within three hours;
        Covers' public page about every 30. Change rows, including cleared.
        Tags only. Writes no picks. RUN_NCAAB_INJURY=0 stops it.)
  * NCAAB totals card     hourly at :05, 24x7, UTC -> run_ncaab_total_card
        (scripts/ncaab_total_card.py: the NCAAB totals model decides each
        game once, at 22:00Z the evening before or else at 15:00Z on the day
        and each hour after, on DraftKings' standing total; then publishes.
        UTC, not Eastern, because those are the hours its evidence bought;
        an Eastern cron would drift an hour when DST returns on 2027-03-14.
        RUN_NCAAB_TOTAL_CARD=0 stops it.)
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
import functools
import math
import os
import subprocess
import sys
import threading
from pathlib import Path

from concurrent.futures import ThreadPoolExecutor
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
# Scoreboard live scores for NFL, NBA and NHL (data/ingestors/live_scoreboard.py).
# Free ESPN reads, no Odds API credits. RUN_LIVE_SCOREBOARD=0 stops it
# without a deploy.
RUN_LIVE_SCOREBOARD = os.environ.get("RUN_LIVE_SCOREBOARD", "1") != "0"

# NFL wind-totals card (the standalone nfl/ package, docs/sports/nfl.md) — set
# RUN_NFL_WIND_CARD=0 to disable without a redeploy. The card itself exits 0 with
# "No games in window." before any odds call on off-days/off-season, so leaving it
# scheduled year-round costs nothing outside the NFL season.
RUN_NFL_WIND_CARD = os.environ.get("RUN_NFL_WIND_CARD", "1") != "0"

# NFL player-prop market card (models/nfl_prop_market, docs §5c) — the
# de-vig-Pinnacle-bet-the-outlier rule. RUN_NFL_PROP_CARD=0 disables it.
RUN_NFL_PROP_CARD = os.environ.get("RUN_NFL_PROP_CARD", "1") != "0"

# Daily model-quality monitor (tracking/model_quality.py). Report only —
# never pauses. RUN_MODEL_QUALITY=0 disables the 11:00am ET cron; the
# daily pipeline step and the worker job still run.
RUN_MODEL_QUALITY = os.environ.get("RUN_MODEL_QUALITY", "1") != "0"

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

# NFL in-play gameday worker (nfl/live_model), the loop that wrote
# nfl_live_prop. That model was RETIRED 2026-10-04 (mike: "Remove this model"),
# so the loop is OFF unless RUN_NFL_LIVE=1 is set explicitly. Setting it would
# write picks for a model in config.RETIRED_MODELS -- do not, without a new
# model id and the go-live gate (CLAUDE.md §2).
RUN_NFL_LIVE = os.environ.get("RUN_NFL_LIVE", "0") == "1"

# NFL in-play LEADER MONEYLINE loop (nfl_live_leader/, run from the repo root)
# -- a different model and a different loop from the retired worker above,
# which stays off. LIVE since 2026-10-13 (mike: "reenable the model"), so ON
# by default; set RUN_NFL_LIVE_LEADER=0 to stop it without a code change
# (a Railway variable takes effect on the redeploy that applying it starts).
RUN_NFL_LIVE_LEADER = (os.environ.get("RUN_NFL_LIVE_LEADER", "1").strip().lower()
                       not in ("0", "false", "off", "no"))

# Hours before kickoff inside which the NFL prop tick runs. 240 = 10 days,
# matching NFL_POLL_HORIZON_DAYS, so props start when the wind and opener cards
# do rather than three days later.
#
# WAS 30, and why that was wrong to keep. 30 bracketed the two MEASURED offsets
# (T-24h and T-3h) and stopped just past the earlier one. But the finding that
# justifies polling at all argues the other way: of the edges found at T-24h and
# T-3h, only 13% are the same proposition — 124 exist only at T-24h, 126 only at
# T-3h. Each poll finds NEW bets rather than re-confirming the last, so more
# polling is more bets, and the only thing that ever argued for stopping at 30
# was the ~1.26M-credit estimate for hourly-from-T-10-days.
#
# mike, 2026-09-06: "I dont care about credit costs." Measured that day, a full
# 16-event Week 1 pass is 484 credits, so hourly across a 126-day season is
# ~1.46M against 4.53M remaining. His call, with the number in front of him.
#
# Pinnacle DOES quote this far out — the T-70h fetch on 2026-09-06 returned all
# eight sharp markets — so the wider window is buying real board, not empty
# calls. What is still true is that no offset beyond T-24h has been GRADED, and
# publishing LOCKS insert-once: a pick taken where the edge is noise is a locked
# bet, not a discarded one. created_at against game_time recovers the offset, so
# the season measures which ones paid. Re-read this before widening further.
# DECLARED IN config.py so the prop SCORER can read the same number. Two
# consumers now: this job decides how far out to FETCH and price the board, and
# run_pipeline.step_nfl_prop_scoring decides how many game-dates to SCORE. They
# were allowed to disagree until 2026-09-07 — the card looked ten days ahead
# while the scorer looked at today only — which is exactly the split §1b's
# shared-constant rule exists to stop. One declaration, both read it.
from config import NFL_PROP_WINDOW_HOURS  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("scheduler")

# Serialises the daily full pipeline inside THIS process. The 6am cron, the
# boot catch-up and pipeline_watch's same-day retry all call the same
# entrypoint; without this, two of them deciding "run" in the same second
# would shell out twice. Cross-process double-starts are capped by
# tracking.daily_retry.MAX_DAILY_STARTS_PER_ET_DAY (ledgered starts today).
_DAILY_LOCK = threading.Lock()


# ---------------------------------------------------------------------------
# Jobs — each just runs an existing entrypoint as a subprocess.
# ---------------------------------------------------------------------------

def _run(cmd: list[str], label: str, cwd: Path | None = None,
         env: dict[str, str] | None = None, timeout: float | None = None) -> str:
    """Run a pipeline entrypoint, logging start/stop. Never raises — a failed run
    must not tear down the long-lived scheduler process. Returns "ok", "fail",
    "timeout" or "error"; most callers ignore it.

    `timeout` kills a step that runs past it. A job registered with
    max_instances=1 skips every tick while one run is still going, so a step
    with no bound can silence its job for hours: on 2026-10-11 one publish step
    held the fast NFL poll from 12:20Z for ~5.7 hours. Default None keeps the
    old unbounded behaviour for steps that are legitimately long."""
    log.info("START %s: %s", label, " ".join(cmd))
    try:
        result = subprocess.run(cmd, cwd=cwd or ROOT, env=env or BASE_ENV,
                                check=False, timeout=timeout)
        if result.returncode == 0:
            log.info("DONE  %s (exit 0)", label)
            return "ok"
        log.warning("FAIL  %s (exit %s)", label, result.returncode)
        return "fail"
    except subprocess.TimeoutExpired:
        log.warning("TIMEOUT %s killed after %ss", label, timeout)
        return "timeout"
    except Exception:  # noqa: BLE001 - keep the scheduler alive no matter what
        log.exception("ERROR %s crashed", label)
        return "error"


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


def run_daily_pipeline(*, retry_reason: str | None = None,
                       retry_source: str | None = None) -> None:
    # Bare invocation == run_pipeline.run_daily_pipeline() (settle, ingest, score,
    # game log, prop scoring, health check).
    #
    # retry_reason is set by the same-day catch-up (boot / pipeline_watch)
    # after a mid-run deploy aborted the 6am daily. The 6am cron passes
    # nothing. The lock is acquired before the ops note so a lost race with
    # the cron cannot post "retrying" and then skip.
    if not _DAILY_LOCK.acquire(blocking=False):
        log.info("daily-pipeline already running in this process — skip")
        return
    try:
        if retry_reason:
            log.info("daily-pipeline retry (%s): %s",
                     retry_source or "catch-up", retry_reason)
            try:
                from tracking.daily_retry import announce_daily_retry
                announce_daily_retry(
                    retry_reason, source=retry_source or "catch-up")
            except Exception:  # noqa: BLE001 — the retry is the point
                log.exception("daily-pipeline retry: ops note failed")
        _wait_for_nhl_window("daily-pipeline")
        _run([sys.executable, "run_pipeline.py"], "daily-pipeline")
    finally:
        _DAILY_LOCK.release()


# One refresh pass at a time in this process. The three refresh crons are
# separate job ids, so APScheduler's max_instances=1 never compared them with
# each other or with the boot catch-up below; a :17 cron landing on a catch-up
# that started at :10 would run the chain twice at once and buy odds twice.
_REFRESH_LOCK = threading.Lock()

# Held by an NHL goalie window tick for its whole run: the goalie poll and the
# deciders (run_nhl_goalie_window). A refresh pass or the daily run that starts
# during a tick WAITS for it rather than skipping, then lets go of the lock and
# runs whole: every writer to picks runs one at a time (the refresh chain's own
# rule), and skipping a pass would cost every sport an hour on the hourly
# cadence. Neither holds it while it runs. The tick stands down on their OWN
# locks (_REFRESH_LOCK, _DAILY_LOCK), read again after it has taken this one,
# so a pass that started in between still wins; and a pass that held this lock
# for its whole run made every other pass that started meanwhile wait on it
# (a 26-minute daily run, then a 15-minute wait blamed on the window).
_NHL_WINDOW_LOCK = threading.Lock()
# Slack over the steps' own timeouts, for the plan read and the publish that
# run inside the lock between them (NHL_GOALIE_WINDOW_TIMEOUT_S, below).
NHL_WINDOW_WAIT_SLACK_S = 300


def _nhl_window_wait_s() -> float:
    """How long a pass waits for a tick: every step the tick runs while holding
    the lock at its full timeout, plus the slack. Derived, so the wait cannot
    fall short of what a tick may legitimately take."""
    t = NHL_GOALIE_WINDOW_TIMEOUT_S
    return sum(t[k] for k in NHL_GOALIE_WINDOW_LOCKED_STEPS) + NHL_WINDOW_WAIT_SLACK_S


def _wait_for_nhl_window(label: str) -> bool:
    """Block until an NHL goalie window tick in progress is done (bounded),
    then let go of the lock: the caller already holds its own lock, which is
    what keeps the next tick out. True when no tick was still running."""
    if _NHL_WINDOW_LOCK.acquire(blocking=False):
        _NHL_WINDOW_LOCK.release()
        return True
    wait = _nhl_window_wait_s()
    log.info("%s: an NHL goalie window tick is in progress — waiting for it", label)
    if _NHL_WINDOW_LOCK.acquire(timeout=wait):
        _NHL_WINDOW_LOCK.release()
        return True
    log.warning("%s: an NHL goalie window tick held its lock past %ss — running anyway",
                label, wait)
    return False


def run_refresh_pass(mode: str = "hourly") -> None:
    # The single-source-of-truth refresh chain (odds + prop odds + lineups + scoring
    # for every sport, opening-signals, parlay record, push notifications).
    if not _REFRESH_LOCK.acquire(blocking=False):
        log.info("refresh-pass[%s]: a pass is already running in this process — skip",
                 mode)
        return
    try:
        _wait_for_nhl_window(f"refresh-pass[{mode}]")
        _run(["bash", "scripts/refresh_pass.sh", mode], f"refresh-pass[{mode}]")
    finally:
        _REFRESH_LOCK.release()


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
    # AFTER the report, not inside it. The watch posting at 7:15am ET is
    # independent of whether today's daily needs a same-day retry; a watch
    # that raised must not skip the retry, and a retry that runs 20 minutes
    # must not delay the morning report. 2026-09-18: watch reported
    # aborted/failed and did not re-queue, so bullpen/team_stats stayed STALE.
    try:
        catch_up_daily_pipeline(source="pipeline_watch")
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR daily catch-up after pipeline-watch crashed")


def run_period_recaps() -> None:
    """Monday 7:30am ET: the prior week, and the prior month on its Monday.

    The function itself decides whether a window is due, and the ledger
    decides whether it already went out. A raise must not kill the scheduler.
    Eggz's own channel gets the same windows, and only that channel.
    """
    try:
        from tracking.discord_notifier import post_period_recaps
        n = post_period_recaps()
        log.info("period recaps: %s post(s)", n)
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR period recaps crashed")
    try:
        from tracking.eggz_picks import post_eggz_recaps
        n = post_eggz_recaps()
        log.info("eggz recaps: %s post(s)", n)
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR eggz recaps crashed")
    try:
        from tracking.eggz_picks import post_parlaymatt_recaps
        n = post_parlaymatt_recaps()
        log.info("parlaymatt recaps: %s post(s)", n)
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR parlaymatt recaps crashed")


def run_eggz_ingest() -> None:
    """Read #eggz-picks and grade what is final. No-op when the token is unset.

    ParlayMatt is the same 15-minute tick, in his own try. Unset channel,
    author, or webhook: his half returns without a request and without a post.
    """
    try:
        from tracking.eggz_picks import run_eggz_ingest as _run
        _run()
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR eggz ingest crashed")
    try:
        from tracking.eggz_picks import run_parlaymatt_ingest
        run_parlaymatt_ingest()
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR parlaymatt ingest crashed")


def run_failure_alerter() -> None:
    """Deliver what the health check already decided, to the ops channel.

    In-process for the same reason as the watchdog and the watches: its output
    is a Discord post, not an exit code.

    Every 10 minutes rather than hourly, because the thing it reports is
    produced every pass and a delivery lag longer than the detection interval
    just moves the blind spot. It is cheap -- a few indexed reads -- and its own
    throttle (2h for CRIT, 12h for WARN) is what stops a standing failure
    posting 144 times a day.
    """
    try:
        from tracking.failure_alerter import run_failure_alerter as _run_alerter
        result = _run_alerter()
        log.info("FailureAlerter: %s condition(s), %s alerted",
                 len(result.get("conditions") or []),
                 len(result.get("alerted") or []))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR failure-alerter crashed")


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


def run_social_post_queue() -> None:
    """Publish manual rows, then one profile update, then at most one pick.

    Pick posts go through notify_x_picks, which sends one tweet and only
    when the last x_pick is at least 10 minutes old and the ET clock is
    outside 1:00am–8:00am. Recaps are not posted here. A raise must not
    kill the scheduler. The claim in each drain is what stops two services
    sending the same manual row; this job does not take the worker_jobs
    session lock. Each pass is its own try, so one failure does not skip
    the others.
    """
    try:
        from data.db import get_connection
        from tracking.social_posts import drain_social_posts
        conn = get_connection()
        try:
            result = drain_social_posts(conn)
        finally:
            conn.close()
        posted = result.get("posted") or 0
        bad = [item for item in result.get("results", [])
               if item.get("status") in ("failed", "uncertain")]
        if posted or bad or result.get("status") not in ("ok", "skipped", "no_table"):
            log.info("social post queue: status=%s posted=%s",
                     result.get("status"), posted)
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR social-post-queue crashed")
    try:
        from data.db import get_connection
        from tracking.social_profile import drain_social_profile
        conn = get_connection()
        try:
            result = drain_social_profile(conn)
        finally:
            conn.close()
        applied = result.get("applied") or 0
        bad = [item for item in result.get("results", [])
               if item.get("status") == "failed"]
        if applied or bad or result.get("status") not in ("ok", "skipped", "no_table"):
            log.info("social profile: status=%s applied=%s",
                     result.get("status"), applied)
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR social-profile crashed")
    try:
        from tracking.x_publisher import notify_x_picks
        posted = notify_x_picks()
        if posted:
            log.info("X pick pace: posted=%s", posted)
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR x pick pace crashed")


def run_job_queue() -> None:
    # The worker's answer to "why on my machine?". Claims at most one queued job
    # per tick and runs it here, in-process, where DATABASE_URL, ODDS_API_KEY and
    # open egress already are.
    #
    # A retrain runs for an hour. That is fine: APScheduler's default pool is ten
    # threads, so a long job occupies one while every other schedule keeps
    # firing, and max_instances=1 makes the ticks during it no-ops.
    #
    # SESSION MODE, deliberately. run_one holds a pg_advisory_lock across
    # claiming a job AND executing it -- which is what stops two workers
    # running the queue at once -- and a session-scoped lock cannot survive
    # transaction pooling, where consecutive statements may land on different
    # backends. Everything else moved to the transaction pooler on 2026-09-06
    # to escape the session pool's 15-client ceiling; this is the one caller
    # that must not.
    try:
        from data.db import get_connection
        from tracking.job_queue import run_one
        conn = get_connection(session_mode=True)
        try:
            result = run_one(conn)
        finally:
            conn.close()
        if result.get("status") != "idle":
            log.info("job queue: %s", result.get("status"))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR job-queue crashed")


def run_model_quality_job() -> None:
    """Betting-quality monitor, in-process like the threshold review.

    11:00am ET so the morning refresh passes have booked more of today's
    slate than the 6am daily. Writes model_quality_checks. Never pauses.
    """
    if not RUN_MODEL_QUALITY:
        log.info("model-quality skipped (RUN_MODEL_QUALITY=0)")
        return
    try:
        from tracking.model_quality import run_model_quality
        result = run_model_quality()
        log.info("model quality: ok=%s crit=%s warn=%s",
                 result.get("ok"), result.get("crit"), result.get("warn"))
    except Exception:  # noqa: BLE001 - must never kill the scheduler
        log.exception("ERROR model-quality crashed")


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
                  "period_recaps", "eggz_ingest",
                  # "nfl_poll_fast", not "nfl_poll_10min": the id was renamed
                  # when the fast tier moved to T-24h and this entry was not,
                  # so it named a job that does not exist. Inert today because
                  # the pipeline role owns everything NOT in _POLLER_JOBS, but
                  # a dead name in a role map is a trap set for whoever
                  # inverts the sets later.
                  "overnight_refresh", "nfl_poll_hourly", "nfl_poll_fast",
                  "nfl_opener_poll", "nfl_schedule_refresh",
                  "savant_refresh", "threshold_review",
                  "model_calibration", "job_queue", "pipeline_watch",
                  "failure_alerter",
                  "calibration_watch",
                  "model_quality",
                  "kalshi_ladders", "kalshi_game_markets",
                  # Writes picks through the same card as the refresh pass,
                  # so it lives beside the passes, not with the loops.
                  "nba_prop_window",
                  # Writes picks through its own cards (nba_total_luck,
                  # nba_team_total_luck and nba_first_half_total_luck), with
                  # their own fetches.
                  "nba_total_luck_window",
                  # Writes NHL picks through the scorer and the NHL cards, and
                  # takes turns with the refresh passes in this process.
                  "nhl_goalie_window",
                  # Writes odds, not picks: a paid fetch beside the refresh
                  # passes' own NCAAB fetch, not a loop.
                  "ncaab_odds_capture",
                  # Writes injury tags, not picks.
                  "ncaab_injury_feed",
                  # Writes NCAAB totals picks through its own card, reading
                  # the odds the passes and the capture stored.
                  "ncaab_total_card"}
# nfl_live_worker is deliberately NOT here. It writes its decision log to
# DECISION_LOG_DIR on the Railway VOLUME mounted at /data, and a Railway volume
# attaches to exactly one service. Moving the worker to the poller service would
# leave it writing to an empty path -- silently, since the log is append-only
# audit output nothing reads back in real time. A split audit trail is worse
# than a worker that a deploy can restart, so it stays with the volume until
# either the log moves into Supabase (CLAUDE.md §1b lists it as still outside)
# or the poller service gets its own volume.
_POLLER_JOBS = {"pregame_poller", "live_loop", "ncaaf_live_loop",
                # Scoreboard live scores: free ESPN reads, writes Supabase only.
                "live_scoreboard",
                # Writes only to Supabase (picks, odds) and needs no volume,
                # so it sits with the other live loops -- unlike
                # nfl_live_worker above.
                "nfl_live_leader",
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


def run_live_scoreboard() -> None:
    # One tick of the Scoreboard's live scores for NFL, NBA and NHL (Matt,
    # 2026-10-29). In process, not a subprocess: an idle tick is one
    # database read, and a tick with live games is one ESPN call per live
    # sport. Raises on a database error so the heartbeat marks it failed.
    from data.ingestors.live_scoreboard import run_once
    run_once()


def run_nfl_live_leader() -> None:
    # The NFL in-play leader moneyline loop (nfl_live_leader/gameday.py), the
    # same supervisor shape as run_ncaaf_live_loop: the loop polls ESPN core
    # (free; site.api is 403 from the worker) every 20 s and EXITS after a
    # few idle ticks with no NFL game in progress, so this */10 cron relaunches
    # it and max_instances=1 makes the ticks during a slate no-ops. Run from the
    # REPO ROOT, not nfl/ (the import trap in data/live_quote_guard.py).
    #
    # Odds API credits are spent ONLY when an in-window game (4th quarter,
    # <= 10:00, lead 4-16) is due its 5-minute evaluation: one bulk
    # DraftKings h2h call covers every due game, capped per process by
    # NFL_LIVE_LEADER_CREDIT_CAP (default 2000).
    outcome = _run(
        [sys.executable, "-m", "nfl_live_leader.gameday"],
        "nfl-live-leader",
    )
    if outcome != "ok":
        # A loop that dies on every launch (a bad import, a missing artifact)
        # must not read as a healthy job: raising makes the heartbeat 'fail'.
        raise RuntimeError(f"nfl-live-leader loop exited {outcome}")


def run_nfl_wind_card(days: int, regions: str = "us",
                      timeout: float | None = None) -> list[str]:
    """Returns the labels of any steps killed at `timeout`."""
    # The Section-28 wind-totals bet card from the standalone nfl/ package. MUST run
    # with cwd=nfl/ — the script writes data/cards/ relative to its package root.
    # Its schedule is the games table (nfl/data_ingest/schedule.py; not the frozen
    # data/games.csv since 2026-10-20). It exits 0 before any odds call when no
    # games are in the window, so off-season/off-day runs are free.
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
    killed = []
    if _run(cmd, f"nfl-wind-card-{days}d", cwd=ROOT / "nfl", env=env,
            timeout=timeout) == "timeout":
        killed.append(f"nfl-wind-card-{days}d")
    # Mirror the card into the app (games + picks tables) — LIVE runs only.
    # A dry-run card has no prices and writes no CSV, so the publisher is
    # skipped without a key. Since 2026-08-22 the wind publisher is INSERT-ONCE
    # like the opener: a locked pick is never re-priced or removed, and a
    # forecast that later collapses is flagged by scripts.nfl_pick_monitor
    # rather than deleting the bet.
    if key and _run([sys.executable, "-m", "scripts.nfl_wind_publisher"],
                    "nfl-wind-publish", timeout=timeout) == "timeout":
        killed.append("nfl-wind-publish")
    return killed


NFL_POLL_HORIZON_DAYS = 10.0   # start watching this far out
# Longest any one step of an NFL poll tick may run before it is killed. The
# steps normally take 1-25 s, and the board flush stops itself at 120 s
# (scripts/nfl_wind_publisher.BOARD_FLUSH_BUDGET_S), so 180 s is headroom, not
# a target.
NFL_POLL_STEP_TIMEOUT_S = float(os.environ.get("NFL_POLL_STEP_TIMEOUT_S", "180"))
NFL_FAST_WINDOW_HOURS = float(os.environ.get("NFL_FAST_WINDOW_HOURS", "24"))
# Inside this many hours to kickoff, poll every 10 minutes instead of hourly.
#
# 3 -> 24 on 2026-09-05 (Matt). The 10-minute tier was meant to cover the
# run-up to kickoff and only reached T-3h, so T-24h..T-3h -- the window the
# opener rule actually fires in, and where the wind forecast firms up --
# resolved at one tick an hour. Cost is ~6 credits a tick (wind us,eu +
# opener us,eu), so the extra 126 ticks a kickoff-day are ~750 credits
# against a 4.71M balance and a ~46-76k/day burn: immaterial.

# The opener's own cadence, in minutes. ONE, because the thing it is watching
# for is instantaneous: Pinnacle posting a number a soft book has not answered
# yet. Everything else about the rule is slow -- the deviation itself decays at
# ~4.8%/day, and BUF@HOU sat at -2.50 unchanged from 2026-09-04 to 09-06 -- so
# this interval buys FIRST DETECTION, not protection from a fast-fading edge.
# That distinction is worth keeping straight if anyone later asks whether the
# spend is justified; the honest answer is that it buys hours at the front, not
# seconds at the back.
#
# Not tuned below a minute: APScheduler's cron granularity is a minute, and the
# measured feed age (7s for Pinnacle) means sub-minute polling would mostly
# re-read a number we already hold.
NFL_OPENER_POLL_MINUTES = max(1, int(os.environ.get("NFL_OPENER_POLL_MINUTES", "1")))
# NO CREDIT CAP HERE, DELIBERATELY, and it is a DATABASE decision rather than a
# spend one. The cap I shipped on 2026-09-06 read api_call_log to total the
# day's burn, which opened a database connection EVERY MINUTE purely to decide
# whether to spend money -- against a Supabase session pool of 15 that was
# already dropping `odds` with EMAXCONNSESSION. A guard that costs a connection
# a minute to protect a budget nobody asked for is a bad trade twice over.
#
# mike has said repeatedly, most recently 2026-09-06: "I dont care about credit
# usage. I have said this countless times". The Odds API's own quota is the
# real backstop, and RUN_NFL_WIND_CARD=0 stops the job without a deploy.


# How long the NFL kickoff list is reused before the games table is read again.
# _nfl_lead_hours runs every MINUTE (the opener poll), year-round, and a
# connection a minute is the cost this file already refused once against a
# session pool of 15 (see the credit-cap note above). Kickoffs move a few times
# a season, so a list up to 15 minutes old changes when a poll starts by at
# most 15 minutes at its 10-day horizon; the lead itself is measured against
# the clock on every call.
NFL_SCHEDULE_CACHE_S = float(os.environ.get("NFL_SCHEDULE_CACHE_S", "900"))
_nfl_kickoff_cache: dict = {"read_at": None, "kicks": None}


def _read_nfl_kickoffs(now) -> list:
    """Every NFL kickoff from yesterday (Eastern) on, from the games table.

    The games table, not nfl/data/games.csv. That file was committed once
    (2026-08-15) and never refreshed: it held no playoff game, so every NFL
    pre-game job would have stood down after week 18, and it still carried a
    CHI @ GB kickoff three and a half hours late. `games.commence_time` is
    rewritten daily from nflverse (data/ingestors/nfl_props_data_ingestor.py).
    Bounded on the indexed game_date; the cast is on a few hundred NFL rows.
    """
    from datetime import datetime as _dt, timedelta as _td, timezone as _tz
    from zoneinfo import ZoneInfo as _ZI
    from data.db import get_connection
    lo = (now.astimezone(_ZI(TIMEZONE)).date() - _td(days=1)).isoformat()
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT commence_time FROM games
            WHERE sport = 'NFL' AND game_date >= %s AND commence_time IS NOT NULL
        """, (lo,)).fetchall()
    finally:
        conn.close()
    kicks = []
    for (raw,) in rows:
        try:
            k = _dt.fromisoformat(str(raw).replace("Z", "+00:00").replace(" ", "T"))
        except ValueError:
            continue
        kicks.append(k if k.tzinfo else k.replace(tzinfo=_tz.utc))
    return kicks


def _nfl_lead_hours() -> float | None:
    """Hours to the next NFL kickoff, or None if nothing is scheduled ahead.

    Reads the games table at most every NFL_SCHEDULE_CACHE_S. A failed read
    keeps the last list it had (loudly); with no list at all it answers None,
    and every NFL pre-game job stands down rather than guess.
    """
    from datetime import datetime as _dt, timezone as _tz
    now = _dt.now(_tz.utc)
    cache = _nfl_kickoff_cache
    age = (None if cache["read_at"] is None
           else (now - cache["read_at"]).total_seconds())
    if age is None or age >= NFL_SCHEDULE_CACHE_S:
        try:
            cache["kicks"] = _read_nfl_kickoffs(now)
            cache["read_at"] = now
        except Exception as exc:                               # noqa: BLE001
            log.warning("NFL schedule read failed (%s: %s); %s", type(exc).__name__,
                        exc, "keeping the last kickoff list" if cache["kicks"] is not None
                        else "no kickoff list, NFL pre-game jobs stand down")
    kicks = cache["kicks"] or []
    leads = [(k - now).total_seconds() / 3600.0 for k in kicks]
    ahead = [x for x in leads if x > 0]
    return min(ahead) if ahead else None


# NFL SCHEDULE REFRESH (2026-10-21). Every NFL pre-game job reads its slate
# from the games table, and until this job only the 6am daily ingest wrote it.
# That left two gaps: a playoff matchup nflverse lists overnight reached the
# opener model 6 to 18 hours late (the 2025 wild card, measured from
# nflverse's commit history), and a deploy that adds a schedule column left it
# empty until the next morning, which for the venue columns meant no wind bet
# all day. So the look-ahead schedule is re-read every NFL_SCHEDULE_REFRESH_
# MINUTES and once as soon as the scheduler starts after a boot.
#
# Free: one GET of nflverse's games.csv on GitHub, no odds call. It writes the
# next 14 days only, and on an existing row only when and where the game is
# played, never a prop model's inputs (nfl_props_data_ingestor.
# refresh_upcoming_schedule says why). RUN_NFL_SCHEDULE_REFRESH=0 stops it.
RUN_NFL_SCHEDULE_REFRESH = os.environ.get("RUN_NFL_SCHEDULE_REFRESH", "1") != "0"
NFL_SCHEDULE_REFRESH_MINUTES = min(60, max(1, int(
    os.environ.get("NFL_SCHEDULE_REFRESH_MINUTES", "15"))))
# A normal run is one download and two small upserts, a few seconds. The bound
# exists so a hung download cannot hold the job (max_instances=1) for hours.
NFL_SCHEDULE_REFRESH_TIMEOUT_S = 300.0


def run_nfl_schedule_refresh() -> None:
    _run([sys.executable, "-m", "data.ingestors.nfl_props_data_ingestor",
          "--schedule-only"], "nfl-schedule-refresh",
         timeout=NFL_SCHEDULE_REFRESH_TIMEOUT_S)


def run_nfl_poll(fast: bool = False) -> None:
    """
    One NFL poll tick: both models, then publish, then record history.

    CADENCE (set 2026-08-22): watch from 10 days out, hourly, and every 10
    minutes once a kickoff is inside 3 hours. The two jobs are mutually
    exclusive — the hourly one stands down inside the fast window so a tick is
    never paid for twice.

    THE OPENER IS NO LONGER RUN HERE (2026-09-06). It moved to its own
    minute-cadence job below, because the two models want opposite things from
    a schedule: wind wants the LATEST forecast and is better the longer it
    waits, while the opener is racing a soft book's correction and wants the
    FIRST moment Pinnacle posts. Running the opener at wind's cadence made the
    slower model set the pace for the faster one. Keeping them in one tick
    would also mean dragging the wind card, the pick monitor and the publisher
    along at one-minute intervals, which is most of the cost and none of the
    benefit.

    So what is left here is WIND, and its firing stays inside the model's
    validated window: wind does not fire past `wind_totals.MAX_FIRE_LEAD`.
    Watching from T-10 buys the first fireable moment, not an earlier bet.

    That was an ASPIRATION in this comment and not true in the code between
    2026-09-05 and 2026-09-06: nothing gated wind firing, so the `--days` handed
    to the card below -- the poll horizon, 10 -- was the firing window too, and
    all five Week 1 picks locked at leads of 7.2 to 8.7 days. The gate now lives
    in the model where every caller gets it, not in this argument.

    Cost is ~2 credits a tick (wind's own fetch), and zero when no game is
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
    # Every step is bounded so that no one of them can hold the poll past its
    # own cadence (see _run): max_instances=1 turns one stuck step into hours
    # of skipped ticks, which is how the fast poll went silent on 2026-10-11.
    step = NFL_POLL_STEP_TIMEOUT_S
    killed = run_nfl_wind_card(int(NFL_POLL_HORIZON_DAYS), "us,eu", timeout=step)
    # Record what the models thought of every game this tick, and flag any
    # locked pick whose conditions have changed. Never re-prices anything.
    if _run([sys.executable, "-m", "scripts.nfl_pick_monitor"], "nfl-pick-monitor",
            timeout=step) == "timeout":
        killed.append("nfl-pick-monitor")
    # And put that same view on the board: one NONE row per (game, model) the
    # wind and opener rules evaluated, refreshed until kickoff (Matt,
    # 2026-09-26: "All bet lines should be showing on the today tab"). Off the
    # opener's one-minute path on purpose -- that path is timed in seconds to
    # Discord, and a NONE row is not a pick. No dump today = no-op.
    if _run([sys.executable, "-m", "scripts.nfl_wind_publisher", "--scored"],
            "nfl-scored-rows", timeout=step) == "timeout":
        killed.append("nfl-scored-rows")
    # PUBLISH WHAT THE CARD JUST WROTE. Same reason as the pre-game poller
    # (2026-09-05): a writer outside the refresh pass used to leave its picks
    # sitting until the next :17 pass captured them, and inside the 3-hour fast
    # window that lag can outlast the kickoff the pick was for. Idempotent and
    # non-raising, so an extra call on a tick that wrote nothing is three cheap
    # reads.
    _publish_new_signals("nfl-poll")
    # A killed step must still be LOUD. Before the timeouts, a stuck step made
    # the poll go silent and the silence alarm fired; a step killed quietly
    # would trade that alarm for nothing. Raising here (after publishing, so a
    # pick that did get written still goes out) makes the heartbeat record
    # "error", which tracking/failure_alerter.py reports.
    if killed:
        raise RuntimeError(f"NFL poll step(s) killed at {step:g}s: {', '.join(killed)}")


def run_ncaaf_prop_odds() -> None:
    """One college prop pass: the scoped slate, every book, standard + alternate.

    A clean no-op off-season and on days with no games -- the ingestor lists
    events first (a free call) and returns before spending anything.
    """
    _run([sys.executable, "-m", "data.ingestors.ncaaf_prop_odds_ingestor"],
         "ncaaf-prop-odds")


def run_kalshi_ladder_record() -> None:
    """Snapshot Kalshi's NFL prop ladders. RECORDING ONLY -- nothing scores off it.

    A reference cannot be graded until a record exists. Pinnacle earned its role
    by clearing a placebo on three seasons; Kalshi's NFL prop settled history
    reaches back only to 2026 preseason, so there is nothing to grade against yet
    and every hour not recorded is evidence that cannot be recovered afterwards.
    This repo has paid for that lesson twice -- 100,116 credits of prop snapshots
    that lived only on a container disk, and 117,048 sharp quotes that survived
    only in a tracked parquet.

    HOURLY, and unbounded by the prop window on purpose. The window governs what
    we BET; this governs what we KNOW, and the whole open question is which
    offset a Kalshi price is worth reading at. Recording only inside the betting
    window would answer that question with the answer already assumed -- the same
    mistake as grading an offset on a board collected at one offset.

    Free: Kalshi's market data needs no key and costs no Odds API credits.
    ~2,000 rungs a run, ~32k rows a day, an order of magnitude under what `odds`
    already takes.
    """
    from data.ingestors.kalshi_prop_ingestor import record_ladders

    try:
        got = record_ladders()
        log.info("kalshi ladders: %s rungs, %s propositions",
                 got.get("rungs"), got.get("propositions"))
    except Exception as exc:                                   # noqa: BLE001
        # Never let a research recorder break a scheduler pass.
        log.warning("kalshi ladder record failed: %s: %s",
                    type(exc).__name__, exc)


def run_kalshi_game_record() -> None:
    """Snapshot Kalshi's NCAAF game markets (winner, total and spread ladders).
    RECORDING ONLY -- nothing scores off it (session 280, 2026-09-10).

    The 13-book NCAAF search found one number across every bookmaker; an
    exchange price is the one kind of college number that record has never
    held, and it cannot be graded until it has been recorded through a season.
    Free, keyless, and never on the betting path: a failure is a warning.
    """
    from data.ingestors.kalshi_game_ingestor import record_game_markets, resolve_events

    try:
        got = record_game_markets()
        log.info("kalshi game markets: %s contracts, %s events",
                 got.get("contracts"), got.get("events"))
        res = resolve_events()
        log.info("kalshi ncaaf events: %s resolved, %s unresolved",
                 res.get("resolved"), res.get("unresolved"))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("kalshi game market record failed: %s: %s",
                    type(exc).__name__, exc)


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
    log.info("NFL prop tick: next kickoff in %.1fh", lead)
    # --days DERIVED FROM THE WINDOW, not a constant. It was pinned at 2 to suit
    # the old 30h window; leaving it there while the window widened would have
    # run this job hourly for ten days and still only priced the next 48 hours,
    # which is the quiet half-change §1b's shared-constant rule exists to stop.
    # Ceil, and at least 2, so the Thursday-to-Monday spread of one NFL week is
    # never split across the boundary.
    days = max(2, math.ceil(NFL_PROP_WINDOW_HOURS / 24))
    _run([sys.executable, "-m", "scripts.nfl_prop_market_card",
          "--days", str(days), "--fetch", "--publish"], "nfl-prop-card")
    # THE FETCH ABOVE IS THE ONLY NFL PROP ODDS PRODUCER, and it writes every
    # market and book — not just the eight Pinnacle sharp markets the card
    # itself reads. So the twelve distributional models (unpaused 2026-09-06)
    # score off the board that was just bought, in the same tick, rather than
    # getting their own fetch on their own cadence. One producer, one cadence,
    # one publish: adding this to refresh_pass.sh instead would have re-bought
    # the board ~50 times a day for the same picks.
    _run([sys.executable, "run_pipeline.py", "--step", "nfl-prop-scoring"],
         "nfl-prop-scoring")
    # As above: the card's `--publish` and the scorer both write the PICK.
    # Getting that pick onto the app and into Discord is this call, and waiting
    # for the next refresh pass to do it is what lost a UFC bet on 2026-09-05.
    _publish_new_signals("nfl-prop-card")


# Each step of an NBA prop window tick is bounded, and the DECIDING steps
# (fetch, both cards, close) fit inside one five-minute tick together
# (max_instances=1 turns one stuck step into skipped ticks -- the 2026-10-11 NFL
# poll, see _run). The fetch is one event call per game about to be decided;
# the cards and the close are a read and a handful of writes, plus one event
# call per bet game owed a close. The PROJECTING steps run after them, on the
# tick about an hour before tip, so a slow frame never delays a decision: the
# ESPN injury pull, then the frame over every box line since 2018-19.
NBA_PROP_WINDOW_TIMEOUT_S = {"fetch": 120, "cards": 120, "close": 60,
                             "injuries": 60, "project": 240}


def run_nba_prop_window() -> None:
    """One NBA prop window tick: every game decided inside its window.

    nba_prop_market and nba_prop_projection decide a game once, 45-57 minutes
    before tip. The refresh passes cannot put a look there for any tip at or
    before 6pm ET (hourly at :17 until 5pm), so this tick runs every five
    minutes, 24x7. It reads what is stored first (scripts/nba_prop_window.plan)
    and returns without an API call when no game is 40-62 minutes out and
    undecided, no bet game is owed its closing snapshot and no game is due its
    projection -- most ticks of most days.

    Otherwise: fetch props for exactly the games to decide, run both NBA prop
    cards on that fetch in one step (one bet a game across both models, at most
    4 a night: scripts/nba_props_card.py), take any closing snapshot
    that is due, and publish what the cards wrote. THEN, for the games about 65
    minutes from tip, pull the ESPN injury list and store their projections (the
    projection card prices them two ticks later, inside the window). A step
    that fails or is killed raises AFTER publishing, so the heartbeat records
    "error" and the failure alerter reports it, while a bet that was written
    still goes out.
    """
    from scripts.nba_prop_window import plan_tick
    plan = plan_tick()
    if not plan.decide and not plan.close and not plan.project:
        if plan.publish:
            # Only a game near its tip: post anything still unposted for it.
            _publish_new_signals("nba-prop-window")
        return
    log.info("NBA prop window: deciding %s; closes due %s; projecting %s",
             plan.decide, plan.close, plan.project)
    t = NBA_PROP_WINDOW_TIMEOUT_S
    outcomes: dict[str, str] = {}
    if plan.decide:
        outcomes["nba-prop-window-fetch"] = _run(
            [sys.executable, "-m", "scripts.nba_prop_window", "--fetch", *plan.decide],
            "nba-prop-window-fetch", timeout=t["fetch"])
        # BOTH NBA prop cards in ONE step: their candidates meet in one choice
        # (one bet a game across both models, four a night, strongest first by
        # each bet's EV percentile within its own model;
        # scripts/nba_props_card.py), so the order they run in cannot decide
        # which model's bet a game gets.
        outcomes["nba-props"] = _run(
            [sys.executable, "run_pipeline.py", "--step", "nba-props"],
            "nba-props", timeout=t["cards"])
    if plan.close:
        outcomes["nba-prop-close"] = _run(
            [sys.executable, "run_pipeline.py", "--step", "nba-prop-close"],
            "nba-prop-close", timeout=t["close"])
    _publish_new_signals("nba-prop-window")
    if plan.project:
        outcomes["nba-injuries"] = _run(
            [sys.executable, "-m", "data.ingestors.injury_ingestor", "--sport", "NBA"],
            "nba-injuries", timeout=t["injuries"])
        outcomes["nba-prop-project"] = _run(
            [sys.executable, "-m", "scripts.nba_prop_projection_card", "--project", *plan.project],
            "nba-prop-project", timeout=t["project"])
    bad = {k: v for k, v in outcomes.items() if v != "ok"}
    if bad:
        raise RuntimeError(f"NBA prop window step(s) did not finish: {bad}")


# Each step of an NHL goalie window tick is bounded, so one stuck step cannot
# hold the job (max_instances=1) or a refresh pass waiting on its lock
# (_wait_for_nhl_window) for long. The poll is ESPN plus one DailyFaceoff page;
# the game odds step is one NHL fetch (the bulk call and the per-game 3-way
# calls); the prop odds step buys only what is owed; the scoring is the NHL
# game models for the named games; the cards are reads and a handful of writes.
NHL_GOALIE_WINDOW_TIMEOUT_S = {"poll": 120, "odds": 120, "prop_odds": 120, "score": 180,
                               "totals": 120, "props": 180}
# Every step runs while _NHL_WINDOW_LOCK is held.
NHL_GOALIE_WINDOW_LOCKED_STEPS = ("poll", "odds", "prop_odds", "score", "totals", "props")
# {game_id: known_at} this process has run the deciders on. A restart empties
# it and the next tick runs them once more for every known game; every NHL
# decider is insert-once, so that re-run writes nothing already written.
_NHL_DECIDED: dict = {}


def run_nhl_goalie_window() -> None:
    """One NHL goalie window tick (scripts/nhl_goalie_window.py).

    mike, 2026-10-20: "We should absolutely always know the goalie matchup
    before making a bet as well." No NHL model bets until both starting goalies
    are confirmed (models/nhl_goalie_gate.py), so a game is decided when its
    goalies are confirmed, which can be at warmups, about 25 minutes before
    puck drop. The hourly passes (:17, 7am-5pm ET) would miss a matinee
    confirmed between them. Every five minutes, 11:00-23:55 ET.

    A day with no unstarted NHL game: one read and return. A refresh pass or
    the daily run in progress: return before anything, the poll included (the
    pass polls first and decides after, and a poll rewriting a goalie row in
    the middle of its scoring could put two models on different goalies).
    Otherwise, holding _NHL_WINDOW_LOCK for the whole tick: the goalie poll for
    today's games. If it failed, nothing is decided this tick. Then, for the
    games whose matchup is known and not yet decided by this process: the NHL
    game odds (so the side models and the totals card price a fetch taken
    after the confirmation, not the last hourly pass's), the prop odds (it buys
    only what is owed), the NHL side models for exactly those games, the totals
    card and the prop cards, then publish. With no game odds, the side models
    and the totals card do not run. A step that fails raises after
    publishing, so the heartbeat records "error" and the game is tried again on
    the next tick.
    """
    from scripts.nhl_goalie_window import has_games_today, plan_tick
    if not has_games_today():
        return
    if not _NHL_WINDOW_LOCK.acquire(blocking=False):
        return
    t = NHL_GOALIE_WINDOW_TIMEOUT_S
    outcomes: dict[str, str] = {}
    try:
        # Read under this lock, never before taking it: a pass that took its
        # own lock a moment earlier is in progress now, and one that starts
        # after this read waits for the tick (_wait_for_nhl_window).
        if _REFRESH_LOCK.locked() or _DAILY_LOCK.locked():
            log.info("NHL goalie window: a refresh pass or the daily run is in progress; "
                     "it polls the goalies and decides the NHL games itself")
            return
        outcomes["nhl-goalie-poll"] = _run(
            [sys.executable, "run_pipeline.py", "--step", "nhl-goalie-designations-today"],
            "nhl-goalie-poll", timeout=t["poll"])
        if outcomes["nhl-goalie-poll"] != "ok":
            log.warning("NHL goalie window: the goalie poll did not finish; deciding nothing "
                        "this tick")
        else:
            plan = plan_tick(_NHL_DECIDED)
            if plan.decide:
                ids = sorted(plan.decide)
                log.info("NHL goalie window: both goalies confirmed, deciding %s", ids)
                outcomes["nhl-odds"] = _run(
                    [sys.executable, "run_pipeline.py", "--step", "nhl-odds"], "nhl-odds",
                    timeout=t["odds"])
                steps = [("nhl-prop-odds", [sys.executable, "run_pipeline.py", "--step",
                                            "nhl-prop-odds"], t["prop_odds"])]
                if outcomes["nhl-odds"] == "ok":
                    steps += [
                        ("nhl-goalie-window-score",
                         [sys.executable, "-m", "scripts.nhl_goalie_window", "--score", *ids],
                         t["score"]),
                        ("nhl-over-under", [sys.executable, "run_pipeline.py", "--step",
                                            "nhl-over-under"], t["totals"]),
                    ]
                else:
                    log.warning("NHL goalie window: no NHL game odds this tick; the side "
                                "models and the totals card wait for the next one")
                steps.append(("nhl-prop-scoring", [sys.executable, "run_pipeline.py", "--step",
                                                   "nhl-prop-scoring"], t["props"]))
                for label, cmd, timeout in steps:
                    outcomes[label] = _run(cmd, label, timeout=timeout)
                _publish_new_signals("nhl-goalie-window")
                if all(v == "ok" for v in outcomes.values()):
                    _NHL_DECIDED.update(plan.decide)
    finally:
        _NHL_WINDOW_LOCK.release()
    bad = {k: v for k, v in outcomes.items() if v != "ok"}
    if bad:
        raise RuntimeError(f"NHL goalie window step(s) did not finish: {bad}")


# The NBA totals window's steps are bounded, so a stuck step cannot hold the
# job past the ticks that follow it (max_instances=1): the fetch is one bulk
# Odds API call; the card reads one season of box scores and the due games'
# quotes, and prices them from the table its artifact stores.
NBA_TOTAL_LUCK_WINDOW_TIMEOUT_S = {"fetch": 90, "card": 180}
# nba_team_total_luck's steps in the same job, bounded the same way: the fetch
# is the event list plus one event call per due game (15 s each at most,
# odds_ingestor._get_event_odds); the card is the full-game card's reads; the
# close is the same calls for the bet games.
NBA_TEAM_TOTAL_WINDOW_TIMEOUT_S = {"fetch": 90, "card": 180, "close": 90}
# nba_first_half_total_luck's steps, bounded the same way: its own event list and
# one event call per due game, then the same card reads.
NBA_FIRST_HALF_WINDOW_TIMEOUT_S = {"fetch": 90, "card": 180, "close": 90}


def _run_models_side_by_side(models: list[list[tuple[str, list[str], float]]]) -> dict[str, str]:
    """Run each model's steps in order and the models at the same time. -> {step:
    outcome}, every model's in the order given, so the report reads the same every
    tick. Each step is a subprocess, and _run never raises, so a thread here only
    waits. A tick then lasts as long as its slowest model, not all of them added up."""
    models = [steps for steps in models if steps]
    if not models:
        return {}

    def run_steps(steps):
        return {label: _run(cmd, label, timeout=timeout) for label, cmd, timeout in steps}

    with ThreadPoolExecutor(max_workers=len(models), thread_name_prefix="nba-window") as pool:
        running = [pool.submit(run_steps, steps) for steps in models]
    outcomes: dict[str, str] = {}
    for done in running:
        outcomes.update(done.result())
    return outcomes


def run_nba_total_luck_window() -> None:
    """One NBA totals window tick: every game due a decision from any of the NBA
    game total models, and every team-total or first-half bet game due its
    closing snapshot.

    nba_total_luck decides a game once, on a fetch that landed 60-66 minutes
    before tip (models/nba_total_luck.py). Riding the refresh pass it had one
    look per game, and a pass that overran its ten minutes made the scheduler
    skip the next tick, and with it every game that tick would have decided.
    So this job runs every minute, 24x7. nba_team_total_luck decides a game
    once, on its own team-total fetch 45-66 minutes before tip
    (models/nba_team_total_luck.py), planned 45-56 minutes out, and
    nba_first_half_total_luck the same way on its own first-half fetch
    (models/nba_first_half_total_luck.py). ONE planning read serves all three
    (scripts/nba_pregame_window.plan), and the tick returns without an API call
    when nothing is due -- most ticks of most days.

    Otherwise, the three models run side by side, each on its own steps in its
    own order. nba_total_luck: fetch the NBA board, run its card.
    nba_team_total_luck: its team-total fetch for exactly the due games, its card,
    then the closing team totals of its bet games. nba_first_half_total_luck: the
    same three steps. No step of one model reads another's rows or outcome, so a
    failed team-total call cannot stop the first half's, and one model's slow card
    cannot move another's fetch or cost it a look at the game: run one after the
    other, a team-total card killed at its limit pushed the first-half fetch back
    about 3 minutes, and with both killed each model lost one of its three attempts
    a window (tests/test_nba_first_half_total_luck_window.py). The longest tick is
    6 minutes at the steps' own limits. Then publish what the cards wrote, once, when
    all of them are done. A tick can pass a minute and the next tick coalesces into
    it; each window holds six ticks or more, so one skipped tick loses no game. A
    step that fails or is killed raises AFTER publishing, so the heartbeat records
    "error" and the failure alerter reports it, while a bet that was written still
    goes out. The next tick, a minute later, tries any game still undecided again.
    A model whose plan raises runs nothing that tick; the other models' steps still
    run, and the tick raises after them.
    """
    from scripts.nba_pregame_window import plan_tick
    plan = plan_tick()
    if not plan:
        return
    total_steps: list[tuple[str, list[str], float]] = []
    if plan.total_luck:
        log.info("NBA totals window: deciding %s", plan.total_luck)
        t = NBA_TOTAL_LUCK_WINDOW_TIMEOUT_S
        total_steps = [
            ("nba-total-luck-fetch",
             [sys.executable, "-m", "scripts.nba_total_luck_window", "--fetch"], t["fetch"]),
            ("nba-total-luck",
             [sys.executable, "run_pipeline.py", "--step", "nba-total-luck"], t["card"])]

    def per_event_steps(name, module, step, due, t):
        """A per-event model's steps: its own fetch of the due games, its card, its
        closing snapshot of the bet games owed one."""
        steps = []
        if due.decide:
            log.info("NBA totals window: %s deciding %s", name, due.decide)
            steps += [
                (f"{step}-fetch", [sys.executable, "-m", module, "--fetch", *due.decide],
                 t["fetch"]),
                (step, [sys.executable, "run_pipeline.py", "--step", step], t["card"])]
        if due.close:
            log.info("NBA totals window: %s closing snapshot for %s", name, due.close)
            steps.append((f"{step}-close", [sys.executable, "-m", module, "--close", *due.close],
                          t["close"]))
        return steps

    outcomes = _run_models_side_by_side([
        total_steps,
        per_event_steps("team totals", "scripts.nba_team_total_luck_window",
                        "nba-team-total-luck", plan.team_total, NBA_TEAM_TOTAL_WINDOW_TIMEOUT_S),
        per_event_steps("first-half totals", "scripts.nba_first_half_total_luck_window",
                        "nba-first-half-total-luck", plan.first_half,
                        NBA_FIRST_HALF_WINDOW_TIMEOUT_S)])
    if outcomes:
        _publish_new_signals("nba-total-luck-window")
    bad = {k: v for k, v in outcomes.items() if v != "ok"}
    # A model whose plan raised ran nothing this tick; the other models did.
    bad.update({f"{model} plan": err for model, err in plan.errors.items()})
    if bad:
        raise RuntimeError(f"NBA totals window step(s) did not finish: {bad}")


# One bulk Odds API call (15 s at most, 30 with _get_odds' one 422 retry) and
# four small database reads; seconds in practice. Bounded so a hung call
# cannot hold the job past the ticks that follow it (max_instances=1).
NCAAB_ODDS_CAPTURE_TIMEOUT_S = 120


def run_ncaab_odds_capture() -> None:
    """One NCAAB odds capture tick (scripts/ncaab_odds_capture.py).

    The refresh passes fetch NCAAB hourly overnight and through the day, and
    college basketball openers are posted overnight and in the morning, so an
    hourly look can only say an opener appeared in the last sixty minutes.
    This tick fetches the board every five minutes and stores only the rows
    whose price or line moved. It writes no picks, so it publishes nothing.
    The script returns without an API call when no NCAAB game tips within 36
    hours, or when RUN_NCAAB_ODDS_CAPTURE=0. A run that fails or is killed
    raises, so the heartbeat records "error" and the failure alerter reports
    it; the next tick, five minutes later, fetches again. That includes a run
    in which the feed listed games and none resolved onto ESPN's schedule
    (the script exits 1): it stored nothing, and must not beat "ok".
    """
    outcome = _run([sys.executable, "-m", "scripts.ncaab_odds_capture"],
                   "ncaab-odds-capture", timeout=NCAAB_ODDS_CAPTURE_TIMEOUT_S)
    if outcome != "ok":
        raise RuntimeError(f"NCAAB odds capture did not finish: {outcome}")


NCAAB_INJURY_FEED_TIMEOUT_S = 90


def run_ncaab_injury_feed() -> None:
    """One NCAAB injury tick (scripts/ncaab_injury_feed.py).

    The script decides whether RotoWire or Covers is actually due, so most
    ticks poll one source or neither. It writes change rows and the current
    injury tags. It writes no picks, so it publishes nothing.     A poll error exits 1. A zero-player report on a game day exits 1 only
    when that source is the one the tags are using. The alert line is the
    heartbeat detail the failure alerter posts. RUN_NCAAB_INJURY=0 exits 0
    without a request.
    """
    cmd = [sys.executable, "-m", "scripts.ncaab_injury_feed"]
    log.info("START ncaab-injury-feed: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd, cwd=ROOT, env=BASE_ENV, check=False, text=True,
            capture_output=True, timeout=NCAAB_INJURY_FEED_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"NCAAB injury feed timed out after {NCAAB_INJURY_FEED_TIMEOUT_S}s"
        ) from exc
    if result.stdout:
        log.info(result.stdout.rstrip())
    if result.stderr:
        log.warning(result.stderr.rstrip())
    if result.returncode != 0:
        lines = (result.stderr or result.stdout or "").strip().splitlines()
        alert = next((ln for ln in reversed(lines) if "NCAAB_INJURY_ALERT" in ln), "")
        why = alert or (lines[-1] if lines else f"exit {result.returncode}")
        raise RuntimeError(f"NCAAB injury feed: {why[:500]}")
    log.info("DONE  ncaab-injury-feed (exit 0)")


# The card reads one season of NCAAB games and box scores and refits the
# ratings once per quote hour; seconds to a minute in practice.
NCAAB_TOTAL_CARD_TIMEOUT_S = 600


def run_ncaab_total_card() -> None:
    """One NCAAB totals card run (scripts/ncaab_total_card.py), then publish.

    Hourly at five past, UTC. A game is decided at 22:00Z the evening before
    its date or, failing a DraftKings total then, at 15:00Z on the day and
    each hour after, so a run at any other hour decides nothing and returns
    after one read. The script returns at once when RUN_NCAAB_TOTAL_CARD=0;
    the job still beats. A run that fails or is killed raises AFTER
    publishing, so the heartbeat records "error" and the failure alerter
    reports it, while a bet that was written still goes out. The script exits
    1 when a due game could not be decided for a reason that will not clear
    by itself (an artifact for another season, a season-long box hold, a
    missing blend), after writing every game it could.
    """
    outcome = _run([sys.executable, "-m", "scripts.ncaab_total_card", "--publish"],
                   "ncaab-total-card", timeout=NCAAB_TOTAL_CARD_TIMEOUT_S)
    _publish_new_signals("ncaab-total-card")
    if outcome != "ok":
        raise RuntimeError(f"NCAAB totals card did not finish: {outcome}")


def run_nfl_opener_card() -> None:
    """One opener tick: fetch the board, fire what qualifies, publish it.

    THE OPENER RULE: wherever a bettable book's spread deviates >= 2.0 pts from
    Pinnacle's (opener_spread.DEPLOY_THRESHOLD; was 1.0 until 2026-09-11), bet
    the side Pinnacle favours at the stale number. The edge IS
    the staleness, so the pick is insert-once — later ticks can only ADD games,
    never re-price one.

    CADENCE, and why it is not the daily run it used to be. "First qualifying
    moment" was approximated at DAILY resolution on the theory that the number
    corrects only ~4.8% a day. That theory is about how fast the deviation
    DECAYS, and it says nothing about when the deviation APPEARS — which is a
    single instant, the one Pinnacle posts. mike, 2026-09-06: "it needs to be
    as soon as pinnacle Lines are released like within a minute or seconds -
    else the edge disappears."

    Measured against the feed before choosing the interval, because polling
    faster than the source updates is pure spend: on 2026-09-06 the Odds API
    reported Pinnacle's NFL spreads `last_update` at 7 SECONDS old (FanDuel 7s,
    DraftKings 40s, BetMGM 44s). The source moves sub-minute, so a one-minute
    poll is resolution we can actually use rather than the same number fetched
    sixty times.

    2 credits/run (us,eu spreads) = 2,880/day while a game is inside the
    10-day horizon, ~432k over a season against 4.59M remaining. Zero
    off-season: the caller returns before spending anything when the board is
    empty.
    """
    env = dict(BASE_ENV)
    key = env.get("THE_ODDS_API_KEY") or env.get("ODDS_API_KEY")
    if key:
        env["THE_ODDS_API_KEY"] = key
    _run([sys.executable, "scripts/daily_opener_card.py"],
         "nfl-opener-card", cwd=ROOT / "nfl", env=env)
    if key:
        _run([sys.executable, "-m", "scripts.nfl_wind_publisher", "--opener"],
             "nfl-opener-publish")
        # DISCORD FIRST, ALONE (mike, 2026-09-22: "it needs to be more real
        # time"). Measured on the TEN @ NYG pick: the number appeared at
        # 21:28:26Z, the card saw it at 21:29:00, the row was written at
        # 21:29:01.7, and Discord got it at 21:29:41 -- 40 s spent in the full
        # publish chain (threshold sync, opening signals, push, then Discord,
        # behind another job's publish lock) on a number that lived four
        # minutes. The Discord post is the thing a reader can act on, so it is
        # made directly, in-process, before anything else in the chain; the
        # ledger it writes keeps the full publish below from posting twice.
        _post_opener_discord()
        # The card + publisher write the pick; this is what carries it to
        # push and the CLV shadow track. Without it a minute-cadence lock
        # would still wait for the next :17 refresh pass to be announced,
        # which throws away exactly the latency this job was created to buy.
        _publish_new_signals("nfl-opener-poll")


def _post_opener_discord() -> None:
    """Post any just-written BET to its Discord channel, and nothing else.

    `notify_discord_signals` is the same function the full publish calls -- same
    thresholds, same started-game guard, same `push_sent` ledger, same
    publisher lock -- so this adds no surface and cannot post anything the
    pass would not. It only moves the Discord post to the front of the tick.
    Never raises: a Discord failure must not stop the publish chain below,
    which will try Discord again itself.
    """
    try:
        from tracking.discord_notifier import notify_discord_signals
        n = notify_discord_signals()
        if n:
            log.info("opener: %d signal(s) to Discord inside the tick", n)
    except Exception:  # noqa: BLE001
        log.exception("opener: in-tick Discord post crashed")


def run_nfl_opener_poll() -> None:
    """The minute-cadence opener watch. Free when no game is on the board.

    Separate from run_nfl_poll so the opener's cadence is not tied to wind's —
    see the note there. Gated the same way: nothing inside the 10-day horizon
    means an immediate return with no socket opened, which is what makes a
    year-round every-minute schedule affordable.
    """
    lead = _nfl_lead_hours()
    if lead is None or lead > NFL_POLL_HORIZON_DAYS * 24:
        return                                  # nothing on the board: free
    run_nfl_opener_card()


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


def catch_up_daily_pipeline(*, source: str = "boot") -> dict:
    """Re-run today's 6am daily if it never completed MLB freshness steps.

    2026-09-18: Railway replaced the worker 7 minutes into the daily. The
    CronTrigger's next fire was tomorrow 6:00am ET, pipeline_watch reported
    the abort and did not re-queue, and mlb_bullpen_workload / mlb_team_stats
    stayed STALE until the next calendar day. Hourlies never write those
    tables.

    Same moment as the weekly catch-up (boot), plus pipeline_watch at 7:15am
    ET so a worker that was down all morning still retries the same ET day.
    Decision lives in tracking.daily_retry so the four guards are unit-tested
    without starting a scheduler: aborted → run; successful → skip;
    in-process → skip; already two starts today → skip.

    Best-effort: raising here must not stop the scheduler starting, and must
    not sink the pipeline watch's Discord post (the caller wraps this).
    """
    skipped = {"status": "skipped"}
    if not owns("daily_pipeline"):
        log.info("daily catch-up: SERVICE_ROLE=%s does not own daily_pipeline",
                 SERVICE_ROLE)
        return {**skipped, "reason": "not this service"}
    try:
        from data.db import get_connection
        from tracking.daily_retry import (
            decide_daily_retry, load_today_dailies,
        )
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
        conn = get_connection()
        try:
            runs = load_today_dailies(conn, now)
        finally:
            conn.close()
        if runs is None:
            log.warning("daily catch-up [%s]: ledger unreadable — not starting blind",
                        source)
            return {"status": "skipped", "reason": "ledger unreadable"}
        decision = decide_daily_retry(
            now=now,
            runs=runs,
            in_process_running=_DAILY_LOCK.locked(),
        )
        if decision.action != "run":
            log.info("daily catch-up [%s]: skip — %s", source, decision.reason)
            return {"status": "skipped", "reason": decision.reason}
        log.info("daily catch-up [%s]: run — %s", source, decision.reason)
        run_daily_pipeline(retry_reason=decision.reason, retry_source=source)
        return {"status": "run", "reason": decision.reason}
    except Exception:  # noqa: BLE001 — never block startup / the watch
        log.exception("daily catch-up [%s] failed (scheduler continues)", source)
        return {"status": "error", "reason": "catch-up raised"}


def abort_orphaned_refresh_runs() -> int:
    """Close refresh ledger rows the previous container left unfinished.

    2026-10-16: evening run 06b9db72a43c4323ad5ed84abf00b591 was still open
    at 11:25Z. The 04:17Z deploy killed it, later hourlies finished, and
    `_abort_orphans` only closes the kind that is starting — so the evening
    stayed unfinished until the next evening and `refresh_pass_completion`
    counted it as stuck.

    Once, before this process starts a pass. Only the service that owns the
    refresh jobs: a poller restart must not stamp a pass the pipeline
    service is still running. The cutoff freezes on the first call, so a
    second call cannot abort a pass this process has since opened. Does not
    touch `daily`. Best-effort: a ledger failure must not stop the scheduler.
    """
    if not owns("hourly_refresh"):
        log.info("refresh orphan sweep: SERVICE_ROLE=%s does not own hourly_refresh",
                 SERVICE_ROLE)
        return 0
    try:
        from data.db import get_connection
        from tracking.run_ledger import abort_prior_refresh_orphans
        conn = get_connection()
        try:
            return abort_prior_refresh_orphans(conn)
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 — never block startup
        log.exception("refresh orphan sweep failed (scheduler continues)")
        return 0


def catch_up_refresh_pass(*, source: str = "boot") -> dict:
    """Re-run the :17 refresh pass a deploy killed, rather than lose the hour.

    2026-09-20: every merge to master replaced the worker mid-pass, no pass
    completed between 16:32 and 19:31 UTC, and MLB props had no rows until
    19:23 on a slate that started at 17:11. The decision, its caps and what a
    catch-up costs in Odds API credits are in tracking.refresh_retry.

    Best-effort, like the daily catch-up: raising here must not stop the
    scheduler.
    """
    if not owns("hourly_refresh"):
        log.info("refresh catch-up: SERVICE_ROLE=%s does not own hourly_refresh",
                 SERVICE_ROLE)
        return {"status": "skipped", "reason": "not this service"}
    try:
        from datetime import timezone as _tz
        from data.db import get_connection
        from tracking.refresh_retry import (
            decide_refresh_retry, load_recent_refreshes,
        )
        now = datetime.now(_tz.utc)
        conn = get_connection()
        try:
            runs = load_recent_refreshes(conn, now)
        finally:
            conn.close()
        if runs is None:
            log.warning("refresh catch-up [%s]: ledger unreadable — not starting blind",
                        source)
            return {"status": "skipped", "reason": "ledger unreadable"}
        decision = decide_refresh_retry(
            now=now, runs=runs, in_process_running=_REFRESH_LOCK.locked())
        if decision.action != "run":
            log.info("refresh catch-up [%s]: skip — %s", source, decision.reason)
            return {"status": "skipped", "reason": decision.reason}
        log.info("refresh catch-up [%s]: run — %s", source, decision.reason)
        run_refresh_pass()
        return {"status": "run", "reason": decision.reason}
    except Exception:  # noqa: BLE001 — never block the scheduler
        log.exception("refresh catch-up [%s] failed (scheduler continues)", source)
        return {"status": "error", "reason": "catch-up raised"}


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

    # EVERY job records that it ran, in ONE place for the same reason the role
    # filter is here: a per-job call site is a chance to forget, and the job
    # that gets forgotten is the one whose silence nobody notices.
    #
    # This watches jobs whose correct output is often NOTHING -- the NFL polls
    # write a pick only when one qualifies, so a dead poll and a quiet market
    # were previously identical -- and the failure alerter itself, which
    # reported on everything except whether it was still running.
    def _with_heartbeat(jid, func):
        if not jid:
            return func

        @functools.wraps(func)
        def _wrapped(*a, **kw):
            status, detail = "ok", ""
            try:
                return func(*a, **kw)
            except Exception as exc:                          # noqa: BLE001
                # Beat anyway, marked failed. A job that raises every tick is
                # RUNNING, and calling that silence would point at the wrong
                # problem -- the failure alerter reports the status separately.
                status, detail = "error", repr(exc)
                raise
            finally:
                from tracking.job_heartbeat import beat
                beat(jid, status, detail)
        return _wrapped


    def _add_job(func, trigger=None, *args, **kwargs):
        jid = kwargs.get("id")
        if jid and not owns(jid):
            log.info(f"SERVICE_ROLE={SERVICE_ROLE} — skipping job {jid}")
            return None
        # Seed at REGISTRATION so a fresh deploy does not report every watched
        # job as silent until its first tick -- an hour for the hourly NFL
        # poll, most of a night for the in-play worker.
        if jid:
            try:
                from tracking.job_heartbeat import MAX_SILENCE, seed
                if jid in MAX_SILENCE:
                    seed(jid)
            except Exception:                                 # noqa: BLE001
                log.warning("could not seed heartbeat for %s", jid)
        return _add(_with_heartbeat(jid, func), trigger, *args, **kwargs)

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

    # Failure alerting — every 10 minutes, 24x7.
    #
    # The health check has run on every refresh pass for months and writes its
    # verdict to a TABLE. On 2026-09-06 the refresh pass failed steps on 32 of
    # 50 passes -- including `odds`, which fetches the lines every model prices
    # against -- and it was found by a person querying pipeline_runs by hand.
    # Detection was never the gap; delivery was.
    #
    # 24x7 for the same reason as the watchdog: the incident it exists for ran
    # through the night.
    sched.add_job(
        run_failure_alerter,
        CronTrigger(minute="*/10", timezone=TIMEZONE),
        id="failure_alerter",
        name="Failure alerter -> ops Discord (every 10 min, 24x7)",
        max_instances=1, coalesce=True, misfire_grace_time=300,
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

    # Manual posts, one profile update, and one paced pick tweet.
    # Five minutes is the pick clock: notify_x_picks itself refuses a second
    # pick inside 10 minutes and refuses 1:00am–8:00am ET. Recaps stay on
    # their own jobs. This does not move any other trigger.
    sched.add_job(
        run_social_post_queue,
        CronTrigger(minute="*/5", timezone=TIMEZONE),
        id="social_post_queue",
        name="X posts and paced picks (every 5 min)",
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

    # Weekly results, and the monthly results on the first Monday. 7:30am ET
    # is after the 6:00am daily recap. A miss retries on later mornings
    # through noon. The ledger posts each window once.
    sched.add_job(
        run_period_recaps,
        CronTrigger(day_of_week="mon", hour=7, minute=30, timezone=TIMEZONE),
        id="period_recaps",
        name="Weekly and monthly results (Mon 7:30am ET)",
        max_instances=1, coalesce=True, misfire_grace_time=3600,
    )

    # Eggz's channel. The poll is the read. Recaps are the 6:00am settle and
    # the Monday 7:30 job above. Unset token or channel: the poll returns
    # without a request.
    sched.add_job(
        run_eggz_ingest,
        CronTrigger(minute="*/15", timezone=TIMEZONE),
        id="eggz_ingest",
        name="Eggz picks (every 15 min)",
        max_instances=1, coalesce=True, misfire_grace_time=300,
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

    # Model quality — daily 11:00am ET, after morning scoring + a few
    # refresh passes. The 6am daily also runs it (observe-only). Report
    # only; a CRIT finding writes model_quality_checks and does not pause.
    sched.add_job(
        run_model_quality_job,
        CronTrigger(hour=11, minute=0, timezone=TIMEZONE),
        id="model_quality",
        name="Model quality monitor (daily 11:00am ET, report only)",
        max_instances=1, coalesce=True, misfire_grace_time=300,
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

    # Scoreboard live scores, every minute, 24x7: NFL London kickoffs are
    # 9:30am ET and NBA west-coast games run past 1am. An idle tick is one
    # database read and no HTTP call.
    if RUN_LIVE_SCOREBOARD:
        sched.add_job(
            run_live_scoreboard,
            CronTrigger(minute="*", timezone=TIMEZONE),
            id="live_scoreboard",
            name="Scoreboard live scores, NFL/NBA/NHL (every minute, 24x7)",
            max_instances=1, coalesce=True, misfire_grace_time=30,
        )
    else:
        log.info("RUN_LIVE_SCOREBOARD=0 — Scoreboard live scores NOT scheduled.")

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
        # re-priced. For wind, qualifying is a kickoff forecast that has held
        # at or above 11 mph across the 12-hour window (wind_totals.ruling_wind),
        # not the first poll that prints 11. Every later tick records whether
        # the conditions still hold (nfl_pick_status_history) without touching
        # the bet.
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
            name=f"NFL poll (every 10 min inside {NFL_FAST_WINDOW_HOURS:g}h of kickoff)",
            max_instances=1, coalesce=True, misfire_grace_time=120,
        )
        # The opener, on its own clock. See run_nfl_opener_card for why it is
        # not a tier of the job above: wind wants the latest forecast, the
        # opener wants the first instant Pinnacle posts, and one schedule
        # cannot serve both.
        #
        # misfire_grace_time is 30s, far tighter than the jobs above, and that
        # is the point: a tick that has already been overtaken by the next one
        # has nothing left to contribute, and running it late would spend 2
        # credits to re-read a board the newer tick already read. coalesce
        # collapses a backlog to one run for the same reason.
        sched.add_job(
            run_nfl_opener_poll,
            CronTrigger(minute=f"*/{NFL_OPENER_POLL_MINUTES}", timezone=TIMEZONE),
            id="nfl_opener_poll",
            name=f"NFL opener poll (every {NFL_OPENER_POLL_MINUTES} min, 10-day horizon)",
            max_instances=1, coalesce=True, misfire_grace_time=30,
        )
    else:
        log.info("RUN_NFL_WIND_CARD=0 — NFL polling NOT scheduled.")

    # The NFL schedule of record, kept current between daily runs (see
    # run_nfl_schedule_refresh). Not gated on RUN_NFL_WIND_CARD: the prop card
    # and the prop scorer read the same rows. Off the hour (:05, :20, ...) so
    # it never shares a minute with the hourly NFL poll or the 6am pipeline.
    # next_run_time is the boot catch-up. It falls due before sched.start(), so
    # the run happens the moment the scheduler starts -- after the boot
    # migrations in catch_up_weekly_jobs have added any new column -- and a
    # deploy that adds one has it filled at boot, not the next morning. If the
    # boot catch-ups hold the start past misfire_grace_time (10 minutes), the
    # first 15-minute tick does it instead.
    if RUN_NFL_SCHEDULE_REFRESH:
        sched.add_job(
            run_nfl_schedule_refresh,
            CronTrigger(minute=f"5-59/{NFL_SCHEDULE_REFRESH_MINUTES}", timezone=TIMEZONE),
            id="nfl_schedule_refresh",
            name=f"NFL schedule refresh (every {NFL_SCHEDULE_REFRESH_MINUTES} min "
                 "and at boot, next 14 days)",
            next_run_time=datetime.now(sched.timezone) + timedelta(seconds=30),
            max_instances=1, coalesce=True, misfire_grace_time=600,
        )
    else:
        log.info("RUN_NFL_SCHEDULE_REFRESH=0 — NFL schedule refresh NOT scheduled.")

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

    # NFL in-play leader moneyline. Every day 9am-midnight ET for the same
    # reason as the worker above (Thursday, Saturday, Monday and the 9:30am ET
    # international kickoffs); an idle launch reads ESPN and exits.
    if RUN_NFL_LIVE_LEADER:
        sched.add_job(
            run_nfl_live_leader,
            CronTrigger(hour="9-23", minute="*/10", timezone=TIMEZONE),
            id="nfl_live_leader",
            name="NFL in-play leader moneyline loop supervisor (9am-midnight ET, */10)",
            max_instances=1, coalesce=True, misfire_grace_time=300,
        )
    else:
        log.info("RUN_NFL_LIVE_LEADER=0 — NFL in-play leader loop NOT scheduled.")

    if RUN_NFL_PROP_CARD:
        sched.add_job(
            run_nfl_prop_card,
            CronTrigger(minute=25, timezone=TIMEZONE),
            id="nfl_prop_card",
            name=f"NFL prop card (hourly inside T-{NFL_PROP_WINDOW_HOURS:g}h)",
        )
    else:
        log.info("RUN_NFL_PROP_CARD=0 — NFL prop card NOT scheduled.")

    # NBA prop window — every 5 minutes, 24x7 (run_nba_prop_window). Around
    # the clock because the cost of an idle tick is one database read, and a
    # schedule with hours in it is a schedule that can miss a tip: the hourly
    # passes missed every one at or before 6pm ET. Unconditional: the card has
    # no write switch (scripts/nba_prop_market_card.py) and neither does this.
    sched.add_job(
        run_nba_prop_window,
        CronTrigger(minute="*/5", timezone=TIMEZONE),
        id="nba_prop_window",
        name="NBA prop window (every 5 min, 24x7: games 40-62 min from tip)",
        max_instances=1, coalesce=True, misfire_grace_time=120,
    )

    # NBA totals window -- every minute, 24x7 (run_nba_total_luck_window). The
    # nba_total_luck, nba_team_total_luck and nba_first_half_total_luck cards
    # decide here and nowhere else: on the refresh pass a skipped tick lost every
    # game it would have decided. Every minute so the 61-66-minute window holds
    # six ticks and the team and first-half totals' 45-56 twelve;
    # misfire_grace_time 30 because a tick overtaken by the next one has nothing
    # left to add. One job for all of them, not three: each job's heartbeat opens
    # a connection every tick
    # (scripts/nba_pregame_window.py). No write switch, like the cards.
    sched.add_job(
        run_nba_total_luck_window,
        CronTrigger(minute="*", timezone=TIMEZONE),
        id="nba_total_luck_window",
        name="NBA totals window (every minute, 24x7: full-game totals 61-66 min, "
             "home team and first-half totals 45-56 min from tip)",
        max_instances=1, coalesce=True, misfire_grace_time=30,
    )

    # NHL goalie window -- every five minutes, 11:00-23:55 ET
    # (run_nhl_goalie_window). No NHL model bets until both starting goalies
    # are confirmed (mike, 2026-10-20), and confirmations come from the morning
    # skate (late morning) to warmups (about 25 minutes before the last puck
    # drop, around 10:30pm ET). Unconditional, like the cards it runs.
    sched.add_job(
        run_nhl_goalie_window,
        CronTrigger(hour="11-23", minute="*/5", timezone=TIMEZONE),
        id="nhl_goalie_window",
        name="NHL goalie window (every 5 min, 11:00-23:55 ET: decide games once both goalies are confirmed)",
        max_instances=1, coalesce=True, misfire_grace_time=120,
    )

    # NCAAB odds capture -- every five minutes, 24x7 (run_ncaab_odds_capture).
    # Around the clock because openers go up overnight, which is exactly where
    # the hourly passes leave the widest gaps. An off-season tick is one read
    # of ncaab_events and no call. The kill switch is in the script
    # (RUN_NCAAB_ODDS_CAPTURE), so the job keeps beating while it is off and
    # its silence still means stopped.
    sched.add_job(
        run_ncaab_odds_capture,
        CronTrigger(minute="*/5", timezone=TIMEZONE),
        id="ncaab_odds_capture",
        name="NCAAB odds capture (every 5 min, 24x7: change-only, opener timing)",
        max_instances=1, coalesce=True, misfire_grace_time=120,
    )

    # NCAAB injury tags -- every five minutes, 24x7 (run_ncaab_injury_feed).
    # The script polls RotoWire about every 10 minutes and every 5 near a tip,
    # and Covers about every 30. An idle tick is one slate read and no request.
    # Writes tags, not picks. RUN_NCAAB_INJURY=0 keeps the beat without a request.
    sched.add_job(
        run_ncaab_injury_feed,
        CronTrigger(minute="*/5", timezone=TIMEZONE),
        id="ncaab_injury_feed",
        name="NCAAB injury feed (every 5 min, 24x7: tags only, change rows)",
        max_instances=1, coalesce=True, misfire_grace_time=120,
    )

    # NCAAB totals card -- hourly at five past, UTC (run_ncaab_total_card).
    # UTC on purpose: the model decides at 22:00Z the evening before and from
    # 15:00Z on the day, the hours its evidence bought, and an Eastern cron
    # would move them an hour when DST returns. Five past, so the hour's
    # standing DraftKings total is the one stored by the capture job's ticks
    # up to then. Unconditional; the kill switch is in the script.
    sched.add_job(
        run_ncaab_total_card,
        CronTrigger(minute=5, timezone="UTC"),
        id="ncaab_total_card",
        name="NCAAB totals card (hourly at :05 UTC: decide at 22Z the evening before, "
             "else 15Z on the day and each hour to tip)",
        max_instances=1, coalesce=True, misfire_grace_time=600,
    )

    # Minute 40, away from the prop card at :25 and the hourly refresh, so a slow
    # Kalshi response cannot delay anything that places a bet.
    sched.add_job(
        run_kalshi_ladder_record,
        CronTrigger(minute=40, timezone=TIMEZONE),
        id="kalshi_ladders",
        name="Kalshi NFL prop ladders (quotes stored, not bet)",
    )
    # Minute 45, same reasoning: the NCAAF game markets (winner / total /
    # spread ladders) are a research record, never on the betting path.
    sched.add_job(
        run_kalshi_game_record,
        CronTrigger(minute=45, timezone=TIMEZONE),
        id="kalshi_game_markets",
        name="Kalshi NCAAF game markets (quotes stored, not bet)",
    )

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

    # A watched job this service owns but did not register is switched off
    # here on purpose (RUN_NFL_LIVE=0 and friends). Record that, or the row
    # its last run left behind reads as silence forever: the NFL in-play
    # worker, off since 2026-10-04, was still alarming on 10-11. Jobs another
    # service owns are left alone -- that service speaks for them.
    try:
        from tracking.job_heartbeat import MAX_SILENCE, mark_disabled
        for jid in sorted(MAX_SILENCE):
            if owns(jid) and sched.get_job(jid) is None:
                mark_disabled(jid)
                log.info("watched job %s is not scheduled here — marked disabled", jid)
    except Exception:                                         # noqa: BLE001
        log.warning("could not mark switched-off watched jobs as disabled")

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

    # Before any pass this process starts, and before sched.start() can fire
    # the :17 cron. Same-kind orphan cleanup does not run again for an
    # evening until the next evening window.
    abort_orphaned_refresh_runs()

    # Before the first cron fires: run any weekly job whose data is already
    # stale. Ownership is checked per job INSIDE the catch-up rather than here:
    # gating the whole thing on savant_refresh meant a role that did not own
    # Savant silently skipped every other weekly catch-up too, and adding a
    # second weekly job is exactly when that stops being a no-op.
    catch_up_weekly_jobs()
    # Same-day daily retry. A CronTrigger whose 6:00am fire has passed does
    # not misfire on a fresh scheduler — that is how 2026-09-18's aborted
    # daily waited until tomorrow, and why this cannot live only in the cron.
    catch_up_daily_pipeline(source="boot")

    now = datetime.now(sched.timezone)
    # The refresh pass a deploy killed. A one-off JOB a minute after start, not
    # a call here: a pass takes 12-15 minutes and everything below -- the live
    # loops, the NFL polls -- would wait behind it.
    from datetime import timedelta as _td
    sched.add_job(
        catch_up_refresh_pass,
        "date",
        run_date=now + _td(seconds=60),
        id="refresh_catch_up",
        name="Refresh catch-up (once, 60s after boot)",
    )
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
