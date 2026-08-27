"""
Does adding QB continuity features improve the PRODUCTION regression models?

The classifier search has repeatedly come back null (CLV ~0.44 everywhere), but
production does not run a classifier -- `ncaaf_over_under` and the spread work
are margin/total REGRESSIONS scored through an ECDF gate. So the question that
actually matters is whether QB features move THAT, and this script answers it
before any of it is wired into the live feature engine.

Method mirrors scripts/ncaaf_margin_eval.py exactly:
  * expanding-window walk-forward, never random k-fold
  * fit on all prior seasons, predict the held-out season
  * bet only where |model - market| >= a disagreement gate
  * grade at real closing numbers, pushes excluded

The comparison is paired: identical folds, identical gates, identical rows
(both arms are restricted to the rows where BOTH feature sets are complete, so
a difference can never be an artefact of one arm quietly seeing more games).

Run:
    python -m scripts.ncaaf_search.qb_ablation --matrix PATH
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.ncaaf_search.features import FEATURE_GROUPS  # noqa: E402
from scripts.ncaaf_search.qb import QB_FEATURES           # noqa: E402

BREAKEVEN = 0.5238
GATES = [4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
TEST_SEASONS = [2022, 2023, 2024, 2025]
EXCLUDE_SEASONS = {2020}          # COVID season, excluded project-wide

# Everything the production regressions get, minus the market number itself:
# the model must predict the game, then disagree with the line. Feeding it the
# line would just teach it to reproduce the line.
BASE_GROUPS = ["A_adj", "A_raw", "B_decay", "C_roster", "E_pace", "F_situ"]


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def _fit(X: pd.DataFrame, y: pd.Series):
    """Same estimator family the production regressions use."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    mdl = HistGradientBoostingRegressor(
        max_depth=3, learning_rate=0.05, max_iter=400,
        l2_regularization=1.0, random_state=0)
    mdl.fit(X, y)
    return mdl


def walk_forward(df: pd.DataFrame, cols: list[str], target: str,
                 market_col: str, sign: int) -> pd.DataFrame:
    """
    sign=+1 for totals  (disagreement = pred - line, positive favours OVER)
    sign=-1 for spreads (disagreement = pred + spread_home, home-relative)

    Returns one row per bet with its disagreement and whether it won.
    """
    out = []
    seasons = sorted(s for s in df["season"].unique() if s not in EXCLUDE_SEASONS)
    for season in TEST_SEASONS:
        past = [s for s in seasons if s < season]
        if not past:
            continue
        tr = df[df["season"].isin(past)]
        ho = df[df["season"] == season]
        if len(tr) < 500 or ho.empty:
            continue
        mdl = _fit(tr[cols], tr[target])
        pred = mdl.predict(ho[cols])
        market = ho[market_col].to_numpy(dtype=float)
        actual = ho[target].to_numpy(dtype=float)
        d = (pred - market) if sign > 0 else (pred + market)
        for i in range(len(ho)):
            if sign > 0:
                won = (actual[i] > market[i]) if d[i] > 0 else (actual[i] < market[i])
                push = actual[i] == market[i]
            else:
                cover = actual[i] + market[i]
                won = (cover > 0) if d[i] > 0 else (cover < 0)
                push = cover == 0
            if push:
                continue
            out.append({"season": season, "d": float(d[i]), "won": bool(won),
                        "err": float(actual[i] - pred[i])})
    return pd.DataFrame(out)


def summarise(bets: pd.DataFrame, gate: float) -> dict:
    s = bets[bets["d"].abs() >= gate]
    n = len(s)
    if n == 0:
        return {"gate": gate, "bets": 0}
    w = int(s["won"].sum())
    wr = w / n
    lo, hi = wilson(w, n)
    per = {int(k): round(float(v["won"].mean()), 3)
           for k, v in s.groupby("season") if len(v) >= 15}
    return {
        "gate": gate, "bets": n, "win_rate": round(wr, 4),
        "roi": round(wr * (100 / 110) - (1 - wr), 4),
        "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
        "clears": lo > BREAKEVEN,
        "seasons_above": sum(1 for v in per.values() if v > BREAKEVEN),
        "seasons": len(per),
    }


def _report(name: str, bets: pd.DataFrame) -> pd.DataFrame:
    rows = [summarise(bets, g) for g in GATES]
    rows = [r for r in rows if r.get("bets")]
    df = pd.DataFrame(rows)
    rmse = float(np.sqrt((bets["err"] ** 2).mean())) if len(bets) else float("nan")
    print(f"\n--- {name}   (OOS RMSE {rmse:.3f}, {len(bets)} graded games) ---")
    if df.empty:
        print("   no bets at any gate")
    else:
        print(df.to_string(index=False))
    return df


def run(m: pd.DataFrame, target: str, market_col: str, sign: int, label: str):
    base = [c for c in dict.fromkeys(
        sum((FEATURE_GROUPS[g] for g in BASE_GROUPS), [])) if c in m.columns]
    qb = [c for c in QB_FEATURES if c in m.columns]

    df = m.dropna(subset=[target, market_col, "season"]).copy()
    # PAIRED: both arms see exactly the same rows, so a difference cannot come
    # from one arm silently training on more games.
    df = df.dropna(subset=base + qb)
    print(f"\n{'=' * 92}\n{label}  |  paired sample: {len(df)} games "
          f"({len(base)} base features, +{len(qb)} QB)\n{'=' * 92}")

    a = _report("BASE (no QB)", walk_forward(df, base, target, market_col, sign))
    b = _report("BASE + QB", walk_forward(df, base + qb, target, market_col, sign))

    if not a.empty and not b.empty:
        j = a.merge(b, on="gate", suffixes=("_base", "_qb"))
        j["d_win"] = (j["win_rate_qb"] - j["win_rate_base"]).round(4)
        j["d_roi"] = (j["roi_qb"] - j["roi_base"]).round(4)
        print("\n--- QB minus BASE (positive = QB helps) ---")
        print(j[["gate", "bets_base", "bets_qb", "win_rate_base", "win_rate_qb",
                 "d_win", "d_roi"]].to_string(index=False))
        helped = int((j["d_win"] > 0).sum())
        print(f"\nQB improves the win rate at {helped}/{len(j)} gates.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", required=True)
    a = ap.parse_args()
    m = pd.read_parquet(a.matrix)
    m = m[~m["season"].isin(EXCLUDE_SEASONS)]

    run(m, "total_points", "total_line", +1, "TOTALS REGRESSION")
    run(m, "margin", "spread_home", -1, "MARGIN REGRESSION (spread)")
    print("\nNOTE: gates and seasons are pre-committed above; the sweep is "
          "reported in full so the multiple-comparison burden is visible.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
