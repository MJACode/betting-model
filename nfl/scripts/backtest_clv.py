"""
Walk-forward CLV backtest on the line-movement target.

Bet logic
---------
The model predicts Pinnacle spread movement from bet time to close. If it
predicts the line will move toward the home team, we take home NOW at the
cheaper number. Realized CLV is then, by construction:

    CLV = sign(prediction) * (pin_cl_spread - bet_spread)

Three CLV series are reported:
  model_clv : Pinnacle bet-time -> Pinnacle close. Pure model quality.
  exec_clv  : DraftKings bet-time -> Pinnacle close. Single-book execution.
  shop_clv  : best of N books at bet time -> Pinnacle close. Line shopping.
"""

from __future__ import annotations

import os
import sys
import warnings

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from features.build import feature_columns

SPLITS = [
    (list(range(2020, 2022)), 2022, 2023),
    (list(range(2020, 2023)), 2023, 2024),
    (list(range(2020, 2024)), 2024, 2025),
]

BASE_PARAMS = [
    dict(n_estimators=700, max_depth=4, learning_rate=0.03, num_leaves=20,
         subsample=0.75, colsample_bytree=0.6, min_child_samples=40,
         reg_alpha=0.3, reg_lambda=1.5),
    dict(n_estimators=500, max_depth=3, learning_rate=0.05, num_leaves=15,
         subsample=0.85, colsample_bytree=0.5, min_child_samples=60,
         reg_alpha=1.0, reg_lambda=3.0),
    dict(n_estimators=900, max_depth=5, learning_rate=0.02, num_leaves=31,
         subsample=0.7, colsample_bytree=0.7, min_child_samples=30,
         reg_alpha=0.1, reg_lambda=1.0),
    dict(n_estimators=600, max_depth=3, learning_rate=0.04, num_leaves=12,
         subsample=0.9, colsample_bytree=0.45, min_child_samples=50,
         reg_alpha=0.5, reg_lambda=2.0),
    dict(n_estimators=800, max_depth=4, learning_rate=0.025, num_leaves=24,
         subsample=0.8, colsample_bytree=0.65, min_child_samples=35,
         reg_alpha=0.2, reg_lambda=1.2),
]


class ShrunkEnsemble:
    """
    LightGBM base learners + a shrinkage-calibrated linear meta-learner.

    The meta-learner is deliberately NOT unconstrained OLS. It is anchored to
    the training target mean with a single bounded shrinkage coefficient:

        pred = mu + beta * (blend - mu),   beta in [0, 1]

    An unconstrained fit on five collinear base predictions can produce
    extreme coefficients that badly miscalibrate the level of the output.
    Bounding beta guarantees the ensemble can never be more aggressive than
    its own base blend, only less.
    """

    def __init__(self, params_list=BASE_PARAMS, seed=42):
        self.params_list = params_list
        self.seed = seed
        self.models: list = []
        self.mu = 0.0
        self.beta = 1.0

    def fit(self, Xtr, ytr, Xva, yva):
        self.mu = float(np.mean(ytr))
        self.models = []
        val_preds = []
        for i, p in enumerate(self.params_list):
            m = lgb.LGBMRegressor(**p, random_state=self.seed + i, verbose=-1)
            m.fit(Xtr, ytr, eval_set=[(Xva, yva)],
                  callbacks=[lgb.early_stopping(50, verbose=False)])
            self.models.append(m)
            val_preds.append(m.predict(Xva))
        blend = np.mean(val_preds, axis=0)

        # bounded shrinkage fit on the validation fold
        num = np.sum((blend - self.mu) * (yva - self.mu))
        den = np.sum((blend - self.mu) ** 2)
        beta = num / den if den > 1e-12 else 0.0
        self.beta = float(np.clip(beta, 0.0, 1.0))
        return self

    def predict(self, X):
        blend = np.mean([m.predict(X) for m in self.models], axis=0)
        return self.mu + self.beta * (blend - self.mu)


def summarize(clv: np.ndarray, label: str) -> dict:
    clv = np.asarray(clv, dtype=float)
    clv = clv[~np.isnan(clv)]
    if len(clv) < 2:
        return {}
    t, p = stats.ttest_1samp(clv, 0.0)
    return dict(label=label, n=len(clv), mean=clv.mean(), sd=clv.std(ddof=1),
                pct_pos=np.mean(clv > 0), pct_zero=np.mean(clv == 0),
                t=t, p=p)


def fmt(d: dict) -> str:
    if not d:
        return "  (insufficient sample)"
    return (f"  {d['label']:24s} n={d['n']:4d}  mean={d['mean']:+.4f}  "
            f"sd={d['sd']:.3f}  %pos={d['pct_pos']:5.1%}  "
            f"t={d['t']:+6.2f}  p={d['p']:.4g}")


def main():
    df = pd.read_parquet("data/processed/features.parquet")
    fc = feature_columns(df)

    # line shopping: best available number at bet time, per side
    odds = pd.read_parquet("data/processed/odds_by_game_book.parquet")
    bt = odds.dropna(subset=["bt_spread"])
    shop = bt.groupby("game_id", as_index=False).agg(
        best_home_spread=("bt_spread", "min"),   # lower = better for home backer
        best_away_spread=("bt_spread", "max"))
    df = df.merge(shop, on="game_id", how="left")

    rows = []
    for train_s, val_s, test_s in SPLITS:
        tr = df[df.season.isin(train_s) & df.spread_move.notna()]
        va = df[(df.season == val_s) & df.spread_move.notna()]
        te = df[(df.season == test_s) & df.spread_move.notna()].copy()

        model = ShrunkEnsemble().fit(
            tr[fc].values, tr.spread_move.values,
            va[fc].values, va.spread_move.values)

        te["pred"] = model.predict(te[fc].values)
        te["split"] = f"train{train_s[0]}-{train_s[-1]}|val{val_s}|test{test_s}"
        te["beta"] = model.beta
        rows.append(te)
        print(f"[{test_s}] trained on {train_s[0]}-{train_s[-1]}, val {val_s} | "
              f"shrinkage beta={model.beta:.3f} | test n={len(te)}")

    res = pd.concat(rows, ignore_index=True)

    # ---- bet construction ----
    res["side"] = np.where(res.pred > 0, "home", "away")
    sgn = np.where(res.side == "home", 1.0, -1.0)

    res["model_clv"] = sgn * (res.pin_cl_spread - res.pin_bt_spread)
    res["exec_clv"] = np.where(
        res.side == "home",
        res.pin_cl_spread - res.dk_bt_spread,
        res.dk_bt_spread - res.pin_cl_spread)
    res["shop_clv"] = np.where(
        res.side == "home",
        res.pin_cl_spread - res.best_home_spread,
        res.best_away_spread - res.pin_cl_spread)

    # ATS result vs the number we actually took (Pinnacle bet-time)
    res["ats_win"] = np.where(
        res.side == "home", res.margin > res.pin_bt_spread,
        res.margin < res.pin_bt_spread).astype(float)
    push = (res.margin == res.pin_bt_spread).values
    res.loc[push, "ats_win"] = np.nan

    res.to_parquet("data/processed/backtest_results.parquet", index=False)

    print("\n" + "=" * 78)
    print("WALK-FORWARD CLV, ALL QUALIFYING BETS (no conviction filter)")
    print("=" * 78)
    for c, lab in [("model_clv", "Model (Pin->Pin)"),
                   ("exec_clv", "Execution (DK->Pin)"),
                   ("shop_clv", "Line-shopped (best->Pin)")]:
        print(fmt(summarize(res[c], lab)))

    print("\n  Benchmarks on the same games:")
    print(fmt(summarize(res.pin_cl_spread - res.pin_bt_spread, "Always-home")))
    rng = np.random.default_rng(0)
    rs = rng.choice([-1.0, 1.0], len(res))
    print(fmt(summarize(rs * (res.pin_cl_spread - res.pin_bt_spread), "Random side")))
    w = res.ats_win.dropna()
    print(f"\n  ATS win rate vs bet-time number: {w.mean():.3%} (n={len(w)}, "
          f"breakeven at -110 = 52.38%)")

    print("\n" + "=" * 78)
    print("CLV BY CONVICTION FILTER (|predicted movement|)")
    print("=" * 78)
    print(f"  {'threshold':>10} {'n':>5} {'model_clv':>10} {'%pos':>7} "
          f"{'t':>7} {'p':>9} {'shop_clv':>10} {'ATS%':>7}")
    for thr in [0.0, 0.15, 0.25, 0.35, 0.50, 0.75, 1.00]:
        s = res[res.pred.abs() >= thr]
        if len(s) < 20:
            continue
        d = summarize(s.model_clv, "x")
        ds = summarize(s.shop_clv, "x")
        ats = s.ats_win.dropna()
        print(f"  {thr:>10.2f} {d['n']:>5d} {d['mean']:>+10.4f} "
              f"{d['pct_pos']:>7.1%} {d['t']:>+7.2f} {d['p']:>9.4g} "
              f"{ds['mean']:>+10.4f} {ats.mean():>7.2%}")

    print("\n" + "=" * 78)
    print("CLV BY TEST SEASON (conviction >= 0.25)")
    print("=" * 78)
    for s_ in sorted(res.season.unique()):
        s = res[(res.season == s_) & (res.pred.abs() >= 0.25)]
        if len(s) < 20:
            continue
        d = summarize(s.model_clv, f"{s_}")
        ds = summarize(s.shop_clv, "x")
        ats = s.ats_win.dropna()
        print(f"  {s_}  n={d['n']:4d}  model_clv={d['mean']:+.4f}  "
              f"%pos={d['pct_pos']:5.1%}  t={d['t']:+5.2f}  p={d['p']:.4g}  "
              f"shop_clv={ds['mean']:+.4f}  ATS={ats.mean():.2%}")

    print("\n" + "=" * 78)
    print("TOP FEATURES (gain, final split)")
    print("=" * 78)
    imp = np.mean([m.booster_.feature_importance("gain") for m in model.models], axis=0)
    top = pd.Series(imp, index=fc).sort_values(ascending=False).head(18)
    for k, v in top.items():
        print(f"  {k:38s} {v:12.1f}")


if __name__ == "__main__":
    main()
