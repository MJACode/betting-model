"""Build the `nba_first_half_total_luck` artifact (models/nba_first_half_total_luck.py).

The live model prices offers with the same first-half distribution the lab
graded with, and states its probability with the same walk-forward uplift. Both
come from research files, so they are written once into a tracked artifact
rather than recomputed on the worker:

  h1_rows  (season, Pinnacle's full-game closing total, the first half's total)
           for every game of 2020-21 .. 2025-26 with a Pinnacle close, one row
           a game, built by the lab's own code (scripts.nba_game_harness.load ->
           with_periods -> pinnacle_close -> scripts.nba_game4_p3
           .period_close_rows), in its row order. A game whose period scores
           fail with_periods' check holds NaN and is left out of the fit, as in
           the lab. The live model's distribution for season S
           (models.nba_first_half_total_luck.pricing_dist) refits a + b x close
           on the rows of seasons before S, so it is the lab's
           period_market_pricing exactly.
  bucket   per graded season (2023-24 .. 2025-26): the shipped cell's bets (P3_F4,
           decision point D, totals_h1, over, cut 2.0), wins, pushes and the sum
           of their market-fair win probabilities, read from the lab's own bet
           file. uplift(S) is fitted on the seasons before S.
  pricing_tables  the finished price table of the season it prices live, built from
           h1_rows (models.nba_total_luck.with_pricing_table).

Reads only the research cache (NBA_RESEARCH_CACHE, a cache of Supabase) and
the lab's bet file; no database, no API.

    NBA_RESEARCH_CACHE=... python -m scripts.nba_first_half_total_luck_build
    NBA_RESEARCH_CACHE=... python -m scripts.nba_first_half_total_luck_build --bets <bets parquet>
    python -m scripts.nba_first_half_total_luck_build --store <artifact>   # copy it into model_artifacts
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

import models.nba_first_half_total_luck as fh  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game4_p3 import period_close_rows  # noqa: E402

BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_game_edge/results4/full/bets/P3/"
            "bets_P3_F4_D_totals_h1_0010.parquet")
ROW_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)          # 2021-2026: the lab's full-game load
BUCKET_SEASONS = (2024, 2025, 2026)                     # the graded first-half seasons
CELL = {"family": "P3_F4", "point": "D", "market": fh.MARKET, "cell_side": fh.SIDE,
        "cut": fh.GAP_CUT}


def h1_rows(cache: Path) -> pd.DataFrame:
    """(season, close_total, h1_total) in period_close_rows' own order."""
    data = H.load(cache, seasons=ROW_SEASONS, require_seasons=ROW_SEASONS)
    x = period_close_rows(H.pinnacle_close(data), H.with_periods(data.games, cache))
    return x.rename(columns={"totals": "close_total", "total_h1": "h1_total"})[
        ["season", "close_total", "h1_total"]].reset_index(drop=True)


def cell_bets(bets_path: Path) -> pd.DataFrame:
    b = pd.read_parquet(bets_path)
    keep = pd.Series(True, index=b.index)
    for k, v in CELL.items():
        keep &= b[k] == v
    return b[keep].reset_index(drop=True)


def bucket_counts(bets_path: Path) -> dict[int, dict]:
    b = cell_bets(bets_path)
    out = {}
    for s in BUCKET_SEASONS:
        x = b[b["season"] == s]
        out[int(s)] = {"n": int(len(x)), "wins": int((x["result"] == "W").sum()),
                       "pushes": int((x["result"] == "P").sum()),
                       "sum_p_win": float(x["p_win"].sum()),
                       "units": float(x["units"].sum())}
    return out


def build(cache: Path, bets_path: Path) -> dict:
    r = h1_rows(cache)
    return {
        "kind": fh.ARTIFACT_KIND,
        "model": None,                          # a rule: no fitted estimator
        "model_id": fh.MODEL_ID,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "rule": {"family": "P3_F4", "decision_point": "D", "market": fh.MARKET,
                 "side": fh.SIDE, "gap_cut": fh.GAP_CUT},
        "h1_rows": [(int(s), float(c), float(t))
                    for s, c, t in zip(r["season"], r["close_total"], r["h1_total"])],
        "bucket": bucket_counts(bets_path),
        "source": {"cache": str(cache), "bets": str(bets_path),
                   "doc": "docs/nba_models_2026.md sections 8.3 and 8.4 (P3, cell C1)"},
    }


def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts (the trainer's restore
    source when the file is missing on the worker). A production write: run it
    deliberately, never from a test."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, fh.MODEL_ID, path.stem.split(fh.MODEL_ID + "_")[-1], path)
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
    art = fh.tl.with_pricing_table(art, fh.pricing_dist, fh.newest_season)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = ROOT / "models" / "saved" / f"{fh.MODEL_ID}_{stamp}.pkl"
    with open(out, "wb") as fh_out:
        pickle.dump(art, fh_out, protocol=4)
    rows = pd.DataFrame(art["h1_rows"], columns=["season", "close_total", "h1_total"])
    print(f"wrote {out.relative_to(ROOT).as_posix()}")
    print("games per season:", rows.groupby("season").size().to_dict())
    print("with a first-half total:",
          rows[np.isfinite(rows["h1_total"])].groupby("season").size().to_dict())
    print("bucket:", art["bucket"])
    for s in (2025, 2026, 2027):
        print(f"uplift for {s}: {fh.uplift(art, s):+.4f}")
    for s in (2024, 2025, 2026, 2027):
        d = fh.pricing_dist(art, s)
        print(f"pricing {s}: n={d.n} sd={d.sd:.2f} ({d.label})")


if __name__ == "__main__":
    main()
