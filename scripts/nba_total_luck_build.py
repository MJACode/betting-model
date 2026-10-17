"""Build the `nba_total_luck` artifact (models/nba_total_luck.py).

The live model prices offers with the same empirical totals distribution the
lab graded with, and states its probability with the same walk-forward uplift.
Both come from research files, so they are written once into a tracked
artifact rather than recomputed on the worker:

  close_resid   (season, final total minus Pinnacle's closing total) for every
                game of 2020-21 .. 2025-26 with a Pinnacle close, built by the
                harness itself: scripts.nba_game_harness.load ->
                pinnacle_close -> close_resid, the rows the lab's close_dist
                was built from. The live model builds season S's distribution
                from the seasons before S (dist_by_season), exactly as the lab.
  bucket        per graded season (2021-22 .. 2025-26): the shipped cell's bets
                (F4, decision point C, totals, over, gap >= 3), wins, pushes and
                the sum of their market-fair win probabilities, read from the
                lab's own bet file. uplift(S) is fitted on the seasons before S.

Reads only the research cache (NBA_RESEARCH_CACHE, a cache of Supabase) and
the lab's bet file; no database, no API.

    NBA_RESEARCH_CACHE=... python -m scripts.nba_total_luck_build
    NBA_RESEARCH_CACHE=... python -m scripts.nba_total_luck_build --bets <bets parquet>
    python -m scripts.nba_total_luck_build --store <artifact>   # copy it into model_artifacts
"""
from __future__ import annotations

import argparse
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_total_luck as tl  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_game_edge/results/house/bets/"
            "bets_F4_C_totals_0004.parquet")
RESID_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)        # 2021-2026
BUCKET_SEASONS = (*H.CHOOSE, H.CONFIRM)                 # 2022-2026: the graded pool


def close_residuals(cache: Path) -> pd.DataFrame:
    data = H.load(cache, seasons=RESID_SEASONS, require_seasons=RESID_SEASONS)
    r = H.close_resid(H.pinnacle_close(data), data.games)
    return r[r["market"] == tl.MARKET][["season", "resid"]].reset_index(drop=True)


def bucket_counts(bets_path: Path) -> dict[int, dict]:
    b = pd.read_parquet(bets_path)
    b = b[(b["family"] == "F4") & (b["point"] == "C") & (b["market"] == tl.MARKET)
          & (b["cell_side"] == tl.SIDE) & (b["cut"] == tl.GAP_CUT)]
    out = {}
    for s in BUCKET_SEASONS:
        x = b[b["season"] == s]
        out[int(s)] = {"n": int(len(x)), "wins": int((x["result"] == "W").sum()),
                       "pushes": int((x["result"] == "P").sum()),
                       "sum_p_win": float(x["p_win"].sum()),
                       "units": float(x["units"].sum())}
    return out


def build(cache: Path, bets_path: Path) -> dict:
    r = close_residuals(cache)
    return {
        "kind": tl.ARTIFACT_KIND,
        "model": None,                          # a rule: no fitted estimator
        "model_id": tl.MODEL_ID,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "rule": {"family": "F4", "decision_point": "C", "market": tl.MARKET,
                 "side": tl.SIDE, "gap_cut": tl.GAP_CUT},
        "close_resid": [(int(s), float(v)) for s, v in zip(r["season"], r["resid"])],
        "bucket": bucket_counts(bets_path),
        "source": {"cache": str(cache), "bets": str(bets_path),
                   "doc": "docs/nba_models_2026.md sections 6.6-6.7"},
    }


def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts (the trainer's restore
    source when the file is missing on the worker). A production write: run it
    deliberately, never from a test."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, tl.MODEL_ID, path.stem.split(tl.MODEL_ID + "_")[-1], path)
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bets", type=Path, default=BETS)
    ap.add_argument("--store", type=Path, help="copy this artifact into model_artifacts")
    a = ap.parse_args()
    if a.store:
        store(a.store)
        return
    art = build(H.CACHE, a.bets)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "models" / "saved" / f"{tl.MODEL_ID}_{stamp}.pkl"
    with open(out, "wb") as fh:
        pickle.dump(art, fh, protocol=4)
    per = pd.DataFrame(art["close_resid"], columns=["season", "resid"]).groupby("season")["resid"]
    print(f"wrote {out.relative_to(ROOT).as_posix()}")
    print("residuals per season:", per.size().to_dict(), "sd", per.std().round(2).to_dict())
    print("bucket:", art["bucket"])
    for s in (2026, 2027):
        print(f"uplift for {s}: {tl.uplift(art, s):+.4f}")


if __name__ == "__main__":
    main()
