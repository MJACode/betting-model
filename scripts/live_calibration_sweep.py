"""Fit mlb_live_total_runs' calibration map on the 2025 in-play history and
re-sweep the cut on the CALIBRATED probability -- one decision, per
classify_live_signal's own comment: promoting a map without re-sweeping takes
the lane to near zero bets, because every cut was swept on raw numbers.

WHY 2025 AND NOT THE GRADED PICKS. The nightly fit reads settled BETs, which
for a live lane is one narrow band above the raw floor (fetch_graded's
docstring); 2025 gives the whole probability range, out of sample, at 2,386
games. The map is the repo's own two-parameter Platt on the preferred side
(models.probability_calibration.fit_platt / apply_calibration), fitted on
FRESH quotes (score unchanged since DK's last_update) so a stale quote's
free run does not teach the map that 0.9 is honest.

THE TESTS A PROMOTED MAP MUST PASS (probability_calibration.promote): fitted
on the older half, it must HELP on the newer half (gap smaller than raw) and
TRANSFER (gap <= MAX_TRANSFER_GAP_PP). Both are computed here on a date split
of 2025, and then the whole thing is checked FORWARD on the 2026 candidate
cache from the 47-slate sweep -- a different season, the dense feed, never
seen by the fit.

    python -m scripts.live_calibration_sweep
    python -m scripts.live_calibration_sweep --cache-2026 path/to/sweep_cache.pkl

Writes nothing. The promotion (a model update, Updated-By on the commit) is
`python -m models.probability_calibration --promote-external ...` once mike
has read the table this prints.
"""
from __future__ import annotations

import argparse
import pickle
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from config import LIVE_MAX_EDGE_CAP
from models.live_scorer import expected_value
from models.probability_calibration import (MAX_TRANSFER_GAP_PP, _gap_pp,
                                            apply_calibration, fit_platt)
from scripts import live_cut_sweep as sweep
from scripts.live_inning_gate_replay import _grade

CACHE_2025 = Path(tempfile.gettempdir()) / "inplay_history_cache_2025.pkl"


def pairs_from(games: list[dict], fresh_only: bool) -> list[tuple[str, float, int]]:
    """(game_date, preferred-side claimed prob, won) per quote."""
    out = []
    for g in games:
        seen = set()
        for c in g["cands"]:
            if fresh_only and c.get("runs_moved") != 0:
                continue
            key = c["snapshot_at"]
            if key in seen:
                continue
            seen.add(key)
            # the over side's prob; preferred side is whichever is >= 0.5
            p_over = c["prob"] if c["side"] == "over" else 1 - c["prob"]
            side = "over" if p_over >= 0.5 else "under"
            p = max(p_over, 1 - p_over)
            res, _ = _grade({"side": side, "line": c["line"], "odds": -110}, g["game"])
            if res == "PUSH":
                continue
            out.append((g["game"]["game_date"], p, 1 if res == "WIN" else 0))
    return out


def recalibrate(games: list[dict], params: dict) -> list[dict]:
    """Every candidate re-expressed on the calibrated probability. Implied is
    unchanged, so edge and EV move with the probability -- exactly what
    classify_live_signal does with decision_prob / decision_edge."""
    out = []
    for g in games:
        cands = []
        for c in g["cands"]:
            implied = c["prob"] - c["edge"]
            p = apply_calibration(c["prob"], params)
            cands.append({**c, "prob": p, "edge": p - implied, "ev": expected_value(p, c["odds"]),
                          "raw_edge": c.get("raw_edge", c["edge"]), "raw_prob": c.get("raw_prob", c["prob"])})
        out.append({**g, "cands": cands})
    return out


def table(games: list[dict], title: str, probs, edges, evs) -> None:
    print(f"\n{title}")
    for ev in evs:
        print(f"--- ev floor {ev:.2f}: prob x edge (bets / units / delivers) ---")
        print("prob/edge " + "".join(f"{e:>26.2f}" for e in edges))
        for p in probs:
            print(f"  {p:.2f}    " + "".join(sweep.short(sweep.cell(games, p, e, ev)["all"]) for e in edges))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache-2025", default=str(CACHE_2025))
    ap.add_argument("--cache-2026", default=None, help="live_cut_sweep candidate cache (2026, dense feed)")
    ap.add_argument("--split", default="2025-07-01")
    args = ap.parse_args()

    d = pickle.load(open(args.cache_2025, "rb"))
    games = d["games"]
    print(f"2025 cache: artifact {d['artifact_version']}, {len(games)} games")

    pairs = pairs_from(games, fresh_only=True)
    older = [(p, y) for dt, p, y in pairs if dt < args.split]
    newer = [(p, y) for dt, p, y in pairs if dt >= args.split]
    print(f"fresh preferred-side pairs: {len(pairs)} (older {len(older)}, newer {len(newer)})")

    a1, b1 = fit_platt([p for p, _ in older], [y for _, y in older])
    half = {"method": "platt", "a": a1, "b": b1}
    raw_gap = _gap_pp(newer)
    cal_gap = _gap_pp(newer, half)
    print(f"fit on older half: a={a1:.4f} b={b1:.4f}; newer half gap raw {raw_gap:+.2f}pp -> "
          f"calibrated {cal_gap:+.2f}pp; helps={abs(cal_gap) < abs(raw_gap)} "
          f"transfers={abs(cal_gap) <= MAX_TRANSFER_GAP_PP} (bar {MAX_TRANSFER_GAP_PP}pp)")

    a, b = fit_platt([p for _, p, _ in pairs], [y for _, _, y in pairs])
    params = {"method": "platt", "a": a, "b": b}
    print(f"fit on all 2025 fresh pairs: a={a:.4f} b={b:.4f}; in-sample gap {_gap_pp([(p, y) for _, p, y in pairs], params):+.2f}pp")
    print("map: " + "  ".join(f"{p:.2f}->{apply_calibration(p, params):.3f}" for p in (0.60, 0.65, 0.70, 0.72, 0.75, 0.80, 0.85)))

    # bands, calibrated, on the newer half (out of the half-fit's sample)
    bands = defaultdict(list)
    for p, y in newer:
        bands[min(int(apply_calibration(p, half) * 20) / 20, 0.95)].append(y)
    print("\nnewer half, HALF-FIT map applied, claimed(cal) -> delivered:")
    for k in sorted(bands):
        if len(bands[k]) >= 50:
            print(f"  {k:.2f}-{k + 0.05:.2f} n={len(bands[k]):>6} {np.mean(bands[k]):.1%}")

    probs = [0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70]
    edges = [0.06, 0.08, 0.10, 0.12, 0.14]
    evs = [0.10, 0.15, 0.20]

    sweep.SPLIT = args.split
    fresh = [{**g, "cands": [c for c in g["cands"] if c.get("runs_moved") == 0]} for g in games]
    cal_fresh = recalibrate(fresh, params)
    cal_all = recalibrate(games, params)
    table(cal_fresh, "=== 2025, FRESH quotes, CALIBRATED probability (full-2025 map; in-sample for the map) ===",
          probs, edges, evs)
    table(cal_all, "=== 2025, ALL quotes, CALIBRATED probability ===", probs, edges, evs)

    if args.cache_2026:
        d26 = pickle.load(open(args.cache_2026, "rb"))
        g26 = d26["games"]
        print(f"\n2026 cache: artifact {d26.get('artifact_version')}, {len(g26)} games (dense feed, out of sample for the map)")
        sweep.SPLIT = "2026-08-16"
        print("raw, shipped cut 0.72/0.14/0.32:")
        for k, v in sweep.cell(g26, 0.72, 0.14, 0.32).items():
            print(f"  {k:5s} {sweep.summarise(v)}")
        cal26 = recalibrate(g26, params)
        table(cal26, "=== 2026 (47 slates), CALIBRATED probability, 2025 map ===", probs, edges, evs)
        print("\n2026 calibrated, selected cells, early/late:")
        for p, e, ev in ((0.62, 0.10, 0.15), (0.64, 0.10, 0.15), (0.64, 0.12, 0.15), (0.66, 0.10, 0.15), (0.66, 0.12, 0.20)):
            r = sweep.cell(cal26, p, e, ev)
            print(f"  {p:.2f}/{e:.2f}/{ev:.2f}: " + " | ".join(f"{k} {sweep.summarise(r[k])}" for k in ("all", "early", "late")))


if __name__ == "__main__":
    main()
