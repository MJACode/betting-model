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


def run_daily_pipeline() -> None:
    # Bare invocation == run_pipeline.run_daily_pipeline() (settle, ingest, score,
    # game log, prop scoring, health check).
    _run([sys.executable, "run_pipeline.py"], "daily-pipeline")


def run_refresh_pass(mode: str = "hourly") -> None:
    # The single-source-of-truth refresh chain (odds + prop odds + lineups + scoring
    # for every sport, opening-signals, parlay record, push notifications).
    _run(["bash", "scripts/refresh_pass.sh", mode], f"refresh-pass[{mode}]")


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
NFL_FAST_WINDOW_HOURS = 3.0    # inside this, poll every 10 minutes


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

    Firing is unchanged and stays inside each model's VALIDATED window. Polling
    early does not mean betting early: at 10 days out Pinnacle has not posted
    (it arrives ~T-6.5), so the opener has nothing to compare against, and wind
    has no measured calibration beyond 7 days. Watching from T-10 buys the
    first fireable moment, not an earlier bet.

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
