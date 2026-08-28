"""
NCAAF line-movement spot scan: does the open->close move predict beyond
the close?

THE QUESTION
------------
Steam chasing ("follow the move") and buy-back ("fade the move") are the two
oldest line-movement strategies. Both are claims that the CLOSING line is
wrong in a direction the movement reveals: follow says the close under-adjusts
(momentum), fade says it overshoots. Efficient-market theory says both are
null -- the close subsumes the path that produced it. The D_market group
ablation already hinted null when `line_move` was fed to a classifier as a
feature; this is the direct, threshold-level test of the same information as a
standalone rule, graded at the close.

The two directions are exact complements (fade win% = 1 - follow win%, pushes
dropped), so this is ONE family of tests per market, reported from the follow
side; a strongly negative follow IS the fade signal.

DATA
----
The Bovada opener cache (scripts/ncaaf_search/openers.py): the single provider
with continuous open+close coverage, 2021-2025, ~860 games/season. One book's
open to the SAME book's close -- no cross-book contamination, unlike the
cross-book opener rule, which is a different (already shipped) signal.

METHOD (house rules)
--------------------
Definitions fixed before results; variant count reported; per-season records;
Wilson CI vs the -110 breakeven; time split early (2021-2023) vs late
(2024-2025) must BOTH be above breakeven for a rule to be believed.

Run:
    python -m scripts.ncaaf_search.line_move_spots
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

BREAKEVEN = 0.5238
MIN_BETS = 60
EARLY = (2021, 2023)
LATE = (2024, 2025)
CACHE = (Path(__file__).parent.parent.parent / "data" / "raw" / "datawarehouse"
         / "ncaaf" / "lines_cache" / "openers_bovada.parquet")


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load() -> pd.DataFrame:
    df = pd.read_parquet(CACHE)
    for c in ("spread_open", "spread_close", "total_open", "total_close",
              "home_score", "away_score"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["home_score"].notna() & df["away_score"].notna()].copy()
    df["margin"] = df["home_score"] - df["away_score"]
    df["total"] = df["home_score"] + df["away_score"]

    # CFBD spread is the HOME handicap (negative = home favoured). A negative
    # move means the home number got MORE negative: the market moved TOWARD
    # home. Cover at the close: margin + spread_close > 0.
    df["sp_move"] = df["spread_close"] - df["spread_open"]
    df["cover_close"] = df["margin"] + df["spread_close"]
    df["tot_move"] = df["total_close"] - df["total_open"]
    return df


def eval_follow_spread(df: pd.DataFrame, thresh: float) -> dict | None:
    """Bet, at the close, the side the market moved toward. Pushes dropped."""
    s = df[(df["sp_move"].abs() >= thresh) & df["cover_close"].notna()
           & (df["cover_close"] != 0)]
    if len(s) < MIN_BETS:
        return None
    # moved toward home (sp_move < 0) -> follow wins when home covers
    won = ((s["sp_move"] < 0) & (s["cover_close"] > 0)) | \
          ((s["sp_move"] > 0) & (s["cover_close"] < 0))
    return _summ(s, won, f"SPREAD follow |move| >= {thresh:g}")


def eval_follow_total(df: pd.DataFrame, thresh: float) -> dict | None:
    """Line dropped -> under at close; line rose -> over at close."""
    s = df[(df["tot_move"].abs() >= thresh) & df["total_close"].notna()
           & (df["total"] != df["total_close"])]
    if len(s) < MIN_BETS:
        return None
    won = ((s["tot_move"] < 0) & (s["total"] < s["total_close"])) | \
          ((s["tot_move"] > 0) & (s["total"] > s["total_close"]))
    return _summ(s, won, f"TOTAL follow |move| >= {thresh:g}")


def _summ(s: pd.DataFrame, won: pd.Series, name: str) -> dict:
    n = len(s)
    w = int(won.sum())
    wr = w / n
    lo, hi = wilson(w, n)
    per = {int(k): round(float(v.mean()), 3)
           for k, v in won.groupby(s["season"]) if len(v) >= 15}

    def half(a, b):
        m = (s["season"] >= a) & (s["season"] <= b)
        return (float(won[m].mean()), int(m.sum())) if m.sum() >= 30 else (float("nan"), 0)

    e, l = half(*EARLY), half(*LATE)
    return {"spot": name, "bets": n, "win_rate": round(wr, 4),
            "roi": round(wr * (100 / 110) - (1 - wr), 4),
            "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
            "clears": lo > BREAKEVEN,
            "early": (round(e[0], 3), e[1]), "late": (round(l[0], 3), l[1]),
            "both_halves": e[0] > BREAKEVEN and l[0] > BREAKEVEN,
            "seasons_above": sum(1 for v in per.values() if v > BREAKEVEN),
            "seasons": len(per), "per_season": per}


def main() -> int:
    d = load()
    print(f"Bovada open+close games with scores: {len(d)} "
          f"across {d['season'].min()}-{d['season'].max()}")
    print(f"spread moved (any): {(d['sp_move'].abs() > 0).mean():.1%}   "
          f"mean |spread move| {d['sp_move'].abs().mean():.2f}   "
          f"mean |total move| {d['tot_move'].abs().mean():.2f}")

    rows = []
    for t in (0.5, 1.0, 1.5, 2.5):
        rows.append(eval_follow_spread(d, t))
    for t in (1.0, 2.0, 3.0):
        rows.append(eval_follow_total(d, t))
    rows = [r for r in rows if r]
    rows.sort(key=lambda r: -r["win_rate"])

    bar = "=" * 116
    print(f"\n{bar}")
    print("FOLLOW-THE-MOVE AT THE CLOSE (fade = 1 - follow; one family per market)")
    print(f"min {MIN_BETS} bets | {len(rows)} definitions | "
          f"~{len(rows) * 0.05:.1f} clear by chance at 95% | "
          "a follow BELOW 47.6% is a fade signal")
    print(bar)
    print(f"{'Spot':<32} {'N':>6} {'Win%':>7} {'ROI':>8} {'95% CI':>17} "
          f"{'early':>13} {'late':>13} {'Szn>BE':>7}")
    print("-" * 116)
    for r in rows:
        ci = f"[{r['ci_lo']:.1%},{r['ci_hi']:.1%}]"
        e = f"{r['early'][0]:.3f}({r['early'][1]})"
        l = f"{r['late'][0]:.3f}({r['late'][1]})"
        flag = ("  <<< BOTH" if (r["clears"] and r["both_halves"])
                else ("  <<<" if r["clears"]
                      else ("  *" if r["win_rate"] > BREAKEVEN else "")))
        print(f"{r['spot']:<32} {r['bets']:>6} {r['win_rate']:>6.1%} "
              f"{r['roi']:>+7.1%} {ci:>17} {e:>13} {l:>13} "
              f"{r['seasons_above']}/{r['seasons']:<3}{flag}")

    print()
    for r in rows:
        if r["clears"] or (1 - r["win_rate"]) > 0.5238:
            side = "FOLLOW" if r["clears"] else "FADE (mirror)"
            print(f"{side}  {r['spot']}: per-season {r['per_season']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
