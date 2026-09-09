"""
Run work on the worker, not on someone's laptop.

WHY THIS EXISTS
---------------
mike, 2026-09-01: "you missed the opposing starter train on my machine and why
on my machine? do it in cloud."

He is right, and the pattern was repeated all night. Four separate times I ended
a turn by handing over a command — the Savant refresh, the five prop retrains,
the threshold sync, the calibration promote — when the Railway worker already
holds DATABASE_URL, ODDS_API_KEY and open egress, and is the machine that runs
everything else. Two of those turned out to be automated already. One I never
solved: I hit a single obstacle (prop-probe has no build snapshot, so `redeploy`
refuses), asked Railway's own agent, was told it would need a commit, and
stopped there rather than building the thing that makes the obstacle irrelevant.

This is that thing. A row in `worker_jobs` is a request; the worker claims it
within five minutes, runs it, and records the result. Anything that needs the
database, the Odds API, or hours of CPU is now a row rather than an instruction.

WHY A REGISTRY AND NOT A COMMAND STRING
---------------------------------------
The obvious design is a `command TEXT` column the worker shells out to. That
would make every credential on the worker reachable by anyone who can write one
row to Postgres — the Supabase service key, an app bug, a leaked connection
string. So a job names a TYPE from a fixed allowlist in this file, and its
arguments are validated before anything runs. Adding a capability is a code
change and a PR, which is the point.

WHAT THE RUNNER GUARANTEES
--------------------------
* One claim, ever. `FOR UPDATE SKIP LOCKED` means two services polling the same
  queue cannot both take the same job — the same reason the live loops are
  supervised rather than duplicated.
* One job per tick. A retrain runs for an hour; the tick after it starts finds
  it already `running` and takes the next PENDING job instead, on another
  thread. APScheduler's default pool is ten, so a long job cannot starve the
  scheduler.
* Bounded retries. A job that dies with its container is reclaimed as stale,
  but only MAX_ATTEMPTS times: a job that crashes the worker on every attempt
  must not become an infinite crash loop.
* Every terminal state is announced. A queue whose failures are only visible in
  a table is a queue nobody reads.
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path
from datetime import datetime, timedelta, timezone

from loguru import logger

import config
from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

MAX_ATTEMPTS = 3

# One job at a time, ACROSS EVERY WORKER AND THREAD.
#
# max_instances=1 on the APScheduler job stops concurrent ticks and I assumed
# that was enough. It is not: a container restart mid-job leaves the row
# `running` with nobody running it, the next tick claims the NEXT job, and the
# retrain that was interrupted is reclaimed later on top of it. Three jobs were
# live at once on 2026-09-01 and the pooler answered
# `FATAL: (EMAXCONNSESSION) max clients reached` -- a retrain holds a session
# for fifteen minutes and a range backfill for eight, so two of them plus the
# scheduler's own traffic is enough to exhaust Supavisor's client slots while
# Postgres itself sits at 22 of 60 connections.
#
# A Postgres advisory lock is the right shape because it is SESSION-SCOPED: if
# the container dies holding it, the connection dies with it and the lock is
# released. No stale flag to clean up, and no second worker can take a job
# while the first is still on one.
QUEUE_LOCK_KEY = 0x6A6F_6271          # "jobq"

DDL = """
CREATE TABLE IF NOT EXISTS worker_jobs (
    job_id       BIGSERIAL PRIMARY KEY,
    dedupe_key   TEXT UNIQUE,
    job_type     TEXT NOT NULL,
    args         JSONB NOT NULL DEFAULT '{}'::jsonb,
    status       TEXT NOT NULL DEFAULT 'pending',
    requested_by TEXT,
    note         TEXT,
    attempts     INTEGER NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at   TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    finished_at  TIMESTAMPTZ,
    result       JSONB,
    error        TEXT
)
"""


def _enabled() -> bool:
    return os.environ.get("RUN_JOB_QUEUE", "1") not in ("0", "false", "False")


_INDEX_NAMES = ("worker_jobs_pending_idx", "worker_jobs_dedupe_idx")


def ensure_schema(conn) -> None:
    # Lock-taking DDL that also forces a PostgREST schema-cache reload on every
    # call; skip it once the catalog matches (data/ddl_guard.py).
    # rls= and revoked_from= are load-bearing, not decoration: without them this
    # returns True on a database where worker_jobs exists but is still
    # anon-granted and RLS-off, and the lock_down() below never runs.
    if schema_is_current(conn, "worker_jobs", columns=("dedupe_key",),
                         indexes=_INDEX_NAMES, rls=True,
                         revoked_from=API_ROLES):
        return
    conn.execute(DDL)
    # Revoke + RLS beside the CREATE, not in a migration: this table is created
    # on demand, so a one-off sweep is undone by the next run against a database
    # where it does not yet exist. lock_down() carries its own catalog gate.
    lock_down(conn, "worker_jobs")
    conn.execute("CREATE INDEX IF NOT EXISTS worker_jobs_pending_idx "
                 "ON worker_jobs (status, created_at)")
    # dedupe_key arrived after the table did, and CREATE TABLE IF NOT EXISTS
    # will not add a column to a table that already exists. Rolled back on
    # failure so a refused ALTER cannot poison the transaction the caller is
    # about to use -- the same bug that left model_calibration without its
    # promoted columns for a day.
    for stmt in ("ALTER TABLE worker_jobs ADD COLUMN IF NOT EXISTS dedupe_key TEXT",
                 "CREATE UNIQUE INDEX IF NOT EXISTS worker_jobs_dedupe_idx "
                 "ON worker_jobs (dedupe_key)"):
        try:
            conn.execute(stmt)
        except Exception:  # noqa: BLE001
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass


# ── the allowlist ────────────────────────────────────────────────────────────
#
# Each entry is (callable, validator). The validator returns the cleaned kwargs
# or raises ValueError; it runs BEFORE the job does, so a malformed request
# fails as a queue error rather than half-way through a paid API pull.

def _job_savant_refresh(**kw):
    from data.ingestors.baseball_savant_ingestor import run_savant_ingestor
    return run_savant_ingestor(season=kw["season"], player_type=kw["player_type"])


def _validate_savant(args: dict) -> dict:
    season = int(args.get("season") or datetime.now().year)
    ptype = str(args.get("player_type") or "both")
    if ptype not in ("pitcher", "batter", "both"):
        raise ValueError(f"player_type must be pitcher|batter|both, got {ptype!r}")
    if not (2015 <= season <= datetime.now().year + 1):
        raise ValueError(f"season out of range: {season}")
    return {"season": season, "player_type": ptype}


def _job_game_log_backfill(**kw):
    """Refill `player_game_log` for games the old per-date skip never fetched.

    Needs MLB StatsAPI egress, so it runs here rather than locally (§1b).
    Idempotent by construction now that the skip is per GAME: a re-run fetches
    only what is still missing, so a partial run is safe to repeat.
    """
    from data.ingestors.mlb_stats_ingestor import backfill_player_game_log
    return backfill_player_game_log(kw["start_season"], kw["end_season"])


def _job_ncaaf_player_backfill(**kw):
    """Refill `ncaaf_player_game_log` for past seasons from CFBD /games/players.

    Runs HERE and not locally for one reason: CFBD_API_KEY is set in the Railway
    variables and is not in the local .env, so the same command fails on the dev
    machine with "CFBD_API_KEY is not set" (§1b -- the sandbox's limits are not
    the system's).

    WHY IT IS NEEDED. ncaaf_player_game_log holds 2026 only. Without prior
    seasons there is nothing to grade an NCAAF player prop against, so buying
    historical NCAAF prop odds (~50k credits) would purchase prices with no
    outcomes to check them against. Stats first, odds second.
    """
    from data.ingestors.cfbd_ingestor import backfill_ncaaf_players
    return backfill_ncaaf_players(kw["start_season"], kw["end_season"])


def _validate_ncaaf_player_backfill(args: dict) -> dict:
    start = int(args.get("start_season") or 2023)
    end = int(args.get("end_season") or 2025)
    if not (2014 <= start <= end <= datetime.now().year):
        raise ValueError(f"season range out of order or out of range: {start}-{end}")
    if end - start > 5:
        raise ValueError(f"range too wide ({start}-{end}); split it")
    return {"start_season": start, "end_season": end}


def _validate_game_log_backfill(args: dict) -> dict:
    start = int(args.get("start_season") or 2019)
    end = int(args.get("end_season") or datetime.now().year)
    if not (2015 <= start <= end <= datetime.now().year + 1):
        raise ValueError(f"season range out of order or out of range: {start}-{end}")
    # Each season is ~2,400 boxscore calls at ~0.15s, so a full 2019-2025 run is
    # roughly 40-60 minutes. Bounded so a typo cannot queue a decade.
    if end - start > 8:
        raise ValueError(f"range too wide ({start}-{end}); split it")
    return {"start_season": start, "end_season": end}


def _job_retrain_model(**kw):
    """Retrain one model on the worker. THE reason this queue exists.

    register=False routes the artifact to models/saved/_baseline/ and leaves
    model_registry alone, so a comparison run cannot swap production to a build
    whose .pkl was never committed.
    """
    import models.trainer as trainer

    previous = trainer.REGISTER_TRAINED_MODELS
    trainer.REGISTER_TRAINED_MODELS = bool(kw["register"])
    # A prop retrain's bulk load exceeds the database's 120s statement timeout:
    # mlb_prop_batter_runs died at exactly 120s. Raised for THIS job's
    # connections only, and restored afterwards, so a long-running query
    # licence belongs to the job that needs it rather than to the process.
    prev_timeout = os.environ.get("DB_STATEMENT_TIMEOUT_MS")
    os.environ["DB_STATEMENT_TIMEOUT_MS"] = str(kw["statement_timeout_ms"])
    try:
        if kw["model_id"] in config.PROP_MODELS:
            return trainer.train_prop_model(kw["model_id"],
                                            train_seasons=kw["seasons"],
                                            holdout_season=kw["holdout"],
                                            n_trials=kw["trials"])
        if kw["model_id"] in config.LIVE_MODELS:
            return trainer.train_live_model(kw["model_id"],
                                            train_seasons=kw["seasons"],
                                            holdout_season=kw["holdout"],
                                            n_trials=kw["trials"])
        return trainer.train_model(kw["model_id"],
                                   train_seasons=kw["seasons"],
                                   holdout_season=kw["holdout"])
    finally:
        trainer.REGISTER_TRAINED_MODELS = previous
        if prev_timeout is None:
            os.environ.pop("DB_STATEMENT_TIMEOUT_MS", None)
        else:
            os.environ["DB_STATEMENT_TIMEOUT_MS"] = prev_timeout


def _validate_retrain(args: dict) -> dict:
    model_id = str(args.get("model_id") or "")
    known = set(config.MODELS) | set(config.PROP_MODELS) | set(config.LIVE_MODELS)
    if model_id not in known:
        raise ValueError(f"unknown model_id {model_id!r}")
    seasons = args.get("seasons")
    if seasons is not None:
        seasons = [int(s) for s in seasons]
        if not seasons:
            raise ValueError("seasons, if given, must be non-empty")
    holdout = args.get("holdout")
    trials = args.get("trials")
    timeout_ms = int(args.get("statement_timeout_ms") or 1_800_000)   # 30 min
    if not (60_000 <= timeout_ms <= 7_200_000):
        raise ValueError(f"statement_timeout_ms out of range: {timeout_ms}")
    return {"model_id": model_id, "seasons": seasons,
            "holdout": int(holdout) if holdout is not None else None,
            "trials": int(trials) if trials is not None else None,
            "register": bool(args.get("register", False)),
            "statement_timeout_ms": timeout_ms}


def _job_historical_odds(**kw):
    from data.ingestors.odds_ingestor import run_historical_odds_range
    return run_historical_odds_range(
        sport=kw["sport"], start=kw["start"], end=kw["end"],
        hours_utc=kw["hours_utc"], bookmakers=kw["bookmakers"],
        credit_cap=kw["credit_cap"], markets=kw["markets"],
        ignore_ledger=kw["ignore_ledger"])


def _job_ncaaf_prop_odds(**kw):
    from data.ingestors.ncaaf_prop_odds_ingestor import (
        probe as ncaaf_prop_probe, run_ncaaf_prop_odds_ingestor)
    if kw["probe"]:
        return ncaaf_prop_probe(kw["date"], kw["limit_events"],
                                with_alternates=kw["with_alternates"])
    return run_ncaaf_prop_odds_ingestor(kw["date"],
                                        with_alternates=kw["with_alternates"])


def _job_market_coverage(**kw):
    from scripts.probe_market_coverage import probe
    return probe(kw["sport"], kw["markets"])


def _validate_market_coverage(args: dict) -> dict:
    """Which books serve which prop markets. Writes nothing.

    Stored data cannot answer this: a market we never REQUEST has no rows, and
    no query can tell "no book prices it" from "we never asked". So this asks
    -- one market per call, which costs the same as chunking and attributes an
    unsupported key exactly.
    """
    from data.ingestors.odds_ingestor import SPORT_KEYS
    sport = str(args.get("sport") or "").upper()
    if sport not in SPORT_KEYS:
        raise ValueError(f"unknown sport {sport!r}")
    # `markets` ABSENT means "every candidate for this sport". An explicit
    # empty list is a caller error, not a full sweep -- `or None` would have
    # quietly turned one into the other, and a probe that asks 30 markets when
    # it was told to ask none is a paid call nobody requested.
    markets = args.get("markets")
    if markets is not None:
        if not isinstance(markets, list):
            raise ValueError("markets must be a list")
        markets = [str(m) for m in markets]
        if not 1 <= len(markets) <= 60:
            raise ValueError(f"markets out of range: {len(markets)}")
    return {"sport": sport, "markets": markets}


def _validate_ncaaf_prop_odds(args: dict) -> dict:
    """College props, measured before they are scheduled.

    `probe: true` writes nothing and reports credits per event, which markets
    the API actually serves for college, and what a full pass would cost --
    the number Matt asked for before this runs on a schedule. The sample is
    capped hard: a "probe" that walks a 70-game Saturday is not a probe.
    """
    date = args.get("date")
    if date:
        datetime.strptime(str(date), "%Y-%m-%d")   # raises if malformed
    limit = int(args.get("limit_events") or 3)
    if not 1 <= limit <= 10:
        raise ValueError(f"limit_events out of range for a probe: {limit}")
    return {"date": str(date) if date else None,
            "probe": bool(args.get("probe", True)),
            "limit_events": limit,
            "with_alternates": bool(args.get("with_alternates", True))}


def _validate_historical_odds(args: dict) -> dict:
    from data.ingestors.odds_ingestor import MARKETS, SPORT_KEYS

    sport = str(args.get("sport") or "").upper()
    if sport not in SPORT_KEYS:
        raise ValueError(f"unknown sport {sport!r}")
    # Markets are what the endpoint bills by, so a job names what it funds.
    # Restricted to the bulk-endpoint set: anything else 422s the whole call.
    markets = [str(m) for m in (args.get("markets") or MARKETS)]
    bad = sorted(set(markets) - set(MARKETS))
    if bad:
        raise ValueError(f"markets not on the bulk endpoint: {bad}")
    markets = [m for m in MARKETS if m in markets]
    start, end = str(args.get("start") or ""), str(args.get("end") or "")
    for d in (start, end):
        datetime.strptime(d, "%Y-%m-%d")      # raises ValueError if malformed
    if end < start:
        raise ValueError("end is before start")
    hours = [int(h) for h in (args.get("hours_utc") or [12, 22])]
    if not all(0 <= h <= 23 for h in hours):
        raise ValueError("hours_utc must be 0-23")
    books = args.get("bookmakers") or config.ODDS_HISTORY_BOOKMAKERS
    # A credit cap is REQUIRED, not defaulted generously: this endpoint bills
    # 10x, and an unbounded date range is how a backfill quietly spends six
    # figures. The caller states the ceiling and the job stops at it.
    cap = int(args.get("credit_cap") or 25_000)
    if cap <= 0 or cap > 500_000:
        raise ValueError(f"credit_cap out of range: {cap}")
    return {"sport": sport, "start": start, "end": end,
            "hours_utc": sorted(set(hours)), "bookmakers": list(books),
            "credit_cap": cap, "markets": markets,
            "ignore_ledger": bool(args.get("ignore_ledger", False))}


def _job_relabel_in_play(**kw):
    from data.ingestors.odds_ingestor import relabel_in_play
    return relabel_in_play(sport=kw["sport"], since=kw["since"])


def _validate_relabel(args: dict) -> dict:
    from data.ingestors.odds_ingestor import SPORT_KEYS

    sport = str(args.get("sport") or "").upper()
    if sport not in SPORT_KEYS:
        raise ValueError(f"unknown sport {sport!r}")
    since = str(args.get("since") or "2000-01-01")
    datetime.strptime(since[:10], "%Y-%m-%d")
    return {"sport": sport, "since": since}


def _job_derive_first_pitch(**kw):
    from data.db import get_connection
    from data.first_pitch import derive_first_pitch

    conn = get_connection()
    try:
        return derive_first_pitch(conn)
    finally:
        conn.close()


def _job_publish_x_results(**kw):
    """Post one settled day's recap to X, clearing a stale ledger row first.

    WHY THIS EXISTS. On 2026-09-02 the recap fix (#402) was merged at 20:42 ET
    and I deleted the `x_results:2026-09-02` ledger row a minute later so the
    corrected record would post at 6am. I had read the Railway deploy stamp
    `2026-09-03T00:42Z` as ET and believed it was already the 3rd. It was still
    the 2nd, the deploy had not finished, and the next refresh pass — running
    the OLD code, which had no day-is-over guard — re-posted a partial 8-4 and
    re-ledgered it. That row then blocked the 6am post, so Discord published
    13-17 and X published nothing. CLAUDE.md §7: use ET, never UTC, for "today"
    — made in reasoning rather than in code.

    The recovery has to run where the X credentials are, which is the worker
    (§1b: a handover is a last resort). Hence a job type rather than an
    instruction.

    The day-is-over guard in notify_x_results is NOT bypassed: this clears the
    ledger and calls the ordinary path, so a date that is not over still posts
    nothing. That is the safety property, and re-posting must not cost it.
    """
    from data.db import get_connection
    from tracking.x_publisher import notify_x_results

    game_date = kw["game_date"]
    lock_key = f"x_results:{game_date}"
    conn = get_connection()
    try:
        # COUNT then DELETE, rather than reading rowcount off the result:
        # data.db._CursorResult wraps a psycopg2 cursor and exposes only
        # fetchone/fetchall/fetchmany/__iter__, so `.rowcount` is an
        # AttributeError. The first version of this job died on exactly that in
        # production -- a reminder that this repo's conn is not a DB-API cursor
        # however much it looks like one.
        removed = int(conn.execute(
            "SELECT count(*) FROM push_sent "
            "WHERE lock_key = %s AND kind = 'x_results'",
            (lock_key,)).fetchone()[0])
        conn.execute(
            "DELETE FROM push_sent WHERE lock_key = %s AND kind = 'x_results'",
            (lock_key,))
        conn.commit()
        posted = notify_x_results(game_date)
        return {"game_date": game_date, "ledger_rows_cleared": removed,
                "posted": posted}
    finally:
        conn.close()


def _job_publish_discord_signals(**kw):
    """Run the ordinary Discord signals producer NOW, instead of at :17.

    WHY THIS EXISTS. 2026-09-05, Matt: two Week 1 nfl_wind_totals picks were on
    the app board and had never reached Discord -- the capture leak #489 fixed
    an hour earlier. By then the fix was deployed and both picks were
    selectable, so nothing was left to repair; the only thing missing was
    something to RUN the producer. notify_discord_signals is called from
    exactly one place, the refresh pass at :17, and that pass had just been
    killed mid-run by the deploy chain (the scheduler restarted 15:22:48Z).
    "Post this pick now" therefore had no answer but "wait for the next cron",
    which §1b says is not an answer -- the worker holds the webhooks and the
    queue polls every five minutes.

    NOTHING IS BYPASSED, and that is the whole safety argument. This calls the
    ordinary producer by its ordinary name: the started-game guard still holds,
    the model_action_thresholds cut still holds, and the push_sent ledger still
    holds, so the job posts what is unposted and nothing else. Run it twice and
    the second run posts zero. It changes WHEN the producer runs, never what it
    selects -- which is also why it needs no date-list gate the way
    notify_discord_restate does: a restatement re-publishes something already
    sent, this one can only ever send something that never was.

    target_date is optional and bounds only picks with NO commence_time (§the
    _new_signals docstring); a pick whose game has a real start time in the
    future is reached whatever date is passed. Omit it for "today".
    """
    from tracking.discord_notifier import notify_discord_signals

    target_date = kw.get("target_date") or None
    posted = notify_discord_signals(target_date=target_date)
    return {"target_date": target_date or "today", "posted": posted}


def _validate_publish_discord_signals(args: dict) -> dict:
    raw = str(args.get("target_date") or "").strip()
    if not raw:
        return {}
    if len(raw) != 10 or raw.count("-") != 2:
        raise ValueError("target_date must be YYYY-MM-DD")
    return {"target_date": raw}


def _job_discord_probe(**kw):
    """Ask Discord WHICH CHANNEL each configured webhook actually points at.

    WHY THIS EXISTS. 2026-09-05, mike: "there are NO UFC picks in the channel."
    The ledger disagreed -- `push_sent` holds a `discord_signal` row for
    `UFC_2026-09-05_ryan-spann_mario-pinto:ufc_total_rounds` WITH a Discord
    message_id, which is only written after a webhook returned 2xx and handed
    back a message. So a message was created somewhere. The one thing neither
    the ledger nor the code can tell you is WHERE: routing is
    `DISCORD_WEBHOOK_{SPORT}` (config.DISCORD_WEBHOOKS), the URL lives only in
    the worker's environment, and a URL pointing at the wrong channel looks
    identical to a correct one from every angle except Discord's.

    So ask Discord. `GET /api/webhooks/{id}/{token}` returns the webhook's own
    metadata -- channel_id, guild_id, its display name -- and POSTS NOTHING.
    No member sees anything; this cannot publish a pick, delete one, or touch
    the ledger.

    THE URL IS NEVER RETURNED. Only the ids and the webhook's display name go
    into the job result, which is stored in Postgres and read by a human: a
    webhook URL is a bearer credential, and a job result is not the place for
    one.

    Reading the answer: two sports sharing a channel_id, or a sport whose
    channel_id equals the free/ops channel, is the bug. A 404 means the webhook
    was deleted after it last posted.
    """
    import requests

    import config

    targets = {f"sport:{sport}": url
               for sport, url in config.DISCORD_WEBHOOKS.items()}
    # The per-sport LIVE channels (mike, 2026-09-09). A live channel sharing
    # its id with the sport's pre-game channel is the mis-paste this probe
    # exists to catch.
    targets.update({f"live:{sport}": url
                    for sport, url in config.DISCORD_WEBHOOKS_LIVE.items()})
    for label, attr in (("default", "DISCORD_WEBHOOK_DEFAULT"),
                        ("live", "DISCORD_WEBHOOK_LIVE"),
                        ("results", "DISCORD_WEBHOOK_RESULTS"),
                        ("free", "DISCORD_WEBHOOK_FREE"),
                        ("ops", "DISCORD_WEBHOOK_OPS")):
        url = getattr(config, attr, "") or ""
        if url:
            targets[label] = url

    out: dict = {}
    for label, url in sorted(targets.items()):
        try:
            # Strip any query string (?wait=true and friends) -- the metadata
            # endpoint is the bare webhook URL.
            resp = requests.get(url.split("?")[0], timeout=15)
            if resp.status_code == 200:
                body = resp.json()
                out[label] = {"status": 200,
                              "channel_id": body.get("channel_id"),
                              "guild_id": body.get("guild_id"),
                              "webhook_name": body.get("name")}
            else:
                out[label] = {"status": resp.status_code,
                              "body": resp.text[:200]}
        except Exception as exc:                              # noqa: BLE001
            out[label] = {"error": str(exc)[:200]}

    channels = [v.get("channel_id") for v in out.values() if v.get("channel_id")]
    out["_summary"] = {
        "probed": len(targets),
        "distinct_channels": len(set(channels)),
        "collisions": sorted({c for c in channels if channels.count(c) > 1}),
    }
    return out


def _validate_publish_x_results(args: dict) -> dict:
    game_date = str(args.get("game_date") or "").strip()
    if len(game_date) != 10 or game_date.count("-") != 2:
        raise ValueError("game_date must be YYYY-MM-DD")
    return {"game_date": game_date}


def _job_void_picks(**kw):
    """Void picks that should never have been official, from the worker.

    scripts/void_picks.py is the documented route (CLAUDE.md 1c: a pick the
    model should never have PRODUCED is voided, never deleted, so the evidence
    that it happened survives), and it needs the database -- which the session
    that finds such a row cannot write to. First use, 2026-09-07: pick 661, a
    BET on MLB_2026-04-16_NYM_LAD, a games row for a game the Stats API never
    scheduled (the 04-15 game filed again under its UTC date).

    Same rules as the script: a graded WIN/LOSS/PUSH is refused, an
    already-void pick is a no-op, and every row keeps its created_at, its line
    and its price. The reason is written to the row.
    """
    from data.db import get_connection
    from scripts.void_picks import _select, plan_voids, void

    conn = get_connection()
    try:
        rows = _select(conn, kw["pick_ids"], None, None, None)
        to_void, refused = plan_voids(rows, kw["reason"])
        void(conn, to_void, kw["reason"])
        conn.commit()
        found = {r["pick_id"] for r in rows}
        return {"voided":  [r["pick_id"] for r in to_void],
                "refused": [[r["pick_id"], r["why"]] for r in refused],
                "missing": [p for p in kw["pick_ids"] if p not in found]}
    finally:
        conn.close()


def _validate_void_picks(args: dict) -> dict:
    raw = args.get("pick_ids")
    if not isinstance(raw, list) or not raw:
        raise ValueError("pick_ids must be a non-empty list of pick ids")
    try:
        ids = sorted({int(p) for p in raw})
    except (TypeError, ValueError):
        raise ValueError("pick_ids must be integers")
    if len(ids) > 50:
        raise ValueError(f"{len(ids)} picks in one job; a void is surgical, split it")
    reason = str(args.get("reason") or "").strip()
    if len(reason) < 20:
        raise ValueError("reason must say what was wrong with the pick "
                         "(20+ characters); it is written to the row")
    return {"pick_ids": ids, "reason": reason[:500]}


def _job_ncaaf_teams_refresh(**kw):
    """Re-pull the school registry, every classification, and PROBE the
    resolver on the worker with the names that broke. The probe is the
    verification: it runs against the registry the worker actually holds."""
    from data.ingestors.cfbd_ingestor import (ingest_ncaaf_teams, reset_school_cache,
                                              resolve_odds_api_school)
    n = ingest_ncaaf_teams(kw["season"])
    reset_school_cache()
    probe = {name: resolve_odds_api_school(name) for name in kw["probe"]}
    return {"season": kw["season"], "rows": n, "probe": probe}


def _validate_ncaaf_teams_refresh(args: dict) -> dict:
    season = int(args.get("season") or datetime.now().year)
    if not (2000 <= season <= datetime.now().year + 1):
        raise ValueError(f"season {season} out of range")
    probe = args.get("probe") or []
    if not isinstance(probe, list) or len(probe) > 50:
        raise ValueError("probe must be a list of at most 50 Odds API names")
    return {"season": season, "probe": [str(p) for p in probe]}


def _job_health_check(**kw):
    """Run the full health pass ON THE WORKER, the only machine with the whole
    environment.

    This is not a convenience. Running it anywhere else is exactly how a
    wrong-dated, half-provisioned day-set reached the board on 2026-09-08:
    prop-probe holds DATABASE_URL but no `TZ`, so `run_date` came out as the UTC
    date -- TOMORROW, after 8pm ET -- and every "yesterday" gate shifted a day
    forward; and it holds none of the per-sport DISCORD_WEBHOOK_* vars, so
    `signal_delivery` reported CRIT SKIPPED about a system that was fine. Twelve
    red rows, none of them real, sitting on top of a board that was actually
    five. The worker has TZ, every webhook and the database, so the answer it
    writes is the answer.
    """
    from tracking.system_health import run_system_health
    res = run_system_health(kw.get("run_date") or None)
    return {"ok": res["ok"], "crit": res["crit"], "warn": res["warn"],
            "checks": len(res.get("results") or [])}


def _validate_health_check(args: dict) -> dict:
    run_date = args.get("run_date")
    if run_date in (None, ""):
        # The default is the point: run_system_health resolves it from
        # config.today_et(), never from the caller's clock.
        return {}
    run_date = str(run_date)
    try:
        datetime.strptime(run_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"run_date must be YYYY-MM-DD, got {run_date!r}") from exc
    return {"run_date": run_date}


JOBS = {
    "void_picks":      (_job_void_picks,       _validate_void_picks),
    # Read-mostly: writes only system_health_checks. Here so nobody has to
    # borrow another service's container to run it -- see _job_health_check.
    "health_check":    (_job_health_check,     _validate_health_check),
    "ncaaf_teams_refresh": (_job_ncaaf_teams_refresh, _validate_ncaaf_teams_refresh),
    "publish_x_results": (_job_publish_x_results, _validate_publish_x_results),
    "publish_discord_signals": (_job_publish_discord_signals,
                                _validate_publish_discord_signals),
    "derive_first_pitch": (_job_derive_first_pitch, lambda a: {}),
    # Read-only: asks Discord which channel each webhook points at.
    "discord_probe": (_job_discord_probe, lambda a: {}),
    "relabel_in_play": (_job_relabel_in_play, _validate_relabel),
    "savant_refresh":  (_job_savant_refresh,   _validate_savant),
    "retrain_model":   (_job_retrain_model,    _validate_retrain),
    "historical_odds": (_job_historical_odds,  _validate_historical_odds),
    "game_log_backfill": (_job_game_log_backfill, _validate_game_log_backfill),
    "ncaaf_player_backfill": (_job_ncaaf_player_backfill,
                              _validate_ncaaf_player_backfill),
    "ncaaf_prop_odds": (_job_ncaaf_prop_odds,  _validate_ncaaf_prop_odds),
    "market_coverage": (_job_market_coverage,  _validate_market_coverage),
}


# ── queueing ─────────────────────────────────────────────────────────────────

def enqueue(conn, job_type: str, args: dict | None = None,
            requested_by: str = "claude", note: str = "",
            dedupe_key: str | None = None) -> int | None:
    """Validate and insert. Returns the new job_id, or None if the key existed.

    Validation happens HERE as well as at run time so a bad request fails in
    front of the person making it rather than half-way through a paid pull.
    """
    if job_type not in JOBS:
        raise ValueError(f"unknown job_type {job_type!r}; known: {sorted(JOBS)}")
    _, validator = JOBS[job_type]
    cleaned = validator(args or {})
    ensure_schema(conn)
    row = conn.execute("""
        INSERT INTO worker_jobs (dedupe_key, job_type, args, requested_by, note)
        VALUES (%s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (dedupe_key) DO NOTHING
        RETURNING job_id
    """, (dedupe_key, job_type, json.dumps(cleaned), requested_by, note)).fetchone()
    conn.commit()
    return int(row[0]) if row else None


# ── declared jobs: a queued job is a commit ──────────────────────────────────
#
# 2026-09-01. The obvious way to ask for a job is to INSERT a row, and that is
# what the queue is for -- but the Supabase MCP a dev session holds is READ
# ONLY, so the one participant most likely to want a backfill run cannot ask
# for one. Rather than widen that access, requests live in a file:
# jobs/declared_jobs.json, enqueued by the worker on its next tick, deduped by
# a stable key so re-reading the file is free.
#
# It turns out to be the better design regardless. A paid backfill or a retrain
# arrives as a diff with a note attached, gets reviewed like any other change,
# and the record of WHY it ran is in git next to the code that ran it -- rather
# than in a table row whose author is a service account.

DECLARED_JOBS_FILE = Path(__file__).resolve().parent.parent / "jobs" / "declared_jobs.json"


def sync_declared_jobs(conn, path: Path | None = None) -> list[int]:
    """Enqueue anything in the declarations file that is not queued already.

    Idempotent through `dedupe_key`: an entry already seen inserts nothing, so
    this runs on every tick without accumulating duplicates. A malformed entry
    is logged and skipped rather than raised -- one bad declaration must not
    stop the queue from draining the good ones.
    """
    path = path or DECLARED_JOBS_FILE
    try:
        declared = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        logger.warning(f"declared jobs unreadable ({exc}); skipping")
        return []

    queued = []
    for entry in declared if isinstance(declared, list) else []:
        try:
            key = str(entry["key"])
            job_id = enqueue(conn, entry["job_type"], entry.get("args") or {},
                             requested_by=entry.get("requested_by", "declared"),
                             note=entry.get("note", ""), dedupe_key=key)
        except Exception as exc:  # noqa: BLE001 — see docstring
            logger.warning(f"declared job {entry!r} rejected: {exc}")
            continue
        if job_id is not None:
            logger.info(f"declared job {key} queued as {job_id}")
            queued.append(job_id)
    return queued


# ── running ──────────────────────────────────────────────────────────────────

def _reclaim_stale(conn, now: datetime) -> int:
    """Return orphaned jobs to the queue. MUST be called holding the lock.

    Holding the queue lock means exactly one runner exists, so ANY row still
    marked `running` is orphaned by definition -- its container died, almost
    always mid-deploy. That makes the reclaim immediate and exact, where the
    original 180-minute timer left an interrupted retrain parked for three
    hours and, worse, invited the overlap that exhausted the pooler.

    The attempt cap stays: without it a job that kills the container comes
    back, kills it again, and the queue never drains.
    """
    cur = conn.execute("""
        UPDATE worker_jobs SET status = CASE WHEN attempts >= %s THEN 'failed'
                                             ELSE 'pending' END,
                               error  = CASE WHEN attempts >= %s
                                             THEN 'abandoned after ' || attempts ||
                                                  ' attempts (worker died mid-run)'
                                             ELSE COALESCE(error, '') ||
                                                  ' [reclaimed: worker died mid-run]'
                                             END,
                               -- Give the attempt back. A container restart is
                               -- not the job failing, and on 2026-09-01 my own
                               -- merges consumed two jobs' entire retry budget:
                               -- every deploy orphaned whatever was running and
                               -- the re-claim charged it an attempt. claim_one
                               -- adds one back, so this nets to zero for a
                               -- death that was not the job's fault.
                               attempts = GREATEST(attempts - 1, 0),
                               claimed_at = NULL
        WHERE status = 'running'
        RETURNING job_id
    """, (MAX_ATTEMPTS, MAX_ATTEMPTS)).fetchall()
    conn.commit()
    return len(cur or [])


def claim_one(conn) -> dict | None:
    """Atomically take the oldest pending job. None when the queue is empty.

    SKIP LOCKED is what makes this safe with more than one service polling:
    the second worker steps over the row the first is taking rather than
    blocking on it or, worse, taking it too.
    """
    row = conn.execute("""
        UPDATE worker_jobs
           SET status = 'running', claimed_at = NOW(), heartbeat_at = NOW(),
               attempts = attempts + 1
         WHERE job_id = (
               SELECT job_id FROM worker_jobs
                WHERE status = 'pending'
                ORDER BY created_at
                LIMIT 1 FOR UPDATE SKIP LOCKED)
        RETURNING job_id, job_type, args, attempts
    """).fetchone()
    conn.commit()
    if not row:
        return None
    job_id, job_type, args, attempts = row
    return {"job_id": int(job_id), "job_type": job_type,
            "args": args if isinstance(args, dict) else json.loads(args or "{}"),
            "attempts": int(attempts)}


def run_one(conn, now: datetime | None = None) -> dict:
    """Claim and run at most one job. Safe to call on a schedule forever."""
    now = now or datetime.now(timezone.utc)
    if not _enabled():
        return {"status": "disabled"}

    ensure_schema(conn)
    sync_declared_jobs(conn)

    # Take the lock BEFORE claiming. Claiming first and then finding the queue
    # busy would leave a job marked `running` that nobody is running.
    got = conn.execute("SELECT pg_try_advisory_lock(%s)",
                       (QUEUE_LOCK_KEY,)).fetchone()
    if not (got and got[0]):
        logger.info("job queue: another worker holds the lock — skipping this tick")
        return {"status": "busy"}

    try:
        reclaimed = _reclaim_stale(conn, now)
        if reclaimed:
            logger.warning(f"job queue: reclaimed {reclaimed} stale job(s)")

        job = claim_one(conn)
        if job is None:
            return {"status": "idle", "reclaimed": reclaimed}
        return _execute(conn, job)
    finally:
        try:
            conn.execute("SELECT pg_advisory_unlock(%s)", (QUEUE_LOCK_KEY,))
            conn.commit()
        except Exception:  # noqa: BLE001 — the session ending releases it anyway
            pass


def _execute(conn, job: dict) -> dict:
    """Run one already-claimed job and record the outcome."""

    logger.info(f"job {job['job_id']} {job['job_type']} starting "
                f"(attempt {job['attempts']}) args={job['args']}")
    fn, validator = JOBS.get(job["job_type"], (None, None))
    try:
        if fn is None:
            raise ValueError(f"unknown job_type {job['job_type']!r} — the row "
                             "predates this build, or the type was removed")
        result = fn(**validator(job["args"]))
        conn.execute("""
            UPDATE worker_jobs SET status='done', finished_at=NOW(),
                                   result=%s::jsonb, error=NULL
             WHERE job_id=%s
        """, (json.dumps(result, default=str), job["job_id"]))
        conn.commit()
        logger.success(f"job {job['job_id']} {job['job_type']} done")
        _announce(job, ok=True, detail=json.dumps(result, default=str)[:900])
        return {"status": "done", "job": job, "result": result}
    except Exception as exc:  # noqa: BLE001 — every failure is recorded, not raised
        err = f"{type(exc).__name__}: {exc}\n{traceback.format_exc()[-1500:]}"
        final = job["attempts"] >= MAX_ATTEMPTS
        conn.execute("""
            UPDATE worker_jobs SET status = %s, finished_at = NOW(), error = %s
             WHERE job_id = %s
        """, ("failed" if final else "pending", err, job["job_id"]))
        conn.commit()
        logger.error(f"job {job['job_id']} {job['job_type']} failed "
                     f"(attempt {job['attempts']}/{MAX_ATTEMPTS}): {exc}")
        if final:
            _announce(job, ok=False, detail=str(exc)[:900])
        return {"status": "failed", "job": job, "error": str(exc), "final": final}


def _announce(job: dict, ok: bool, detail: str) -> None:
    from tracking.discord_notifier import _post

    body = (f"`{job['job_type']}` job {job['job_id']}\n"
            f"args: `{json.dumps(job['args'], default=str)[:300]}`\n"
            f"```{detail}```")
    url = config.DISCORD_WEBHOOK_OPS
    if not url:
        logger.critical(f"JOB {'DONE' if ok else 'FAILED'} (no DISCORD_WEBHOOK_OPS)\n{body}")
        return
    _post(url, {"embeds": [{
        "title": ("✅ Worker job finished" if ok else "❌ Worker job failed"),
        "description": body[:4000],
        "color": 0x2ECC71 if ok else 0xE74C3C,
    }]})


if __name__ == "__main__":  # pragma: no cover — manual invocation
    import argparse

    from data.db import get_connection

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--enqueue", choices=sorted(JOBS))
    ap.add_argument("--args", default="{}", help="JSON object of job arguments")
    ap.add_argument("--run", action="store_true", help="run one pending job now")
    a = ap.parse_args()

    _conn = get_connection()
    try:
        if a.enqueue:
            print("queued job", enqueue(_conn, a.enqueue, json.loads(a.args),
                                        requested_by="cli"))
        if a.run:
            print(json.dumps(run_one(_conn), indent=2, default=str))
    finally:
        _conn.close()
