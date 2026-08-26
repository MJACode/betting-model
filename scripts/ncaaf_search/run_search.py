"""
NCAAF search -- leaderboard driver.

Runs the spec's deliverables 1-3 over a prebuilt matrix:
  1. leaderboard across model family x feature-group x era-handling
  2. per-season breakdown for the top candidates
  3. add-one-group-in ablation over the market-only baseline

Everything routes through the same `walk_forward`, so families are directly
comparable. The market-only sanity gate runs FIRST and the driver refuses to
report anything if it fails -- a leaking harness makes every other number
meaningless.

Run:
    python -m scripts.ncaaf_search.run_search --matrix <parquet> --label home_covers
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
    FEATURE_GROUPS, GROUP_ORDER, MARKET_ONLY, features_for)
from scripts.ncaaf_search.validate import (  # noqa: E402
    walk_forward, market_only_sanity, BREAKEVEN)
from scripts.ncaaf_search.models import (  # noqa: E402
    make_logreg, make_xgb, make_lgbm, make_ensemble,
    exponential_recency_weights)

TEST_SEASONS = [2022, 2023, 2024, 2025]
REPORT_THRESHOLD = 0.03


def _families(season_col):
    """Model families. Deliberately shallow/regularised -- ~800 games a season."""
    lr = make_logreg(C=0.05, l1_ratio=0.5, calibration="platt", season_col=season_col)
    xg = make_xgb(calibration="raw", season_col=season_col)
    lg = make_lgbm(calibration="raw", season_col=season_col)
    return {
        "logreg_en_platt": lr,
        "xgb_d3": xg,
        "xgb_d3_iso": make_xgb(calibration="isotonic", season_col=season_col),
        "lgbm_d3": lg,
        "ens_logit(xgb,lgbm,lr)": make_ensemble([xg, lg, lr], mode="logit"),
    }


def _summarise(res: dict, name: str, cols: list[str]) -> dict:
    p = res["pooled"]
    if not p:
        return {"config": name, "n_feat": len(cols)}
    sw = {r["threshold"]: r for r in p["sweep"]}
    a = sw.get(REPORT_THRESHOLD, {})
    per = " ".join(
        f"{f.season}:{[x for x in f.sweep if x['threshold'] == REPORT_THRESHOLD][0]['bets']}"
        for f in res["folds"])
    return {
        "config": name,
        "n_feat": len(cols),
        "log_loss": round(p["log_loss"], 5),
        "brier": round(p["brier"], 5),
        "ece": round(p["ece"], 4),
        "bets": a.get("bets"),
        "win_rate": round(a["win_rate"], 4) if a.get("bets") else np.nan,
        "roi_flat": round(a["roi_flat"], 4) if a.get("bets") else np.nan,
        "roi_kelly": round(a["roi_kelly"], 4) if a.get("bets") else np.nan,
        "ci_lo": round(a["ci_lo"], 4) if a.get("bets") else np.nan,
        "clv": round(p["clv"]["beat_close_pct"], 3) if p["clv"]["n"] else np.nan,
        "consistent": p["consistent"],
        "leak_suspect": p["leak_suspect"],
        "bets_per_season": per,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--matrix", required=True)
    ap.add_argument("--label", default="home_covers",
                    choices=["home_covers", "went_over"])
    ap.add_argument("--portal-only", action="store_true",
                    help="restrict to 2021+ (single-provider, opener-covered)")
    a = ap.parse_args()

    m = pd.read_parquet(a.matrix)
    if a.portal_only:
        m = m[m["season"] >= 2021].copy()
    season_col = m["season"]
    ALL = [c for c in dict.fromkeys(features_for(GROUP_ORDER) + MARKET_ONLY)
           if c in m.columns]
    CLEAN = ALL

    bar = "=" * 100
    print(bar)
    print(f"NCAAF SEARCH -- label={a.label}  seasons={sorted(m.season.unique())}")
    print(f"breakeven={BREAKEVEN:.4f}  ln2=0.69315  report threshold={REPORT_THRESHOLD}")
    print(bar)

    # ── gate ────────────────────────────────────────────────────────────────
    sanity = market_only_sanity(m, a.label, TEST_SEASONS)
    print(f"\nMARKET-ONLY SANITY: win_rate={sanity['win_rate_at_zero_threshold']:.4f} "
          f"(n={sanity['n']})  ->  {sanity['verdict']}")
    if not sanity["passes"]:
        print("\nABORTING: harness sanity gate failed.")
        return 1

    # ── 1. leaderboard ──────────────────────────────────────────────────────
    rows = []
    for fname, fp in _families(season_col).items():
        rows.append(_summarise(walk_forward(m, ALL, a.label, fp, TEST_SEASONS),
                               f"{fname} | ALL", ALL))
    # era handling (spec item 4a): full sample + exponential recency weighting
    rows.append(_summarise(
        walk_forward(m, ALL, a.label, make_xgb(calibration="raw", season_col=season_col),
                     TEST_SEASONS, sample_weight_fn=exponential_recency_weights(3.0)),
        "xgb_d3 | ALL | recency-wt", ALL))

    lb = pd.DataFrame(rows).sort_values("log_loss")
    print(f"\n{bar}\n1. LEADERBOARD (sorted by pooled walk-forward log loss)\n{bar}")
    print(lb.to_string(index=False))

    # ── 3. ablation ─────────────────────────────────────────────────────────
    ab = [_summarise(walk_forward(m, MARKET_ONLY, a.label,
                                  make_xgb(calibration="raw", season_col=season_col),
                                  TEST_SEASONS), "market_only", MARKET_ONLY)]
    for g in GROUP_ORDER:
        cols = MARKET_ONLY + [c for c in FEATURE_GROUPS[g]
                              if c not in MARKET_ONLY and c in m.columns]
        ab.append(_summarise(
            walk_forward(m, cols, a.label,
                         make_xgb(calibration="raw", season_col=season_col),
                         TEST_SEASONS), f"market+{g}", cols))
    abdf = pd.DataFrame(ab)
    base = abdf.iloc[0]["log_loss"]
    abdf["delta_logloss"] = (abdf["log_loss"] - base).round(5)
    print(f"\n{bar}\n3. ADD-ONE-GROUP-IN ABLATION (XGB d3; negative delta = helps)\n{bar}")
    print(abdf[["config", "n_feat", "log_loss", "delta_logloss", "bets",
                "win_rate", "roi_flat", "clv"]].to_string(index=False))

    # ── verdict ─────────────────────────────────────────────────────────────
    # The kill line is an ROI number, but the spec ranks CONSISTENCY above ROI
    # ("prefer +2% in all four seasons over +8% in one"), and CLV is the one
    # check that does not depend on where thresholds are cut. Reporting the ROI
    # test alone printed "2 configs cleared" for candidates whose confidence
    # intervals sat below breakeven, whose CLV was 0.44, and which placed zero
    # bets in half the test seasons. So every gate is applied here.
    print(chr(10) + bar + chr(10) + "VERDICT" + chr(10) + bar)

    def _gates(r) -> tuple[bool, list[str]]:
        fails = []
        if not (r["bets"] and r["bets"] >= 150):
            fails.append("volume<150")
        if not (r["roi_flat"] and r["roi_flat"] >= 0.03):
            fails.append("roi<3%")
        if not (r["ci_lo"] and r["ci_lo"] > BREAKEVEN):
            fails.append(f"ci_lo<={BREAKEVEN:.4f}")
        if not (r["clv"] and r["clv"] > 0.50):
            fails.append("clv<=0.500")
        seasons_bet = sum(1 for tok in str(r["bets_per_season"]).split()
                          if tok.split(":")[-1] not in ("0", "nan"))
        if seasons_bet < 3:
            fails.append(f"bets in only {seasons_bet}/4 seasons")
        return (not fails), fails

    survivors = []
    for _, r in lb.iterrows():
        if r.get("bets") is None or (isinstance(r.get("bets"), float) and np.isnan(r["bets"])):
            continue
        ok, fails = _gates(r)
        mark = "PASS" if ok else "fail: " + ", ".join(fails)
        print(f"  {r['config']:32s} roi={r['roi_flat'] if r['roi_flat'] == r['roi_flat'] else float('nan'):+.4f} "
              f"bets={int(r['bets'] or 0):4d}  {mark}")
        if ok:
            survivors.append(r["config"])

    print()
    if survivors:
        print(f"{len(survivors)} config(s) clear EVERY gate: {survivors}")
        print("Treat as a candidate, not a result: confirm on a fresh season "
              "before risking money.")
    else:
        print("No configuration clears every gate. The spec's kill criterion "
              "is NOT honestly met.")
        print("Note: a config can clear the raw +3% ROI test and still fail "
              "here on CI, CLV, or season coverage -- that combination is the "
              "signature of noise, not edge.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
