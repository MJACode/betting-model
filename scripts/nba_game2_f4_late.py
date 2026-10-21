"""Diagnostic, NOT pre-registered: F4 (shooting-luck ratings) graded at decision point D.

docs/nba_models_2026.md §6.7. F4 was registered at A and C, where its overs
show closing-line value about 2.4% against them. Graded at 45-75 minutes before
tip, after most of the market's move, it shows whether the profit survives that
move. Written to its own family name (F4_late_diagnostic) so it can never enter
the 422 cells or the verdict as a candidate.

    NBA_GAME2_GO=1 PYTHONPATH=. python -m scripts.nba_game2_f4_late
"""
from __future__ import annotations

import os
from pathlib import Path

import scripts.nba_game_harness as H
import scripts.nba_game2_luck as L


def main() -> None:
    if os.environ.get("NBA_GAME2_GO") != "1":
        raise SystemExit("refused: set NBA_GAME2_GO=1")
    out = Path(os.environ.get("NBA_GAME2_DIAG", str(L.RESULTS / "diagnostic")))
    out.mkdir(parents=True, exist_ok=True)
    box, _ = L._load_box(H.CACHE)
    data = H.load(H.CACHE, seasons=L.FULL_SEASONS, require_seasons=L.FULL_SEASONS)
    close = H.pinnacle_close(data)
    sig = H.close_dist(close, data.games)
    tb = L.team_box(box, data.games)
    L.F4_POINTS = ("D",)
    rows, _ = L.run_f4(data, tb, close, sig)
    for r in rows:
        r["family"] = "F4_late_diagnostic"
    L.write_cells(rows, out / "cells_F4_late_diagnostic.parquet")
    print(f"{len(rows)} diagnostic cells written to {out}")


if __name__ == "__main__":
    main()
