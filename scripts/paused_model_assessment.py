"""Can a paused model be made profitable? Run the sweep; never ask to unpause.

mike, 2026-09-12: *"I didn't fucking tell you to pause the NCA models. I said
find profitable cuts. Find profitable models. I want profitable backtest... I
need you to always run an assessment if these models can be profitable. That is
the whole point."*

CLAUDE.md section 1b now carries that as a standing rule. This is the tool it
names: for every model in `config.PAUSED_MODELS`, sweep its own cut over its own
record and say whether ANY cut clears the section-7 standards -- plateau not
peak, positive in both halves of its own era, enough settled bets to mean
something -- or that none does, with the grid.

THE ERA THE RECORD BELONGS TO
-----------------------------
A record measured across a retrain describes a BLEND of the live model and its
dead predecessor, and this is not a footnote: every candidate cut this tool
found on pooled history collapsed to a handful of bets once scoped to the
artifact actually deployed (mlb_prop_pitcher_k: +3.5% over 134 pooled, -0.6%
over 19 on the model that is live). So every cell is reported twice -- pooled,
and on the CURRENT artifact from `model_registry.trained_on WHERE is_active` --
and a cut is only ever a candidate on the second.

TWO POPULATIONS, AND THE DIFFERENCE MATTERS
-------------------------------------------
* `mv_scored_pick_outcomes` grades the WHOLE universe a model scored: BET,
  AVOID and dead-zone NONE alike. That is the population section 7's evaluation
  rule requires, because a BET-only sample contains only picks that already
  cleared the live bar and cannot see what a looser cut would draw from.
* Some models have NO such universe: the live models write no NONE rows by
  construction (a live game would write hundreds of dead rows a day), and
  NCAAF/UFC/WNBA game models carry AVOID and NONE rows that are never settled.
  For those this falls back to their settled BETs and SAYS SO. A sweep on a
  BET-only sample is systematically optimistic; it is reported as a floor on
  what is knowable, not as a backtest.

`scripts/calibrated_threshold_sweep.py` is the sibling that sweeps the same
universe on CALIBRATED probabilities for the models that have a promoted map.
Run both; they answer different questions and this one is the wider net.

    python -m scripts.paused_model_assessment
    python -m scripts.paused_model_assessment --model mlb_prop_pitcher_er
    python -m scripts.paused_model_assessment --all        # every model, not just paused
"""
from __future__ import annotations

import argparse
import math
from collections import defaultdict

import config
from data.db import get_connection

PROB_GRID = [0.50, 0.54, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.74, 0.78]
EDGE_GRID = [0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.16, 0.20]
MIN_SETTLED = 25       # below this a cell's ROI is a number, not a result
MIN_PLATEAU = 4        # of 8 neighbours positive


def _units(odds: float | None, result: str) -> float | None:
    """Units won or lost on one flat bet at `odds`. None when unpriced -- a
    settled pick with no price fabricates -110 in profit_flat (CLAUDE.md 6)."""
    if odds is None or result == "PUSH":
        return 0.0 if result == "PUSH" else None
    if result == "WIN":
        return odds / 100.0 if odds > 0 else 100.0 / abs(odds)
    if result == "LOSS":
        return -1.0
    return None


def active_era(conn) -> dict[str, str]:
    """model_id -> the date its LIVE artifact was trained. A record older than
    this belongs to a model that no longer exists."""
    return {m: str(d) for m, d in conn.execute(
        "SELECT model_id, MAX(trained_on) FROM model_registry "
        "WHERE is_active = 1 GROUP BY model_id").fetchall()}


def fetch(conn, model_id: str) -> tuple[list[dict], str]:
    """(rows, population). Prefers the graded universe; falls back to settled
    BETs, which is named in the output so no reader mistakes one for the other."""
    rows = conn.execute("""
        SELECT game_date, model_probability::float8, decision_edge::float8,
               decision_odds::float8, result
        FROM mv_scored_pick_outcomes
        WHERE model_id = %s AND result IN ('WIN','LOSS','PUSH')
    """, (model_id,)).fetchall()
    population = "graded universe (BET + AVOID + NONE)"
    if not rows:
        rows = conn.execute("""
            SELECT game_date, model_probability::float8,
                   COALESCE(decision_edge, edge)::float8,
                   COALESCE(decision_odds, dk_odds)::float8, result
            FROM picks
            WHERE model_id = %s AND signal_type = 'BET'
              AND result IN ('WIN','LOSS','PUSH')
        """, (model_id,)).fetchall()
        population = "SETTLED BETS ONLY -- optimistic, not a backtest"
    out = []
    for d, p, e, o, res in rows:
        u = _units(o, res)
        if p is None or e is None or u is None:
            continue
        out.append({"date": str(d), "p": float(p), "edge": float(e), "u": u,
                    "res": res})
    return out, population


def grade(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {"n": 0, "w": 0, "l": 0, "units": 0.0, "roi": None, "ci_lo": None}
    w = sum(1 for r in rows if r["res"] == "WIN")
    l = sum(1 for r in rows if r["res"] == "LOSS")
    units = sum(r["u"] for r in rows)
    roi = 100 * units / n
    # Normal-approximation lower bound on ROI, from the spread of the per-bet
    # results. Wide by construction on a small sample, which is the point.
    mean = units / n
    var = sum((r["u"] - mean) ** 2 for r in rows) / n if n > 1 else 0.0
    se = math.sqrt(var / n) if n > 1 else 0.0
    return {"n": n, "w": w, "l": l, "units": round(units, 2),
            "roi": round(roi, 1), "ci_lo": round(100 * (mean - 1.96 * se), 1)}


def sweep(rows: list[dict]) -> list[dict]:
    cells = []
    for pmin in PROB_GRID:
        for emin in EDGE_GRID:
            keep = [r for r in rows if r["p"] >= pmin and r["edge"] >= emin]
            if keep:
                cells.append({"min_prob": pmin, "min_edge": emin, **grade(keep)})
    by = {(c["min_prob"], c["min_edge"]): c for c in cells}
    for c in cells:
        pi, ei = PROB_GRID.index(c["min_prob"]), EDGE_GRID.index(c["min_edge"])
        good = 0
        for dp in (-1, 0, 1):
            for de in (-1, 0, 1):
                if dp == de == 0:
                    continue
                if 0 <= pi + dp < len(PROB_GRID) and 0 <= ei + de < len(EDGE_GRID):
                    n = by.get((PROB_GRID[pi + dp], EDGE_GRID[ei + de]))
                    if n and (n["roi"] or 0) > 0:
                        good += 1
        c["plateau"] = good
    return cells


def assess(conn, model_id: str, era: str | None = None) -> dict:
    rows, population = fetch(conn, model_id)
    era_rows = [r for r in rows if era and r["date"] >= era]
    cur = config.ACTION_THRESHOLDS.get(model_id, {})
    cur_rows = [r for r in rows
                if r["p"] >= cur.get("min_prob", 0)
                and r["edge"] >= cur.get("min_edge", 0)]
    current = grade(cur_rows)

    cells = sweep(rows)
    usable = [c for c in cells if c["n"] >= MIN_SETTLED]
    positive = [c for c in usable if (c["roi"] or 0) > 0]
    plateau = [c for c in positive if c["plateau"] >= MIN_PLATEAU]

    # The time split, which killed every false positive in the NCAAF search:
    # a cut is endorsed only if it is positive in BOTH halves of its own era.
    ordered = sorted(rows, key=lambda r: r["date"])
    mid = len(ordered) // 2
    first, second = ordered[:mid], ordered[mid:]
    survivors = []
    for c in plateau:
        def _half(h):
            k = [r for r in h if r["p"] >= c["min_prob"] and r["edge"] >= c["min_edge"]]
            return grade(k)
        a, b = _half(first), _half(second)
        c["half_a"], c["half_b"] = a["roi"], b["roi"]
        if (a["roi"] or 0) > 0 and (b["roi"] or 0) > 0 and a["n"] and b["n"]:
            survivors.append(c)

    best = max(survivors, key=lambda c: c["roi"]) if survivors else (
        max(plateau, key=lambda c: c["roi"]) if plateau else (
            max(positive, key=lambda c: c["roi"]) if positive else None))

    if best is None:
        verdict = f"NO CUT CLEARS. {len(usable)} cells with {MIN_SETTLED}+ settled, none profitable."
    elif best in survivors:
        verdict = (f"CANDIDATE {best['min_prob']}/{best['min_edge']}: "
                   f"{best['w']}-{best['l']} {best['roi']:+.1f}% "
                   f"({best['half_a']:+.1f}% then {best['half_b']:+.1f}%)")
    elif best in plateau:
        verdict = (f"FAILS THE TIME SPLIT at {best['min_prob']}/{best['min_edge']} "
                   f"({best['half_a']}% then {best['half_b']}%)")
    else:
        verdict = (f"PEAK, NOT A PLATEAU at {best['min_prob']}/{best['min_edge']} "
                   f"({best['plateau']}/8 neighbours positive)")

    # THE ERA CHECK. A cut that clears on pooled history has still only been
    # measured on a model that may no longer exist; this is the same cell
    # graded on the artifact that is actually deployed.
    era_grade = None
    if best is not None and era:
        era_grade = grade([r for r in era_rows
                           if r["p"] >= best["min_prob"] and r["edge"] >= best["min_edge"]])
        if era_grade["n"] < MIN_SETTLED:
            verdict += (f" -- but only {era_grade['n']} settled on the artifact live "
                        f"since {era}, so it is NOT yet evidence about this model")
        elif (era_grade["roi"] or 0) <= 0:
            verdict += (f" -- and {era_grade['roi']:+.1f}% over {era_grade['n']} "
                        f"on the artifact live since {era}")

    return {"model_id": model_id, "population": population, "rows": len(rows),
            "era": era, "era_rows": len(era_rows), "era_grade": era_grade,
            "current": current, "cells": cells, "usable": len(usable),
            "positive": len(positive), "plateau": len(plateau),
            "survivors": survivors, "best": best, "verdict": verdict}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model")
    ap.add_argument("--all", action="store_true",
                    help="every registered model, not only the paused ones")
    ap.add_argument("--grid", action="store_true",
                    help="print the whole neighbourhood, not just the verdict")
    a = ap.parse_args()

    if a.model:
        models = [a.model]
    elif a.all:
        models = sorted(config.ACTION_THRESHOLDS)
    else:
        # BOTH pause registers: config.PAUSED_MODELS is what a person chose,
        # model_auto_pauses is what the 250-bet review decided on its own
        # (tracking/threshold_review.py). Sweeping only the first missed
        # mlb_prop_batter_runs and mlb_prop_pitcher_k on 2026-09-12, the day
        # after the review paused them -- exactly the two models most in need
        # of the assessment.
        from models.scorer import _auto_paused_models
        models = sorted(set(config.PAUSED_MODELS) | set(_auto_paused_models()))

    conn = get_connection()
    try:
        eras = active_era(conn)
        print(f"{'model':28s} {'rows':>6s} {'era':>5s} {'current cut':>14s} {'record':>18s}  verdict")
        for m in models:
            r = assess(conn, m, eras.get(m))
            c, cut = r["current"], config.ACTION_THRESHOLDS.get(m, {})
            cut_s = f"{cut.get('min_prob','-')}/{cut.get('min_edge','-')}"
            rec = (f"{c['w']}-{c['l']} {c['roi']:+.1f}%" if c["roi"] is not None
                   else "no settled rows")
            print(f"{m:28s} {r['rows']:6d} {r['era_rows']:5d} {cut_s:>14s} "
                  f"{rec:>18s}  {r['verdict']}")
            if "SETTLED BETS ONLY" in r["population"]:
                print(f"{'':28s} {'':6s} {'':>18s} {'':>20s}  population: {r['population']}")
            if a.grid:
                for cell in sorted(r["cells"], key=lambda x: -(x["roi"] or -999))[:12]:
                    print(f"    {cell['min_prob']:.2f}/{cell['min_edge']:.2f} "
                          f"n={cell['n']:4d} {cell['w']}-{cell['l']} "
                          f"{cell['roi']:+6.1f}% ci_lo {cell['ci_lo']:+6.1f}% "
                          f"plateau {cell['plateau']}/8")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
