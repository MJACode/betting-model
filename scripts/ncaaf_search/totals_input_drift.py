"""
Why does the NCAAF totals model lean UNDER on three quarters of the 2026 board?

Session 280 (2026-09-10) measured the lean and ruled out the market (the mean
DK total on the 2026 board, 53.2, matches the 2023-25 early-season close mean
of 52.6) and the far-out no-weather regime alone (the lean holds inside 7
days). Every backtest September leaned over or flat: mean pred - line +1.48 /
-0.07 / +1.53 for 2023 / 2024 / 2025 through 09-20. What remains is the
feature vector the live scorer builds for a 2026 game.

DEFINITIONS (fixed before any number was looked at)
- 2026 rows: every unstarted game the board currently prices for
  `ncaaf_over_under` (one row per game from `picks`), featurised through the
  LIVE path `build_ncaaf_game_features` -- the exact vector the scorer sees.
- Reference rows: the 2025 season's training frame (`build_frames`, the bulk
  path the fit used), restricted to games through 09-20 by the game id's
  date, so it is the same slice of the calendar.
- Prediction: the PRODUCTION artifact (`model_registry` active version for
  `ncaaf_over_under`, loaded from models/saved), applied to both sets. The
  2025 rows are in-sample for that artifact; the comparison is of the INPUTS
  and of the prediction's level, not of accuracy.
- Attribution: for each feature, replace the 2026 column with the reference
  mean and re-predict. The change in mean prediction is that feature's share
  of the shift. One-at-a-time, so shares need not sum to the total.

    python -m scripts.ncaaf_search.totals_input_drift
    python -m scripts.ncaaf_search.totals_input_drift --ref-season 2025 --through 09-20
"""
from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.db import get_connection                       # noqa: E402
from features.feature_engine import NCAAF_TOTALS_FEATURES, SPARSE_OK_FEATURES  # noqa: E402
from features.ncaaf_feature_engine import build_ncaaf_game_features  # noqa: E402
from scripts.ncaaf_margin_eval import build_frames        # noqa: E402

TOTAL_FEATURES = [c for c in NCAAF_TOTALS_FEATURES if c != "total_line"]
MODEL_ID = "ncaaf_over_under"


def load_artifact(conn) -> dict:
    row = conn.execute("""
        SELECT version FROM model_registry
        WHERE model_id = ? AND is_active = 1 ORDER BY version DESC LIMIT 1
    """, (MODEL_ID,)).fetchone()
    if not row:
        raise SystemExit("no active ncaaf_over_under in model_registry")
    path = ROOT / "models" / "saved" / f"{MODEL_ID}_{row[0]}.pkl"
    with open(path, "rb") as fh:
        art = pickle.load(fh)
    art["_path"] = str(path)
    return art


def live_rows(conn) -> pd.DataFrame:
    games = conn.execute("""
        SELECT DISTINCT p.game_id, g.game_date, g.home_team, g.away_team,
               g.season, p.scored_line, p.game_time
        FROM picks p JOIN games g ON g.game_id = p.game_id
        WHERE p.sport = 'NCAAF' AND p.model_id = ? AND p.is_live IS NOT TRUE
          AND p.game_time::timestamptz > NOW()
        ORDER BY p.game_time
    """, (MODEL_ID,)).fetchall()
    rows = []
    for gid, gdate, home, away, season, line, gtime in games:
        feat = build_ncaaf_game_features(conn, gid, gdate, home, away, int(season))
        if feat is None:
            continue
        feat.update({"_game_id": gid, "_total_line": float(line) if line is not None else np.nan,
                     "_game_time": gtime})
        rows.append(feat)
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--ref-season", type=int, default=2025)
    ap.add_argument("--through", default="09-20", help="MM-DD cutoff for the reference slice")
    ap.add_argument("--csv", default=None)
    args = ap.parse_args()

    conn = get_connection()
    try:
        art = load_artifact(conn)
        cols = art["feature_cols"]
        model = art["model"]
        print(f"artifact {art['_path']}  features {len(cols)}  gate {art.get('d_threshold')}")

        live = live_rows(conn)
    finally:
        conn.close()
    print(f"2026 live rows: {len(live)}")

    ref = build_frames([args.ref_season])
    ref["_md"] = ref["_game_id"].str.extract(r"_(\d{4}-\d{2}-\d{2})_")[0].str[5:]
    ref = ref[ref["_md"] <= args.through].copy()
    print(f"reference rows ({args.ref_season} through {args.through}): {len(ref)}")

    def matrix(df):
        X = df.reindex(columns=cols)
        for c in cols:
            X[c] = pd.to_numeric(X[c], errors="coerce")
        return X

    Xl, Xr = matrix(live), matrix(ref)
    live["pred"] = model.predict(Xl)
    ref["pred"] = model.predict(Xr)

    print("\n== prediction level ==")
    print(f"  {args.ref_season} early : mean pred {ref['pred'].mean():6.2f}  "
          f"mean line {ref['_total_line'].mean():6.2f}  "
          f"mean pred-line {(ref['pred'] - ref['_total_line']).mean():+6.2f}  "
          f"pred<line {(ref['pred'] < ref['_total_line']).mean()*100:4.1f}%")
    print(f"  2026 board  : mean pred {live['pred'].mean():6.2f}  "
          f"mean line {live['_total_line'].mean():6.2f}  "
          f"mean pred-line {(live['pred'] - live['_total_line']).mean():+6.2f}  "
          f"pred<line {(live['pred'] < live['_total_line']).mean()*100:4.1f}%")

    print("\n== feature means: reference vs 2026 (sorted by |shift| in reference SDs) ==")
    stats = []
    for c in cols:
        r, l = Xr[c], Xl[c]
        sd = r.std() if r.std() and not np.isnan(r.std()) else np.nan
        stats.append(dict(feature=c, ref_mean=r.mean(), live_mean=l.mean(),
                          shift=l.mean() - r.mean(),
                          shift_sd=(l.mean() - r.mean()) / sd if sd and not np.isnan(sd) else np.nan,
                          ref_nan=r.isna().mean(), live_nan=l.isna().mean()))
    st = pd.DataFrame(stats)
    st["abs"] = st["shift_sd"].abs()
    st = st.sort_values("abs", ascending=False).drop(columns="abs")
    with pd.option_context("display.width", 200, "display.max_rows", 100):
        print(st.round(3).to_string(index=False))

    print("\n== attribution: set one 2026 feature to the reference mean, re-predict ==")
    base = live["pred"].mean()
    att = []
    for c in cols:
        X2 = Xl.copy()
        X2[c] = Xr[c].mean()
        att.append(dict(feature=c, mean_pred_after=model.predict(X2).mean(),
                        delta=model.predict(X2).mean() - base))
    at = pd.DataFrame(att)
    at["abs"] = at["delta"].abs()
    at = at.sort_values("abs", ascending=False).drop(columns="abs")
    print(f"  base 2026 mean pred {base:.2f}; reference mean pred {ref['pred'].mean():.2f}")
    print(at.head(12).round(3).to_string(index=False))

    print("\n== all-at-once: every feature at the reference mean ==")
    Xall = Xl.copy()
    for c in cols:
        Xall[c] = Xr[c].mean()
    print(f"  mean pred {model.predict(Xall).mean():.2f}")

    if args.csv:
        pd.concat([Xr.assign(_set="ref", pred=ref["pred"].values, line=ref["_total_line"].values),
                   Xl.assign(_set="live", pred=live["pred"].values, line=live["_total_line"].values,
                             game_id=live["_game_id"].values)]).to_csv(args.csv, index=False)
        print(f"wrote {args.csv}")


if __name__ == "__main__":
    main()
