"""
The pipeline watch, as a cron job on the worker rather than a scheduled agent.

WHY IT MOVED HERE (2026-09-03, mike: "move the watch to the worker")
--------------------------------------------------------------------
Sentinel was a scheduled Claude session that read the database through the
Supabase MCP. Routine sessions carry no `mcp__*` entry in their permitted-tool
list, so every one of those reads raised a permission prompt. Unattended, that
prompt has nobody to answer it: two consecutive daily runs died in
REQUIRES_ACTION having reported nothing (`mcp__Railway__get-logs` on 09-01,
`mcp__Supabase__list_tables` on 09-02). Attended, it is worse -- the prompts
queue up on a person's screen and a watch that pages you every morning is not
a watch, it is a chore.

The fix is to stop needing the permission. The worker already holds
DATABASE_URL and DISCORD_WEBHOOK_OPS and already runs eleven cron jobs; it can
read the report and post it without asking anyone for anything.

WHAT IS LOST, STATED PLAINLY
----------------------------
Judgement. An agent could notice something nobody wrote a rule for. This
cannot -- it applies the six rules from the watch's contract and nothing else.
That is a real downgrade, and the honest trade is: a narrower watch that runs
every day beats a broader one that has not completed a run since 2026-08-31.

The rules are deliberately conservative. A false alarm every week trains the
reader to ignore the channel, which is the same silence by another route.
"""

from __future__ import annotations

import os
from datetime import date, timedelta

from loguru import logger

import config
from tracking.watch_util import post_and_ledger, query_rows

# A step has to be slow enough to matter AND relatively slower than its own
# baseline. Either test alone is noise: a 0.2s step that doubles is 0.2s, and a
# 40s step that has always taken 40s is not a regression.
REGRESSION_MIN_AVG_S = 5.0
REGRESSION_FACTOR = 1.5
REGRESSION_BASELINE_DAYS = 7

# The pre-game poller runs ~45k credits/day at its 30s interval against a 60k
# cap. Well above that means something is looping, and the account resets
# monthly rather than being unlimited.
BURN_WARN_CREDITS = 55_000

# Both weekly jobs are caught up on boot when older than this (scheduler.py).
WEEKLY_STALE_DAYS = 8

# A kind that fires REGULARLY and then stops has gone quiet. Nothing is
# ledgered unless a POST confirmed, so this only ever compares successes
# against successes.
#
# The cadence floor is what makes it usable. Measured against production
# 2026-09-03, before this shipped: "fired in the fortnight but not today"
# flagged `discord_restate` and `discord_results_restate`, each of which had
# fired on exactly 1 day of 14 -- a restate only happens when a pick is
# restated, so it is occasional BY DESIGN and would have been flagged every
# single morning forever. A false alarm that never stops is how a channel
# becomes unreadable, which is silence by another route.
#
# At >=7 of 14 days the rule still covers everything that actually runs daily
# (live_signal 14/14, new_bet 11/14, discord_signal 8/14) and drops the two
# occasional ones.
SILENT_KIND_LOOKBACK_DAYS = 14
SILENT_KIND_MIN_ACTIVE_DAYS = 7


def _enabled() -> bool:
    return os.environ.get("RUN_PIPELINE_WATCH", "1") not in ("0", "false", "False")


def _rows(conn, sql, params=()):
    """Delegates to the shared helper — the rollback lives in one place now.

    Extracted to tracking/watch_util.py 2026-09-03 when the calibration
    judgement pass became the second watch. §1b prefers a shared helper over
    a per-watch copy, and this one in particular: the missing rollback is bug
    #390, which was fixed here, then found AGAIN in scripts/pipeline_report.py
    on this watch's first live run (#417). A third copy would have been a third
    chance to omit it.
    """
    return query_rows(conn, sql, params, label="pipeline_watch")


# ── the six rules, each a pure function of rows so it can be tested ──────────

def findings_from_passes(rows) -> list[str]:
    """A pass that failed, aborted, or never finished.

    `minutes` is NULL when finished_at is NULL -- the pass died OR its
    finish-ledger call failed. The contract says not to over-read that, so the
    wording stays neutral.
    """
    out = []
    for r in rows or []:
        started, minutes, steps_total, failed = (list(r) + [None] * 4)[:4]
        if minutes is None:
            out.append(f"pass at {started} never recorded a finish "
                       f"(died, or its finish-ledger call failed)")
        elif failed:
            out.append(f"pass at {started} recorded {failed} failed step(s) "
                       f"of {steps_total}")
    return out


def findings_from_checks(rows) -> list[str]:
    """Any health check not OK. CRIT first — that ordering is the report's."""
    out = []
    for r in rows or []:
        name, severity, status, detail = (list(r) + [None] * 4)[:4]
        out.append(f"health check `{name}` is {status} ({severity}): {detail}")
    return out


def findings_from_burn(rows) -> list[str]:
    """Metered spend, against the cap rather than against yesterday."""
    total = 0
    errors = []
    for r in rows or []:
        source, calls, credits, errs = (list(r) + [None] * 4)[:4]
        try:
            total += int(credits or 0)
        except (TypeError, ValueError):
            pass
        if errs:
            errors.append(f"`{source}` had {errs} failed call(s)")
    out = []
    if total >= BURN_WARN_CREDITS:
        out.append(f"Odds API burn {total:,} credits in the window, at or above "
                   f"the {BURN_WARN_CREDITS:,} warning line (60k cap)")
    out.extend(errors)
    return out


def _step_regressions(conn, hours: int) -> list[str]:
    """Per-step wall clock now vs its own preceding baseline.

    The dispatch rows are the only per-step timing there is; before they
    existed only 8 of 28 steps were timed and 9 minutes of a 12-minute pass
    were invisible.
    """
    rows = _rows(conn, """
        WITH recent AS (
            SELECT replace(step, 'dispatch:', '') AS step,
                   avg(duration_s::numeric) AS avg_s
            FROM pipeline_log
            WHERE step LIKE 'dispatch:%%'
              AND created_at::timestamptz >= now() - (%s || ' hours')::interval
            GROUP BY 1
        ), baseline AS (
            SELECT replace(step, 'dispatch:', '') AS step,
                   avg(duration_s::numeric) AS avg_s
            FROM pipeline_log
            WHERE step LIKE 'dispatch:%%'
              AND created_at::timestamptz <  now() - (%s || ' hours')::interval
              AND created_at::timestamptz >= now() - (%s || ' days')::interval
            GROUP BY 1
        )
        SELECT r.step, round(r.avg_s, 1), round(b.avg_s, 1)
        FROM recent r JOIN baseline b USING (step)
        WHERE r.avg_s >= %s AND b.avg_s > 0 AND r.avg_s >= b.avg_s * %s
        ORDER BY r.avg_s - b.avg_s DESC
        LIMIT 5
    """, (hours, hours, REGRESSION_BASELINE_DAYS,
          REGRESSION_MIN_AVG_S, REGRESSION_FACTOR))
    return [f"step `{s}` averaged {now}s, against a {base}s baseline"
            for s, now, base in rows]


def _silent_kinds(conn, hours: int) -> list[str]:
    rows = _rows(conn, """
        SELECT kind,
               count(DISTINCT substring(sent_at, 1, 10)) AS days_active,
               max(sent_at) AS latest
        FROM push_sent
        WHERE sent_at::timestamptz >= now() - (%s || ' days')::interval
        GROUP BY 1
        HAVING count(DISTINCT substring(sent_at, 1, 10)) >= %s
           AND max(sent_at::timestamptz) < now() - (%s || ' hours')::interval
        ORDER BY 1
    """, (SILENT_KIND_LOOKBACK_DAYS, SILENT_KIND_MIN_ACTIVE_DAYS, hours))
    return [f"`{kind}` last delivered {latest} — it had fired on {days} of the "
            f"last {SILENT_KIND_LOOKBACK_DAYS} days"
            for kind, days, latest in rows]


def _stale_weeklies(conn, today: date | None = None) -> list[str]:
    """The two weekly jobs, and a MISSING table read as never-completed."""
    today = today or date.today()
    cutoff = (today - timedelta(days=WEEKLY_STALE_DAYS)).isoformat()
    out = []

    rows = _rows(conn, "SELECT max(run_date) FROM model_calibration_sweeps")
    newest = rows[0][0] if rows else None
    if not rows:
        out.append("`model_calibration_sweeps` is unreadable or missing — the "
                   "ModelCalibration sweep has never completed")
    elif newest is None or str(newest) < cutoff:
        out.append(f"ModelCalibration last swept {newest or 'never'} "
                   f"(stale past {WEEKLY_STALE_DAYS} days)")

    rows = _rows(conn, """
        SELECT max(as_of_date), count(DISTINCT player_type)
        FROM player_savant_stats WHERE season = %s
    """, (today.year,))
    if rows:
        newest, kinds = (list(rows[0]) + [None, None])[:2]
        if newest is None or (kinds or 0) < 2 or str(newest) < cutoff:
            out.append(f"Savant for {today.year} last pulled {newest or 'never'} "
                       f"with {kinds or 0} player type(s)")
    return out


# ── the run ─────────────────────────────────────────────────────────────────

def run_watch(conn, hours: int = 24, today: date | None = None) -> dict:
    """Collect, judge against the six rules, announce. Returns the summary."""
    if not _enabled():
        logger.info("pipeline_watch: disabled by RUN_PIPELINE_WATCH")
        return {"status": "disabled"}

    from scripts.pipeline_report import collect

    data = collect(conn, hours)

    findings: list[str] = []
    findings += findings_from_passes(data.get("recent_passes"))
    findings += findings_from_checks(data.get("failing_checks"))
    findings += findings_from_burn(data.get("api_burn_by_source"))
    findings += _step_regressions(conn, hours)
    findings += _silent_kinds(conn, hours)
    findings += _stale_weeklies(conn, today)

    picks = sum(int(r[2] or 0) for r in (data.get("picks_written") or [])
                if len(r) > 2 and str(r[2]).isdigit())
    passes = len(data.get("recent_passes") or [])

    summary = {"status": "ok", "hours": hours, "findings": findings,
               "passes": passes, "picks": picks}
    summary["posted"] = _announce_and_ledger(conn, summary, today or date.today())
    logger.info(f"pipeline_watch: {len(findings)} finding(s), "
                f"{passes} pass(es), {picks} picks, posted={summary['posted']}")
    return summary


def _announce_and_ledger(conn, summary: dict, run_day: date) -> bool:
    """Post, then record the post — in that order, and only on confirmation.

    CLAUDE.md §7: "check `push_sent` before believing a notifier ever worked —
    nothing is ledgered unless a POST confirmed, so a `kind` with zero rows
    means it has NEVER succeeded."

    Without this the watch is unverifiable: it either posted to Discord or it
    did not, and no query could tell you which. That is the same blindness the
    move off the agent was supposed to end, so a run that cannot be checked is
    not finished. `_post` returns a message id on success and None on failure,
    so it doubles as the confirmation.

    One row per day (`lock_key` is the ET run date), ON CONFLICT DO NOTHING, so
    a retry or a second container cannot double-count a morning.
    """
    return post_and_ledger(conn, "pipeline_watch", run_day,
                           lambda: _announce(summary))


def _announce(s: dict) -> bool:
    """Post EVERY run, clean or not.

    A watch that only speaks when it has news is indistinguishable from a watch
    that has stopped -- which is exactly how the agent version failed, twice,
    without anyone noticing until a person went looking.
    """
    from tracking.discord_notifier import _post

    if s["findings"]:
        body = "\n".join(f"• {f}" for f in s["findings"][:15])
        title = f"🔎 Pipeline watch — {len(s['findings'])} finding(s)"
        colour = 0xE67E22
    else:
        body = (f"Nothing to flag. {s['passes']} pass(es) recorded, "
                f"{s['picks']} picks written in the last {s['hours']}h.")
        title = "🔎 Pipeline watch — clean"
        colour = 0x2ECC71

    url = config.DISCORD_WEBHOOK_OPS
    if not url:
        logger.critical(f"PIPELINE WATCH (no DISCORD_WEBHOOK_OPS set)\n{body}")
        return False
    return bool(_post(url, {"embeds": [{"title": title,
                                        "description": body[:4000],
                                        "color": colour}]}))


if __name__ == "__main__":  # pragma: no cover — manual invocation
    import json

    from data.db import get_connection

    _conn = get_connection()
    try:
        print(json.dumps(run_watch(_conn), indent=2, default=str))
    finally:
        _conn.close()
