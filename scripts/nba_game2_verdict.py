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
     is a different bet, not a nearby threshold), and neither are the values
     of a categorical axis (F6c's situations): such a cell has no neighbours
     and bar 7 reduces to its own ROI above zero.
  8  both date halves of the choosing seasons positive
  9  beats the blind bet on its dominant real side (section 1's wording): when
     more than 70% of the cell's choosing-season bets fall on one side of a
     split -- home/away, favourite/underdog (by the market's fair line at T),
     over/under -- the cell's ROI must beat that side bet on every game of the
     cell's own priced population at that point, no model, no cut, at the
     best deciding offer under the market's fair line. A dominant side with no
     blind number fails. (Supersedes the 2026-10-17 "each cell bets one side"
     reading; amendment of the same date in section 6.4.)
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
CONTROL_PREFIX = "control_"
DOMINANT = 0.70
SPLITS = {"home": ("home", "away"), "fav": ("fav", "dog"), "over": ("over", "under")}
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


def _floats(v) -> np.ndarray:
    """A placebo list as floats: parquet stores an all-NaN list as list<null>,
    which reads back as None."""
    if v is None:
        return np.array([], float)
    a = np.array(list(v), dtype=float)          # a None element reads as NaN
    return a[np.isfinite(a)]


def bar9(row: pd.Series) -> bool:
    for split, (a, b) in SPLITS.items():
        share = row.get(f"share_{split}", np.nan)
        if not np.isfinite(share):
            continue
        side = a if share > DOMINANT else b if share < 1 - DOMINANT else None
        if side is None:
            continue
        blind = row.get(f"blind_{side}", np.nan)
        if not (np.isfinite(blind) and row["roi_choose"] > blind):
            return False
    return True


def verdict(cells: pd.DataFrame, bh_basis: str = "confirm", m_first: int = M_FIRST_SEARCH,
            q: float = 0.05) -> pd.DataFrame:
    """Every bar on every candidate cell. Controls (family control_*) are
    graded by the labs and reported, never judged or counted in m."""
    c = cells[~cells["family"].astype(str).str.startswith(CONTROL_PREFIX)].copy()
    axes = axes_of(c)
    c["key"] = [cell_key(r, axes) for _, r in c.iterrows()]
    assert c["key"].is_unique, "two cells share every axis: a lab emitted a duplicate"
    p95 = c["placebo_rois"].apply(lambda v: np.percentile(_floats(v), 95)
                                  if len(_floats(v)) else np.nan)
    c["bar5"] = c["seasons_positive"].astype(bool) & (c["n_choose"] > 0)
    c["bar6"] = (c["n_choose"] >= MIN_BETS) & (c["ci_lo_choose"] > 0)
    c["bar7"] = plateau_ok(c, axes) & (c["roi_choose"] > 0)
    c["bar8"] = (c["half_early_roi"] > 0) & (c["half_late_roi"] > 0)
    c["bar9"] = c.apply(bar9, axis=1) & c["roi_choose"].notna()
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
    # A cell below the bet-count bar enters the correction at p = 1: with a
    # handful of bets that all won, no resample can show a loss, so its p is 0
    # and it would loosen the bar for every other cell (found 2026-10-17 on the
    # graded run: six such cells, 1-14 bets each; the outcome, 0 of 422, is
    # the same either way).
    n_col = "n_confirm" if bh_basis == "confirm" else "n_choose"
    p_used = c[pcol].where(c[n_col] >= MIN_BETS, 1.0).fillna(1.0)
    passed = bh_pass(dict(zip(c["key"], p_used)), m_total=m, q=q)
    c["bh"] = c["key"].isin(passed)
    c["bh_basis"], c["bh_m"] = bh_basis, m
    bars = ["bar5", "bar6", "bar7", "bar8", "bar9", "bar10", "bar11", "confirm", "bh"]
    c["passes"] = c[bars].all(axis=1)
    c["failed"] = c[bars].apply(lambda r: ",".join(b for b in bars if not r[b]), axis=1)
    return c


HOUSE_BARS = ["h1_bets", "h2_ci95", "h3_seasons", "h4_blind", "h5_plateau", "h6_placebo"]


def house_bar4(row: pd.Series) -> bool:
    """Beats the blind same real side, pooled (bar 9's rule on pooled numbers)."""
    for split, (a, b) in SPLITS.items():
        share = row.get(f"pool_share_{split}", np.nan)
        if not np.isfinite(share):
            continue
        side = a if share > DOMINANT else b if share < 1 - DOMINANT else None
        if side is None:
            continue
        blind = row.get(f"blind_pool_{side}", np.nan)
        if not (np.isfinite(blind) and row["pool_roi"] > blind):
            return False
    return True


def house_verdict(cells: pd.DataFrame, judge_controls=()) -> pd.DataFrame:
    """§6.7: the standard the repo's shipped models were held to, one fixed list.

    1 pooled bets >= 200; 2 pooled 95% interval above zero; 3 of the graded
    seasons with >= 30 bets, all but at most one positive; 4 beats the blind
    same real side, pooled; 5 every existing cut neighbour positive, pooled;
    6 placebo (bar 10). Closing-line value is reported, never a bar.
    `judge_controls`: control families judged like candidates (section 9.8);
    none by default, so every earlier caller reads the same rows."""
    fam = cells["family"].astype(str)
    c = cells[~fam.str.startswith(CONTROL_PREFIX) | fam.isin(tuple(judge_controls))].copy()
    axes = axes_of(c)
    c["key"] = [cell_key(r, axes) for _, r in c.iterrows()]
    assert c["key"].is_unique, "two cells share every axis"
    c["h1_bets"] = c["pool_n"] >= MIN_BETS
    c["h2_ci95"] = c["pool_ci95_lo"] > 0
    c["h3_seasons"] = (c["pool_seasons_counted"] >= 2) & (
        c["pool_seasons_counted"] - c["pool_seasons_positive"] <= 1)
    c["h4_blind"] = c.apply(house_bar4, axis=1) & c["pool_roi"].notna()
    ok = pd.Series(True, index=c.index)
    for _, grp in c.groupby(axes, dropna=False, sort=False):
        by_k = grp.set_index("cut_index")["pool_roi"]
        for i, row in grp.iterrows():
            nb = [by_k.get(row["cut_index"] - 1), by_k.get(row["cut_index"] + 1)]
            ok[i] = all(np.isfinite(x) and x > 0 for x in nb if x is not None)
    c["h5_plateau"] = ok & (c["pool_roi"] > 0)
    p95 = c["placebo_rois"].apply(lambda v: np.percentile(_floats(v), 95)
                                  if len(_floats(v)) else np.nan)
    c["h6_placebo"] = c["roi_choose"] > p95.fillna(np.inf)
    c["house_passes"] = c[HOUSE_BARS].all(axis=1)
    c["house_failed"] = c[HOUSE_BARS].apply(lambda r: ",".join(b for b in HOUSE_BARS if not r[b]),
                                            axis=1)
    return c


# ── the fifth search's bars (docs/nba_models_2026.md section 9, 2026-10-20) ──
# The house standard above with the two flaws section 8.4 found, fixed before
# any fifth-search cell was graded:
#   * bar 5 compares BANDS, not nested cuts: the band just below the cut and
#     every band from the cut to the top must each be positive, pooled. The
#     nested neighbour (cut >= 1 holds every cut >= 2 bet) never tested the
#     band below the cut, and that band lost for both fourth-search passes.
#     A band with fewer than BAND_MIN_BETS pooled bets is reported, not judged
#     (the house standard's own floor for a season to count).
#   * bar 6's placebo has PLACEBO_RUNS_5 shuffles (seeds 1-200), not 20; a
#     cell carrying any other count is a lab error and stops the verdict.
# house_verdict itself is unchanged: the fourth search's stored cells read
# through it.
# Section 9.8 (2026-10-20, after the check, before any cell was graded):
#   * the control (control_F7_league) is judged under the same bars, with its
#     own 200 placebo runs, and an F7 cell is credited to team tendencies only
#     when it passes AND its pooled return beats its control's at the same
#     market, side and cut (a control with no bet counts as 0);
#   * a placebo run that placed no bet counts as a return of 0 (it made
#     nothing); the 200-run check still counts runs.

PLACEBO_RUNS_5, BAND_MIN_BETS, BAND_SLOTS = 200, 30, 5
FIFTH_BARS = ["h1_bets", "h2_ci95", "h3_seasons", "h4_blind", "h5_bands", "h6_placebo"]
JUDGED_CONTROLS_5 = ("control_F7_league",)
CREDIT_CONTROL_5 = {"F7": "control_F7_league"}


def placebo_runs(v) -> np.ndarray:
    """Section 9.8: every placebo run as a float, a run with no bet (NaN or
    None, as parquet reads it back) counted as a return of 0."""
    if v is None:
        return np.array([], float)
    a = np.array(list(v), dtype=float)          # a None element reads as NaN
    return np.where(np.isfinite(a), a, 0.0)


def band_slots(row: pd.Series) -> int:
    """How many bands the lab wrote for this row: one past the highest bandN_n column, and
    never fewer than BAND_SLOTS. The sixth search writes up to six for its lowest cut
    (docs/nba_models_2026.md 10.5); a fixed five would never judge the top band."""
    idx = [int(k[4:-2]) for k in row.index if k.startswith("band") and k.endswith("_n") and k[4:-2].isdigit()]
    return max([BAND_SLOTS] + [i + 1 for i in idx])


def bands_ok(row: pd.Series, min_bets: int = BAND_MIN_BETS) -> bool:
    """Every band the lab wrote (band0 = just below the cut, band1.. = from
    the cut up) with at least `min_bets` pooled bets has a positive return."""
    for i in range(band_slots(row)):
        n = row.get(f"band{i}_n", 0)
        n = 0 if n is None or not np.isfinite(n) else n
        if n < min_bets:
            continue
        r = row.get(f"band{i}_roi", np.nan)
        if not (r is not None and np.isfinite(r) and r > 0):
            return False
    return True


def house_verdict_bands(cells: pd.DataFrame, n_placebo: int = PLACEBO_RUNS_5,
                        judge_controls=JUDGED_CONTROLS_5, credit=CREDIT_CONTROL_5) -> pd.DataFrame:
    """Section 9: house_verdict's bars 1-4, bar 5 on bands (bands_ok and the
    cell's own pooled return above zero), bar 6 on exactly `n_placebo` placebo
    runs per judged cell with a run that bet nothing counted as 0, and the
    controls in `judge_controls` judged like candidates (section 9.8).
    `credit`: {family: its control}; beats_control is the family's pooled
    return above its control's at the same market, side and cut_index (a
    control with no bet counts as 0), and credited is the cell passing AND,
    where it has a control, beating it. A family whose control is missing
    from `cells` is never credited."""
    c = house_verdict(cells, judge_controls)
    runs = c["placebo_rois"].apply(lambda v: len(placebo_runs(v)))
    bad = c.loc[runs != n_placebo, "key"]
    if len(bad):
        raise ValueError(f"{len(bad)} cells carry a placebo count other than {n_placebo} "
                         f"(e.g. {list(bad)[:3]}): section 9 fixes {n_placebo} shuffles")
    if not any(f"band{i}_n" in c for i in range(BAND_SLOTS)):
        raise ValueError("no band columns: section 9's bar 5 reads the lab's band0..band4")
    runs_z = c["placebo_rois"].apply(placebo_runs)
    c["placebo_empty_runs"] = c["placebo_rois"].apply(
        lambda v: 0 if v is None else int((~np.isfinite(np.array(list(v), dtype=float))).sum()))
    c["placebo_p95"] = runs_z.apply(lambda a: float(np.percentile(a, 95)) if len(a) else np.nan)
    c["h6_placebo"] = c["roi_choose"] > c["placebo_p95"].fillna(np.inf)
    c["h5_bands"] = c.apply(bands_ok, axis=1) & (c["pool_roi"] > 0)
    c["house5_passes"] = c[FIFTH_BARS].all(axis=1)
    c["house5_failed"] = c[FIFTH_BARS].apply(lambda r: ",".join(b for b in FIFTH_BARS if not r[b]), axis=1)
    c["control_pool_roi"] = np.nan
    c["beats_control"] = pd.Series(pd.NA, index=c.index, dtype="boolean")
    for fam, ctl_fam in (credit or {}).items():
        m = c["family"].astype(str) == fam
        if not m.any():
            continue
        ctl = c[c["family"].astype(str) == ctl_fam]
        if ctl.empty:
            continue
        ref = ctl.set_index(["market", "side", "cut_index"])["pool_roi"]
        got = np.array([ref.get(k, np.nan) for k in zip(c.loc[m, "market"], c.loc[m, "side"],
                                                         c.loc[m, "cut_index"])], dtype=float)
        c.loc[m, "control_pool_roi"] = got
        c.loc[m, "beats_control"] = c.loc[m, "pool_roi"].to_numpy(float) > np.nan_to_num(got, nan=0.0)
    need = c["family"].astype(str).isin(tuple(credit or {})).to_numpy()
    beat = c["beats_control"].fillna(False).astype(bool).to_numpy()
    c["credited"] = c["house5_passes"].to_numpy() & np.where(need, beat, True)
    return c


def load_cells(results: Path) -> pd.DataFrame:
    parts = [pd.read_parquet(p) for p in sorted(results.glob("cells_*.parquet"))]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--bh-basis", choices=["confirm", "choose"], default="confirm")
    ap.add_argument("--house", action="store_true", help="the house standard of §6.7")
    ap.add_argument("--house5", action="store_true",
                    help="section 9: the house standard with bands and 200 placebo runs")
    a = ap.parse_args()
    cells = load_cells(a.results)
    if a.house5:
        h = house_verdict_bands(cells)
        h.drop(columns=["placebo_rois"]).to_parquet(a.results / "verdict_house5.parquet")
        reg = ~h["family"].astype(str).str.startswith(CONTROL_PREFIX)
        for name, x in (("registered", h[reg]), ("with the control", h)):
            print(f"{name}: {len(x)} cells; {int(x['house5_passes'].sum())} pass section 9's bars "
                  f"({int(x['credited'].sum())} credited); {int(x['h2_ci95'].sum())} clear the 95% "
                  f"interval alone (about {0.025 * len(x):.2f} expected by chance before correlation)")
        print(h.groupby("family")[FIFTH_BARS + ["house5_passes", "credited"]].sum())
        return
    if a.house:
        h = house_verdict(cells)
        h.drop(columns=["placebo_rois"]).to_parquet(a.results / "verdict_house.parquet")
        print(f"{len(h)} cells; {int(h['house_passes'].sum())} pass the house standard; "
              f"{int(h['h2_ci95'].sum())} clear the 95% interval alone "
              f"(about {0.025 * len(h):.1f} expected by chance before correlation)")
        print(h.groupby("family")[HOUSE_BARS + ["house_passes"]].sum())
        return
    v = verdict(cells, a.bh_basis)
    v.drop(columns=["placebo_rois"]).to_parquet(a.results / f"verdict_{a.bh_basis}.parquet")
    print(f"{len(v)} cells; {int(v['passes'].sum())} pass (BH basis {a.bh_basis}, m = {v['bh_m'].iloc[0]})")
    print(v.groupby("family")[["bar5", "bar6", "bar7", "bar8", "bar9", "bar10", "bar11",
                               "confirm", "bh", "passes"]].sum())


if __name__ == "__main__":
    main()
