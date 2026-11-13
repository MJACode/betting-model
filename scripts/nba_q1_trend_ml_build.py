"""Build the `nba_q1_trend_ml` artifact (models/nba_q1_trend_ml.py).

The live model states its probability with the cell's walk-forward uplift, which comes from the graded bets, so it is
written once into a tracked artifact rather than recomputed on the worker (models/nba_q1_trend.py's shape). The
moneyline is priced from the books' own no-vig prices, so unlike the spread model it carries no margin distribution.

  bucket       per graded season (2023-24 .. 2025-26): the shipped cell's bets (Q1M, the spread check, k >= 2), wins,
               pushes, the decided bets (bets minus pushes) and the sum of their market-fair win probabilities, from
               the lab's bet file.
  graded_bets  the 87 bets themselves, keys and prices only, so the replay can be checked against them anywhere.

Reads only the lab's bet file; no database, no API.

    python -m scripts.nba_q1_trend_ml_build
    python -m scripts.nba_q1_trend_ml_build --store C:/.../models/saved/nba_q1_trend_ml_20261107.pkl   # model_artifacts
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

import models.nba_q1_trend_ml as ml  # noqa: E402

# The search's bet file for the spread-check cells (run 2026-11-07-q1mt, scripts/nba_s_q1mt.py --full).
BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_s/q1mt/results/bets/bets_Q1M_D_h2h_q1_0003.parquet")
BUCKET_SEASONS = (2024, 2025, 2026)
CELL = {"family": "Q1M", "point": "D", "market": ml.MARKET, "cell_side": ml.SIDE_LABEL, "cut": ml.K_CUT}
EXPECTED_BETS = 87                                      # run 2026-11-07-q1mt, nba_game2_cells
EXPECTED_UNITS = 17.78


def cell_bets(bets_path: Path) -> pd.DataFrame:
    b = pd.read_parquet(bets_path)
    keep = pd.Series(True, index=b.index)
    for k, v in CELL.items():
        keep &= b[k] == v
    b = b[keep].reset_index(drop=True)
    if len(b) != EXPECTED_BETS or round(float(b["units"].sum()), 2) != EXPECTED_UNITS:
        raise RuntimeError(f"{bets_path}: {len(b)} bets, {b['units'].sum():+.2f} units in the cell; the stored run "
                           f"holds {EXPECTED_BETS} and {EXPECTED_UNITS:+.2f}")
    return b


def bucket_counts(b: pd.DataFrame) -> dict[int, dict]:
    out = {}
    for s in BUCKET_SEASONS:
        x = b[b["season"] == s]
        d = x[x["result"] != "P"]
        out[int(s)] = {"n": int(len(x)), "wins": int((x["result"] == "W").sum()),
                       "pushes": int((x["result"] == "P").sum()), "decided": int(len(d)),
                       "sum_p_win_decided": float(d["p_win"].sum()), "units": float(x["units"].sum())}
    return out


def build(bets_path: Path) -> dict:
    b = cell_bets(bets_path)
    return {
        "kind": ml.ARTIFACT_KIND,
        "model": None,
        "model_id": ml.MODEL_ID,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "rule": {"family": "Q1M", "decision_point": "D", "market": ml.MARKET, "window": ml.WINDOW,
                 "check": ml.CHECK, "k_cut": ml.K_CUT},
        "bucket": bucket_counts(b),
        "graded_bets": [(str(g), str(sd), str(bk), float(px), str(res)) for g, sd, bk, px, res in
                        zip(b["game_id"], b["side"], b["book"], b["price"], b["result"])],
        "source": {"bets": str(bets_path), "doc": "docs/nba_search_q1mt.md (Q1M, the spread check, k >= 2)"},
    }


def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts. A production write: run it deliberately."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, ml.MODEL_ID, path.stem.split(ml.MODEL_ID + "_")[-1], path)
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
    art = build(a.bets)
    out = ROOT / ml.ARTIFACT_PATH
    with open(out, "wb") as fh_out:
        pickle.dump(art, fh_out, protocol=4)
    print(f"wrote {out.relative_to(ROOT).as_posix()}")
    print("bucket:", art["bucket"])
    for s in (2025, 2026, 2027):
        print(f"uplift for {s}: {ml.uplift(art, s):+.4f}")


if __name__ == "__main__":
    main()
