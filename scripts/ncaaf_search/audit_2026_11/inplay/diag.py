"""Checks on the graded tables (run after grid.py): orientation, sides, bias
against the line, whether EV ranks, whether the model adds information to the
price. Nothing here chooses a cut."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import json
from pathlib import Path

import numpy as np
import pandas as pd

OUT = WORK / "inplay"
pd.set_option("display.width", 300); pd.set_option("display.max_columns", 60)
res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
out = {}

print("== sides bet, test A ==")
for v in ("V1", "V2"):
    for c in res["A"][v]["cells"]:
        if c["bets"]:
            print(v, c["rule"], c["cut"], c["sides"], "median EV", c["median_ev"])


def logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def logistic(X, y, iters=50):
    b = np.zeros(X.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-X @ b))
        W = p * (1 - p)
        H = X.T @ (X * W[:, None]) + 1e-9 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (y - p))
        b = b + step
        if np.abs(step).max() < 1e-9:
            break
    return b


def info_test(x, rule, n_boot=500, seed=3):
    """Outcome of side A (over / home) on logit(market no-vig) and logit(model),
    every eligible quote, games resampled for the interval. A model that only
    repeats the price has weight 0; one that replaces it has weight 1."""
    g = x[(x["rule"] == rule) & (x["res_a"] != "P")]
    if g["game_id"].nunique() < 30:
        return None
    y = (g["res_a"] == "W").to_numpy(float)
    cond = g["p_a"].to_numpy(float) / np.maximum(1 - g["p_push"].to_numpy(float), 1e-9)
    X = np.column_stack([np.ones(len(g)), logit(g["novig_a"].to_numpy(float)), logit(cond)])
    b = logistic(X, y)
    codes, ids = pd.factorize(g["game_id"])
    rows_of = [np.flatnonzero(codes == i) for i in range(len(ids))]
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(ids), len(ids))
        idx = np.concatenate([rows_of[i] for i in pick])
        try:
            bs.append(logistic(X[idx], y[idx]))
        except np.linalg.LinAlgError:
            pass
    bs = np.asarray(bs)
    # the one-number read on a total: slope of the outcome on the model alone
    b1 = logistic(X[:, [0, 2]], y)
    return {"quotes": int(len(g)), "games": int(len(ids)),
            "w_market": round(float(b[1]), 3), "w_model": round(float(b[2]), 3),
            "w_model_lo": round(float(np.percentile(bs[:, 2], 2.5)), 3),
            "w_model_hi": round(float(np.percentile(bs[:, 2], 97.5)), 3),
            "slope_model_alone": round(float(b1[1]), 3)}


def ev_bands(x, split=None):
    """ROI by EV band at each game's FIRST eligible quote (the cross-section,
    one decision a game and rule, no first-crossing selection)."""
    rows = []
    edges = [-np.inf, 0.0, 0.02, 0.05, 0.08, 0.12, 0.20, np.inf]
    f = x.drop_duplicates(["rule", "game_id"], keep="first")
    ea = np.where(f["ok_a"], f["ev_a"], -np.inf); eb = np.where(f["ok_b"], f["ev_b"], -np.inf)
    a = ea >= eb
    d = pd.DataFrame({"rule": f["rule"].to_numpy(), "ev": np.where(a, ea, eb),
                      "units": np.where(a, f["units_a"], f["units_b"]), "risk": np.where(a, f["risk_a"], f["risk_b"]),
                      "won": np.where(a, f["res_a"], f["res_b"]) == "W"})
    for rule, g in d.groupby("rule"):
        for lo, hi in zip(edges[:-1], edges[1:]):
            b = g[(g["ev"] >= lo) & (g["ev"] < hi)]
            rows.append({"rule": rule, "ev_band": f"{lo:.2f}..{hi:.2f}", "bets": len(b),
                         "win": int(b["won"].sum()),
                         "units": round(float(b["units"].sum()), 2),
                         "roi": round(float(b["units"].sum() / b["risk"].sum()), 4) if len(b) else None})
    return pd.DataFrame(rows)


for name in ("A", "B1", "B2"):
    x = pd.read_parquet(OUT / f"priced_{name}.parquet")
    out[name] = {}
    for v in ("V1", "V2"):
        xv = x if v == "V1" else x[x["v2"]]
        print(f"\n===== {name} / {v} =====")
        tot = xv[xv["market"] == "totals"]
        gap = (tot["mu_t"] - tot["total_line"])
        fb = pd.cut(tot["f"], [0, 0.25, 0.5, 0.75, 1.0], include_lowest=True)
        t1 = pd.DataFrame({"fb": fb, "gap": gap, "abs": gap.abs(), "sd": tot["sd_t"],
                           "final_minus_line": tot["final_total"] - tot["total_line"]}).groupby("fb", observed=True).agg(
            quotes=("gap", "size"), model_minus_line=("gap", "mean"), abs_gap=("abs", "mean"),
            model_sd=("sd", "mean"), final_minus_line=("final_minus_line", "mean"))
        print("totals: model mean minus DraftKings' line, every eligible quote, by share left:\n", t1.round(3).to_string())
        ml = xv[xv["market"] == "h2h"]
        t2 = pd.DataFrame({"fb": pd.cut(ml["f"], [0, 0.25, 0.5, 0.75, 1.0], include_lowest=True),
                           "gap": ml["p_a"] - ml["novig_a"], "abs": (ml["p_a"] - ml["novig_a"]).abs(),
                           "home_won": (ml["res_a"] == "W").astype(float), "novig": ml["novig_a"]}).groupby("fb", observed=True).agg(
            quotes=("gap", "size"), model_minus_novig=("gap", "mean"), abs_gap=("abs", "mean"),
            novig_home=("novig", "mean"), home_won=("home_won", "mean"))
        print("moneyline: model P(home) minus DraftKings' no-vig P(home):\n", t2.round(4).to_string())
        info = {r: info_test(xv, r) for r in ("totals_H1", "totals_H2", "h2h_H1", "h2h_H2")}
        print("information test (outcome on market and model, games resampled):")
        for r, i in info.items():
            print("  ", r, i)
        eb = ev_bands(xv)
        print("EV band at each game's first eligible quote:\n", eb.to_string(index=False))
        out[name][v] = {"info": info, "ev_bands": eb.to_dict(orient="records"),
                        "totals_gap": t1.round(3).reset_index().astype({"fb": str}).to_dict(orient="records"),
                        "ml_gap": t2.round(4).reset_index().astype({"fb": str}).to_dict(orient="records")}
    if name == "A":
        # orientation: the pre-game home spread against the first in-play no-vig P(home), and the result
        ml = x[x["market"] == "h2h"].drop_duplicates("game_id")
        print("\norientation check, 2026: corr(pre-game home spread, first in-play no-vig P(home)) =",
              round(float(np.corrcoef(ml["sp_pre"], ml["novig_a"])[0, 1]), 3),
              "| corr(no-vig P(home), home won) =",
              round(float(np.corrcoef(ml["novig_a"], (ml["res_a"] == "W").astype(float))[0, 1]), 3))
        tt = x[x["market"] == "totals"].drop_duplicates("game_id")
        print("first in-play total minus pre-game total: mean", round(float((tt.total_line - tt.T_pre).mean()), 2),
              "corr", round(float(np.corrcoef(tt.total_line, tt.T_pre)[0, 1]), 3))
        # the largest-EV V2 total decisions, to read by eye
        b = pd.read_parquet(OUT / "bets_A_V2_totals_H2_0.20.parquet").sort_values("ev", ascending=False).head(12)
        print(b[["game_id", "side", "line", "price", "ev", "p_win", "f", "m", "t", "result"]].to_string(index=False))
(OUT / "diag.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
