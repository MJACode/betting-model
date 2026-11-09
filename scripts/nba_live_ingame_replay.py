"""Replay the LIVE decision code on the lab's in-play table, fetch by fetch.

models/nba_live_ingame.decide() is what the live loop calls on each fetch.
Here it is called on the archive's purchases in time order, exactly as the
loop would meet them: a (game, model) decided at one fetch is never decided
again, a fetch with no eligible quote for it leaves it open. Each season is
decided by the lab's own walk-forward model for that season (fit on the
seasons before it), not by the live artifact, so the result can be compared
with the lab's bets game for game.

    PYTHONPATH=. NBA_RESEARCH_CACHE=<v2> python -m scripts.nba_live_ingame_replay
    ... --seasons 2022,2023,2024,2025,2026     every graded season
    ... --hourly                               only the top-of-hour purchases
    ... --quotes <path>                        another build of the table

The lab's bets are read from NBA_GAME2_BETS output of `scripts.nba_ingame_ig2
--grid` (ig2_bets/ beside the shared table).
"""
from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import models.nba_live_ingame as M  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_ingame_ig2 as G  # noqa: E402
from scripts.nba_ingame_data import OUT, OUT_DIR  # noqa: E402

LAB_BETS = OUT_DIR / "ig2_bets"
_LAB_FILE = {"nba_live_spread_h1": ("Q1-Q2", "spreads"), "nba_live_spread_q3": ("Q3", "spreads"),
             "nba_live_moneyline": ("Q3", "h2h")}


def load_table(path: Path = OUT) -> pd.DataFrame:
    q = pd.read_parquet(path)
    q = q[q["market"].isin(M.MARKETS)].copy()
    return M.with_pin_freshness(q).assign(phase_ig2=lambda d: M.phase_label(d))


def replay(q: pd.DataFrame, prior: pd.DataFrame, models: dict, seasons,
           hourly_only: bool = False) -> pd.DataFrame:
    rows = []
    for S in seasons:
        qs = q[q["season"] == S]
        if hourly_only:
            qs = qs[(qs["fetch_at"].dt.minute == 0) & (qs["fetch_at"].dt.second == 0)]
        decided: set = set()
        for _, fetch in qs.groupby("fetch_at", sort=True):
            ds = M.decide(fetch, prior, models[S], decided=decided)
            for d in ds:
                decided.add((d.game_id, d.model_id))
                rows.append({k: getattr(d, k) for k in
                             ("model_id", "game_id", "market", "phase", "season", "fetch_at",
                              "served_at", "bet", "reason", "side", "book", "line", "price",
                              "ev", "p_win", "p_push", "mean", "sd", "p_home", "offers")})
    return pd.DataFrame(rows)


def lab_bets(model_id: str, bets_dir: Path = LAB_BETS) -> pd.DataFrame:
    point, market = _LAB_FILE[model_id]
    cut = M.CELL_BY_MODEL[model_id].cut
    files = glob.glob(str(bets_dir / f"bets_IG-2_{point}_{market}_*.parquet"))
    if len(files) != 1:
        raise FileNotFoundError(f"{model_id}: expected one lab bet file for {point} {market}, got {files}")
    b = pd.read_parquet(files[0])
    return b[np.isclose(b["cut"], cut)].reset_index(drop=True)


def compare(mine: pd.DataFrame, lab: pd.DataFrame) -> dict:
    """Game-for-game: the same games bet, on the same side, book, number and price."""
    a = mine.set_index("game_id")
    b = lab.set_index("game_id")
    only_mine = sorted(set(a.index) - set(b.index))
    only_lab = sorted(set(b.index) - set(a.index))
    both = sorted(set(a.index) & set(b.index))
    diff = []
    for g in both:
        x, y = a.loc[g], b.loc[g]
        same = (x["side"] == y["side"] and x["book"] == y["book"]
                and np.isclose(float(x["price"]), float(y["price"]))
                and (x["market"] == "h2h" or np.isclose(float(x["line"]), float(y["line"])))
                and np.isclose(float(x["ev"]), float(y["ev"]), atol=1e-9)
                and pd.Timestamp(x["served_at"]) == pd.Timestamp(y["T"]))
        if not same:
            diff.append({"game_id": g,
                         "replay": f"{x['side']} {x['book']} {x['line']} {x['price']:+.0f} ev {x['ev']:.5f}",
                         "lab": f"{y['side']} {y['book']} {y['line']} {y['price']:+.0f} ev {y['ev']:.5f}"})
    return {"lab": int(len(b)), "replay": int(len(a)), "matched": int(len(both) - len(diff)),
            "only_replay": only_mine, "only_lab": only_lab, "differ": diff}


def graded(bets: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    b = bets.merge(games[["game_id", "game_date"]], on="game_id", how="left")
    return H.grade(b.assign(line=b["line"].astype(float)), games)


def summary(g: pd.DataFrame) -> dict:
    if g.empty:
        return {"bets": 0}
    lo, hi = H.ci95(g)
    per = {int(s): {"n": int(len(x)), "units": round(float(x["units"].sum()), 2),
                    "roi": round(H.roi(x), 4)} for s, x in g.groupby("season")}
    return {"bets": int(len(g)), "units": round(float(g["units"].sum()), 2), "roi": round(H.roi(g), 4),
            "ci95": [round(lo, 4), round(hi, 4)], "by_season": per,
            "price_min": float(g["price"].min()), "price_median": float(g["price"].median()),
            "price_max": float(g["price"].max())}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", default="2026")
    ap.add_argument("--hourly", action="store_true", help="only purchases on the top of the hour")
    ap.add_argument("--quotes", default=str(OUT))
    ap.add_argument("--json", default=None, help="write the result here")
    a = ap.parse_args()
    seasons = tuple(int(s) for s in a.seasons.split(","))
    prior = G.pregame_prior(H.CACHE)
    train, _ = G.training_states(H.CACHE)
    models = G.models_by_season(train, M.FEATURES)
    q = load_table(Path(a.quotes))
    dec = replay(q, prior, models, seasons, hourly_only=a.hourly)
    games = H.load_games(H.CACHE)
    out = {"seasons": list(seasons), "hourly_only": a.hourly, "quotes": a.quotes,
           "decisions": {m: int((dec["model_id"] == m).sum()) for m in M.MODEL_IDS},
           "cells": {}}
    for m in M.MODEL_IDS:
        mine = dec[(dec["model_id"] == m) & dec["bet"]].reset_index(drop=True)
        lab = lab_bets(m)
        lab = lab[lab["season"].isin(seasons)]
        cmp = compare(mine, lab)
        out["cells"][m] = {"compare": {k: (v if not isinstance(v, list) or len(v) <= 40 else v[:40] + ["..."])
                                       for k, v in cmp.items()},
                           "replay": summary(graded(mine, games)),
                           "lab": summary(lab)}
        c = cmp
        print(f"{m}: lab {c['lab']} bets, replay {c['replay']}, matched {c['matched']}, "
              f"only in replay {len(c['only_replay'])}, only in lab {len(c['only_lab'])}, "
              f"differ {len(c['differ'])}")
        print(f"   replay graded: {out['cells'][m]['replay']}")
    if a.json:
        Path(a.json).write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
