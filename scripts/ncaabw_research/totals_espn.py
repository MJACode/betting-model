"""Does the women's rating model know anything the line does not? A test on
lines the model was never fitted to: ESPN's stored sportsbook total for each
game of 2022-23 and 2023-24 (one provider, capture time unknown, no usable
price, so this says nothing about profit).

  total - line = c + beta x (model - line) + noise

beta > 0 with an interval clear of zero means the model's disagreement with
the line predicts which way the game lands. The model total is the date-rule
prediction (ratings and the luck and style correction from finals dated before
the game), cache/totals_preds_date_rule.parquet.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401

d = pd.read_parquet(CACHE / "totals_preds_date_rule.parquet")
g = pd.read_parquet(CACHE / "games.parquet")[["game_id", "espn_event_id", "game_date"]]
E = pd.read_parquet(CACHE / "espn_lines.parquet")
E = E.dropna(subset=["total_line"]).merge(g, left_on="event", right_on="espn_event_id")
x = E.merge(d[["game_id", "pt", "pt_s1", "total", "ng_h", "ng_a"]].rename(columns={"total": "tot"}),
            on="game_id")
x["line"] = x["total_line"].astype(float)
x = x[x["line"].between(90, 200)]
x["phase"] = np.where(x["game_date"].astype(str).str[5:7] == "11", "Nov", "Dec+")
rng = np.random.default_rng(7)


def fit(z, label):
    X = np.column_stack([np.ones(len(z)), z["pt"] - z["line"]])
    y = (z["tot"] - z["line"]).values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    dates = z["game_date"].astype(str).values
    u = np.unique(dates)
    idx = {k: np.where(dates == k)[0] for k in u}
    boot = []
    for _ in range(600):
        pick = np.concatenate([idx[k] for k in rng.choice(u, len(u))])
        boot.append(np.linalg.lstsq(X[pick], y[pick], rcond=None)[0][1])
    lo, hi = np.percentile(boot, [2.5, 97.5])
    e_line = np.abs(y).mean(); e_mod = np.abs(z["tot"] - z["pt"]).mean()
    e_blend = np.abs(y - X @ b).mean()
    print(f"  {label:26s} n {len(z):5d}  c {b[0]:+.2f}  beta {b[1]:.3f} [{lo:.3f}, {hi:.3f}]  "
          f"MAE line {e_line:.3f}  model {e_mod:.3f}  blend {e_blend:.3f}  "
          f"sd(model - line) {(z['pt'] - z['line']).std():.2f}")


for season, z in x.groupby("season"):
    print(f"season {season} ({z['provider'].value_counts().to_dict()})")
    fit(z, "every game")
    for ph, zz in z.groupby("phase"):
        fit(zz, ph)
    fit(z[(z["ng_h"] >= 10) & (z["ng_a"] >= 10)], "both teams 10+ games")
    big = z[(z["pt"] - z["line"]).abs() >= 5]
    side = np.sign(big["pt"] - big["line"])
    res = np.sign(big["tot"] - big["line"])
    print(f"  model 5+ points off the line: {len(big)} games, landed the model's side "
          f"{(side == res).sum()} - {(side == -res).sum()} - {(res == 0).sum()} "
          f"({(side == res).sum() / max(1, ((side == res) | (side == -res)).sum()):.3f})")
