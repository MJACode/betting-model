"""NCAAB: do two bets on one game earn their place, and does a model's own EV
say which bet deserves more units?  Reads the six NCAAB builds' replay bets and
grades, over the seasons all six cover:

  1. volume: bets a season per model, bets a game day, bets a game;
  2. stacking: games where two or more models bet, each model's record alone
     and stacked, the win correlation of each pair, and the units every
     "one bet a game" rule would have made (highest EV, each model first,
     highest EV plus any other bet above an EV bar);
  3. sizing: each model's bets split into thirds by EV, the thirds' cutoffs
     taken from that model's EARLIER seasons only, and 1u / 1-2-3u / 1-1-2u
     to win (risk capped at 3u) graded on the same bets.

    python -m scripts.ncaab_stacking_check --fg-total P --h1-total P \\
        --h1-spread P --spread P --ml P --ml-first-post P --periods P

Each P is the parquet a build writes with --bets-out:
  --fg-total       scripts.ncaab_total_blend_build (game_id, season, total,
                   line, side, price, edge, prob)
  --h1-total       scripts.ncaab_first_half_total_build (every decision; the
                   rows with status 'bets' are its bets)
  --h1-spread      scripts.ncaab_first_half_spread_build (the same shape)
  --spread         scripts.ncaab_spread_market_build (status 'bets' is the
                   live rule, three or more other books; side 1 is home)
  --ml             scripts.ncaab_moneyline_build (units, risk, result)
  --ml-first-post  scripts.ncaab_moneyline_first_post_build (the same)
and --periods is SELECT game_id, period, home_points, away_points, source FROM
ncaab_period_scores, which grades the two first-half models.

Grading is stake_for: one unit to win, risk capped at 3 units, a push 0. EV
is the model's own probability (a push left out) times the decimal price,
minus 1. Reads only the files named; writes nothing. The 2026-11-06 run and
its result: docs/sports/ncaab.md, "Two bets on one game, and unit sizing".
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

SEASONS = (2024, 2025, 2026)       # the seasons all six replays cover
EV_BARS = (0.06, 0.08, 0.10, 0.12, 0.15, 0.20)
BOOTSTRAP = 2000


def dec(american) -> np.ndarray:
    a = np.asarray(american, float)
    return np.where(a > 0, 1 + a / 100, 1 + 100 / np.abs(a))


def stake(price, res, conviction=1.0) -> tuple[np.ndarray, np.ndarray]:
    """(risk, units) for `conviction` units to win, risk capped at 3."""
    d = dec(price)
    risk = np.minimum(np.asarray(conviction, float) / (d - 1), 3.0)
    units = np.select([res > 0, res < 0], [risk * (d - 1), -risk], 0.0)
    return risk, units


def first_half_points(periods: pd.DataFrame) -> pd.DataFrame:
    p = periods.sort_values(["game_id", "period", "source"])
    h1 = p[p["period"] == 1].drop_duplicates("game_id")
    return h1.rename(columns={"home_points": "h1_home", "away_points": "h1_away"})[
        ["game_id", "h1_home", "h1_away"]]


def frame(model, family, z, side, res, risk=None, units=None) -> pd.DataFrame:
    if risk is None:
        risk, units = stake(z["price"], res)
    return pd.DataFrame({
        "model": model, "family": family, "game_id": z["game_id"].values,
        "season": z["season"].values, "side": np.asarray(side), "price": z["price"].values,
        "prob": z["prob"].values, "risk": np.asarray(risk, float),
        "units": np.asarray(units, float), "res": np.asarray(res, float)})


def load(a) -> pd.DataFrame:
    h1 = first_half_points(pd.read_parquet(a.periods))
    out = []

    t = pd.read_parquet(a.fg_total)
    res = np.where(t["side"] == "over", t["total"] - t["line"], t["line"] - t["total"])
    out.append(frame("fg_total", "total", t, t["side"], res))

    ft = pd.read_parquet(a.h1_total)
    ft = ft[ft["status"] == "bets"].merge(h1, on="game_id", how="inner")
    pts = ft["h1_home"] + ft["h1_away"]
    res = np.where(ft["side"] == "over", pts - ft["line"], ft["line"] - pts)
    out.append(frame("h1_total", "total", ft, ft["side"], res))

    fs = pd.read_parquet(a.h1_spread)
    fs = fs[fs["status"] == "bets"].merge(h1, on="game_id", how="inner")
    cover = (fs["h1_home"] - fs["h1_away"]) + fs["line"]
    out.append(frame("h1_spread", "side", fs, fs["side"], np.where(fs["side"] == "home", cover, -cover)))

    sp = pd.read_parquet(a.spread)
    sp = sp[sp["status"] == "bets"]
    res = np.where(sp["side"] == 1, sp["margin"] + sp["line"], -(sp["margin"] + sp["line"]))
    out.append(frame("fg_spread", "side", sp, np.where(sp["side"] == 1, "home", "away"), res))

    for model, path in (("ml_15utc", a.ml), ("ml_first_post", a.ml_first_post)):
        m = pd.read_parquet(path)
        m = m[m["status"] == "bets"] if "status" in m.columns else m
        res = np.select([m["result"] == "W", m["result"] == "L"], [1.0, -1.0], 0.0)
        out.append(frame(model, "side", m, m["side"], res, m["risk"], m["units"]))

    b = pd.concat(out, ignore_index=True)
    b["game_date"] = b["game_id"].str.split("_").str[1]
    b["ev"] = b["prob"] * dec(b["price"]) - 1
    b["win"] = (b["res"] > 0).astype(int)
    return b


def summary(x: pd.DataFrame, label: str, rng) -> dict:
    if not len(x):
        return {"rule": label, "bets": 0}
    d = x.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    j = rng.integers(0, len(d), size=(BOOTSTRAP, len(d)))
    lo, hi = np.percentile(d["u"].values[j].sum(1) / d["r"].values[j].sum(1) * 100, [2.5, 97.5])
    row = {"rule": label, "bets": len(x), "units": round(x["units"].sum(), 2),
           "roi_pct": round(x["units"].sum() / x["risk"].sum() * 100, 2),
           "ci95": f"[{lo:.1f}, {hi:.1f}]"}
    for s in SEASONS:
        row[f"units_{s}"] = round(x.loc[x["season"] == s, "units"].sum(), 1)
    return row


def one_a_game(x: pd.DataFrame, models: list[str], rng) -> pd.DataFrame:
    rows = [summary(x, "every bet (live today)", rng)]
    best = x.sort_values("ev", ascending=False).drop_duplicates("game_id")
    rows.append(summary(best, "one a game: highest EV", rng))
    for m in models:
        pri = (x.assign(_o=(x["model"] != m).astype(int))
                .sort_values(["_o", "ev"], ascending=[True, False]).drop_duplicates("game_id"))
        rows.append(summary(pri, f"one a game: {m} first", rng))
    ranked = x.sort_values("ev", ascending=False)
    ranked = ranked.assign(_r=ranked.groupby("game_id").cumcount())
    for bar in EV_BARS:
        rows.append(summary(ranked[(ranked["_r"] == 0) | (ranked["ev"] >= bar)],
                            f"highest EV, plus others with EV >= {bar}", rng))
    rows.append(summary(x.drop(best.index), "the bets 'highest EV' drops", rng))
    return pd.DataFrame(rows)


def stacking(b: pd.DataFrame, name: str, models: list[str], rng) -> None:
    x = b[b["model"].isin(models)]
    n = x.groupby("game_id")["model"].nunique()
    multi = set(n[n > 1].index)
    print(f"\n=== {name}: {', '.join(models)}")
    print("games by number of these models betting:", n.value_counts().sort_index().to_dict())
    for i, m1 in enumerate(models):
        for m2 in models[i + 1:]:
            a = x[x["model"] == m1].set_index("game_id")
            c = x[x["model"] == m2].set_index("game_id")
            both = a.index.intersection(c.index)
            if len(both) < 3:
                continue
            same = int((a.loc[both, "side"] == c.loc[both, "side"]).sum())
            corr = np.corrcoef(a.loc[both, "win"], c.loc[both, "win"])[0, 1]
            print(f"  {m1} + {m2}: {len(both)} games, same side {same}, win correlation {corr:.2f}")
    rows = []
    for m in models:
        z = x[x["model"] == m]
        rows.append(summary(z[~z["game_id"].isin(multi)], f"{m} alone", rng))
        rows.append(summary(z[z["game_id"].isin(multi)], f"{m} stacked", rng))
    print(pd.DataFrame(rows).to_string(index=False))
    print(one_a_game(x, models, rng).to_string(index=False))


def tiers(b: pd.DataFrame) -> pd.DataFrame:
    """Each bet's EV third, cut on the same model's earlier seasons."""
    out = []
    for _, z in b.groupby("model"):
        for s in sorted(z["season"].unique())[1:]:
            q1, q2 = z.loc[z["season"] < s, "ev"].quantile([1 / 3, 2 / 3])
            cur = z[z["season"] == s].copy()
            cur["tier"] = np.select([cur["ev"] < q1, cur["ev"] < q2], [1, 2], 3)
            out.append(cur)
    return pd.concat(out, ignore_index=True)


def sizing(b: pd.DataFrame) -> None:
    t = tiers(b)
    roi = lambda g: (g["units"].sum() / g["risk"].sum() * 100)
    print("\n=== return by EV third (1 = lowest), thirds cut on earlier seasons")
    print(t.groupby(["model", "tier"]).apply(roi, include_groups=False).unstack().round(2).to_string())
    print(t.groupby(["model", "season", "tier"]).apply(roi, include_groups=False).unstack().round(1).to_string())
    print("all models:", t.groupby("tier").apply(roi, include_groups=False).round(2).to_dict())
    print("\n=== stake schemes on the same bets (to win, risk capped at 3u)")
    for label, conv in (("flat 1u", np.ones(len(t))),
                        ("1/2/3u by third", t["tier"].to_numpy(float)),
                        ("1/1/2u by third", np.where(t["tier"] == 3, 2.0, 1.0))):
        risk, units = stake(t["price"], t["res"].to_numpy(), conv)
        print(f"  {label:16s} units {units.sum():8.1f}  risk {risk.sum():8.1f}  "
              f"return {units.sum() / risk.sum() * 100:5.2f}%")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    for flag in ("--fg-total", "--h1-total", "--h1-spread", "--spread", "--ml",
                 "--ml-first-post", "--periods"):
        ap.add_argument(flag, required=True, type=Path)
    a = ap.parse_args(argv)
    rng = np.random.default_rng(7)
    b = load(a)
    print("=== replay bets a season, every model")
    print(b.groupby(["model", "season"]).agg(bets=("units", "size"), units=("units", "sum"))
          .round(2).unstack(0).to_string())
    w = b[b["season"].isin(SEASONS)]
    per_day = w.groupby("game_date").size()
    print(f"\nseasons {SEASONS}: bets a game day mean {per_day.mean():.1f}, "
          f"90th percentile {per_day.quantile(0.9):.0f}, most {per_day.max()}")
    print("bets a game, games with any bet:", w.groupby("game_id").size().value_counts().sort_index().to_dict())
    stacking(w, "totals", ["fg_total", "h1_total"], rng)
    stacking(w, "sides", ["fg_spread", "ml_15utc", "ml_first_post", "h1_spread"], rng)
    stacking(w, "all six", ["fg_total", "h1_total", "fg_spread", "ml_15utc", "ml_first_post",
                            "h1_spread"], rng)
    sizing(b)


if __name__ == "__main__":
    main()
