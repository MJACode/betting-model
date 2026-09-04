"""
The ModelCalibration JUDGEMENT pass, as a cron job on the worker.

WHY IT MOVED HERE (2026-09-03, mike: "move the modelcalibration judgement pass
to the worker")
---------------------------------------------------------------------------
The sweep has always been mechanical and has always run here
(`tracking/model_calibration_agent.py`, Mondays 8:30am ET) -- it writes one row
per model per run_date into `model_calibration_sweeps`. Reading those rows and
deciding what they MEAN was the judgement half, and it never had a working
home:

  * Its own Routine was created with no Supabase connector at all, so it could
    never read the one table it existed to read.
  * The work was then folded into Sentinel's prompt. Sentinel died in
    REQUIRES_ACTION on two consecutive days and was retired.
  * Janitor, the last scheduled agent, was retired 2026-09-03 after four runs
    landed nothing.

So the rows have been accumulating unread. This module reads them.

WHAT IS LOST, STATED PLAINLY
----------------------------
Judgement, in the sense an agent had it. This applies fixed rules and nothing
else; it cannot notice something nobody wrote a rule for. That is a real
downgrade and the honest trade is the same one the pipeline watch made: a
narrower pass that actually runs beats a broader one that has never completed.

WHAT IT WILL NEVER DO
---------------------
Change anything. A threshold change, a pause, a promotion or a registry swap
is a model update and needs `Updated-By: <person>` (CLAUDE.md §1b). This writes
the exact `config.py` edit and the evidence into a Discord post and stops. Its
job is to make a decision unavoidable, not to make it.

WHY EVERY RULE IS A DELTA
-------------------------
Measured against production before this shipped: of the 22 models in the
2026-09-02 sweep, **13 carry a standing "RE-CUT to ..." verdict**. A rule that
reported every RE-CUT would post a wall of thirteen identical findings every
Monday forever, and a false alarm that never stops is how a channel becomes
unreadable -- which is silence by another route. That is exactly the trap the
pipeline watch's silent-kind rule fell into and was fixed for.

A verdict is a standing FACT, not an event. The event is a verdict CHANGING.
So every rule below compares this sweep against the previous one, and a first
sweep with no baseline reports that it has no baseline rather than reporting
everything as new.

TWO THINGS MEASURED HERE THAT THE OLD PROMPT GOT WRONG
------------------------------------------------------
  * It told the agent to check `model_auto_pauses`. **That table does not
    exist** (`to_regclass` returns NULL, 2026-09-03) and never has, so the
    instruction could only ever have failed. Handled as unreadable and said
    once, not silently skipped.
  * It told the agent to compare pick volume against `best_per_week`. Those are
    not comparable: `best_per_week` is the projected rate at the BEST cut,
    while live volume happens at the CURRENT cut. Comparing them measures the
    gap between two different thresholds, not a change in the model. The
    volume rule here compares `cur_n` against `cur_n`.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

from loguru import logger

import config
from tracking.watch_util import post_and_ledger, query_rows

# Every sweep number is IN-SAMPLE: the cut is chosen on the same settled bets it
# is then scored against. This method's own measured forward record is that
# shipped cuts land 13-48pp BELOW their swept claim (pooled -4.7% over 258
# forward bets). Stamped on every post, because without it a description reads
# as a forecast.
IN_SAMPLE_CAVEAT = ("Every ROI here is IN-SAMPLE. This method's shipped cuts have "
                    "landed 13-48pp below their swept claim (pooled -4.7% over 258 "
                    "forward bets), so read these as descriptions, not forecasts.")

# A cur_n move is only a signal when the count is big enough that a change is
# not one or two bets, AND the move is proportionally large. Either test alone
# is noise: 2 -> 4 doubles and means nothing, and 169 -> 171 is 2 bets.
VOLUME_SHIFT_MIN_N = 10
VOLUME_SHIFT_FACTOR = 1.5


def _enabled() -> bool:
    return os.environ.get("RUN_CALIBRATION_WATCH", "1") not in ("0", "false", "False")


def _sweep_dates(conn) -> list[str]:
    """The two most recent run_dates, newest first."""
    rows = query_rows(conn, """
        SELECT DISTINCT run_date FROM model_calibration_sweeps
        ORDER BY run_date DESC LIMIT 2
    """, label="calibration_watch")
    return [str(r[0]) for r in rows if r and r[0] is not None]


def _sweep(conn, run_date: str) -> dict:
    """One sweep keyed by model_id."""
    rows = query_rows(conn, """
        SELECT model_id, paused, settled, cur_n, cur_roi,
               best_prob, best_edge, best_n, best_roi, best_per_week,
               half_a, half_b, verdict
        FROM model_calibration_sweeps WHERE run_date = %s
    """, (run_date,), label="calibration_watch")
    cols = ("model_id", "paused", "settled", "cur_n", "cur_roi", "best_prob",
            "best_edge", "best_n", "best_roi", "best_per_week", "half_a",
            "half_b", "verdict")
    return {str(r[0]): dict(zip(cols, r)) for r in rows if r}


# ── the rules, each a pure function so it can be tested without a database ───

def verdict_changes(cur: dict, prev: dict) -> list[str]:
    """A verdict that CHANGED. A standing verdict is not news."""
    out = []
    for model_id in sorted(cur):
        if model_id not in prev:
            continue                      # roster_changes owns arrivals
        was, now = prev[model_id].get("verdict"), cur[model_id].get("verdict")
        if was == now:
            continue
        line = f"**{model_id}** verdict changed:\n    was: {_short(was)}\n    now: {_short(now)}"
        edit = _proposed_edit(cur[model_id])
        if edit:
            line += f"\n    {edit}"
        out.append(line)
    return out


def dormant_live_models(cur: dict, paused_now: set | None = None) -> list[str]:
    """A model live in config that placed no bets at its own cut.

    Reads the CURRENT `config.PAUSED_MODELS` rather than the sweep's stored
    `paused` column on purpose. That column is a snapshot of what the sweep saw
    on its run_date, so pausing a model would keep firing this rule until the
    next Monday. The question the rule asks is "is anything live and dormant
    RIGHT NOW", which is a question about config, not about last week.
    """
    paused_now = config.PAUSED_MODELS if paused_now is None else paused_now
    out = []
    for model_id in sorted(cur):
        if model_id in paused_now:
            continue
        if int(cur[model_id].get("cur_n") or 0) != 0:
            continue
        settled = cur[model_id].get("settled")
        out.append(
            f"**{model_id}** is LIVE but placed 0 bets at its own cut "
            f"({settled} settled). Dormant and broken-feed look identical here "
            f"(§7) — check whether it is still SCORING before assuming dormancy.")
    return out


def roster_changes(cur: dict, prev: dict) -> list[str]:
    """A model that entered or left the sweep.

    Leaving is the interesting direction: the sweep skips anything under
    MIN_SETTLED or anything that raised, so a model dropping out silently is a
    model nobody is measuring any more.
    """
    out = []
    for model_id in sorted(set(prev) - set(cur)):
        out.append(f"**{model_id}** DROPPED OUT of the sweep — it fell under the "
                   f"settled minimum or raised while being analysed, so it is no "
                   f"longer being measured")
    for model_id in sorted(set(cur) - set(prev)):
        out.append(f"**{model_id}** entered the sweep: {_short(cur[model_id].get('verdict'))}")
    return out


def volume_shifts(cur: dict, prev: dict) -> list[str]:
    """`cur_n` moved materially — the population at the current cut changed.

    Compares cur_n against cur_n. The old prompt compared live volume against
    `best_per_week`, which is the projected rate at a DIFFERENT threshold; that
    measures the gap between two cuts, not a change in the model.
    """
    out = []
    for model_id in sorted(cur):
        if model_id not in prev:
            continue
        now = int(cur[model_id].get("cur_n") or 0)
        was = int(prev[model_id].get("cur_n") or 0)
        if max(now, was) < VOLUME_SHIFT_MIN_N:
            continue
        if was and now and (max(now, was) / min(now, was)) < VOLUME_SHIFT_FACTOR:
            continue
        if was == now:
            continue
        out.append(f"**{model_id}** bets at its current cut moved {was} → {now}. "
                   f"A model firing far more or far less has had its MEANING "
                   f"change, not its threshold.")
    return out


def auto_pause_caveat(conn) -> str:
    """`model_auto_pauses`, which the old agent prompt told Sentinel to read.

    It does not exist and never has (`to_regclass` NULL, verified 2026-09-03),
    so that instruction could only ever have failed silently.

    A CAVEAT, not a finding — and that distinction was got wrong here first.
    Written as a finding, it fired on the very first simulated run against real
    production rows and produced the title "1 change(s)" when nothing had
    changed, while ALSO masking the no-baseline branch, which only renders when
    `findings` is empty. A missing table is a standing fact about coverage; it
    will be equally true every Monday forever, so as a finding it is precisely
    the false alarm that never stops which this module's every-rule-is-a-delta
    design exists to prevent. Building that trap into the thing written to
    avoid it is the reason simulating against real rows before shipping is
    worth the hour.

    Returns "" when the table exists, so the footnote disappears if it is ever
    created.
    """
    rows = query_rows(conn, "SELECT to_regclass('public.model_auto_pauses')",
                      label="calibration_watch")
    if rows and rows[0] and rows[0][0]:
        return ""
    return ("`model_auto_pauses` does not exist, so the 250-bet review's pauses "
            "are not covered here.")


def _short(verdict, n: int = 90) -> str:
    v = (verdict or "—").strip()
    return v if len(v) <= n else v[: n - 1] + "…"


def _proposed_edit(row: dict) -> str:
    """The exact config edit a RE-CUT verdict implies, and who may make it.

    Written out so a person can act without re-deriving it, and explicitly NOT
    made here: a threshold change is a model update needing `Updated-By:`.
    """
    verdict = (row.get("verdict") or "")
    if "RE-CUT" not in verdict.upper():
        return ""
    prob, edge = row.get("best_prob"), row.get("best_edge")
    if prob is None or edge is None:
        return ""
    return (f"proposed: ACTION_THRESHOLDS['{row['model_id']}'] → prob {prob}, "
            f"edge {edge} (n={row.get('best_n')}, halves "
            f"{row.get('half_a')}/{row.get('half_b')}) — a person decides, "
            f"needs Updated-By")


# ── the run ─────────────────────────────────────────────────────────────────

def run_calibration_watch(conn, today: date | None = None) -> dict:
    if not _enabled():
        logger.info("calibration_watch: disabled by RUN_CALIBRATION_WATCH")
        return {"status": "disabled"}

    today = today or date.today()
    dates = _sweep_dates(conn)

    if not dates:
        summary = {"status": "no_sweep", "findings": [
            "`model_calibration_sweeps` is empty or unreadable — the weekly sweep "
            "has never completed, so there is nothing to judge."], "models": 0}
        summary["posted"] = _announce_and_ledger(conn, summary, today)
        return summary

    cur = _sweep(conn, dates[0])
    prev = _sweep(conn, dates[1]) if len(dates) > 1 else {}

    findings: list[str] = []
    if prev:
        findings += verdict_changes(cur, prev)
        findings += roster_changes(cur, prev)
        findings += volume_shifts(cur, prev)
    findings += dormant_live_models(cur)

    summary = {
        "status": "ok",
        "run_date": dates[0],
        "baseline": dates[1] if len(dates) > 1 else None,
        "models": len(cur),
        "findings": findings,
        "caveats": [c for c in (auto_pause_caveat(conn),) if c],
    }
    summary["posted"] = _announce_and_ledger(conn, summary, today)
    logger.info(f"calibration_watch: {len(findings)} finding(s) across "
                f"{len(cur)} model(s), baseline={summary['baseline']}, "
                f"posted={summary['posted']}")
    return summary


def _announce_and_ledger(conn, summary: dict, run_day: date) -> bool:
    return post_and_ledger(conn, "calibration_watch", run_day,
                           lambda: _announce(summary))


def _announce(s: dict) -> bool:
    """Post EVERY run, clean or not.

    A watch that only speaks when it has news is indistinguishable from one that
    has stopped — which is how both agent versions of this failed, unnoticed,
    until a person went looking.
    """
    from tracking.discord_notifier import _post

    if s.get("status") == "no_sweep":
        title, colour = "📐 Calibration watch — no sweep to judge", 0xE74C3C
        body = "\n".join(f"• {f}" for f in s["findings"])
    elif s["findings"]:
        title = f"📐 Calibration watch — {len(s['findings'])} change(s)"
        colour = 0xE67E22
        body = "\n".join(f"• {f}" for f in s["findings"][:12])
    elif s.get("baseline") is None:
        title, colour = "📐 Calibration watch — first sweep, no baseline", 0x3498DB
        body = (f"{s['models']} model(s) swept on {s['run_date']}. Nothing to "
                f"compare against yet, so nothing is reported as changed — the "
                f"next run has a baseline.")
    else:
        title, colour = "📐 Calibration watch — nothing changed", 0x2ECC71
        body = (f"{s['models']} model(s) swept on {s['run_date']}, compared "
                f"against {s['baseline']}. No verdict, roster or volume change.")

    footnotes = [IN_SAMPLE_CAVEAT] + list(s.get("caveats") or [])
    body = body + "\n\n" + "\n".join(f"_{f}_" for f in footnotes)

    url = config.DISCORD_WEBHOOK_OPS
    if not url:
        logger.critical(f"CALIBRATION WATCH (no DISCORD_WEBHOOK_OPS set)\n{body}")
        return False
    return bool(_post(url, {"embeds": [{"title": title,
                                        "description": body[:4000],
                                        "color": colour}]}))


if __name__ == "__main__":  # pragma: no cover — manual invocation
    import json

    from data.db import get_connection

    _conn = get_connection()
    try:
        print(json.dumps(run_calibration_watch(_conn), indent=2, default=str))
    finally:
        _conn.close()
