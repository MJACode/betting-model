"""NBA search: first-quarter and first-half team totals priced at Pinnacle's own period spread and total.

docs/nba_search_q1pin.md registers every choice, committed BEFORE this lab and before any bet in the search was
graded. Everything is the team-totals search's (scripts/nba_s_q1tt.py), imported unchanged, but the reference: each
deciding book's team-total offer is priced at the team's period points implied by Pinnacle's own coherent period spread
and total in the same fetch (home = (total centre + home margin centre) / 2), through the team-totals search's period
pricing and result shape. 12 cells (asserted): first quarter, first half x over, under x EV >= 0.02 / 0.04 / 0.06.

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_q1pin --counts
    NBA_RESEARCH_CACHE=<cache> NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<dir> NBA_GAME2_BETS=<dir>/bets \\
        PYTHONPATH=. python -m scripts.nba_s_q1pin --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <dir> --house5
    PYTHONPATH=. python -m scripts.nba_s_q1pin --judge --results <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_s_q1tt as T  # noqa: E402

H, L, P = T.H, T.L, T.P
FAM = "A_pinnacle"
SHARP = "pinnacle"
EXPECTED_CELLS = 12
T.REFERENCE[FAM] = "pinnacle"
MEANING = ("each team-total offer priced at the team's period points implied by Pinnacle's own period spread and "
           "total in the same fetch")


def pinnacle_numbers(vis_ref_p: pd.DataFrame, pricing: dict, period: str) -> pd.DataFrame:
    """(game_id, team, mu): the period points implied by Pinnacle's own coherent spread and total centres. A game
    with no Pinnacle spread or no Pinnacle total has no row."""
    cent = T.quote_centres(vis_ref_p, pricing, books=(SHARP,))
    _, pin = T.implied_numbers(cent, period)
    return pin


def add_pinnacle(prep: dict) -> dict:
    for p in T.PERIODS:
        pp = prep["periods"][p]
        pin = pinnacle_numbers(prep["vis_ref"][p], prep["pricing"], p)
        pp["pin"] = pin
        pp["cands"][FAM] = T.price_offers(pp["off"], pin, T.a_keys(FAM), prep["shapes"], p)
    return prep


def emit(prep: dict, n_placebo: int, say=None, tag=None) -> list[dict]:
    rows = []
    for p in T.PERIODS:
        before = tag() if tag else None
        r, _ = T.emit_a(prep, FAM, p, n_placebo, say)
        for x in r:
            x["signal_meaning"] = MEANING
        rows += r
        if tag:
            tag(p, before)
    assert len(rows) == EXPECTED_CELLS, len(rows)
    return rows


def synthetic_checks(n_placebo: int = 2) -> dict:
    """The team-totals search's synthetic world through this family: 12 cells reach run_cells, both periods bet,
    every cell carries its placebo runs. No bet file is written (NBA_GAME2_BETS is unset while it runs)."""
    H.check()
    saved = os.environ.pop(T.BETS_ENV, None)
    try:
        prep = add_pinnacle(T.synthetic_prep())
        rows = emit(prep, n_placebo)
    finally:
        if saved is not None:
            os.environ[T.BETS_ENV] = saved
    t = pd.DataFrame(rows)
    assert set(t.family) == {FAM}
    assert (t.groupby("period")["pool_n"].max() > 0).all(), "a period placed no bet"
    assert all(len(r["placebo_rois"]) == n_placebo for r in rows)
    return {"synthetic_checks": "pass", "cells": int(len(t))}


def counts(prep: dict) -> dict:
    """Counts only, no result read: games with a Pinnacle number, offers priced, the disagreement with the team-total
    market's own fair centre, and the bets each cell would place by season."""
    out = {}
    for p in T.PERIODS:
        pp = prep["periods"][p]
        cand = pp["cands"][FAM]
        cen = pp["centres"]
        fair = cen[cen.book == "*"][["game_id", "team", "mu_tt"]]
        d = pp["pin"].merge(fair, on=["game_id", "team"])
        gap = (d["mu"] - d["mu_tt"]).to_numpy(float)
        cells = []
        for side in T.A_SIDES:
            for cut in T.EV_CUTS:
                b = H.choose(cand, cut, sides=[side])
                px = b.price.to_numpy(float) if len(b) else np.array([np.nan])
                cells.append({"side": side, "cut": cut, "bets": int(len(b)),
                              "by_season": b.season.value_counts().sort_index().to_dict() if len(b) else {},
                              "price_min": float(np.nanmin(px)), "price_median": float(np.nanmedian(px)),
                              "price_max": float(np.nanmax(px))})
        out[p] = {"games_with_pinnacle_number": int(pp["pin"].game_id.nunique()),
                  "games_with_offers": int(pp["off"].game_id.nunique()),
                  "offers_priced": int(len(cand)),
                  "disagreement_abs_quantiles": np.nanquantile(np.abs(gap), [0.5, 0.75, 0.9, 0.95, 0.99]).round(3).tolist()
                  if len(gap) else [],
                  "disagreement_mean": float(np.nanmean(gap)) if len(gap) else None,
                  "cells": cells}
    return out


def full(cache: Path = H.CACHE, out: Path | None = None) -> None:
    scratch = T.scratch_dir()
    why = T.refuse_full(cache, scratch)
    if why:
        P.refuse(why)
    out = Path(os.environ[T.RESULTS_ENV]) if out is None else out
    t0 = time.time()
    T.synthetic_checks()
    synthetic_checks()
    prep = add_pinnacle(T.prepare(cache, True, scratch))
    bets_dir = Path(os.environ[T.BETS_ENV])

    def tag(p=None, before=None):
        if p is None:
            return set(bets_dir.glob("*.parquet")) if bets_dir.exists() else set()
        T.tag_bets(bets_dir, FAM, T.A_LABEL[p], p, before)
    rows = emit(prep, T.N_PLACEBO, T.log, tag)
    out.mkdir(parents=True, exist_ok=True)
    L.write_cells(rows, out / f"cells_{FAM}.parquet")
    for p in T.PERIODS:
        prep["periods"][p]["pin"].assign(period=p).to_parquet(out / f"implied_pinnacle_{p}.parquet")
    T.log(f"cells written to {out}: {len(rows)}; {(time.time() - t0) / 60.0:.1f} minutes")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--counts", action="store_true", help="synthetic checks, then counts on the real data, no grade")
    g.add_argument("--full", action="store_true", help="the graded run (needs the three variables)")
    g.add_argument("--judge", action="store_true", help="the bars plus both seasons positive, on a graded run")
    ap.add_argument("--results", type=Path)
    a = ap.parse_args(argv)
    if a.counts:
        print(json.dumps(synthetic_checks()))
        prep = add_pinnacle(T.prepare(H.CACHE, True, T.scratch_dir()))
        print(json.dumps(counts(prep), indent=1, default=str))
    elif a.full:
        full(H.CACHE)
    else:
        if a.results is None:
            ap.error("--judge needs --results")
        T.judge(a.results)


if __name__ == "__main__":
    main()
