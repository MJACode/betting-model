"""Women's totals, part A (no prices): the men's rating model's own functions
(models/ncaab_total_blend.py, scripts/ncaab_total_blend_build.py) run on the
women's games and NCAA box scores. How accurate is the predicted total, by
season, at the men's settings and at a few neighbours?

Every prediction uses only finals dated before the game (season_pass's date
rule), each season starting from the season before's end state.

    python -m scripts.ncaabw_research.totals_a [grid]
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

FIRST, STAGE2_FIRST, STAGE2_SCORED = 2011, 2012, 2014


def load():
    g = pd.read_parquet(CACHE / "games.parquet")
    g = g[g["home_score"].notna() & (g["season"] >= FIRST)].copy()
    g["home_score"] = g["home_score"].astype(float)
    g["away_score"] = g["away_score"].astype(float)
    g["game_date"] = g["game_date"].astype(str).str[:10]
    g["neutral_site"] = pd.to_numeric(g["neutral_site"], errors="coerce").fillna(0).astype(int)
    box = pd.read_parquet(CACHE / "box.parquet")
    box = box[box["season"] >= FIRST].copy()
    return g, box


def run(g, b, settings, quiet=True):
    params = nb.Params.from_dict(settings)
    preds, ends = mb.ratings_chain(g, {}, params, log=(lambda *_: None) if quiet else print)
    d = preds.merge(g[["game_id", "home_score", "away_score"]], on="game_id")
    d["total"] = d["home_score"] + d["away_score"]
    return d[d["pt_s1"].notna()].copy(), ends


def report(d, col, label):
    out = {}
    for s, x in d.groupby("season"):
        err = x["total"] - x[col]
        out[int(s)] = (len(x), round(float(err.abs().mean()), 3), round(float(err.mean()), 2))
    dev = d[(d["season"] >= 2017)]
    e = dev["total"] - dev[col]
    print(f"{label}: MAE 2017-2027 {e.abs().mean():.3f}, RMSE {np.sqrt((e ** 2).mean()):.3f}, bias {e.mean():+.2f}")
    return out


if __name__ == "__main__":
    t0 = time.time()
    g, box = load()
    g, b = mb.prepare(g, box)
    print(f"games {len(g)}, with possessions {int(g['poss'].notna().sum())}; box rows {len(b)}, "
          f"placed on a game {int(b['game_id'].notna().sum())} ({time.time() - t0:.0f}s)")
    print("possession coverage by season:",
          g.groupby("season")["poss"].apply(lambda s: round(float(s.notna().mean()), 3)).to_dict())
    print("mean total by season:",
          (g["home_score"] + g["away_score"]).groupby(g["season"]).mean().round(1).to_dict())
    base = dict(mb.SETTINGS)
    if len(sys.argv) > 1 and sys.argv[1] == "grid":
        grid = [("men's settings", {}),
                ("half_life 30", {"half_life": 30.0}), ("half_life 60", {"half_life": 60.0}),
                ("half_life 90", {"half_life": 90.0}),
                ("carry a 0.6", {"a": 0.6}), ("carry a 0.85", {"a": 0.85}),
                ("K 5", {"K": 5.0}), ("K 14", {"K": 14.0}),
                ("KT 1.5", {"KT": 1.5}), ("KT 6", {"KT": 6.0}),
                ("r_tempo 0.75", {"r_tempo": 0.75})]
        for label, over in grid:
            t = time.time()
            d, _ = run(g, b, {**base, **over})
            report(d, "pt_s1", f"{label:16s}")
            print(f"    ({time.time() - t:.0f}s)")
        sys.exit(0)
    d, ends = run(g, b, base, quiet=False)
    by1 = report(d, "pt_s1", "stage 1 (ratings)")
    # the naive baseline: last season's league mean total
    lg = d.groupby("season")["total"].mean()
    d["naive"] = d["season"].map(lambda s: lg.get(s - 1, lg.get(s)))
    report(d, "naive", "naive (last season's mean)")
    feats, lgr = mb.features_all(g, b, pd.DataFrame({"game_id": [], "quote_ns": []}))
    d = d.merge(feats, on="game_id", how="left")
    rh = pd.Series(np.nan, index=d.index)
    for S in range(STAGE2_SCORED, int(d["season"].max()) + 1):
        tr = d[(d["season"] >= STAGE2_FIRST) & (d["season"] < S)]
        coef = nb.fit_stage2(tr)
        te = d[d["season"] == S]
        rh.loc[te.index] = nb.residual(te, coef)
    d["pt"] = d["pt_s1"] + rh.fillna(0.0)
    by2 = report(d, "pt", "stage 1 + 2 (luck and style)")
    print("stage-2 coefficients on 2012-2026:",
          dict(zip(("const",) + nb.STAGE2_COLS,
                   [round(c, 3) for c in nb.fit_stage2(d[(d["season"] >= STAGE2_FIRST) & (d["season"] <= 2026)])])))
    print("season: games, MAE stage 1 -> stage 1+2, bias")
    for s in sorted(by1):
        print(f"  {s}: {by1[s][0]:5d}  {by1[s][1]:.3f} -> {by2[s][1]:.3f}   bias {by1[s][2]:+.2f} -> {by2[s][2]:+.2f}")
    d.to_parquet(CACHE / "totals_preds_date_rule.parquet", index=False)
    print(f"done ({time.time() - t0:.0f}s)")
