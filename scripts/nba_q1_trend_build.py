"""Build the `nba_q1_trend` artifact (models/nba_q1_trend.py).

The live model prices offers with the first-quarter margin distribution the lab graded with, and states its
probability with the cell's walk-forward uplift. Both come from research files, so they are written once into a
tracked artifact rather than recomputed on the worker (the first-half model's shape,
scripts/nba_first_half_total_luck_build.py):

  q1_rows  (season, Pinnacle's full-game closing HOME number, the first quarter's home margin) for every game of
           2020-21 .. 2025-26 with a Pinnacle close, one row a game, by the lab's own code
           (scripts.nba_game_harness.load -> with_periods -> pinnacle_close -> scripts.nba_game4_p3
           .period_close_rows), in its row order. A game whose period scores fail with_periods' check holds NaN and
           is left out of the fit, as in the lab.
  bucket   per graded season (2023-24 .. 2025-26): the shipped cell's bets (Q1A, window L5to10, the spread check,
           cut 2.0), wins, pushes and the sum of their market-fair win probabilities, from the lab's bet file.
  pricing_tables  the finished price table of the season it prices live (models.nba_total_luck.with_pricing_table).

Reads only the research cache (NBA_RESEARCH_CACHE, a cache of Supabase) and the lab's bet file; no database, no API.

    NBA_RESEARCH_CACHE=... python -m scripts.nba_q1_trend_build
    python -m scripts.nba_q1_trend_build --store models/saved/nba_q1_trend_20261107.pkl   # into model_artifacts
"""
from __future__ import annotations

import argparse
import pickle
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_q1_trend as q1  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game4_p3 import period_close_rows  # noqa: E402

BETS = Path("C:/Users/micha/AppData/Local/Temp/q1trend/results/bets/bets_Q1A_D_spreads_q1_0008.parquet")
ROW_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)          # 2021-2026: the lab's full-game load
BUCKET_SEASONS = (2024, 2025, 2026)
CELL = {"family": "Q1A", "point": "D", "market": q1.MARKET, "cell_side": q1.SIDE_LABEL, "cut": q1.K_CUT}
EXPECTED_BETS = 88                                      # run 2026-10-28-eighth, nba_game2_cells


def q1_rows(cache: Path) -> pd.DataFrame:
    """(season, close_spread, q1_margin) in period_close_rows' own order."""
    data = H.load(cache, seasons=ROW_SEASONS, require_seasons=ROW_SEASONS)
    x = period_close_rows(H.pinnacle_close(data), H.with_periods(data.games, cache))
    return x.rename(columns={"spreads": "close_spread", "margin_q1": "q1_margin"})[
        ["season", "close_spread", "q1_margin"]].reset_index(drop=True)


def cell_bets(bets_path: Path) -> pd.DataFrame:
    b = pd.read_parquet(bets_path)
    keep = pd.Series(True, index=b.index)
    for k, v in CELL.items():
        keep &= b[k] == v
    b = b[keep].reset_index(drop=True)
    if len(b) != EXPECTED_BETS:
        raise RuntimeError(f"{bets_path}: {len(b)} bets in the cell, the stored run holds {EXPECTED_BETS}")
    return b


def bucket_counts(bets_path: Path) -> dict[int, dict]:
    b = cell_bets(bets_path)
    out = {}
    for s in BUCKET_SEASONS:
        x = b[b["season"] == s]
        out[int(s)] = {"n": int(len(x)), "wins": int((x["result"] == "W").sum()),
                       "pushes": int((x["result"] == "P").sum()),
                       "sum_p_win": float(x["p_win"].sum()), "units": float(x["units"].sum())}
    return out


def build(cache: Path, bets_path: Path) -> dict:
    r = q1_rows(cache)
    b = cell_bets(bets_path)
    return {
        "kind": q1.ARTIFACT_KIND,
        "model": None,
        "model_id": q1.MODEL_ID,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "rule": {"family": "Q1A", "decision_point": "D", "market": q1.MARKET, "window": q1.WINDOW,
                 "check": q1.CHECK, "k_cut": q1.K_CUT},
        "q1_rows": [(int(s), float(c), float(m)) for s, c, m in zip(r["season"], r["close_spread"],
                                                                    r["q1_margin"])],
        "bucket": bucket_counts(bets_path),
        # The graded bets themselves, keys and prices only, so the replay can be checked against them anywhere.
        "graded_bets": [(str(g), str(sd), str(bk), float(ln), float(px), str(res)) for g, sd, bk, ln, px, res in
                        zip(b["game_id"], b["side"], b["book"], b["line"], b["price"], b["result"])],
        "source": {"cache": str(cache), "bets": str(bets_path),
                   "doc": "docs/nba_models_2026.md section 12 (Q1A, L5to10, spread check, k >= 2)"},
    }


def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts. A production write: run it deliberately."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, q1.MODEL_ID, path.stem.split(q1.MODEL_ID + "_")[-1], path)
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
    art = tl.with_pricing_table(art, q1.pricing_dist, q1.newest_season)
    out = ROOT / q1.ARTIFACT_PATH
    with open(out, "wb") as fh_out:
        pickle.dump(art, fh_out, protocol=4)
    rows = pd.DataFrame(art["q1_rows"], columns=["season", "close_spread", "q1_margin"])
    print(f"wrote {out.relative_to(ROOT).as_posix()}")
    print("games per season:", rows.groupby("season").size().to_dict())
    print("with a first-quarter margin:", rows[np.isfinite(rows["q1_margin"])].groupby("season").size().to_dict())
    print("bucket:", art["bucket"])
    for s in (2025, 2026, 2027):
        print(f"uplift for {s}: {q1.uplift(art, s):+.4f}")
    for s in (2024, 2025, 2026, 2027):
        d = q1.pricing_dist(art, s)
        print(f"pricing {s}: n={d.n} sd={d.sd:.2f} ({d.label})")


if __name__ == "__main__":
    main()
