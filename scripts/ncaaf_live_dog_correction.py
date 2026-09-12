"""Correct the live win-probability model's pregame-status bias, out of sample.

mike, 2026-09-12: *"I don't want a cap... give me an actual statistical model."*

`scripts/ncaaf_live_dog_calibration.py` established the defect on 2025: the
model's ORDERING is sound (calibration by current lead is inside the interval
in every bucket) but its LEVEL is wrong conditional on the pregame line. It
under-rates favourites and over-rates underdogs, monotonically:

    backed side laying 14+     claims 0.890  wins 0.955   under by 6.5pp
    backed side laying 7-14    claims 0.685  wins 0.804   under by 11.9pp
    backed side getting 7-14   claims 0.291  wins 0.207   OVER  by 8.5pp
    backed side getting 21+    claims 0.060  wins 0.010   OVER  by 5.0pp
    a >=14pt dog that is AHEAD claims 0.239  wins 0.121   OVER  by 11.8pp

A cap refuses to bet there. This removes the bias instead, which is the thing
that makes the number usable everywhere rather than unusable in one corner.

THE CORRECTION, deliberately the smallest thing that can fix a LEVEL error:

    logit(p_adj) = a + b*logit(p_model) + c*dog_points

`dog_points` is how many points the BACKED side was getting pregame. Three
parameters, fitted by Newton-Raphson on the log-likelihood -- the same shape as
models/probability_calibration.py's Platt map, plus the one term the defect is
measured in. It cannot reorder within a (state, side); it can only re-level.

HONESTY, fixed before any number was looked at:
- Fit on the FIRST half of the season, read on the SECOND. Never both.
- Report Brier and log-loss on the held-out half for raw, plain-Platt (b only)
  and this map, so the dog term has to beat a recalibration that does not know
  about the spread. If plain Platt does as well, the dog term is decorative.
- Report the conditional table again on the held-out half. Removing the bias
  in-sample is not the claim; removing it out of sample is.
- Report what it does to the BETS at the shipped cut. A calibration that fixes
  the number and changes no decision is still worth having, but say so.

    python -m scripts.ncaaf_live_dog_correction --season 2025
"""
from __future__ import annotations

import argparse
import math
import pickle
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LANE = "ncaaf_live_win_prob"
EPS = 1e-6


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -35, 35)))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-4):
    """Newton-Raphson with a whisper of ridge, so a separable slice cannot run
    a coefficient to infinity. Returns (weights, standard errors)."""
    w = np.zeros(X.shape[1])
    for _ in range(120):
        p = sigmoid(X @ w)
        g = X.T @ (y - p) - l2 * w
        W = p * (1 - p) + 1e-12
        H = (X * W[:, None]).T @ X + l2 * np.eye(X.shape[1])
        step = np.linalg.solve(H, g)
        w += step
        if np.max(np.abs(step)) < 1e-10:
            break
    cov = np.linalg.inv((X * (sigmoid(X @ w) * (1 - sigmoid(X @ w)))[:, None]).T @ X
                        + l2 * np.eye(X.shape[1]))
    return w, np.sqrt(np.diag(cov))


def wilson(w: int, n: int, z: float = 1.96):
    if not n:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load(season: int, states: str):
    import pandas as pd

    cache = Path(tempfile.gettempdir()) / f"ncaaf_inplay_candidates_{season}.pkl"
    cands = pickle.loads(cache.read_bytes())
    st = pd.read_parquet(ROOT / states, columns=["game_id", "pregame_spread"])
    spread = st.drop_duplicates("game_id").set_index("game_id")["pregame_spread"].to_dict()

    rows = []
    for c in cands:
        if c["model_id"] != LANE or c["points_since_update"] != 0:
            continue
        if c["result"] not in ("WIN", "LOSS"):
            continue
        sp = spread.get(c["game_id"])
        if sp is None or (isinstance(sp, float) and math.isnan(sp)):
            continue
        sp = float(sp)
        c["dog"] = sp if c["pick_side"] == "home" else -sp
        c["y"] = 1.0 if c["result"] == "WIN" else 0.0
        rows.append(c)
    rows.sort(key=lambda r: r["served"])
    return rows


def one_per_game(rows):
    seen, out = set(), []
    for r in rows:
        if r["game_id"] in seen:
            continue
        seen.add(r["game_id"])
        out.append(r)
    return out


def brier(p, y):
    return float(np.mean((np.asarray(p) - np.asarray(y)) ** 2))


def logloss(p, y):
    p = np.clip(np.asarray(p), EPS, 1 - EPS)
    y = np.asarray(y)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def conditional_table(rows, probs, title):
    """ONE STATE PER GAME PER BUCKET. Without it a single blowout contributes
    hundreds of near-identical states, the interval collapses, and a bucket
    reads 1.000 on "911 observations" that are really a handful of games."""
    buckets = [(-99, -14), (-14, -7), (-7, 0), (0, 7), (7, 14), (14, 99)]
    print(f"\n  {title}")
    print(f"    {'pregame':>12} {'n':>5} {'claimed':>8} {'actual':>8} {'gap':>7} "
          f"{'95% CI':>17}  verdict")
    for lo, hi in buckets:
        seen_b, idx = set(), []
        for i, r in enumerate(rows):
            if not (lo <= r["dog"] < hi) or r["game_id"] in seen_b:
                continue
            seen_b.add(r["game_id"]); idx.append(i)
        if len(idx) < 15:
            continue
        n = len(idx)
        w = int(sum(rows[i]["y"] for i in idx))
        claimed = float(np.mean([probs[i] for i in idx]))
        actual = w / n
        clo, chi = wilson(w, n)
        v = "OVER" if claimed > chi else ("under" if claimed < clo else "ok")
        lab = f"<{hi:+g}" if lo <= -99 else (f">={lo:+g}" if hi >= 99 else f"{lo:+g}..{hi:+g}")
        print(f"    {lab:>12} {n:>5} {claimed:>8.3f} {actual:>8.3f} "
              f"{claimed - actual:>+7.3f} [{clo:>6.3f},{chi:>6.3f}]  {v}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--states", default="ncaaf_live/data/artifacts/states_2025.parquet")
    ap.add_argument("--fit", action="store_true",
                    help="refit on the WHOLE season and rewrite the shipped artifact")
    args = ap.parse_args()

    rows = load(args.season, args.states)
    print(f"fresh graded {LANE} candidates: {len(rows):,}")

    dates = sorted({r["served"].date() for r in rows})
    mid = dates[len(dates) // 2]
    tr = [r for r in rows if r["served"].date() <= mid]
    te = [r for r in rows if r["served"].date() > mid]
    print(f"fit on <= {mid} ({len(tr):,} states), read on > {mid} ({len(te):,} states)")

    def design(rs, with_dog: bool):
        z = logit([r["model_probability"] for r in rs])
        cols = [np.ones(len(rs)), z]
        if with_dog:
            cols.append(np.array([r["dog"] for r in rs], dtype=float))
        return np.column_stack(cols)

    y_tr = np.array([r["y"] for r in tr])
    y_te = np.array([r["y"] for r in te])

    w_p, se_p = fit_logistic(design(tr, False), y_tr)
    w_d, se_d = fit_logistic(design(tr, True), y_tr)
    print(f"\nplain Platt : a={w_p[0]:+.4f}  b={w_p[1]:+.4f}")
    print(f"with dog    : a={w_d[0]:+.4f}  b={w_d[1]:+.4f}  "
          f"c={w_d[2]:+.5f} +- {se_d[2]:.5f}  "
          f"({'EXCLUDES 0' if abs(w_d[2]) > 1.96 * se_d[2] else 'includes 0'})")
    print(f"  c is per point: a 24.5-point dog moves the logit by "
          f"{w_d[2] * 24.5:+.3f}")

    p_raw = np.array([r["model_probability"] for r in te])
    p_pl = sigmoid(design(te, False) @ w_p)
    p_dg = sigmoid(design(te, True) @ w_d)

    print(f"\nHELD-OUT HALF ({len(te):,} states)")
    print(f"  {'model':>12} {'brier':>9} {'logloss':>9}")
    for nm, p in (("raw", p_raw), ("platt", p_pl), ("platt+dog", p_dg)):
        print(f"  {nm:>12} {brier(p, y_te):>9.5f} {logloss(p, y_te):>9.5f}")

    conditional_table(te, p_raw, "RAW, held-out half")
    conditional_table(te, p_dg, "CORRECTED (platt+dog), held-out half")

    # The case in question, on the held-out half only.
    print("\n  the case in question: >=14pt pregame dog, currently ahead is not "
          "recoverable here (no live score in the candidate); using >=14pt dog:")
    seen_g, idx = set(), []
    for i, r in enumerate(te):
        if r["dog"] < 14 or r["game_id"] in seen_g:
            continue
        seen_g.add(r["game_id"]); idx.append(i)
    if len(idx) >= 15:
        n = len(idx)
        w = int(sum(te[i]["y"] for i in idx))
        lo, hi = wilson(w, n)
        print(f"    n={n}  actual {w / n:.3f} [{lo:.3f},{hi:.3f}]  "
              f"raw claims {np.mean(p_raw[idx]):.3f}  "
              f"corrected claims {np.mean(p_dg[idx]):.3f}")

    # What it does to the decisions at the shipped cut.
    from ncaaf_live.serve import MAX_EDGE_CAP
    import config
    pmin = config.ACTION_THRESHOLDS[LANE]["min_prob"]
    emin = config.ACTION_THRESHOLDS[LANE]["min_edge"]
    evmin = config.MODEL_MIN_EV.get(LANE)

    def bets(rs, probs):
        seen, out = set(), []
        for r, p in zip(rs, probs):
            if r["game_id"] in seen:
                continue
            price = r["dk_odds"]
            profit = (price / 100.0) if price > 0 else (100.0 / abs(price))
            implied = r["dk_implied_prob"]
            edge = p - implied
            if p < pmin or edge < emin or abs(edge) > MAX_EDGE_CAP:
                continue
            if evmin is not None and (p * profit - (1 - p)) < evmin:
                continue
            seen.add(r["game_id"])
            out.append((r, p, profit))
        return out

    if args.fit:
        write_artifact(rows, args.season)

    print(f"\n  BETS on the held-out half at the shipped cut "
          f"(prob>={pmin}, edge>={emin}, ev>={evmin}):")
    for nm, probs in (("raw", p_raw), ("platt+dog", p_dg)):
        bs = bets(te, probs)
        units = sum((profit if r["y"] else -1.0) for r, _, profit in bs)
        n = len(bs)
        w = int(sum(r["y"] for r, _, _ in bs))
        lo, hi = wilson(w, n) if n else (float("nan"),) * 2
        roi = 100 * units / n if n else float("nan")
        print(f"    {nm:>10}: {n:>3} bets  {w}-{n - w}  {units:+7.2f}u  {roi:+6.1f}%"
              f"  [{100 * lo:.1f},{100 * hi:.1f}]")


def write_artifact(rows, season: int) -> None:
    """Refit on the WHOLE season and rewrite the shipped artifact.

    The half-split in main() is the evidence the METHOD works; the coefficients
    that SHIP are fitted on everything, because holding half the data out of
    production buys nothing once the method is validated. The forward season is
    the real test -- refit when it accrues.
    """
    import json
    from datetime import date

    z = logit([r["model_probability"] for r in rows])
    d = np.array([r["dog"] for r in rows], dtype=float)
    y = np.array([r["y"] for r in rows])
    w, se = fit_logistic(np.column_stack([np.ones(len(rows)), z, d]), y)

    path = ROOT / "ncaaf_live" / "data" / "artifacts" / "win_prob_pregame_calibration.json"
    art = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    art.update({
        "model_id": LANE, "kind": "pregame_status_logistic",
        "form": "logit(p_adj) = a + b*logit(p_raw) + c*dog_points",
        "a": round(float(w[0]), 5), "b": round(float(w[1]), 5),
        "c": round(float(w[2]), 5), "c_stderr": round(float(se[2]), 5),
        "fitted_on": str(season), "fitted_at": date.today().isoformat(),
        "n_states": len(rows),
    })
    path.write_text(json.dumps(art, indent=2) + chr(10), encoding="utf-8")
    print("wrote " + str(path))
    print(f"  a={w[0]:+.5f} b={w[1]:+.5f} c={w[2]:+.5f} +- {se[2]:.5f} on {len(rows):,} states")


if __name__ == "__main__":
    main()
