"""Pass / fail for every cell of the second NBA game-market search.

docs/nba_models_2026.md §6.4 fixes the bars; this applies them, the same way,
to every family's cell table (the rows scripts/nba_game_harness.run_cells
writes). Written and committed BEFORE any lab produced a cell, so no rule here
was chosen knowing a result.

A cell passes only if every line holds:

  5  positive in every choosing season with >= 30 bets
  6  >= 200 bets on the choosing seasons and their whole-day 90% CI above zero
  7  plateau: every existing neighbour (cut_index +-1, same family, decision
     point, market, side and every extra axis) is positive on the choosing
     seasons. Adjacent decision points are NOT neighbours (a different moment
     is a different bet, not a nearby threshold).
  8  both date halves of the choosing seasons positive
  9  beats the blind bet on the same side: every game at that decision point,
     the best deciding offer under the market's own fair price, no cut. Each
     cell is one side, so this applies to every cell (the 70% rule of section
     1 is always met).
  10 placebo: the cell's ROI above the 95th percentile of its placebo ROIs
     (fair parameters shuffled within date and market, 20 reps)
  11 closing-line value at decision points A-C: the median choosing-season
     bet beats Pinnacle's no-vig last pre-tip price. At D it is reported only.
  C  confirmation on 2025-26 alone: >= 200 bets, ROI > 0, 90% CI above zero
  BH Benjamini-Hochberg at q = 0.05. Basis "confirm" (as pre-registered): the
     one-sided p on 2025-26 alone, m = 4,172 (the first search's 3,750 cells
     entered at p = 1). Basis "choose": the p on the choosing seasons pooled,
     m = the cells of this search. Which basis applies is decided by mike
     before this is run on real cells (section 6.4).

    PYTHONPATH=. python -m scripts.nba_game2_verdict --results DIR [--bh-basis confirm]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.nba_game_harness import bh_pass  # noqa: E402

CORE_AXES = ["family", "point", "market", "side"]
NOT_AXES = {"cut_index", "cut"}
M_FIRST_SEARCH = 3750
CLV_POINTS = ("A", "B", "C")
MIN_BETS, MIN_SEASON_BETS = 200, 30


def axes_of(cells: pd.DataFrame) -> list[str]:
    """Core axes plus any extra axis a lab added (a column named axis_*)."""
    return CORE_AXES + sorted(c for c in cells.columns if c.startswith("axis_"))


def cell_key(row: pd.Series, axes: list[str]) -> str:
    return "|".join(str(row[a]) for a in axes) + f"|cut={row['cut']}"


def plateau_ok(cells: pd.DataFrame, axes: list[str]) -> pd.Series:
    ok = pd.Series(True, index=cells.index)
    for _, grp in cells.groupby(axes, dropna=False, sort=False):
        by_k = grp.set_index("cut_index")["roi_choose"]
        for i, row in grp.iterrows():
            k = row["cut_index"]
            nb = [by_k.get(k - 1), by_k.get(k + 1)]
            nb = [x for x in nb if x is not None]
            ok[i] = all(np.isfinite(x) and x > 0 for x in nb)
    return ok


def verdict(cells: pd.DataFrame, bh_basis: str = "confirm", m_first: int = M_FIRST_SEARCH,
            q: float = 0.05) -> pd.DataFrame:
    c = cells.copy()
    axes = axes_of(c)
    c["key"] = [cell_key(r, axes) for _, r in c.iterrows()]
    assert c["key"].is_unique, "two cells share every axis: a lab emitted a duplicate"
    p95 = c["placebo_rois"].apply(
        lambda v: np.percentile([x for x in v if np.isfinite(x)], 95)
        if len([x for x in v if np.isfinite(x)]) else np.nan)
    c["bar5"] = c["seasons_positive"].astype(bool) & (c["n_choose"] > 0)
    c["bar6"] = (c["n_choose"] >= MIN_BETS) & (c["ci_lo_choose"] > 0)
    c["bar7"] = plateau_ok(c, axes) & (c["roi_choose"] > 0)
    c["bar8"] = (c["half_early_roi"] > 0) & (c["half_late_roi"] > 0)
    c["bar9"] = c["roi_choose"] > c["blind_roi_choose"].fillna(np.inf)
    c["bar10"] = c["roi_choose"] > p95.fillna(np.inf)
    at_clv = c["point"].isin(CLV_POINTS)
    c["bar11"] = ~at_clv | (c["clv_median"] > 0)
    c["confirm"] = (c["n_confirm"] >= MIN_BETS) & (c["roi_confirm"] > 0) & (c["ci_lo_confirm"] > 0)
    if bh_basis == "confirm":
        pcol, m = "p_confirm", len(c) + m_first
    elif bh_basis == "choose":
        pcol, m = "p_choose", len(c)
    else:
        raise ValueError(bh_basis)
    passed = bh_pass(dict(zip(c["key"], c[pcol].fillna(1.0))), m_total=m, q=q)
    c["bh"] = c["key"].isin(passed)
    c["bh_basis"], c["bh_m"] = bh_basis, m
    bars = ["bar5", "bar6", "bar7", "bar8", "bar9", "bar10", "bar11", "confirm", "bh"]
    c["passes"] = c[bars].all(axis=1)
    c["failed"] = c[bars].apply(lambda r: ",".join(b for b in bars if not r[b]), axis=1)
    return c


def load_cells(results: Path) -> pd.DataFrame:
    parts = [pd.read_parquet(p) for p in sorted(results.glob("cells_*.parquet"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--bh-basis", choices=["confirm", "choose"], default="confirm")
    a = ap.parse_args()
    cells = load_cells(a.results)
    v = verdict(cells, a.bh_basis)
    v.drop(columns=["placebo_rois"]).to_parquet(a.results / f"verdict_{a.bh_basis}.parquet")
    print(f"{len(v)} cells; {int(v['passes'].sum())} pass (BH basis {a.bh_basis}, m = {v['bh_m'].iloc[0]})")
    print(v.groupby("family")[["bar5", "bar6", "bar7", "bar8", "bar9", "bar10", "bar11",
                               "confirm", "bh", "passes"]].sum())


if __name__ == "__main__":
    main()
