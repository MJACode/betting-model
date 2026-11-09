"""Build the NBA in-play model's artifact (models/nba_live_ingame.py).

The live artifact is the lab's walk-forward rule applied to the live season:
season 2026-27 (label 2027) is predicted by the state model fit on every
season before it, 2020-21..2025-26 (scripts/nba_ingame_ig2.py fits season S
on seasons < S, and the graded cells used exactly that). Inputs, all caches
of Supabase (NBA_RESEARCH_CACHE and the sportsdataverse ESPN files the nba_pbp
ingestor downloaded):

  * training states 2020-21..2024-25: the lab's own cache (ig2_train_states);
  * training states 2025-26: built here by the lab's training_states(), the
    same functions, into a file beside it (the lab never needed them: its
    2025-26 model is fit on the seasons before);
  * the pre-game prior's distribution: final home margin plus Pinnacle's
    closing home spread, per season, 2020-21..2025-26
    (scripts.nba_game_harness.close_resid on its pinnacle_close).

    PYTHONPATH=. NBA_RESEARCH_CACHE=<v2> python -m scripts.nba_live_ingame_build
"""
from __future__ import annotations

import argparse
import json
import pickle
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import models.nba_live_ingame as M  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_ingame_ig2 as G  # noqa: E402

LIVE_SEASON = 2027
TRAIN_2026 = G.OUT_DIR / "ig2_train_states_2026.parquet"


def build(cache: Path = H.CACHE, refresh: bool = False) -> dict:
    lab, lab_notes = G.training_states(cache)                       # 2021..2025
    new, new_notes = G.training_states(cache, seasons=(2026,), refresh=refresh, out=TRAIN_2026)
    train = pd.concat([lab, new], ignore_index=True)
    seasons = sorted(int(s) for s in train["season"].unique())
    if seasons != [2021, 2022, 2023, 2024, 2025, 2026]:
        raise RuntimeError(f"training seasons {seasons}: expected 2021..2026")
    model = M.StateModel(M.FEATURES).fit(train[train["season"] < LIVE_SEASON], LIVE_SEASON)
    data = H.load(cache)
    close = H.pinnacle_close(data)
    resid = H.close_resid(close, data.games)
    resid = resid[resid["market"] == "spreads"]
    try:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                             text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        sha = None
    art = {
        "kind": M.ARTIFACT_KIND,
        "model": model.to_dict(),
        "season": LIVE_SEASON,
        "close_resid": [(int(s), float(r)) for s, r in zip(resid["season"], resid["resid"])],
        "cells": [c.__dict__ for c in M.CELLS],
        "training": {"seasons": seasons, "states_by_season":
                     {int(k): int(v) for k, v in train.groupby("season").size().items()},
                     "notes": {**lab_notes, **new_notes}},
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha,
        "source": "scripts/nba_live_ingame_build.py",
    }
    return art


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--refresh", action="store_true", help="rebuild the 2025-26 training states")
    ap.add_argument("--out", default=str(ROOT / M.ARTIFACT_PATH))
    a = ap.parse_args()
    art = build(H.CACHE, refresh=a.refresh)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as fh:
        pickle.dump(art, fh, protocol=4)
    m = art["model"]
    print(json.dumps({"out": str(out), "season": art["season"], "n_train": m["n_train"],
                      "beta": dict(zip(m["cols"], np.round(m["beta"], 4).tolist())),
                      "s1": round(m["s1"], 2), "s0": round(m["s0"], 2),
                      "residuals": len(art["close_resid"]),
                      "states_by_season": art["training"]["states_by_season"]}, indent=1))


if __name__ == "__main__":
    main()
