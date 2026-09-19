"""Re-choose every model's prob/edge cut on its HONEST probability, with the
global EV floor already applied.

Phase 3 follow-up (2026-09-19, mike: "do the needful"). Every cut in
config.ACTION_THRESHOLDS was swept on the model's RAW claim. On 2026-09-19 every
model was promoted a calibration map that shrinks that claim (a 70% becomes ~64%)
and a 0.30 EV floor on the corrected number was put on top -- so a cut that
was "prob >= 0.72" now asks for a claim near 0.80, and several profitable
models went dark by arithmetic rather than by evidence. This re-chooses each
cut on the number the decision path actually reads tonight.

The cell predicate is EXACTLY models.scorer._decide / classify_live_signal:

    cal_p >= min_prob AND (cal_p - implied) >= min_edge
    AND expected_value(cal_p, price) >= config.min_ev_for(model_id)

after config.MODEL_MIN_ODDS, with `cal_p` = the PROMOTED map applied (what
production decides on, not today's candidate). Grid, plateau rule and time
split are scripts/calibrated_threshold_sweep's; the graded universe is
scripts/ev_floor_replay.fetch_rows', which covers all three sources.

What each universe can and cannot say, printed per model:

  full   MLB/WNBA pre-game: BET + AVOID + dead-zone NONE (the matview). A
         cut can be loosened or tightened on this.
  BET    in-play and rule models: BET rows only. A sweep here can only
         TIGHTEN; nothing looser than today's cut is measurable. The two
         in-play loops are re-cut on their bought replays instead
         (live_cut_sweep, ncaaf_inplay_history_backtest).

A cell SHIPS when it has >= MIN_SETTLED settled bets, positive ROI in BOTH
date halves, and >= 4 positive neighbours. Otherwise the current cut stays and
the grid is the answer (CLAUDE.md 1b). Nothing here writes config; the verdict
table is what a person turns into a model update.

    python -m scripts.honest_cut_sweep
    python -m scripts.honest_cut_sweep --model mlb_prop_pitcher_walks --grid
"""
from __future__ import annotations

import argparse
from datetime import date

import config
from data.db import get_connection
from models import probability_calibration as pc
from scripts.calibrated_threshold_sweep import (MIN_SETTLED,
                                                _era, _guard_mlb, grade)
from scripts.ev_floor_replay import _decimal, fetch_rows

# Looser than the current cuts on purpose: the floor already implies a
# calibrated probability near 0.68 at -110, so most of the room is below
# today's prob bars and in the edge dimension.
PROB_GRID = [0.50, 0.52, 0.54, 0.56, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.74, 0.78]
EDGE_GRID = [0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.20]


def _clears(r: dict, pmin: float, emin: float, floor: float, prob_only: bool) -> bool:
    if r["cal_p"] < pmin:
        return False
    if not prob_only and (r["cal_p"] - r["implied"]) < emin:
        return False
    return r["ev"] >= floor


def sweep(rows, floor, prob_only, halves):
    cells = []
    for pmin in PROB_GRID:
        for emin in ([0.0] if prob_only else EDGE_GRID):
            keep = [r for r in rows if _clears(r, pmin, emin, floor, prob_only)]
            if not keep:
                continue
            g = grade(keep, 0)
            a = [r for r in halves[0] if _clears(r, pmin, emin, floor, prob_only)]
            b = [r for r in halves[1] if _clears(r, pmin, emin, floor, prob_only)]
            g["half_a"] = round(100 * sum(r["units"] for r in a) / len(a), 1) if len(a) >= 8 else None
            g["half_b"] = round(100 * sum(r["units"] for r in b) / len(b), 1) if len(b) >= 8 else None
            cells.append({"min_prob": pmin, "min_edge": emin, **g})
    by = {(c["min_prob"], c["min_edge"]): c for c in cells}
    egrid = [0.0] if prob_only else EDGE_GRID
    for c in cells:
        pi, ei = PROB_GRID.index(c["min_prob"]), egrid.index(c["min_edge"])
        good = 0
        for dp in (-1, 0, 1):
            for de in (-1, 0, 1):
                if dp == de == 0 or not (0 <= pi + dp < len(PROB_GRID)) \
                        or not (0 <= ei + de < len(egrid)):
                    continue
                n = by.get((PROB_GRID[pi + dp], egrid[ei + de]))
                if n and (n["roi"] or 0) > 0:
                    good += 1
        c["plateau"] = good
    return cells


def analyse(conn, model_id, active_since, cal, today):
    since = _era(model_id, active_since)
    rows = fetch_rows(conn, model_id, since)
    params = cal.get(model_id)
    for r in rows:
        r["cal_p"] = pc.apply_calibration(r["p"], params)
        r["ev"] = r["cal_p"] * _decimal(r["odds"]) - 1.0
    floor = config.min_ev_for(model_id)
    prob_only = model_id in config.PROB_ONLY_MODELS
    universe = "full" if (pc._in_graded_matview(model_id) and not pc._is_live_lane(model_id)) else "BET"
    days = len({r["date"] for r in rows})
    srt = sorted(rows, key=lambda r: r["date"])
    halves = (srt[: len(srt) // 2], srt[len(srt) // 2:])

    cur = config.ACTION_THRESHOLDS.get(model_id, {})
    mp, me = cur.get("min_prob", 0.0), cur.get("min_edge", 0.0)
    cur_rows = [r for r in rows if _clears(r, mp, me, floor, prob_only)]
    current = grade(cur_rows, 0)
    current["per_day"] = round(len(cur_rows) / days, 2) if days else None

    cells = sweep(rows, floor, prob_only, halves)
    usable = [c for c in cells if c["n"] >= MIN_SETTLED]
    positive = [c for c in usable if (c["roi"] or 0) > 0]
    plateau = [c for c in positive if c["plateau"] >= 4]
    survivors = [c for c in plateau if c["half_a"] is not None and c["half_b"] is not None
                 and c["half_a"] > 0 and c["half_b"] > 0]
    best = max(survivors, key=lambda c: (c["roi"], c["n"])) if survivors else None
    # The most-volume cell that still survives, for the reader who wants
    # bets rather than the peak.
    widest = max(survivors, key=lambda c: (c["n"], c["roi"])) if survivors else None
    if best is not None:
        for c in (best, widest):
            c["per_day"] = round(c["n"] / days, 2) if days else None
    if not usable:
        verdict = f"NO CELL with {MIN_SETTLED}+ settled under the floor"
    elif not positive:
        verdict = "NEGATIVE EVERYWHERE under the floor"
    elif not plateau:
        verdict = "peaks only, no plateau"
    elif not survivors:
        verdict = "plateau fails the time split"
    else:
        verdict = (f"SHIP {best['min_prob']:.2f}/{best['min_edge']:.2f}"
                   + (f" (widest {widest['min_prob']:.2f}/{widest['min_edge']:.2f})"
                      if widest is not best else ""))
    return {"model_id": model_id, "era": since, "universe": universe, "n": len(rows),
            "days": days, "floor": floor, "mapped": params is not None,
            "current": current, "cut": (mp, me), "best": best, "widest": widest,
            "verdict": verdict, "cells": cells}


def _cell(c):
    if not c or not c["n"]:
        return "—"
    return (f"{c['w']}-{c['l']} {c['roi']:+.1f}% ({c['n']}, {c.get('per_day', 0) or 0:.2f}/d,"
            f" halves {c.get('half_a')}/{c.get('half_b')})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", nargs="+")
    ap.add_argument("--grid", action="store_true", help="print every cell")
    args = ap.parse_args()
    conn = get_connection()
    try:
        cal = pc.load_calibrations(conn, promoted_only=True)
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
        today = date.today()
        for m in args.model or sorted(config.ACTION_THRESHOLDS):
            if m in config.LIVE_MODELS or m == "nfl_live_prop":
                continue   # re-cut on their bought replays, see the module docstring
            _guard_mlb(m)
            rep = analyse(conn, m, active.get(m), cal, today)
            if rep["n"] < MIN_SETTLED:
                continue
            paused = " PAUSED" if m in config.PAUSED_MODELS else ""
            print(f"\n{m}{paused}  [{rep['universe']} universe, {rep['n']} rows / {rep['days']} days, "
                  f"era {rep['era']}, map {'yes' if rep['mapped'] else 'NO'}, floor {rep['floor']:.2f}]")
            print(f"   current {rep['cut'][0]:.2f}/{rep['cut'][1]:.2f}: {_cell(rep['current'])}")
            print(f"   verdict: {rep['verdict']}")
            if rep["best"]:
                print(f"   best   : {_cell(rep['best'])}")
                if rep["widest"] is not rep["best"]:
                    print(f"   widest : {_cell(rep['widest'])}")
            if args.grid:
                for c in rep["cells"]:
                    if c["n"] >= MIN_SETTLED:
                        print(f"      {c['min_prob']:.2f}/{c['min_edge']:.2f} {c['w']}-{c['l']} "
                              f"{c['roi']:+.1f}% n={c['n']} plateau={c['plateau']} "
                              f"halves {c['half_a']}/{c['half_b']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
