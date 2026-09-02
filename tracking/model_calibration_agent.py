"""
ModelCalibration — the weekly agent that re-measures every model.

mike, 2026-08-31: "Run recurring calibrated sweeps on all models. it should be
global rule. this should ultimately be an agent that runs weekly called
ModelCalibration."

WHY A STANDING AGENT AND NOT A SCRIPT SOMEONE REMEMBERS TO RUN
--------------------------------------------------------------
Every threshold in this repo decays, and each time it has, the decay was found
by a person noticing a bad number rather than by anything watching:

  * `mlb_f5_moneyline` was set at +9.86%/105 in June and questioned in August
    only because a -195 pick looked wrong. It had been -9.3% for a month.
  * `mlb_runline` stopped producing picks on 2026-07-19 and nobody noticed for
    six weeks, because a model that publishes nothing looks exactly like a
    quiet slate.
  * `wnba_prop_player_threes` was unpaused on 2026-08-30 off a sweep with a
    measurement bug and re-paused a day later.

A sweep that runs only when someone is suspicious finds problems at the speed
of suspicion. This runs every Monday whether or not anyone is worried.

WHAT IT DOES, AND DELIBERATELY DOES NOT DO
------------------------------------------
DOES:
  1. Refit the calibration maps (candidates only -- promotion stays manual).
  2. Sweep EVERY registered model on calibrated probabilities, with the price
     floor applied and the time split enforced. Prob-only models included, on
     the probability dimension alone: their `edge` is measured against an
     invented baseline, so sweeping it would tune a meaningless number. Their
     exclusion is how the worst model on the board (mlb_prop_batter_hr, -63%
     over 252 bets) sat outside every review until now.
  3. Persist one row per model per run, so threshold decay becomes a series
     rather than a series of arguments.
  4. Post a summary: what drifted, what has no winning cut, what is dormant.

DOES NOT: change a threshold, pause, unpause, or promote a map. Every one of
those is a model update needing a person's name (CLAUDE.md 1b). The agent's job
is to make the decision unavoidable, not to make it.

The one automatic action in this system is the 250-bet pause rule in
tracking/threshold_review.py, which is narrow, pre-registered, and one-way.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

from loguru import logger

import config

DDL = """
CREATE TABLE IF NOT EXISTS model_calibration_sweeps (
    run_date     TEXT NOT NULL,
    model_id     TEXT NOT NULL,
    paused       BOOLEAN,
    mapped       BOOLEAN,
    settled      INTEGER,
    cur_prob     NUMERIC,
    cur_edge     NUMERIC,
    cur_n        INTEGER,
    cur_roi      NUMERIC,
    best_prob    NUMERIC,
    best_edge    NUMERIC,
    best_n       INTEGER,
    best_roi     NUMERIC,
    best_per_week NUMERIC,
    half_a       NUMERIC,
    half_b       NUMERIC,
    verdict      TEXT,
    PRIMARY KEY (run_date, model_id)
)
"""


def _enabled() -> bool:
    return os.environ.get("RUN_MODEL_CALIBRATION", "1") not in ("0", "false", "False")


def run_agent(conn, today: date | None = None, refit: bool = True) -> dict:
    """Refit, sweep every model, persist, announce. Returns the summary."""
    if not _enabled():
        logger.info("ModelCalibration: disabled by RUN_MODEL_CALIBRATION")
        return {"status": "disabled"}

    today = today or date.today()
    from models.probability_calibration import load_calibrations, run_calibration_fit
    from scripts.calibrated_threshold_sweep import MIN_SETTLED, analyse

    if refit:
        # Candidates only. A refit that moved the decision path on its own would
        # re-cut every mapped model overnight with nobody deciding to.
        try:
            run_calibration_fit(conn)
        except Exception as exc:  # noqa: BLE001 — a failed refit must not stop the sweep
            logger.warning(f"ModelCalibration: refit failed, sweeping on the "
                           f"existing maps: {exc}")

    conn.execute(DDL)
    cal = load_calibrations(conn, promoted_only=False)
    active = dict(conn.execute("""
        SELECT model_id, substring(created_at,1,10)
        FROM model_registry WHERE is_active = 1
    """).fetchall())

    rows, skipped = [], []
    for model_id in sorted(config.ACTION_THRESHOLDS):
        if model_id in config.LIVE_MODELS:
            continue                      # tracking/live_calibration.py owns these
        grid = [0.0] if model_id in config.PROB_ONLY_MODELS else None
        try:
            rep = analyse(conn, model_id, active.get(model_id), cal, today, grid)
        except Exception as exc:  # noqa: BLE001 — one model must not sink the run
            logger.warning(f"ModelCalibration: {model_id} failed: {exc}")
            skipped.append(model_id)
            continue
        if rep["total"] < MIN_SETTLED:
            skipped.append(model_id)
            continue
        rows.append(rep)

    stamp = today.isoformat()
    for rep in rows:
        cur, best = rep["current"], rep["best"]
        cfg = config.ACTION_THRESHOLDS[rep["model_id"]]
        conn.execute("""
            INSERT INTO model_calibration_sweeps
                (run_date, model_id, paused, mapped, settled,
                 cur_prob, cur_edge, cur_n, cur_roi,
                 best_prob, best_edge, best_n, best_roi, best_per_week,
                 half_a, half_b, verdict)
            VALUES (%(d)s, %(m)s, %(paused)s, %(mapped)s, %(settled)s,
                    %(cp)s, %(ce)s, %(cn)s, %(cr)s,
                    %(bp)s, %(be)s, %(bn)s, %(br)s, %(bw)s,
                    %(ha)s, %(hb)s, %(v)s)
            ON CONFLICT (run_date, model_id) DO UPDATE SET
                paused = EXCLUDED.paused, mapped = EXCLUDED.mapped,
                settled = EXCLUDED.settled, cur_n = EXCLUDED.cur_n,
                cur_roi = EXCLUDED.cur_roi, best_prob = EXCLUDED.best_prob,
                best_edge = EXCLUDED.best_edge, best_n = EXCLUDED.best_n,
                best_roi = EXCLUDED.best_roi, best_per_week = EXCLUDED.best_per_week,
                half_a = EXCLUDED.half_a, half_b = EXCLUDED.half_b,
                verdict = EXCLUDED.verdict
        """, {"d": stamp, "m": rep["model_id"], "paused": rep["paused"],
              "mapped": rep["mapped"], "settled": rep["total"],
              "cp": cfg["min_prob"], "ce": cfg["min_edge"],
              "cn": cur["n"], "cr": cur["roi"],
              "bp": best["min_prob"] if best else None,
              "be": best["min_edge"] if best else None,
              "bn": best["n"] if best else None,
              "br": best["roi"] if best else None,
              "bw": best["per_week"] if best else None,
              "ha": best.get("half_a") if best else None,
              "hb": best.get("half_b") if best else None,
              "v": rep["verdict"]})
    conn.commit()

    summary = {
        "status": "ok", "run_date": stamp,
        "swept": len(rows), "skipped": len(skipped),
        "no_cut": [r["model_id"] for r in rows if r["verdict"].startswith("NO CUT")],
        "dormant": [r["model_id"] for r in rows
                    if not r["paused"] and (r["current"]["n"] or 0) == 0],
        "actionable": [
            {"model_id": r["model_id"], "verdict": r["verdict"],
             "cur_roi": r["current"]["roi"], "best_roi": r["best"]["roi"] if r["best"] else None}
            for r in rows
            if r["verdict"].startswith(("RE-CUT", "UNPAUSE"))
        ],
    }
    _announce(summary)
    logger.info(f"ModelCalibration: swept {summary['swept']}, "
                f"{len(summary['actionable'])} actionable, "
                f"{len(summary['no_cut'])} with no cut")
    return summary


def _announce(s: dict) -> None:
    from tracking.discord_notifier import _post

    lines = [f"Swept **{s['swept']}** models "
             f"({s['skipped']} below the settled-bet floor).", ""]
    if s["actionable"]:
        lines.append(f"**{len(s['actionable'])} models where a better cut survives "
                     "the time split:**")
        lines += [f"• `{a['model_id']}` — now "
                  + (f"{a['cur_roi']:+.1f}%" if a["cur_roi"] is not None else "no bets")
                  + (f", best {a['best_roi']:+.1f}%" if a["best_roi"] is not None else "")
                  for a in s["actionable"][:12]]
        lines.append("")
    if s["no_cut"]:
        lines.append("**No profitable cut exists:** "
                     + ", ".join(f"`{m}`" for m in s["no_cut"]))
    if s["dormant"]:
        lines.append("**Live but producing nothing** (a dormant model and a broken "
                     "feed look identical): " + ", ".join(f"`{m}`" for m in s["dormant"]))
    lines += ["", "_Nothing was changed. Thresholds, pauses and promotions are "
              "model updates and need a person (CLAUDE.md §1b)._"]

    body = "\n".join(lines)
    url = config.DISCORD_WEBHOOK_OPS
    if not url:
        logger.critical(f"MODELCALIBRATION (no DISCORD_WEBHOOK_OPS set)\n{body}")
        return
    _post(url, {"embeds": [{
        "title": f"📐 ModelCalibration — weekly sweep {s['run_date']}",
        "description": body[:4000],
        "color": 0x3498DB,
    }]})


if __name__ == "__main__":  # pragma: no cover — manual invocation
    import json
    from data.db import get_connection

    _conn = get_connection()
    try:
        print(json.dumps(run_agent(_conn), indent=2, default=str))
    finally:
        _conn.close()
