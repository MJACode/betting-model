"""
NCAAF search — bet-at-OPEN experiments.

Everything before this bet at the CLOSE, which is the sharpest number the
market produces. This module asks the different question the NFL section-28
opener rule is built on: is the OPENING number beatable?

Two experiments:

  A. model-vs-open   train on strictly-prior information, predict the game,
                     bet the OPENING spread. The closing line is NOT a feature
                     (it is future information relative to the open) -- it is
                     used only to measure CLV afterwards.

  B. cross-book      the section-28 pattern. Where two books' OPENING numbers
                     disagree, bet the side the sharper book favours at the
                     softer book's stale number. Needs two books with openers,
                     which exists for 2023-2025 (Bovada + DraftKings).

CLV is the honest scoreboard for both: betting at the open, a real edge should
see the close move TOWARD the pick. Every close-time experiment we ran had CLV
in the 0.41-0.48 band, i.e. the market moved against us. If the open is
genuinely softer, CLV here should exceed 0.500.

Run:
    python -m scripts.ncaaf_search.opener_strategy --experiment model
    python -m scripts.ncaaf_search.opener_strategy --experiment crossbook
"""

from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
warnings.filterwarnings("ignore")

from scripts.ncaaf_search.features import (  # noqa: E402
    FEATURE_GROUPS, GROUP_ORDER, features_for)
from scripts.ncaaf_search.validate import (  # noqa: E402
    walk_forward, simulate, wilson_ci, BREAKEVEN, DEFAULT_THRESHOLDS)
from scripts.ncaaf_search.models import make_xgb, make_logreg  # noqa: E402
from scripts.ncaaf_search.openers import fetch_season, to_frame  # noqa: E402

MATRIX = ("data/raw/datawarehouse/ncaaf/lines_cache/matrix_fixed.parquet")
TEST_SEASONS = [2023, 2024, 2025]

# Features legal when betting at the OPEN: no closing number, no open->close
# movement (both are future information at bet time).
_ILLEGAL_AT_OPEN = {"close_spread", "close_total", "line_move",
                    "abs_line_move", "total_move"}


def _open_features(m: pd.DataFrame) -> list[str]:
    cols = [c for c in dict.fromkeys(features_for(GROUP_ORDER))
            if c in m.columns and c not in _ILLEGAL_AT_OPEN]
    # the OPENING number is the legitimate market anchor at bet time
    for c in ("spread_open", "total_open", "is_neutral_site"):
        if c in m.columns and c not in cols:
            cols.append(c)
    return cols


def experiment_model(m: pd.DataFrame) -> None:
    """A: model predicts, we bet the opening spread."""
    d = m.dropna(subset=["spread_open", "home_score", "away_score"]).copy()
    d["margin"] = d["home_score"] - d["away_score"]
    ats_open = d["margin"] + d["spread_open"]
    d = d[ats_open != 0].copy()                       # drop pushes
    d["covers_open"] = (d["margin"] + d["spread_open"] > 0).astype(float)

    cols = _open_features(d)
    print(f"rows with an opening spread: {len(d)}  features: {len(cols)}")
    print(f"seasons: {sorted(d.season.unique().tolist())}")
    print(f"base rate (home covers the OPEN): {d['covers_open'].mean():.4f}")

    for name, fp in (
        ("xgb_d3", make_xgb(calibration="raw", season_col=d["season"])),
        ("logreg_en", make_logreg(C=0.05, calibration="platt", season_col=d["season"])),
    ):
        res = walk_forward(d, cols, "covers_open", fp, TEST_SEASONS)
        p = res["pooled"]
        if not p:
            print(f"\n{name}: no folds")
            continue
        print(f"\n--- {name} | bet at OPEN ---")
        print(f"pooled logloss={p['log_loss']:.5f} (ln2=0.69315)  ECE={p['ece']:.4f}")
        sw = pd.DataFrame(p["sweep"])[
            ["threshold", "bets", "wins", "win_rate", "roi_flat", "ci_lo", "ci_hi"]]
        print(sw.round(4).to_string(index=False))
        for f in res["folds"]:
            r = [x for x in f.sweep if x["threshold"] == 0.03][0]
            wr = r["win_rate"] if r["bets"] else float("nan")
            print(f"  {f.season}: bets={r['bets']:4d} wr={wr:.4f}")
        c = p["clv"]
        if c["n"]:
            print(f"  CLV vs close: beat={c['beat_close_pct']:.3f} "
                  f"avg_move={c['avg_move_captured']:+.3f} (>0.500 = open was soft)")


def _load_cross_book(seasons: list[int]) -> pd.DataFrame:
    """One row per game with BOTH books' opening spreads."""
    frames = [to_frame(fetch_season(s)) for s in seasons]
    df = pd.concat(frames, ignore_index=True)
    df = df[df["provider"].isin(["Bovada", "DraftKings"])]
    df = df.dropna(subset=["spread_open"])
    key = ["season", "home_team", "away_team", "home_score", "away_score"]
    piv = df.pivot_table(index=key, columns="provider",
                         values=["spread_open", "spread_close"], aggfunc="first")
    piv.columns = [f"{a}_{b}" for a, b in piv.columns]
    piv = piv.reset_index().dropna(
        subset=["spread_open_Bovada", "spread_open_DraftKings"])
    piv["margin"] = piv["home_score"] - piv["away_score"]
    return piv


def experiment_crossbook(seasons: list[int]) -> None:
    """
    B: section-28 opener pattern.

    dev = soft_open - sharp_open (both HOME-relative). Bet the side the SHARP
    book favours, at the SOFT book's number. There is no Pinnacle here, so we
    run BOTH assignments rather than assuming which book is sharp -- if the
    edge is real it should appear in one direction and not the other, and a
    result that shows up in both directions is a red flag, not a doubling.
    """
    df = _load_cross_book(seasons)
    print(f"games with BOTH books' openers: {len(df)} "
          f"({sorted(df.season.unique().tolist())})")
    if df.empty:
        return

    for sharp, soft in (("DraftKings", "Bovada"), ("Bovada", "DraftKings")):
        so, sh = f"spread_open_{soft}", f"spread_open_{sharp}"
        d = df.copy()
        d["dev"] = d[so] - d[sh]
        print(f"\n=== sharp={sharp}  soft={soft} ===")
        print(f"  |dev| mean={d['dev'].abs().mean():.2f}  "
              f"identical={(d['dev'] == 0).mean():.1%}  "
              f">=1pt={(d['dev'].abs() >= 1).mean():.1%}")

        rows = []
        for thr in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0):
            q = d[d["dev"].abs() >= thr].copy()
            if q.empty:
                continue
            # dev > 0 : soft's home number is HIGHER (more generous to home)
            # than sharp's, so sharp implicitly favours HOME -> bet home at soft
            q["pick_home"] = q["dev"] > 0
            ats = q["margin"] + q[so]
            q = q[ats != 0]
            if q.empty:
                continue
            won = np.where(q["pick_home"], (q["margin"] + q[so]) > 0,
                           (q["margin"] + q[so]) < 0)
            n, w = len(q), int(won.sum())
            wr = w / n
            roi = wr * (100 / 110) - (1 - wr)
            lo, hi = wilson_ci(w, n)
            rows.append({"min_dev": thr, "bets": n, "wins": w,
                         "win_rate": round(wr, 4), "roi": round(roi, 4),
                         "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
                         "clears": lo > BREAKEVEN})
        if rows:
            print(pd.DataFrame(rows).to_string(index=False))
            good = [r for r in rows if r["clears"] and r["bets"] >= 100]
            print(f"  -> cells clearing breakeven at 95% with >=100 bets: {len(good)}")


def experiment_bands(seasons: list[int]) -> None:
    """
    DISJOINT deviation bands, not cumulative gates.

    A tighter gate is a strict SUBSET of a looser one: every |dev| >= 2.5 game
    is already inside |dev| >= 1.0. Shipping both as separate models would fire
    two picks on the SAME side of the SAME game -- double staking dressed up as
    diversification, and two rows in the app for one bet.

    The honest way to offer a high-conviction tier is to split the range into
    bands that do not overlap, so every qualifying game produces exactly one
    pick. That is only viable if the REMAINDER band (the games the premium tier
    gives up) still stands on its own -- otherwise the tighter gate should
    REPLACE the looser one rather than supplement it. This prints both.
    """
    df = _load_cross_book(seasons)
    sharp, soft = "Bovada", "DraftKings"          # the shipped assignment
    so, sh = f"spread_open_{soft}", f"spread_open_{sharp}"
    d = df.copy()
    d["dev"] = d[so] - d[sh]
    d["pick_home"] = d["dev"] > 0
    d["ats"] = d["margin"] + d[so]
    d = d[d["ats"] != 0]
    d["won"] = np.where(d["pick_home"], d["ats"] > 0, d["ats"] < 0)

    bands = [(1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 99.0),
             (1.0, 2.5), (2.5, 99.0), (1.0, 99.0)]
    print("")
    print(f"=== DISJOINT BANDS (sharp={sharp}, soft={soft}) ===")
    print(f"{'band':>14} {'bets':>6} {'wins':>6} {'win%':>7} {'ROI':>8} "
          f"{'95% CI':>17} {'per-season':>40}")
    for lo_b, hi_b in bands:
        q = d[(d["dev"].abs() >= lo_b) & (d["dev"].abs() < hi_b)]
        n = len(q)
        if n < 40:
            continue
        w = int(q["won"].sum())
        wr = w / n
        roi = wr * (100 / 110) - (1 - wr)
        lo, hi = wilson_ci(w, n)
        per = {int(k): round(float(v.mean()), 3)
               for k, v in q.groupby("season")["won"] if len(v) >= 20}
        label = (f"[{lo_b:g}, {hi_b:g})" if hi_b < 99 else f"[{lo_b:g}, inf)")
        mark = "  <<<" if lo > BREAKEVEN else ""
        print(f"{label:>14} {n:>6} {w:>6} {wr:>6.1%} {roi:>+7.1%} "
              f"[{lo:.3f},{hi:.3f}]  {str(per):>40}{mark}")
    print("")
    print("  A premium tier is only additive if [1.0, 2.5) survives on its "
          "own; if it does not, tighten the single model instead of adding one.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--experiment", choices=["model", "crossbook", "both", "bands"],
                    default="both")
    a = ap.parse_args()

    bar = "=" * 88
    if a.experiment in ("model", "both"):
        print(bar)
        print("EXPERIMENT A -- model predicts, bet the OPENING spread")
        print(bar)
        experiment_model(pd.read_parquet(MATRIX))

    if a.experiment in ("crossbook", "both"):
        print(f"\n{bar}")
        print("EXPERIMENT B -- cross-book opener disagreement (section-28 pattern)")
        print(bar)
        experiment_crossbook([2023, 2024, 2025])

    if a.experiment == "bands":
        print(bar)
        print("DISJOINT BANDS -- can a high-conviction tier be ADDED, or must "
              "the single gate be tightened?")
        print(bar)
        experiment_bands([2023, 2024, 2025])
    return 0


if __name__ == "__main__":
    sys.exit(main())
