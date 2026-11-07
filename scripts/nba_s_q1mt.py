"""NBA search: the first-quarter moneyline on the cover-record step, the first-quarter total on the shooting-luck gap.

docs/nba_search_q1mt.md registers every choice, committed BEFORE this lab and before any bet in the search was graded.
12 cells (asserted):
  M  the eighth search's L5to10 step (scripts.nba_game8_q1_trends.signals, the rule nba_q1_trend bets on the
     spread), its hot team bet on the FIRST-QUARTER MONEYLINE: check none / the spread check x k >= 2 / 4 (4 cells).
  T  the shooting-luck gap (scripts.nba_game2_luck.f4_projections' gap_total, unscaled, the fourth search's P3_F4
     number for the first-half total) on the FIRST-QUARTER TOTAL: over, under x gap >= 1 / 2 / 3 / 4 (8 cells).
Data, decision point D, the deciding books, pricing and settlement are the eighth search's (scripts.nba_game8_q1_trends
.prepare). Placebo: 200 runs each (M: the trend inputs moved within date; T: the gap shuffled within date).

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_q1mt --counts
    NBA_RESEARCH_CACHE=<cache> NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<dir> NBA_GAME2_BETS=<dir>/bets \\
        PYTHONPATH=. python -m scripts.nba_s_q1mt --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <dir> --house5
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
from scripts import nba_game2_luck as L  # noqa: E402
from scripts import nba_game4_p3 as P3  # noqa: E402
from scripts import nba_game5 as G5  # noqa: E402
from scripts import nba_game8_q1_trends as G8  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

FAM_M, FAM_T, CTL_M = "Q1M", "Q1L", "control_Q1M_fade"
ML, TOTAL = "h2h_q1", "totals_q1"
WINDOW = G8.STEP
M_CHECKS = ("none", "spread")
M_CUTS, M_FLOOR = G8.STEP_CUTS, G8.STEP_FLOOR             # (2, 4), 0
T_CUTS, T_FLOOR = (1.0, 2.0, 3.0, 4.0), 0.0                # the fourth search's F4_CUTS
N_PLACEBO = 200
SEEDS = tuple(range(1, N_PLACEBO + 1))
EXPECTED_CELLS = {FAM_M: 4, FAM_T: 8}
GO_ENV, RESULTS_ENV, BETS_ENV = "NBA_GAME2_GO", "NBA_GAME2_RESULTS", "NBA_GAME2_BETS"


def ml_cand(neutral_m: pd.DataFrame, sig: pd.DataFrame, check: str, fade: bool = False) -> pd.DataFrame:
    """Market-fair first-quarter moneyline offers on games with a step pick (and, under the check, passing it),
    carrying k as strength and the hot (or, fading, the cold) team's REAL side as side_pick: the eighth search's
    spread_cand on the moneyline."""
    pick = sig[f"pick_{WINDOW}"].to_numpy(object)
    pick = np.where(pd.Series(pick).isin(["home", "away"]), pick, None).astype(object)
    if fade:
        pick = np.where(pick == "home", "away", np.where(pick == "away", "home", None)).astype(object)
    keep = (pick != None) & np.isfinite(sig[f"k_{WINDOW}"].to_numpy(float))  # noqa: E711
    if check == "spread":
        keep &= sig[f"chk_{WINDOW}"].to_numpy(bool)
    s = pd.DataFrame({"game_id": sig["game_id"].to_numpy()[keep], "market": ML,
                      "strength": sig[f"k_{WINDOW}"].to_numpy(float)[keep], "side_pick": pick[keep]})
    base = neutral_m.drop(columns=[c for c in ("strength", "side_pick") if c in neutral_m])
    return base.merge(s, on=["game_id", "market"], how="inner")


def t_signal(proj: pd.DataFrame) -> pd.DataFrame:
    """(game_id, market, strength) toward the over: the full-game total gap, unscaled (P3.f4_signal's first-half
    number, on the first-quarter total)."""
    s = proj[["game_id"]].assign(market=TOTAL, strength=proj["gap_total"].to_numpy(float))
    return s[np.isfinite(s["strength"].to_numpy(float))].reset_index(drop=True)


def _bands(rows: list[dict], cand: pd.DataFrame, cuts, floor: float, games: pd.DataFrame) -> list[dict]:
    for r in rows:
        bounds = G5.band_bounds(cuts, r["cut_index"], lowest=floor)
        pool = tuple(int(s) for s in str(r["pool_seasons"]).split(",") if s)
        r.update(G5.band_columns(cand, r["side"], "strength", bounds, games, pool))
    return rows


def prepare(cache: Path, require: bool = True) -> dict:
    """Every frame the cells read (no grade): the eighth search's prepare, plus the first-quarter moneyline offers and
    the shooting-luck gap."""
    t0 = time.time()
    prep = G8.prepare(cache, require)
    vis = prep["vis"]
    prep["neutral_m"] = P3.neutral_offers(vis[vis["market"] == ML], {})
    prep["neutral_t"] = prep["neutral"][prep["neutral"]["market"] == TOTAL].reset_index(drop=True)
    data = H.load(cache, seasons=P3.FULL_GAME_SEASONS, require_seasons=P3.FULL_GAME_SEASONS if require else None)
    graded_games = data.games[data.games["season"].isin(prep["graded"])]
    box, _ = L._load_box(cache)
    proj = L.f4_projections(graded_games, L.team_box(box, data.games))
    prep["t_sig"] = t_signal(proj).merge(prep["neutral_t"][["game_id", "market"]].drop_duplicates(),
                                         on=["game_id", "market"])
    prep["choose"] = P3.choosing(prep["graded"])
    prep["seconds"] = round(time.time() - t0, 1)
    return prep


def emit_m(prep: dict, n_placebo: int = N_PLACEBO) -> tuple[list[dict], list[dict]]:
    nm, sig, dd = prep["neutral_m"], prep["sig"], prep["dd"]
    plc = G8.placebo_signals(prep["inp"], prep["numbers"], SEEDS[:n_placebo]) if n_placebo else None
    rows, ctl = [], []
    for check in M_CHECKS:
        cand = ml_cand(nm, sig, check)
        lazy = G5.LazyFrames(plc, lambda s, c=check: ml_cand(nm, s, c)) if plc else None
        r = H.run_cells(dd, FAM_M, G8.POINT, cand, cand, list(M_CUTS), {ML: [G8.SIDE_HOT]}, placebo=lazy,
                        strength="strength", choose_seasons=prep["choose"], times=prep["times"])
        for x in _bands(r, cand, M_CUTS, M_FLOOR, dd.games):
            x.update({"axis_window": WINDOW, "axis_check": check,
                      "signal_meaning": "the cover-record step's hot team on the first-quarter moneyline"})
        rows += r
        if check == "none":
            fade = ml_cand(nm, sig, check, fade=True)
            c = H.run_cells(dd, CTL_M, G8.POINT, fade, fade, list(M_CUTS), {ML: [G8.SIDE_COLD]}, placebo=None,
                            strength="strength", choose_seasons=prep["choose"], times=prep["times"])
            for x in c:
                x.update({"axis_window": WINDOW, "axis_check": check, "signal_meaning": "control: the cold team"})
            ctl += c
    assert len(rows) == EXPECTED_CELLS[FAM_M], len(rows)
    return rows, ctl


def emit_t(prep: dict, n_placebo: int = N_PLACEBO) -> list[dict]:
    nt, sig, dd = prep["neutral_t"], prep["t_sig"], prep["dd"]
    cand = L.side_strength(nt, sig)
    placebo = ([L.side_strength(nt, sh) for sh in P3.shuffled(sig[["game_id", "market", "strength"]], dd.games,
                                                               n_placebo)] if n_placebo else None)
    rows = H.run_cells(dd, FAM_T, G8.POINT, cand, nt, list(T_CUTS), {TOTAL: ["over", "under"]}, placebo=placebo,
                       strength="strength", choose_seasons=prep["choose"], times=prep["times"])
    for x in _bands(rows, cand, T_CUTS, T_FLOOR, dd.games):
        x["signal_meaning"] = "the full-game shooting-luck gap, unscaled, on the first-quarter total"
    assert len(rows) == EXPECTED_CELLS[FAM_T], len(rows)
    return rows


def counts(prep: dict) -> dict:
    """The bets each cell would place, counted and never graded."""
    out = {"seconds": prep["seconds"], "graded": list(prep["graded"]), "choose": list(prep["choose"]),
           "ml_offers": int(len(prep["neutral_m"])), "ml_games": int(prep["neutral_m"]["game_id"].nunique()),
           "total_offers": int(len(prep["neutral_t"])), "gap_games": int(prep["t_sig"]["game_id"].nunique())}
    season = prep["dd"].games.drop_duplicates("game_id").set_index("game_id")["season"]
    cells = []
    for check in M_CHECKS:
        cand = ml_cand(prep["neutral_m"], prep["sig"], check)
        for cut in M_CUTS:
            b = H.choose(cand[cand["strength"] >= cut], -np.inf, sides=[G8.SIDE_HOT])
            px = b["price"].to_numpy(float) if len(b) else np.array([np.nan])
            cells.append({"family": FAM_M, "check": check, "cut": cut, "bets": int(len(b)),
                          "by_season": b["game_id"].map(season).value_counts().sort_index().to_dict(),
                          "price_min": float(np.nanmin(px)), "price_median": float(np.nanmedian(px)),
                          "price_max": float(np.nanmax(px))})
    cand_t = L.side_strength(prep["neutral_t"], prep["t_sig"])
    for side in ("over", "under"):
        for cut in T_CUTS:
            b = H.choose(cand_t[cand_t["strength"] >= cut], -np.inf, sides=[side])
            px = b["price"].to_numpy(float) if len(b) else np.array([np.nan])
            cells.append({"family": FAM_T, "side": side, "cut": cut, "bets": int(len(b)),
                          "by_season": b["game_id"].map(season).value_counts().sort_index().to_dict(),
                          "price_min": float(np.nanmin(px)), "price_median": float(np.nanmedian(px)),
                          "price_max": float(np.nanmax(px))})
    out["cells"] = cells
    return out


def full(cache: Path = H.CACHE) -> None:
    why = [f"{v} is not set" for v in (RESULTS_ENV, BETS_ENV) if not os.environ.get(v)]
    if os.environ.get(GO_ENV) != "1":
        why.append(f"{GO_ENV}=1 is not set")
    if why:
        for w in why:
            print("REFUSED:", w)
        raise SystemExit(2)
    out = Path(os.environ[RESULTS_ENV])
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    prep = prepare(cache, True)
    print(f"prepared in {prep['seconds']}s", flush=True)
    rows_m, ctl_m = emit_m(prep)
    print(f"family M in {time.time() - t0:.0f}s", flush=True)
    rows_t = emit_t(prep)
    print(f"family T in {time.time() - t0:.0f}s", flush=True)
    for name, rr in ((FAM_M, rows_m), (CTL_M, ctl_m), (FAM_T, rows_t)):
        L.write_cells(rr, out / f"cells_{name}.parquet")
    print(f"cells written to {out}: {len(rows_m) + len(rows_t)} registered, {len(ctl_m)} control", flush=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--counts", action="store_true")
    g.add_argument("--full", action="store_true")
    a = ap.parse_args(argv)
    if a.counts:
        print(json.dumps(counts(prepare(H.CACHE, True)), indent=1, default=str))
    else:
        full(H.CACHE)


if __name__ == "__main__":
    main()
