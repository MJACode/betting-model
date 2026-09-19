"""What a global EV floor on the HONEST probability would have bet, per model.

Phase 3 pre-flight (2026-09-19, mike: "I want only best of the best in terms
of expected value ... a best big bet model"). Two changes land together --
every model decides on its calibrated probability (tiered fit, see
models/probability_calibration.py PHASE 3) and a single EV floor on that
number is applied wherever a BET is written -- and this replays each model's
graded record through both before either ships, because the 0.30 that looked
non-negative on 2026-09-19 was measured with identity maps on the models the
new fit corrects most.

For each model: the graded universe (the matview for MLB/WNBA, `picks` for
everything else and for the in-play models), the map the tiered fit produces
TODAY, then for each floor the bets that clear `cal_p x decimal(price) - 1 >=
floor` -- once on top of the model's current prob/edge cut (what phase 3
ships: the floor only ever tightens) and once as the sole selector. Volume is
per slate day the model had a graded row; the record is split into halves by
date so a cell that is only one half's luck is visible.

Nothing here writes. It is the table CLAUDE.md 1b asks for before a model
update, printed.

    python -m scripts.ev_floor_replay
    python -m scripts.ev_floor_replay --model mlb_live_total_runs --floors 0.2 0.3
"""
from __future__ import annotations

import argparse
from collections import defaultdict

import config
from data.db import get_connection
from models import probability_calibration as pc
from scripts.calibrated_threshold_sweep import _apply_price_floor, _era

FLOORS = (0.10, 0.15, 0.20, 0.25, 0.30, 0.35)


def _decimal(odds: float) -> float:
    return 1.0 + (odds / 100.0 if odds > 0 else 100.0 / abs(odds))


def fetch_rows(conn, model_id: str, since: str) -> list[dict]:
    """date, p, implied, odds, result, units for every graded row in the era."""
    if pc._is_live_lane(model_id) or not pc._in_graded_matview(model_id):
        rows = conn.execute("""
            SELECT game_date, model_probability::float8,
                   coalesce(decision_odds, dk_odds)::float8, result,
                   profit_flat::float8 / 100.0
            FROM picks
            WHERE model_id = %(m)s AND signal_type = 'BET'
              AND result IN ('WIN','LOSS','PUSH') AND game_date >= %(since)s
              AND coalesce(decision_odds, dk_odds) IS NOT NULL
              AND coalesce(condition_status, '') <> 'VOID'
        """, {"m": model_id, "since": since}).fetchall()
        out = [{"date": d, "p": float(p), "odds": float(o),
                "implied": 1.0 / _decimal(float(o)), "result": r,
                "units": float(u or 0.0)} for d, p, o, r, u in rows]
        return out
    clauses = " OR ".join(f"(game_date BETWEEN '{lo}' AND '{hi}')"
                          for lo, hi in pc.CLEAN_WINDOWS)
    rows = conn.execute(f"""
        SELECT game_date, model_probability::float8, edge::float8,
               dk_odds::float8, result, profit_units::float8
        FROM mv_scored_pick_outcomes
        WHERE model_id = %(m)s AND result IN ('WIN','LOSS','PUSH')
          AND game_date >= %(since)s AND dk_odds IS NOT NULL
          AND edge IS NOT NULL AND profit_units IS NOT NULL
          AND ({clauses})
    """, {"m": model_id, "since": since}).fetchall()
    out = [{"date": d, "p": float(p), "implied": float(p) - float(e),
            "odds": float(o), "result": r, "units": float(u)}
           for d, p, e, o, r, u in rows]
    return _apply_price_floor(model_id, out)


def grade(keep: list[dict], days: int) -> dict:
    n = len(keep)
    w = sum(1 for r in keep if r["result"] == "WIN")
    l = sum(1 for r in keep if r["result"] == "LOSS")
    units = sum(r["units"] for r in keep)
    return {"n": n, "w": w, "l": l, "units": round(units, 2),
            "roi": round(100 * units / n, 1) if n else None,
            "per_day": round(n / days, 2) if days else None,
            "claimed": round(100 * sum(r["cal_p"] for r in keep) / n, 1) if n else None,
            "hit": round(100 * w / (w + l), 1) if (w + l) else None}


def halves(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    s = sorted(rows, key=lambda r: r["date"])
    return s[: len(s) // 2], s[len(s) // 2:]


def replay(conn, model_id: str, active_since: str | None, pool: dict,
           floors=FLOORS) -> dict:
    since = _era(model_id, active_since)
    rows = fetch_rows(conn, model_id, since)
    rep = pc.fit_model(conn, model_id, active_since, pool)
    params = ({"method": "platt", "a": rep["a"], "b": rep["b"]}
              if rep.get("method") else None)
    for r in rows:
        r["cal_p"] = pc.apply_calibration(r["p"], params)
        r["ev"] = r["cal_p"] * _decimal(r["odds"]) - 1.0
        r["ev_raw"] = r["p"] * _decimal(r["odds"]) - 1.0
    days = len({r["date"] for r in rows})
    cut = config.ACTION_THRESHOLDS.get(model_id, {})
    mp, me = cut.get("min_prob", 0.0), cut.get("min_edge", 0.0)
    prob_only = model_id in config.PROB_ONLY_MODELS
    live_ev = config.MODEL_MIN_EV.get(model_id)

    def clears_cut(r, on_cal: bool):
        p = r["cal_p"] if on_cal else r["p"]
        e = p - r["implied"]
        ok = p >= mp and (prob_only or e >= me)
        if ok and live_ev is not None:
            ev = (r["ev"] if on_cal else r["ev_raw"])
            ok = ev >= live_ev
        return ok

    a, b = halves(rows)
    out = {"model_id": model_id, "era": since, "n_universe": len(rows), "days": days,
           "fit": rep.get("fit"), "b": rep.get("b"), "a": rep.get("a"),
           "raw_gap_pp": rep.get("raw_gap_pp"), "n_graded": rep.get("n"),
           "note": rep.get("note", ""),
           "today_raw": grade([r for r in rows if clears_cut(r, False)], days),
           "cut_on_cal": grade([r for r in rows if clears_cut(r, True)], days),
           "floors": {}}
    for f in floors:
        with_cut = [r for r in rows if clears_cut(r, True) and r["ev"] >= f]
        alone = [r for r in rows if r["ev"] >= f]
        out["floors"][f] = {
            "with_cut": grade(with_cut, days),
            "with_cut_halves": (grade([r for r in a if clears_cut(r, True) and r["ev"] >= f], 0)["roi"],
                                grade([r for r in b if clears_cut(r, True) and r["ev"] >= f], 0)["roi"]),
            "alone": grade(alone, days),
            "alone_halves": (grade([r for r in a if r["ev"] >= f], 0)["roi"],
                             grade([r for r in b if r["ev"] >= f], 0)["roi"]),
        }
    return out


def _cell(g: dict, hv=None) -> str:
    if not g["n"]:
        return "—".rjust(22)
    s = f"{g['n']:>4} {g['per_day']:>5.2f}/d {g['roi']:>+6.1f}%"
    if hv is not None:
        s += f" ({'—' if hv[0] is None else f'{hv[0]:+.0f}'}/{'—' if hv[1] is None else f'{hv[1]:+.0f}'})"
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", nargs="+")
    ap.add_argument("--floors", nargs="+", type=float, default=list(FLOORS))
    args = ap.parse_args()
    conn = get_connection()
    try:
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
        pool = pc.fit_pool(conn, active)
        print(f"pooled offset {pool['b']:+.4f} from {pool['n_models']} models")
        for m, b in sorted(pool["per_model"].items()):
            print(f"   {m:<28} b={b:+.3f}  n={len(pool['pairs'][m])}")
        models = args.model or sorted(config.ACTION_THRESHOLDS)
        totals = defaultdict(lambda: defaultdict(lambda: {"n": 0, "units": 0.0, "days": set()}))
        for m in models:
            if m in config.PROB_ONLY_MODELS:
                continue
            rep = replay(conn, m, active.get(m), pool, args.floors)
            if rep["n_universe"] == 0:
                continue
            print(f"\n{m}  era {rep['era']}  universe {rep['n_universe']} rows / "
                  f"{rep['days']} days  fit={rep['fit']} b={rep['b']}  "
                  f"raw gap {rep['raw_gap_pp']:+.1f}pp on {rep['n_graded']} graded")
            print(f"   {rep['note'][:110]}")
            print(f"   {'today (raw cut)':<22}{_cell(rep['today_raw'])}")
            print(f"   {'cut on calibrated':<22}{_cell(rep['cut_on_cal'])}")
            print(f"   {'floor':<8}{'cut + floor  (halves)':<34}{'floor alone  (halves)'}")
            for f, g in rep["floors"].items():
                print(f"   {f:<8.2f}{_cell(g['with_cut'], g['with_cut_halves']):<34}"
                      f"{_cell(g['alone'], g['alone_halves'])}")
                for k in ("with_cut", "alone"):
                    t = totals[k][f]
                    t["n"] += g[k]["n"]
                    t["units"] += g[k]["units"]
        # Slate days across the platform: the union of days is not knowable per
        # model here, so the platform line reports bets and units only.
        print("\nPLATFORM (sum over models)")
        for k in ("with_cut", "alone"):
            print(f"  {k}")
            for f in args.floors:
                t = totals[k][f]
                roi = 100 * t["units"] / t["n"] if t["n"] else 0.0
                print(f"    floor {f:.2f}: {t['n']:>5} bets  {t['units']:>+8.2f}u  {roi:>+6.1f}%")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
