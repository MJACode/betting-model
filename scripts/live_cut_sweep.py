"""Sweep mlb_live_total_runs' cut on the honest replay.

WHY THIS EXISTS. The model was replaced on 2026-09-09 (v20260908_230751) and
every threshold it carried had been swept on the OLD model's leaked
probabilities. A cut is a property of a probability; when the probability
changes the cut has to be re-measured, and mike's instruction was to measure it
on a backtest rather than wait for a settled record: "this is what backtesting
is for."

WHAT IT DOES. Reuses scripts.live_inning_gate_replay's pairing (live state x
newest DK in-play price within the age bound) and grading. Computes every
candidate signal ONCE per snapshot with the ACTIVE artifact, caches them, then
applies the production decision -- 0.20 cap, prob floor, edge floor, EV floor,
first-signal lock -- at each grid cell. Nothing here re-implements the model;
`decide` re-implements classify_live_signal's arithmetic with the thresholds
as parameters, and tests/test_live_cut_sweep.py pins that they agree.

READ THE OUTPUT RIGHT. Cells are NESTED: a tighter cut is a subset of a looser
one, so units fall as you tighten by construction. What ranks cells is whether
the delivered rate's interval clears breakeven in BOTH time halves (CLAUDE.md
7: a plateau, not a peak). "Per slate" is only meaningful where the in-play
price feed is dense -- ~800 paired snapshots a game from 2026-08-29, ~90
before -- so quote the recent window's rate for volume.

    python -m scripts.live_cut_sweep --since 2026-07-22 --split 2026-08-16
    python -m scripts.live_cut_sweep --since 2026-07-22 --rebuild

The 2026-09-09 sweep that set 0.72 is in docs/thresholds.md,
"mlb_live_total_runs cut, 2026-09-09".
"""
from __future__ import annotations

import argparse
import pickle
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from config import LIVE_MAX_EDGE_CAP
from data.db import get_connection
from features.live_game_features import build_live_state_row
from models.live_scorer import expected_value
from models.scorer import _count_over_prob, _get_dk_odds
from models.trainer import load_model
from scripts.live_inning_gate_replay import (
    MODEL_ID, _games, _states, _prices, _pair, _implied, _grade)

SINCE = "2026-08-29"
SPLIT = "2026-09-04"      # early / late halves, per CLAUDE.md 7
# tempdir, NOT data/local: that directory is committed, and a 500-game
# candidate cache is a measurement, not a dataset.
CACHE = Path(tempfile.gettempdir()) / f"live_cut_sweep_cache_{SINCE}.pkl"


def build_cache():
    from features.feature_engine import build_mlb_game_features
    conn = get_connection()
    art = load_model(MODEL_ID)
    cols, clf, disp = art["feature_cols"], art["model"], art.get("dispersion")
    games = []
    try:
        for g in _games(conn, SINCE):
            gid = g["game_id"]
            states = _states(conn, gid)
            prices = _prices(conn, gid) if states else []
            if not states or not prices:
                continue
            pre = build_mlb_game_features(
                conn, gid, g["game_date"], g["home_team"], g["away_team"],
                g["season"], odds_row=_get_dk_odds(conn, gid, "h2h"),
                totals_row=_get_dk_odds(conn, gid, "totals"))
            if not pre:
                continue
            cands = []
            for state, price in _pair(states, prices):
                row = build_live_state_row(state, pre, MODEL_ID)
                if row is None:
                    continue
                x = np.array([[np.nan if row.get(c) is None else float(row[c])
                               for c in cols]], dtype=float)
                lam = float(np.clip(clf.predict(x)[0], 1e-6, None))
                rest = float(price["total_line"]) - row["total_runs"]
                if rest < 0:
                    continue
                p_over = _count_over_prob(lam, rest, disp)
                for side, prob, odds in (("over", p_over, price["over_price"]),
                                         ("under", 1 - p_over, price["under_price"])):
                    if odds is None:
                        continue
                    imp = _implied(odds)
                    if imp is None:
                        continue
                    cands.append({"side": side, "prob": prob, "odds": float(odds),
                                  "edge": prob - imp, "ev": expected_value(prob, odds),
                                  "line": float(price["total_line"]),
                                  "inning": state.get("inning"),
                                  "snapshot_at": str(state["snapshot_at"])})
            games.append({"game": g, "cands": cands})
            if len(games) % 20 == 0:
                print(f"  cached {len(games)} games", flush=True)
    finally:
        conn.close()
    pickle.dump({"artifact_version": art["version"], "games": games},
                open(CACHE, "wb"))
    return games


def decide(cands, min_prob, min_edge, min_ev):
    """First candidate that production would call BET, in time order."""
    for c in cands:
        if abs(c["edge"]) > LIVE_MAX_EDGE_CAP:
            continue
        if c["edge"] >= min_edge and c["prob"] >= min_prob:
            if c["ev"] is not None and c["ev"] < min_ev:
                continue
            return c
    return None


def cell(games, min_prob, min_edge, min_ev):
    out = {"all": [], "early": [], "late": []}
    for g in games:
        sig = decide(g["cands"], min_prob, min_edge, min_ev)
        if sig is None:
            continue
        res, units = _grade(sig, g["game"])
        rec = (res, units, sig["prob"], sig["prob"] - sig["edge"])
        out["all"].append(rec)
        out["early" if g["game"]["game_date"] < SPLIT else "late"].append(rec)
    return out


def summarise(recs):
    n = len(recs)
    if n == 0:
        return "   0 bets"
    w = sum(1 for r in recs if r[0] == "WIN")
    l = sum(1 for r in recs if r[0] == "LOSS")
    p = n - w - l
    units = sum(r[1] for r in recs)
    claimed = float(np.mean([r[2] for r in recs]))
    breakeven = float(np.mean([r[3] for r in recs]))
    dec = w + l
    delivered = (w / dec) if dec else float("nan")
    z = 1.645  # Wilson 90% on delivered
    if dec:
        ph = w / dec
        d = 1 + z * z / dec
        c = (ph + z * z / (2 * dec)) / d
        h = z * np.sqrt(ph * (1 - ph) / dec + z * z / (4 * dec * dec)) / d
        ci = f"[{c - h:.0%},{c + h:.0%}]"
    else:
        ci = ""
    push = f"-{p}" if p else "  "
    return (f"{n:>4} bets {w:>3}-{l:<3}{push} {units:>+7.2f}u {units / n:>+6.1%} "
            f"claims {claimed:.1%} delivers {delivered:.1%} {ci} breakeven {breakeven:.1%}")


def short(rr):
    n = len(rr)
    u = sum(x[1] for x in rr)
    w = sum(1 for x in rr if x[0] == "WIN")
    dec = sum(1 for x in rr if x[0] != "PUSH")
    return f"{n:>4}b {u:>+7.2f}u {(w / dec if dec else 0):>5.0%}      "


def main():
    global SINCE, SPLIT, CACHE
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default=SINCE)
    ap.add_argument("--split", default=SPLIT, help="early/late boundary")
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()
    SINCE, SPLIT = args.since, args.split
    CACHE = Path(tempfile.gettempdir()) / f"live_cut_sweep_cache_{SINCE}.pkl"
    if args.rebuild or not CACHE.exists():
        games = build_cache()
    else:
        d = pickle.load(open(CACHE, "rb"))
        games = d["games"]
        print(f"[cache] artifact {d['artifact_version']}, {len(games)} games")
    slates = len({g["game"]["game_date"] for g in games})
    print(f"\n{len(games)} games over {slates} slates since {SINCE}; split at {SPLIT}\n")

    print("CURRENT CUT  prob 0.70 / edge 0.14 / ev 0.32")
    r = cell(games, 0.70, 0.14, 0.32)
    for k in ("all", "early", "late"):
        print(f"  {k:5s} {summarise(r[k])}")

    probs = [0.70, 0.72, 0.74, 0.76, 0.78, 0.80]
    edges = [0.14, 0.16, 0.18]
    print("\n--- prob x edge at ev 0.32 (bets / units / delivers) ---")
    print("prob/edge " + "".join(f"{e:>26.2f}" for e in edges))
    for p in probs:
        print(f"  {p:.2f}    " + "".join(short(cell(games, p, e, 0.32)["all"]) for e in edges))

    evs = [0.32, 0.36, 0.40, 0.45]
    print("\n--- prob x ev at edge 0.14 ---")
    print("prob/ev   " + "".join(f"{v:>26.2f}" for v in evs))
    for p in probs:
        print(f"  {p:.2f}    " + "".join(short(cell(games, p, 0.14, v)["all"]) for v in evs))

    print("\n--- per-slate bets at a few cuts ---")
    dates = sorted({g["game"]["game_date"] for g in games})
    for (p, e, v) in [(0.70, 0.14, 0.32), (0.74, 0.14, 0.32), (0.78, 0.14, 0.32),
                      (0.70, 0.16, 0.36), (0.75, 0.16, 0.40)]:
        counts = defaultdict(int)
        for g in games:
            if decide(g["cands"], p, e, v) is not None:
                counts[g["game"]["game_date"]] += 1
        seq = " ".join(f"{counts[dd]:>2}" for dd in dates)
        print(f"  {p:.2f}/{e:.2f}/{v:.2f}  total {sum(counts.values()):>3}  per slate: {seq}")
    print("  slates:              " + " ".join(dd[5:] for dd in dates))


if __name__ == "__main__":
    main()
