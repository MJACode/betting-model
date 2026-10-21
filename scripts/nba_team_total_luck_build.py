"""Build the `nba_team_total_luck` artifact (models/nba_team_total_luck.py).

The live model prices offers with the same empirical team-total distribution
the lab graded with, and states its probability with the same walk-forward
uplift. Both come from research files, so they are written once into a tracked
artifact rather than recomputed on the worker:

  tt_resid  (season, resid) for every game of 2020-21 .. 2025-26 with a
            Pinnacle full-game close, two rows a game: the home team's score
            minus (close total - close home spread) / 2, and the away team's
            minus (close total + close home spread) / 2. Built by the lab's own
            code (scripts.nba_game_harness.load -> pinnacle_close ->
            scripts.nba_game2_market.team_total_resid), in its row order, so
            the live model's distribution for season S (the rows of seasons
            before S, models.nba_team_total_luck.pricing_dist) is the lab's
            team_total_dist exactly.
  bucket    per graded season (2023-24 .. 2025-26): the shipped cell's bets
            (P3_F4, decision point D, team_totals_home, under, cut 2.0), wins,
            pushes and the sum of their market-fair win probabilities, read
            from the lab's own bet file. uplift(S) is fitted on the seasons
            before S.

Reads only the research cache (NBA_RESEARCH_CACHE, a cache of Supabase) and
the lab's bet file; no database, no API.

    NBA_RESEARCH_CACHE=... python -m scripts.nba_team_total_luck_build
    NBA_RESEARCH_CACHE=... python -m scripts.nba_team_total_luck_build --bets <bets parquet>
    python -m scripts.nba_team_total_luck_build --store <artifact>   # copy it into model_artifacts
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

import models.nba_team_total_luck as tt  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game2_market import team_total_resid  # noqa: E402

BETS = Path("C:/Users/micha/AppData/Local/Temp/nba_game_edge/results4/full/bets/P3/"
            "bets_P3_F4_D_team_totals_home_0011.parquet")
RESID_SEASONS = (H.REGIME, *H.CHOOSE, H.CONFIRM)        # 2021-2026: the lab's full-game load
BUCKET_SEASONS = (2024, 2025, 2026)                     # the graded team-total seasons
CELL = {"family": "P3_F4", "point": "D", "market": tt.MARKET, "cell_side": tt.SIDE,
        "cut": tt.GAP_CUT}


def tt_residuals(cache: Path) -> pd.DataFrame:
    """(season, resid) in team_total_resid's own order."""
    data = H.load(cache, seasons=RESID_SEASONS, require_seasons=RESID_SEASONS)
    r = team_total_resid(H.pinnacle_close(data), data.games)
    return r[["season", "resid"]].reset_index(drop=True)


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
    r = tt_residuals(cache)
    return {
        "kind": tt.ARTIFACT_KIND,
        "model": None,                          # a rule: no fitted estimator
        "model_id": tt.MODEL_ID,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "rule": {"family": "P3_F4", "decision_point": "D", "market": tt.MARKET,
                 "side": tt.SIDE, "gap_cut": tt.GAP_CUT},
        "tt_resid": [(int(s), float(v)) for s, v in zip(r["season"], r["resid"])],
        "bucket": bucket_counts(bets_path),
        "source": {"cache": str(cache), "bets": str(bets_path),
                   "doc": "docs/nba_models_2026.md section 8 (P3, team totals)"},
    }


def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts (the trainer's restore
    source when the file is missing on the worker). A production write: run it
    deliberately, never from a test."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, tt.MODEL_ID, path.stem.split(tt.MODEL_ID + "_")[-1], path)
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
    out = ROOT / "models" / "saved" / f"{tt.MODEL_ID}_{stamp}.pkl"
    with open(out, "wb") as fh:
        pickle.dump(art, fh, protocol=4)
    per = pd.DataFrame(art["tt_resid"], columns=["season", "resid"]).groupby("season")["resid"]
    print(f"wrote {out.relative_to(ROOT).as_posix()}")
    print("residuals per season:", per.size().to_dict(), "sd", per.std().round(2).to_dict())
    print("bucket:", art["bucket"])
    for s in (2025, 2026, 2027):
        print(f"uplift for {s}: {tt.uplift(art, s):+.4f}")
    for s in (2024, 2025, 2026, 2027):
        d = tt.pricing_dist(art, s)
        print(f"pricing {s}: n={d.n} sd={d.sd:.2f} mean before centring {d.mean:+.3f}")


if __name__ == "__main__":
    main()
