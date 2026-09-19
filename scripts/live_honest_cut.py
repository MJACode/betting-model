"""Re-choose the in-play cuts on the HONEST probability with the EV floor on.

The pre-game companion is scripts/honest_cut_sweep. The in-play models cannot
be re-cut on their forward records (13 graded on mlb_live_total_runs' 09-09
artifact, 25 on ncaaf_live_win_prob), so this reads the two replay caches the
current cuts were chosen from -- scripts/live_cut_sweep (every stored 2026
in-play MLB state x quote through the live artifact) and
scripts/ncaaf_inplay_history_backtest (the bought 2025 NCAAF board through the
engine) -- applies the PROMOTED map to every candidate probability, puts
config.min_ev_for on top, and grids prob x edge with first-signal-per-game
(the lock) exactly as each loop decides.

    python -m scripts.live_honest_cut --mlb-since 2026-07-22 --mlb-split 2026-08-20
    python -m scripts.live_honest_cut --ncaaf-season 2025
"""
from __future__ import annotations

import argparse
import pickle
import tempfile
from pathlib import Path

import config
from data.db import get_connection
from models import probability_calibration as pc
from scripts.ev_floor_replay import _decimal

PROB_GRID = [0.50, 0.54, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.74, 0.78]
EDGE_GRID = [0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.20]
MIN_SETTLED = 25


def _summ(recs):
    n = len(recs)
    if not n:
        return {"n": 0}
    w = sum(1 for r in recs if r["result"] == "WIN")
    l = sum(1 for r in recs if r["result"] == "LOSS")
    u = sum(r["units"] for r in recs)
    return {"n": n, "w": w, "l": l, "units": round(u, 2), "roi": round(100 * u / n, 1)}


def _grid(groups, floor, cap, split_key):
    """groups: list of (sort_key, [cands]) -- one bet per group, the first
    candidate in time that clears. Each cand has cal_p, implied, raw_edge,
    odds, result, units."""
    cells = []
    for pmin in PROB_GRID:
        for emin in EDGE_GRID:
            bets = []
            for _, cands in groups:
                for c in cands:
                    if abs(c["raw_edge"]) > cap:
                        continue
                    if c["cal_p"] >= pmin and (c["cal_p"] - c["implied"]) >= emin \
                            and (c["cal_p"] * _decimal(c["odds"]) - 1.0) >= floor:
                        bets.append(c)
                        break
            if not bets:
                continue
            s = _summ(bets)
            a = [b for b in bets if b[split_key] < bets_split(bets, split_key)]
            b_ = [b for b in bets if b[split_key] >= bets_split(bets, split_key)]
            s["half_a"] = round(100 * sum(x["units"] for x in a) / len(a), 1) if len(a) >= 8 else None
            s["half_b"] = round(100 * sum(x["units"] for x in b_) / len(b_), 1) if len(b_) >= 8 else None
            cells.append({"min_prob": pmin, "min_edge": emin, **s})
    by = {(c["min_prob"], c["min_edge"]): c for c in cells}
    for c in cells:
        pi, ei = PROB_GRID.index(c["min_prob"]), EDGE_GRID.index(c["min_edge"])
        c["plateau"] = sum(
            1 for dp in (-1, 0, 1) for de in (-1, 0, 1)
            if not (dp == de == 0) and 0 <= pi + dp < len(PROB_GRID)
            and 0 <= ei + de < len(EDGE_GRID)
            and (by.get((PROB_GRID[pi + dp], EDGE_GRID[ei + de])) or {}).get("roi", 0) > 0)
    return cells


def bets_split(bets, key):
    ks = sorted(b[key] for b in bets)
    return ks[len(ks) // 2]


def verdict(cells, cur):
    usable = [c for c in cells if c["n"] >= MIN_SETTLED]
    positive = [c for c in usable if c["roi"] > 0]
    plateau = [c for c in positive if c["plateau"] >= 4]
    surv = [c for c in plateau if c["half_a"] and c["half_b"] and c["half_a"] > 0 and c["half_b"] > 0]
    best = max(surv, key=lambda c: (c["roi"], c["n"])) if surv else None
    widest = max(surv, key=lambda c: (c["n"], c["roi"])) if surv else None
    if not usable:
        v = f"NO CELL with {MIN_SETTLED}+ bets under the floor"
    elif not positive:
        v = "NEGATIVE EVERYWHERE under the floor"
    elif not plateau:
        v = "peaks only"
    elif not surv:
        v = "plateau fails the time split"
    else:
        v = f"SHIP {best['min_prob']:.2f}/{best['min_edge']:.2f}"
    return v, best, widest


def _fmt(c):
    if not c or not c.get("n"):
        return "—"
    return (f"{c['w']}-{c['l']} {c['roi']:+.1f}% (n={c['n']}, halves "
            f"{c.get('half_a')}/{c.get('half_b')}, plateau {c.get('plateau')})")


def run_mlb(cal, since, split):
    from config import LIVE_MAX_EDGE_CAP
    from scripts.live_inning_gate_replay import _grade
    cache = Path(tempfile.gettempdir()) / f"live_cut_sweep_cache_{since}.pkl"
    d = pickle.load(open(cache, "rb"))
    params = cal.get("mlb_live_total_runs")
    floor = config.min_ev_for("mlb_live_total_runs")
    groups = []
    for g in d["games"]:
        cands = []
        for c in g["cands"]:
            cal_p = pc.apply_calibration(c["prob"], params)
            implied = c["prob"] - c["edge"]
            res, units = _grade(c, g["game"])
            cands.append({"cal_p": cal_p, "implied": implied, "raw_edge": c["edge"],
                          "odds": c["odds"], "result": res, "units": units,
                          "date": g["game"]["game_date"]})
        groups.append((g["game"]["game_date"], cands))
    print(f"\nmlb_live_total_runs  artifact {d['artifact_version']}, {len(groups)} games since {since}, "
          f"map {'a=%.3f b=%.3f' % (params['a'], params['b']) if params else 'NO'}, floor {floor:.2f}")
    cells = _grid(groups, floor, LIVE_MAX_EDGE_CAP, "date")
    cur = config.ACTION_THRESHOLDS["mlb_live_total_runs"]
    cur_cell = next((c for c in cells if c["min_prob"] == cur["min_prob"]
                     and c["min_edge"] == cur["min_edge"]), None)
    print(f"   current {cur['min_prob']:.2f}/{cur['min_edge']:.2f}: {_fmt(cur_cell)}")
    v, best, widest = verdict(cells, cur)
    print(f"   verdict: {v}")
    if best:
        print(f"   best   : {best['min_prob']:.2f}/{best['min_edge']:.2f} {_fmt(best)}")
        print(f"   widest : {widest['min_prob']:.2f}/{widest['min_edge']:.2f} {_fmt(widest)}")
    _print_grid(cells)


def run_ncaaf(cal, season):
    from ncaaf_live.serve import MAX_EDGE_CAP as cap
    cache = Path(tempfile.gettempdir()) / f"ncaaf_inplay_candidates_{season}.pkl"
    cands = pickle.loads(cache.read_bytes())
    for model_id in ("ncaaf_live_win_prob", "ncaaf_live_total"):
        params = cal.get(model_id)
        floor = config.min_ev_for(model_id)
        by_game: dict = {}
        for c in cands:
            if c["model_id"] != model_id or c["points_since_update"] != 0:
                continue
            cal_p = pc.apply_calibration(c["model_probability"], params)
            by_game.setdefault(c["game_id"], []).append({
                "cal_p": cal_p, "implied": c["dk_implied_prob"], "raw_edge": c["edge"],
                "odds": c["dk_odds"], "result": c["result"], "units": c["units"],
                "served": c["served"]})
        groups = sorted(by_game.items())
        print(f"\n{model_id}  {season} replay, {len(groups)} games (fresh quotes), "
              f"map {'a=%.3f b=%.3f' % (params['a'], params['b']) if params else 'NO'}, floor {floor:.2f}")
        cells = _grid(groups, floor, cap, "served")
        cur = config.ACTION_THRESHOLDS[model_id]
        cur_cell = next((c for c in cells if c["min_prob"] == cur["min_prob"]
                         and c["min_edge"] == cur["min_edge"]), None)
        print(f"   current {cur['min_prob']:.2f}/{cur['min_edge']:.2f}: {_fmt(cur_cell)}")
        v, best, widest = verdict(cells, cur)
        print(f"   verdict: {v}")
        if best:
            print(f"   best   : {best['min_prob']:.2f}/{best['min_edge']:.2f} {_fmt(best)}")
            print(f"   widest : {widest['min_prob']:.2f}/{widest['min_edge']:.2f} {_fmt(widest)}")
        _print_grid(cells)


def _print_grid(cells):
    print("   grid (bets / ROI), rows prob, cols edge:")
    print("        " + "".join(f"{e:>12.2f}" for e in EDGE_GRID))
    by = {(c["min_prob"], c["min_edge"]): c for c in cells}
    for p in PROB_GRID:
        row = []
        for e in EDGE_GRID:
            c = by.get((p, e))
            row.append(f"{c['n']:>4} {c['roi']:>+6.1f}" if c else f"{'—':>11}")
        print(f"   {p:.2f} " + " ".join(row))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mlb-since", default=None)
    ap.add_argument("--mlb-split", default=None)
    ap.add_argument("--ncaaf-season", type=int, default=None)
    a = ap.parse_args()
    conn = get_connection()
    try:
        cal = pc.load_calibrations(conn, promoted_only=True)
    finally:
        conn.close()
    if a.mlb_since:
        run_mlb(cal, a.mlb_since, a.mlb_split)
    if a.ncaaf_season:
        run_ncaaf(cal, a.ncaaf_season)


if __name__ == "__main__":
    main()
