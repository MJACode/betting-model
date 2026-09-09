"""Do the eleven NFL prop projections know anything the book's line does not?

THE QUESTION. `models/nfl_prop_backtest` found that ten of the eleven
distributional models put P(over) BELOW the empirical over-rate on every row
they could have bet, which is why they bet under 87% of the time. A bias can
be corrected without a retrain. But correcting it only helps if the projection
carries information beyond the line: a model that is merely a noisy copy of the
market becomes, once calibrated, a model with no edges at all.

THE TEST, per model, on the rows the backtest dumped (`--dump`):

  1. BRIER on the whole quoted universe -- the book's de-vigged price against
     the model's P(over) against a 2024-fitted calibration of the model. Lower
     is better; the book is the bar.
  2. THE RESIDUAL REGRESSION, fitted on 2024 and read on 2025:

         logit P(over) = a + c * logit(book_fair) + b * z,   z = (pred - line) / sd

     If b is positive with an interval excluding zero OUT OF SAMPLE, the
     projection adds something to the line. If not, no calibration and no
     threshold can make the model profitable, and the honest answer is that the
     feature set holds less than the market.
  3. THE BLEND, graded as a bet: the fitted equation's probability against the
     DraftKings price on 2025, at several cuts, with the usual interval.

Rows come from:  python -m models.nfl_prop_backtest --all --dump <dir>
Then:            python -m scripts.nfl_prop_information_test --rows <dir>
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd


def logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-3):
    """Newton-Raphson logistic regression with a tiny ridge; returns the
    coefficient vector and its standard errors. No sklearn dependency, so
    the standard errors are the real Fisher ones rather than absent."""
    n, k = X.shape
    w = np.zeros(k)
    for _ in range(50):
        p = sigmoid(X @ w)
        g = X.T @ (p - y) + l2 * w
        H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(k)
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    p = sigmoid(X @ w)
    H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(k)
    se = np.sqrt(np.diag(np.linalg.inv(H)))
    return w, se


def profit(price, won):
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def implied(price):
    p = float(price)
    return 100.0 / (p + 100.0) if p > 0 else abs(p) / (abs(p) + 100.0)


def grade(prof: np.ndarray, rng) -> str:
    if len(prof) < 20:
        return f"{len(prof):>5}  (thin)"
    idx = rng.integers(0, len(prof), (20000, len(prof)))
    roi = 100 * prof[idx].mean(axis=1)
    lo, hi = np.percentile(roi, 5), np.percentile(roi, 95)
    return (f"{len(prof):>5} {100*(prof>0).mean():>5.1f}% {prof.sum():>+8.2f}u "
            f"{100*prof.mean():>+7.2f}%  ({lo:+.1f}, {hi:+.1f})")


def analyse(df: pd.DataFrame, rng, cuts) -> dict:
    df = df.dropna(subset=["fair_over", "p_over", "pred", "line", "actual"]).copy()
    df = df[df["actual"] != df["line"]]                     # pushes carry no outcome
    df["y"] = (df["actual"] > df["line"]).astype(float)
    df["resid"] = df["pred"] - df["line"]
    sd = df.loc[df["season"] == 2024, "resid"].std() or 1.0
    df["z"] = df["resid"] / sd
    tr, te = df[df["season"] == 2024], df[df["season"] == 2025]
    out = {"n_train": len(tr), "n_test": len(te)}
    if len(tr) < 100 or len(te) < 100:
        out["thin"] = True
        return out

    # 1. Brier on the test season: book, raw model, calibrated model (Platt on 2024).
    y = te["y"].values
    out["brier_book"] = float(np.mean((te["fair_over"] - y) ** 2))
    out["brier_model"] = float(np.mean((te["p_over"] - y) ** 2))
    Xc = np.column_stack([np.ones(len(tr)), logit(tr["p_over"])])
    wc, _ = fit_logistic(Xc, tr["y"].values)
    p_cal = sigmoid(np.column_stack([np.ones(len(te)), logit(te["p_over"])]) @ wc)
    out["brier_model_cal"] = float(np.mean((p_cal - y) ** 2))

    # 2. Residual regression: does z add to the book?
    Xb = np.column_stack([np.ones(len(tr)), logit(tr["fair_over"]), tr["z"]])
    wb, se = fit_logistic(Xb, tr["y"].values)
    out["b"], out["b_se"] = float(wb[2]), float(se[2])
    out["c"] = float(wb[1])
    Xt = np.column_stack([np.ones(len(te)), logit(te["fair_over"]), te["z"]])
    p_blend = sigmoid(Xt @ wb)
    out["brier_blend"] = float(np.mean((p_blend - y) ** 2))
    # The same coefficient refitted on 2025 alone: the sign has to hold in a
    # season the fit never saw, or it is one season's noise.
    wb2, se2 = fit_logistic(Xt, y)
    out["b_2025"], out["b_2025_se"] = float(wb2[2]), float(se2[2])

    # 3. The blend as a bet on 2025 against the DK price.
    bets = {}
    for cut in cuts:
        prof = []
        for pb, r in zip(p_blend, te.itertuples(index=False)):
            for side, p, price in (("over", pb, r.over_price),
                                   ("under", 1 - pb, r.under_price)):
                if price is None or not np.isfinite(float(price)):
                    continue
                if p - implied(price) >= cut:
                    won = (r.actual > r.line) if side == "over" else (r.actual < r.line)
                    prof.append(profit(price, won))
        bets[cut] = grade(np.array(prof), rng) if prof else "    0"
    out["bets"] = bets
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", required=True)
    ap.add_argument("--cuts", nargs="+", type=float, default=[0.02, 0.03, 0.04, 0.05])
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    files = sorted(Path(a.rows).glob("nfl_prop_*.csv"))

    print("\n1+2. INFORMATION TEST -- 2025 rows, everything fitted on 2024")
    print(f"{'model':26s} {'n24':>5} {'n25':>5} | {'book':>6} {'model':>6} {'cal':>6} "
          f"{'blend':>6} | {'b(24)':>7} {'se':>5} | {'b(25)':>7} {'se':>5}  verdict")
    print("-" * 118)
    res = {}
    for f in files:
        mid = f.stem
        r = analyse(pd.read_csv(f), rng, a.cuts)
        res[mid] = r
        if r.get("thin"):
            print(f"{mid:26s} {r['n_train']:>5} {r['n_test']:>5}   (thin)")
            continue
        sig24 = abs(r["b"]) > 1.96 * r["b_se"]
        sig25 = abs(r["b_2025"]) > 1.96 * r["b_2025_se"]
        if r["b"] > 0 and r["b_2025"] > 0 and sig24 and sig25:
            v = "INFORMATION in both seasons"
        elif r["b"] > 0 and r["b_2025"] > 0:
            v = "positive both, not significant"
        else:
            v = "none / unstable"
        beats = ("blend beats book" if r["brier_blend"] < r["brier_book"] - 1e-5
                 else "blend not better than book")
        print(f"{mid:26s} {r['n_train']:>5} {r['n_test']:>5} | {r['brier_book']:.4f} "
              f"{r['brier_model']:.4f} {r['brier_model_cal']:.4f} {r['brier_blend']:.4f} | "
              f"{r['b']:+.3f} {r['b_se']:.3f} | {r['b_2025']:+.3f} {r['b_2025_se']:.3f}  "
              f"{v}; {beats}")

    print("\n3. THE BLEND AS A BET -- 2025, DraftKings price, fitted on 2024")
    print(f"{'model':26s} {'cut':>4} {'bets':>5} {'win%':>6} {'units':>9} {'ROI':>8}  90% CI")
    print("-" * 90)
    for mid, r in res.items():
        if r.get("thin"):
            continue
        for cut, line in r["bets"].items():
            print(f"{mid:26s} {cut:>4.0%} {line}")


if __name__ == "__main__":
    main()
