"""Build the NCAAB in-play artifact the live loop loads
(models/saved/ncaab_live_ig_2027.json, models/ncaab_live_ig.load_artifact).

What it holds, each from Supabase through scripts/ncaab_ingame_search (the
grade's own code):
  margin, total   the 2026-27 state models, fit on every 30-second game state
                  of 2020-21 .. 2025-26 (walk-forward: no 2026-27 game)
  ev_quantiles    the EV of every graded decision of the three live rules at
                  the half-hour cadence, 2021-22 .. 2025-26, at q = 0 .. 1 in
                  1,001 steps: the table M.night_cut reads
  per_game        those decisions per slate game: how many decisions a slate
                  of N games is expected to hold
  graded          the shipped selection's grade (--best-per-night), for the record

    PYTHONPATH=. python -m scripts.build_ncaab_live_ig_artifact
    (needs `python -m scripts.ncaab_ingame_search --grade --step 30` first)
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from models import ncaab_live_ig as M  # noqa: E402
from scripts import ncaab_ingame_search as S  # noqa: E402


def build(conn) -> dict:
    games = S.load_games(conn)
    states = {s: S.training_states(conn, s, games) for s in S.SEASONS}
    models = S.fit_models(states, M.SEASON)
    off = pd.read_parquet(S.CACHE / "offers_step30.parquet")
    dec, slates = S.live_decisions(off, games)
    q, per_game = S.night_table(dec, slates)
    graded = None
    p = S.CACHE / "best_per_night.json"
    if p.exists():
        graded = json.loads(p.read_text(encoding="utf-8"))
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                text=True, timeout=10).stdout.strip()
    except Exception:  # noqa: BLE001
        commit = ""
    built = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "kind": M.ARTIFACT_KIND, "version": f"{M.SEASON}.{built[:10]}", "built_at": built,
        "built_from_commit": commit, "season": M.SEASON,
        "train_seasons": sorted(int(s) for s in states), "graded_seasons": sorted(int(s) for s in dec.season.unique()),
        "model_ids": list(M.MODEL_IDS),
        "rules": [{"model_id": r.model_id, "market": r.market, "phase": r.phase, "floor": r.floor}
                  for r in M.RULES],
        "night_target": M.NIGHT_TARGET, "night_cap": M.NIGHT_CAP, "cadence_min": M.CADENCE_MIN,
        "fetch_offset_sec": M.FETCH_OFFSET_SEC,
        "margin": models["margin"].to_dict(), "total": models["total"].to_dict(),
        "ev_quantiles": [round(float(x), 9) for x in q], "per_game": per_game,
        "n_decisions": int(len(dec)), "graded": graded,
    }


def main() -> int:
    conn = S._conn()
    try:
        art = build(conn)
    finally:
        conn.close()
    out = ROOT / M.ARTIFACT_PATH
    out.write_text(json.dumps(art, indent=1), encoding="utf-8")
    back = M.load_artifact(out)                       # what the loop will read
    for n in (10, 60, 150):
        print(f"slate of {n} games: night cuts",
              {r.model_id: round(M.night_cut(back, n, r), 4) for r in M.RULES})
    print(f"wrote {out} ({out.stat().st_size:,} bytes), version {back.version}, "
          f"{art['n_decisions']:,} decisions, {back.per_game:.3f} a slate game")
    return 0


if __name__ == "__main__":
    sys.exit(main())
