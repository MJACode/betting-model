"""
The totals model's weather features: trained on REANALYSIS, served a FORECAST.
Does the asymmetry cost anything, and does training on the issued forecast fix it?

Session 280 (2026-09-10). `game_weather` is Open-Meteo reanalysis (what
happened); production scores on the forecast `ingest_upcoming` writes 1-7 days
out. `game_weather_issued` (scripts/ncaaf_weather_issued_backfill.py) holds the
forecast as ISSUED 1/3/5 days before kickoff for 2024-2025, the only seasons
Open-Meteo's issued archive covers.

DEFINITIONS (fixed before any number was looked at)
- Frame: `ncaaf_margin_eval.build_frames`, the fit's own path; TOTAL_FEATURES.
- Walk-forward: for each test season in {2024, 2025}, fit on every earlier
  frame season, predict the test season once. The shipped XGB params.
- Arms, differing ONLY in the three wx_* columns:
    reanalysis      as stored (the shipped fit).
    served          train rows keep reanalysis; TEST rows take the issued
                    lead-3 forecast. This is production as it stands.
    issued          every 2024+ row (train and test) takes the issued lead-3
                    forecast; pre-2024 rows keep reanalysis (no archive).
    none            wx_* NaN everywhere (XGBoost routes missing natively).
- Grade: at DK's close (`_total_line`, the frame's archive line), the rule's
  win rate at gates 6/7/8/9/10 with Wilson CIs, and model RMSE. A row with no
  issued forecast at the lead is dropped from EVERY arm so the four arms
  grade the same games.

Power: ~90 rule bets a season at the gate. Two seasons ~180; a 4pp difference
between arms is inside the noise. This measures direction and RMSE, not a
cut.

    python -m scripts.ncaaf_search.totals_weather_source --lead 3
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.db import get_connection                                        # noqa: E402
from scripts.ncaaf_margin_eval import TOTAL_FEATURES, _fit, _matrix, build_frames, sweep_total  # noqa: E402

SEASONS = [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]
TESTS = [2024, 2025]
WX = ["wx_temp_f", "wx_wind_mph", "wx_precip_mm"]
GATES = [6.0, 7.0, 8.0, 9.0, 10.0]


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load_issued(conn, lead: int) -> pd.DataFrame:
    rows = conn.execute("""
        SELECT game_id, temp_f, wind_mph, precip_mm FROM game_weather_issued
        WHERE lead_days = %s
    """, (lead,)).fetchall()
    return pd.DataFrame(rows, columns=["_game_id", "i_temp_f", "i_wind_mph", "i_precip_mm"])


def arm_frame(df: pd.DataFrame, arm: str, test_season: int) -> pd.DataFrame:
    f = df.copy()
    has = f["i_temp_f"].notna()
    if arm == "none":
        f[WX] = np.nan
    elif arm == "served":
        m = (f["_season"] == test_season) & has
        for c, ic in zip(WX, ["i_temp_f", "i_wind_mph", "i_precip_mm"]):
            f.loc[m, c] = f.loc[m, ic]
    elif arm == "issued":
        for c, ic in zip(WX, ["i_temp_f", "i_wind_mph", "i_precip_mm"]):
            f.loc[has, c] = f.loc[has, ic]
    return f


def run_arm(df: pd.DataFrame, arm: str, test_season: int) -> dict:
    f = arm_frame(df, arm, test_season)
    train = f[f["_season"] < test_season]
    test = f[(f["_season"] == test_season) & f["i_temp_f"].notna() & f["_total_line"].notna()]
    Xtr, cols = _matrix(train, TOTAL_FEATURES)
    Xte, _ = _matrix(test, TOTAL_FEATURES)
    model = _fit(Xtr[cols], Xtr["_total"])
    pred = model.predict(Xte[cols])
    rmse = float(np.sqrt(np.mean((pred - Xte["_total"].values) ** 2)))
    rows = sweep_total(pred, Xte["_total_line"], Xte["_total"], thresholds=GATES)
    return {"n_test": len(Xte), "rmse": rmse, "sweep": rows}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--lead", type=int, default=3)
    args = ap.parse_args()

    conn = get_connection()
    try:
        issued = load_issued(conn, args.lead)
    finally:
        conn.close()
    print(f"issued lead-{args.lead} rows: {len(issued)}")

    df = build_frames(SEASONS)
    df = df.merge(issued, on="_game_id", how="left")
    for s in TESTS:
        n = int(((df["_season"] == s) & df["i_temp_f"].notna()).sum())
        print(f"  {s}: {n} frame rows carry an issued forecast")

    for test in TESTS:
        print(f"\n=== test {test} ===")
        if test == 2024:
            print("  (no training row before 2024 carries an issued forecast, so the "
                  "`issued` arm is the `served` arm here by construction)")
        print(f"{'arm':12s} {'n':>5s} {'rmse':>6s}  " + "  ".join(f"gate{g:g}: bets win% [CI]".ljust(28) for g in GATES))
        for arm in ("reanalysis", "served", "issued", "none"):
            r = run_arm(df, arm, test)
            cells = []
            for row in r["sweep"]:
                b, w = row["bets"], row["wins"]
                lo, hi = wilson(w, b)
                cells.append(f"{b:4d} {100 * (row['win_rate'] or 0):5.1f}% [{100*lo:4.1f},{100*hi:4.1f}]".ljust(28))
            print(f"{arm:12s} {r['n_test']:5d} {r['rmse']:6.2f}  " + "  ".join(cells))


if __name__ == "__main__":
    main()
