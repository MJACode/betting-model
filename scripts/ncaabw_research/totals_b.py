"""Women's totals, part B: the men's totals model end to end on the women's
prices, at DraftKings' FIRST POSTED total.

The men's method unchanged (models/ncaab_total_blend.py): ratings and the luck
and style correction as of the hour of DraftKings' own time on its first total,
then mean = line + c + beta x (model - line), priced at DraftKings' two prices.
Settings are the men's (not tuned on the women's prices). The blend is fitted
on earlier priced seasons only:

  2025-26 graded with the blend fitted on 2024-25          (walk-forward)
  2026-27 to date graded with the blend fitted on 2024-26  (walk-forward)
  2024-25 graded with the blend fitted on 2025-26          (NOT walk-forward: a second look)

A phase (November; December on) with under 300 priced games in the fitting
seasons uses the fit on every priced game of those seasons.

Stake: one unit to win, risk capped at 3 (the house stake_for). 95% interval
resampled by date.
"""
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE, SPOOL  # noqa: E402,F401
import models.ncaab_total_blend as nb  # noqa: E402
import scripts.ncaab_total_blend_build as mb  # noqa: E402

from scripts.ncaabw_research.totals_a import load  # noqa: E402

TOTAL_RANGE = (90.0, 200.0)
CUTS = (0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08)
RNG = np.random.default_rng(20261109)


def dk_first_totals():
    P = pd.read_parquet(CACHE / "pregame_quotes.parquet")
    t = P[(P["market"] == "totals") & (P["bookmaker"] == "draftkings")].copy()
    t = t.dropna(subset=["total_line", "over_price", "under_price"])
    bad = t[(t["total_line"] < TOTAL_RANGE[0]) | (t["total_line"] > TOTAL_RANGE[1])]
    print(f"DraftKings totals rows {len(t):,}; outside {TOTAL_RANGE}: {len(bad)}"
          + (f" {sorted(bad['total_line'].unique())[:12]}" if len(bad) else ""))
    t = t[(t["total_line"] >= TOTAL_RANGE[0]) & (t["total_line"] <= TOTAL_RANGE[1])]
    t = t.sort_values(["game_id", "last_update", "snapshot_ts"])
    first = t.groupby("game_id").head(1).copy()
    nxt = t.groupby("game_id").nth(1)[["game_id", "last_update"]].rename(columns={"last_update": "next_change"})
    first = first.merge(nxt, on="game_id", how="left")
    last = t.groupby("game_id").tail(1)[["game_id", "total_line", "over_price", "under_price"]]
    last.columns = ["game_id", "close_line", "close_over", "close_under"]
    first = first.merge(last, on="game_id", how="left")
    first["quote_ns"] = first["last_update"].dt.as_unit("ns").astype("int64")
    first = first.rename(columns={"total_line": "line"})
    return first[["game_id", "line", "over_price", "under_price", "quote_ns", "last_update",
                  "snapshot_ts", "next_change", "close_line", "close_over", "close_under"]]


def consensus_close():
    """Median of every book's last pre-game total, per game."""
    P = pd.read_parquet(CACHE / "pregame_quotes.parquet")
    t = P[(P["market"] == "totals")].dropna(subset=["total_line"])
    t = t[(t["total_line"] >= TOTAL_RANGE[0]) & (t["total_line"] <= TOTAL_RANGE[1])]
    last = t.sort_values("last_update").groupby(["game_id", "bookmaker"]).tail(1)
    return last.groupby("game_id")["total_line"].median().rename("cons_close")


def units(x):
    dd = np.array([nb.dec(p) for p in x["price"]])
    risk = np.minimum(1.0 / (dd - 1.0), 3.0)
    res = np.where(x["side"] == "over", x["total"] - x["line"], x["line"] - x["total"])
    u = np.where(res > 0, risk * (dd - 1.0), np.where(res < 0, -risk, 0.0))
    return u, risk, res


def summarise(x, label):
    if not len(x):
        print(f"  {label:34s} 0 bets")
        return
    u, risk, res = units(x)
    roi = u.sum() / risk.sum() * 100
    dates = x["game_date"].values
    ud = pd.Series(u).groupby(dates).sum()
    rd = pd.Series(risk).groupby(dates).sum()
    idx = RNG.integers(0, len(ud), size=(2000, len(ud)))
    boot = ud.values[idx].sum(axis=1) / rd.values[idx].sum(axis=1) * 100
    lo, hi = np.percentile(boot, [2.5, 97.5])
    clv = np.where(x["side"] == "over", x["cons_close"] - x["line"], x["line"] - x["cons_close"])
    overs = int((x["side"] == "over").sum())
    print(f"  {label:34s} {len(x):5d} bets  {int((res > 0).sum())}-{int((res < 0).sum())}-{int((res == 0).sum())}"
          f"  {u.sum():+8.2f}u  {roi:+6.2f}%  [{lo:+.1f}, {hi:+.1f}]  overs {overs}"
          f"  prices {x['price'].min():.0f}..{x['price'].max():.0f}"
          f"  close {np.nanmean(clv):+.2f} pts")


def price_all(te, blends):
    rows = []
    for r in te.itertuples(index=False):
        b = blends.get(r.phase) or blends["all"]
        pz = nb.price(r.pt, r.line, r.over_price, r.under_price, b)
        rows.append((pz.side, pz.price, pz.edge, pz.prob))
    out = te.copy()
    out[["side", "price", "edge", "prob"]] = pd.DataFrame(rows, index=out.index)
    return out


def fit_blends(tr):
    out = {"all": nb.fit_blend(tr)}
    for ph in nb.PHASES:
        out[ph] = nb.fit_blend(tr[tr["phase"] == ph])
    return out


if __name__ == "__main__":
    t0 = time.time()
    dk = dk_first_totals()
    g, box = load()
    g, b = mb.prepare(g, box)
    dk = dk[dk["game_id"].isin(set(g["game_id"]))]
    print(f"DraftKings first totals on scored games: {len(dk):,} "
          f"({dk.merge(g[['game_id', 'season']]).groupby('season').size().to_dict()})")
    cut = dict(zip(dk["game_id"], dk["quote_ns"]))
    params = nb.Params.from_dict(mb.SETTINGS)
    preds, ends = mb.ratings_chain(g, cut, params, log=lambda *_: None)
    feats, lg = mb.features_all(g, b, dk)
    d = preds.merge(g[["game_id", "home_score", "away_score"]], on="game_id")
    d["total"] = d["home_score"] + d["away_score"]
    d = d.merge(feats, on="game_id", how="left")
    d = d[d["pt_s1"].notna() & d["total"].notna()].copy()
    rh = pd.Series(np.nan, index=d.index)
    for S in range(2017, int(d["season"].max()) + 1):
        coef = nb.fit_stage2(d[(d["season"] >= 2016) & (d["season"] < S)])
        te = d[d["season"] == S]
        rh.loc[te.index] = nb.residual(te, coef)
    d["pt"] = d["pt_s1"] + rh.fillna(0.0)
    x = d.merge(dk, on="game_id").merge(consensus_close(), on="game_id", how="left")
    x["phase"] = [nb.phase_of(v) for v in x["game_date"]]
    x["lead_h"] = (pd.to_datetime(g.set_index("game_id").loc[x["game_id"], "commence_time"].values, utc=True)
                   - x["last_update"]).dt.total_seconds() / 3600
    x["stood_min"] = (x["next_change"] - x["last_update"]).dt.total_seconds() / 60
    x.to_parquet(CACHE / "totals_scored_input.parquet", index=False)
    print(f"scored games with a model total and a DraftKings first total: {len(x):,} ({time.time() - t0:.0f}s)")
    for s, xs in x.groupby("season"):
        e_line = (xs["total"] - xs["line"]); e_mod = (xs["total"] - xs["pt"])
        print(f"  {s}: n {len(xs)}  line MAE {e_line.abs().mean():.2f} bias {e_line.mean():+.2f} | "
              f"model MAE {e_mod.abs().mean():.2f} bias {e_mod.mean():+.2f} | model-line mean "
              f"{(xs['pt'] - xs['line']).mean():+.2f} sd {(xs['pt'] - xs['line']).std():.2f} | "
              f"first post a median {xs['lead_h'].median():.1f} h before tip, stood a median "
              f"{xs['stood_min'].median():.0f} min")
    folds = [("2025-26, blend from 2024-25 (walk-forward)", [2025], 2026),
             ("2026-27 to date, blend from 2024-26 (walk-forward)", [2025, 2026], 2027),
             ("2024-25, blend from 2025-26 (second look, not walk-forward)", [2026], 2025)]
    scored = []
    for label, tr_s, te_s in folds:
        tr = x[x["season"].isin(tr_s)]
        te = x[x["season"] == te_s]
        blends = fit_blends(tr)
        if blends["all"] is None or not len(te):
            print(f"\n{label}: not enough games (fit on {len(tr)}, graded on {len(te)})")
            continue
        print(f"\n{label}")
        for k, v in blends.items():
            if v:
                print(f"  blend {k}: c {v['c']:+.3f} beta {v['beta']:.3f} sigma {v['sigma']:.2f} n {v['n']}")
        sc = price_all(te, blends)
        sc["fold"] = label
        scored.append(sc)
        for cutv in CUTS:
            summarise(sc[sc["edge"] > cutv], f"edge > {cutv:.2f}")
        base = sc.copy(); base["side"] = "over"; base["price"] = base["over_price"]
        summarise(base, "every over, blind")
        base = sc.copy(); base["side"] = "under"; base["price"] = base["under_price"]
        summarise(base, "every under, blind")
        for cutv in (0.03, 0.04, 0.05):
            bets = sc[sc["edge"] > cutv]
            summarise(bets[bets["phase"] == "Nov"], f"  > {cutv:.2f}, November")
            summarise(bets[bets["phase"] != "Nov"], f"  > {cutv:.2f}, December on")
            summarise(bets[bets["stood_min"].fillna(1e9) >= 10], f"  > {cutv:.2f}, stood 10+ min")
            summarise(bets[bets["side"] == "over"], f"  > {cutv:.2f}, overs")
            summarise(bets[bets["side"] == "under"], f"  > {cutv:.2f}, unders")
    if scored:
        pd.concat(scored).to_parquet(CACHE / "totals_scored.parquet", index=False)
    print(f"\ndone ({time.time() - t0:.0f}s)")
