"""Re-derive every threshold on the HONEST probability, and decide the unpauses.

Phase 2. Phase 1 published a calibrated probability but kept deciding on the raw
one, because every cut in `config.py` was swept on raw numbers and flipping
without re-cutting would have starved the mapped models. This is the re-cut.

For each model it replays the whole graded universe through the calibrated
decision function — `cal_p = f(raw_p)`, `cal_edge = cal_p - dk_implied_prob`
against the price actually stored on the pick — and sweeps prob x edge on those
numbers rather than the model's own claims.

Three disciplines, all of them the repo's own scar tissue:

* **Version-era scoped.** A record measured across a retrain describes a blend
  of the live model and its dead predecessor. Correcting this moved the
  calibration gap for `batter_tb` from +4.6pp to +1.2pp, and it moves ROI the
  same way — `mlb_prop_pitcher_outs`' headline +11.0%/175 spans a 06-21 retrain.
* **Plateau, not peak** (sessions 74 and 87). A cell whose neighbours flip
  negative is noise. The verdict refuses to endorse an isolated cell.
* **The verdict is allowed to be "no cut".** `mlb_prop_pitcher_hits` claims 0.70
  where its calibrated probability is 0.527; against a -140 price implying
  0.583 that is NEGATIVE edge, so the honest answer for it is likely that there
  is no edge to cut for. That is the system working.

Output is the pre-flight table: current cut, best calibrated cut, its record,
its projected volume, and an unpause verdict per paused model. Nothing here
writes a threshold — that is a model update and needs a person's name on it.

    python -m scripts.calibrated_threshold_sweep
    python -m scripts.calibrated_threshold_sweep --model mlb_prop_pitcher_outs
"""
from __future__ import annotations

import argparse
import math
from datetime import date, datetime, timedelta

import config
from data.db import get_connection
from models.probability_calibration import (CLEAN_WINDOWS, HONEST_ERA_FROM,
                                            PAPER_START, apply_calibration,
                                            load_calibrations)

PROB_GRID = [0.50, 0.54, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.74, 0.78]
EDGE_GRID = [0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.16, 0.20]
MIN_SETTLED = 25          # below this a cell's ROI is a number, not a result
REGIME_DAYS = 21          # the window that sets forward volume expectations


def _era(model_id: str, active_since: str | None) -> str:
    return max(active_since or PAPER_START,
               HONEST_ERA_FROM.get(model_id, PAPER_START))


def fetch(conn, model_id: str, since: str) -> list[dict]:
    clauses = " OR ".join(f"(game_date BETWEEN '{lo}' AND '{hi}')"
                          for lo, hi in CLEAN_WINDOWS)
    rows = conn.execute(f"""
        SELECT game_date, model_probability::float8, edge::float8,
               dk_odds::float8, result, profit_units::float8
        FROM mv_scored_pick_outcomes
        WHERE model_id = %(m)s AND result IN ('WIN','LOSS','PUSH')
          AND game_date >= %(since)s AND dk_odds IS NOT NULL
          AND edge IS NOT NULL AND profit_units IS NOT NULL
          AND ({clauses})
    """, {"m": model_id, "since": since}).fetchall()
    # The matview stores `edge`, not the implied probability, and profit in
    # UNITS already (1u flat) rather than the picks table's per-$100 figure.
    # implied = model_probability - edge, exactly as the scorer computed it.
    out = [{"date": d, "p": float(p), "implied": float(p) - float(e),
            "odds": float(o), "result": r, "units": float(u)}
           for d, p, e, o, r, u in rows]
    return _apply_price_floor(model_id, out)


def _apply_price_floor(model_id: str, rows: list[dict]) -> list[dict]:
    """Drop picks the live scorer would refuse on price.

    config.MODEL_MIN_ODDS downgrades BET -> NONE when the DK price is juicier
    than the floor (models/scorer.py::_price_blocked), and every prop model
    carries a -140 one. The sweep did not apply it, so it was choosing cuts on
    a population the system will not bet: measured 2026-08-31, the floor blocks
    24-48% of the settled rows for eight of the nine prop models
    (`mlb_prop_batter_rbi` 47.6%, `batter_runs` 44.4%, `batter_hits` 39.3%).
    A cut whose record is half made of refused bets is not a cut, and the
    projected volume was overstated by the same factor.

    Same comparison as the scorer, deliberately: blocked when odds < floor, and
    a missing floor blocks nothing.
    """
    floor = config.MODEL_MIN_ODDS.get(model_id)
    if floor is None:
        return rows
    return [r for r in rows if r["odds"] >= floor]


def wilson(w: int, n: int) -> tuple[float, float] | None:
    if n <= 0:
        return None
    z, p = 1.96, w / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def grade(rows: list[dict], days: float) -> dict:
    settled = [r for r in rows if r["result"] in ("WIN", "LOSS", "PUSH")]
    w = sum(1 for r in settled if r["result"] == "WIN")
    l = sum(1 for r in settled if r["result"] == "LOSS")
    units = sum(r["units"] for r in settled)
    ci = wilson(w, w + l)
    recent = [r for r in rows if days > 0]
    return {
        "n": len(settled), "w": w, "l": l,
        "units": round(units, 2),
        "roi": round(100 * units / len(settled), 1) if settled else None,
        "win": round(100 * w / (w + l), 1) if (w + l) else None,
        "ci_lo": round(100 * ci[0], 1) if ci else None,
        "per_week": round(len(recent) / days * 7, 1) if days > 0 else None,
    }


def sweep(rows: list[dict], recent_days: float,
          recent: list[dict]) -> list[dict]:
    cells = []
    for pmin in PROB_GRID:
        for emin in EDGE_GRID:
            keep = [r for r in rows if r["cal_p"] >= pmin and r["cal_edge"] >= emin]
            if not keep:
                continue
            kept_recent = [r for r in recent
                           if r["cal_p"] >= pmin and r["cal_edge"] >= emin]
            g = grade(keep, 0)
            g["per_week"] = (round(len(kept_recent) / recent_days * 7, 1)
                             if recent_days > 0 else None)
            cells.append({"min_prob": pmin, "min_edge": emin, **g})
    by = {(c["min_prob"], c["min_edge"]): c for c in cells}
    for c in cells:
        pi, ei = PROB_GRID.index(c["min_prob"]), EDGE_GRID.index(c["min_edge"])
        good = 0
        for dp in (-1, 0, 1):
            for de in (-1, 0, 1):
                if dp == de == 0:
                    continue
                if not (0 <= pi + dp < len(PROB_GRID) and 0 <= ei + de < len(EDGE_GRID)):
                    continue
                n = by.get((PROB_GRID[pi + dp], EDGE_GRID[ei + de]))
                if n and (n["roi"] or 0) > 0:
                    good += 1
        c["plateau"] = good
    return cells


def analyse(conn, model_id: str, active_since: str | None,
            cal: dict, today: date) -> dict:
    since = _era(model_id, active_since)
    rows = fetch(conn, model_id, since)
    params = cal.get(model_id)
    for r in rows:
        r["cal_p"] = apply_calibration(r["p"], params)
        r["cal_edge"] = r["cal_p"] - r["implied"]

    cutoff = (today - timedelta(days=REGIME_DAYS)).isoformat()
    recent = [r for r in rows if r["date"] >= cutoff]
    recent_days = float(len({r["date"] for r in recent})) or 0.0

    cur = config.ACTION_THRESHOLDS.get(model_id, {})
    cur_rows = [r for r in rows
                if r["p"] >= cur.get("min_prob", 0) and (r["cal_p"] - r["implied"] is not None)
                and (r["p"] - r["implied"]) >= cur.get("min_edge", 0)]
    cur_recent = [r for r in recent
                  if r["p"] >= cur.get("min_prob", 0)
                  and (r["p"] - r["implied"]) >= cur.get("min_edge", 0)]
    current = grade(cur_rows, 0)
    current["per_week"] = (round(len(cur_recent) / recent_days * 7, 1)
                           if recent_days > 0 else None)

    cells = sweep(rows, recent_days, recent)
    usable = [c for c in cells if c["n"] >= MIN_SETTLED]
    positive = [c for c in usable if (c["roi"] or 0) > 0]
    plateau = [c for c in positive if c["plateau"] >= 4]

    # TIME SPLIT — the test that killed every false positive in the NCAAF search
    # and is a house rule (section 31). A plateau measured in sample is still in
    # sample, and these prices run from -5000 to +1600, so a cell can look
    # profitable purely by having caught a few plus-money longshots. A cut is
    # only endorsed if it is positive in BOTH halves of its own era.
    rows_sorted = sorted(rows, key=lambda r: r["date"])
    mid = len(rows_sorted) // 2
    halves = (rows_sorted[:mid], rows_sorted[mid:])

    def split_roi(cell):
        out = []
        for half in halves:
            keep = [r for r in half
                    if r["cal_p"] >= cell["min_prob"] and r["cal_edge"] >= cell["min_edge"]]
            out.append(round(100 * sum(r["units"] for r in keep) / len(keep), 1)
                       if len(keep) >= 8 else None)
        return out

    survivors = []
    for c in (plateau or positive):
        a, b = split_roi(c)
        c["half_a"], c["half_b"] = a, b
        if a is not None and b is not None and a > 0 and b > 0:
            survivors.append(c)
    best = (max(survivors, key=lambda c: (c["roi"], c["n"])) if survivors
            else (max(plateau or positive, key=lambda c: (c["roi"], c["n"]))
                  if positive else None))
    if best is not None and "half_a" not in best:
        best["half_a"], best["half_b"] = split_roi(best)
    survived = bool(survivors) and best in survivors

    paused = model_id in config.PAUSED_MODELS
    if best is None:
        verdict = ("NO CUT — nothing profitable at "
                   f"{MIN_SETTLED}+ settled on the calibrated numbers. "
                   + ("Stay paused." if paused else "Consider pausing."))
    elif not survived:
        verdict = (f"FAILS THE TIME SPLIT ({best['half_a']}% then "
                   f"{best['half_b']}%) — watch, do not ship."
                   + (" Stay paused." if paused else ""))
    elif not plateau:
        verdict = "PEAK, NOT A PLATEAU — watch, do not ship."
    else:
        verdict = (("UNPAUSE at " if paused else "RE-CUT to ")
                   + f"{best['min_prob']:.2f}/{best['min_edge']:.2f} "
                   + f"({best['half_a']}% / {best['half_b']}% by half)")
    return {"model_id": model_id, "paused": paused, "era": since,
            "total": len(rows), "current": current, "best": best,
            "verdict": verdict, "mapped": params is not None}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model")
    args = ap.parse_args()
    conn = get_connection()
    try:
        cal = load_calibrations(conn, promoted_only=False)
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
        today = date.today()
        models = [args.model] if args.model else sorted(config.ACTION_THRESHOLDS)
        print(f"{'model':<28}{'P':>2}{'map':>4}{'now cut':>10}{'now':>16}"
              f"{'best cut':>10}{'best':>18}{'/wk':>6}  verdict")
        for m in models:
            if m in config.PROB_ONLY_MODELS or m in config.LIVE_MODELS:
                continue
            rep = analyse(conn, m, active.get(m), cal, today)
            if rep["total"] < MIN_SETTLED:
                continue
            c, b = rep["current"], rep["best"]
            cc = config.ACTION_THRESHOLDS[m]
            now = f"{c['w']}-{c['l']} {c['roi']}%" if c["n"] else "—"
            bs = f"{b['w']}-{b['l']} {b['roi']}%" if b else "—"
            bc = f"{b['min_prob']:.2f}/{b['min_edge']:.2f}" if b else "—"
            print(f"{m:<28}{'Y' if rep['paused'] else ' ':>2}"
                  f"{'cal' if rep['mapped'] else '—':>4}"
                  f"{cc['min_prob']:.2f}/{cc['min_edge']:.2f}".rjust(10)
                  + f"{now:>16}{bc:>10}{bs:>18}"
                  f"{(b['per_week'] if b else None) or 0:>6.1f}  {rep['verdict'][:44]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
