"""A nonlinear market-anchored classifier on the DraftKings rows.

The offset logistic in `nfl_prop_market_stack` is linear in its features. A
book's line may be wrong in ways that are only visible in INTERACTIONS -- a
line far above the rolling-8 for a player whose sharp line disagrees, a move
from t72 that the consensus did not follow -- and a linear stack cannot see
those. This fits a small gradient-boosted classifier on the same market
features plus the model's projection, per market, walk-forward, and grades it
at the DraftKings price on the same fixed grid.

Kept deliberately small (depth 3, few trees, strong regularisation, early
stopping on the training season's own tail) because two test seasons and
five cuts is a search a boosted model can win by chance. Both the training
and the test Brier are printed beside the book's: a model that beats the book
in-sample and loses out-of-sample has memorised, and the cells under it are
noise however they look.

    python -m scripts.nfl_prop_dk_boost --feats <dk cache dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from models.market_relative import implied
from scripts.nfl_prop_information_test import grade, logit, profit

FEATS = ["line", "fair_over", "pred", "roll3", "roll8",
         "pinnacle_line", "pinnacle_fair_own", "pinnacle_fair_dk",
         "betonlineag_line", "betonlineag_fair_own", "betonlineag_fair_dk",
         "cons_line", "cons_n", "cons_fair_dk", "cons_n_same",
         "dk_line_t72", "dk_fair_t72", "dk_line_t48", "dk_fair_t48"]


def design(df: pd.DataFrame) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for c in FEATS:
        X[c] = df[c] if c in df else np.nan
    # Differences the trees would otherwise have to rediscover.
    X["pred_minus_line"] = df.pred - df.line
    X["roll8_minus_line"] = df.roll8 - df.line
    X["roll3_minus_roll8"] = df.roll3 - df.roll8
    for b in ("pinnacle", "betonlineag", "cons"):
        X[f"{b}_line_diff"] = X[f"{b}_line"] - df.line
    X["mv72"] = df.line - X["dk_line_t72"]
    X["mv48"] = df.line - X["dk_line_t48"]
    X["logit_fair"] = logit(df.fair_over)
    return X


def bets(p: np.ndarray, te: pd.DataFrame, cut: float) -> list[float]:
    out = []
    for pb, r in zip(p, te.itertuples(index=False)):
        for side, pp, price in (("over", pb, r.over_price), ("under", 1 - pb, r.under_price)):
            if price is None or not np.isfinite(float(price)):
                continue
            if pp - implied(price) >= cut:
                won = (r.actual > r.line) if side == "over" else (r.actual < r.line)
                out.append(profit(price, won))
    return out


def main() -> None:
    import xgboost as xgb
    ap = argparse.ArgumentParser()
    ap.add_argument("--feats", required=True)
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    for f in sorted(Path(a.feats).glob("nfl_prop_*.parquet")):
        if f.stem.endswith("_soft") or "_" + f.stem.split("_")[-1] in ("_fanduel", "_betmgm"):
            continue
        df = pd.read_parquet(f)
        df = df.dropna(subset=["fair_over", "pred", "line", "actual"])
        df = df[df.actual != df.line].copy()
        df["y"] = (df.actual > df.line).astype(int)
        print(f"\n=== {f.stem} ===")
        for test in (2024, 2025):
            tr, te = df[df.season < test], df[df.season == test]
            if len(tr) < 300 or len(te) < 200:
                print(f"  {test}: thin"); continue
            Xtr, Xte = design(tr), design(te)
            # Early stopping on the LAST 20% of the training season by date
            # order, never on the test season.
            n = len(tr); k = int(n * 0.8)
            clf = xgb.XGBClassifier(n_estimators=400, max_depth=3, learning_rate=0.03,
                                    subsample=0.8, colsample_bytree=0.7, min_child_weight=20,
                                    reg_lambda=5.0, gamma=0.5, eval_metric="logloss",
                                    early_stopping_rounds=40, random_state=42)
            clf.fit(Xtr.iloc[:k], tr.y.iloc[:k], eval_set=[(Xtr.iloc[k:], tr.y.iloc[k:])], verbose=False)
            p_tr = clf.predict_proba(Xtr)[:, 1]; p_te = clf.predict_proba(Xte)[:, 1]
            b_book_tr = np.mean((tr.fair_over - tr.y) ** 2); b_tr = np.mean((p_tr - tr.y) ** 2)
            b_book = np.mean((te.fair_over - te.y) ** 2); b_te = np.mean((p_te - te.y) ** 2)
            print(f"  {test}: n={len(te)} trees={clf.best_iteration}  Brier book {b_book:.4f} boost {b_te:.4f}"
                  f"   [train: book {b_book_tr:.4f} boost {b_tr:.4f}]")
            for cut in (0.02, 0.03, 0.04, 0.05, 0.06):
                prof = bets(p_te, te, cut)
                print(f"    cut {cut:.0%} {grade(np.array(prof), rng) if prof else '    0'}")


if __name__ == "__main__":
    main()
