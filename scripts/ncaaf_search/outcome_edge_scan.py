"""
NCAAF outcome x edge scan: the conditional surface of the PRODUCTION models,
across all three markets -- including the first-ever moneyline test.

WHAT IS NEW HERE (vs the closed feature search)
-----------------------------------------------
The feature search asked "can more inputs beat the close" (no). This asks a
different question: given the two regressions we already trust, WHERE in their
own output space does the edge live?

  1. MONEYLINE -- genuinely untested. The margin regression implies a win
     probability (P(home) = P(pred + residual > 0), residuals from a leak-free
     inner split). We hold real Bovada moneyline prices for 2021-2025, so this
     grades at ACTUAL odds -- the only market here where ROI is measured, not
     assumed at -110.
  2. TOTALS -- the live model's conditional record: over-side vs under-side
     disagreements, line level, week of season, and whether the win rate is
     MONOTONE in the disagreement (the signature of real signal vs a lucky
     threshold).
  3. SPREAD -- the margin regression's same surface (side of the pick,
     favorite vs dog, spread size), relevant because it is the displaced
     candidate for a third model slot.

DISCIPLINE (the part that keeps this from being a trend-mining exercise)
------------------------------------------------------------------------
  * expanding-window walk-forward on the PRODUCTION feature engine; test
    seasons 2022-2025; 2020 excluded project-wide.
  * probabilities come from an INNER split (last training season held out of
    the residual fit), so no test-season information touches the ECDF.
  * every bettable cell reports per-season records, the early(2022-23)/
    late(2024-25) halves, and a Wilson CI vs the relevant breakeven.
  * the variant count is printed. Any single cell that clears while its
    MIRROR cell (same rule, opposite side) shows nothing is flagged as a
    likely confound, not an edge -- the session-87 lesson.
  * descriptive surfaces (calibration deciles, monotonicity) are separated
    from bettable-rule tests and carry no pass/fail flags.

Run:
    python -m scripts.ncaaf_search.outcome_edge_scan
"""

from __future__ import annotations

import math
import sys
from bisect import bisect_right
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.ncaaf_margin_eval import (  # noqa: E402
    build_frames, _matrix, _fit, MARGIN_FEATURES, TOTAL_FEATURES)

BREAKEVEN = 0.5238        # -110 two-way markets (spread / total)
TEST_SEASONS = [2022, 2023, 2024, 2025]
ALL_SEASONS = [s for s in range(2015, 2026) if s != 2020]
EARLY, LATE = (2022, 2023), (2024, 2025)
ML_BOOK = "cfbd_bovada"   # the one provider with continuous ML coverage
MIN_BETS = 50


# ── helpers ───────────────────────────────────────────────────────────────────

def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def implied(american: float) -> float:
    a = float(american)
    return (-a) / (-a + 100.0) if a < 0 else 100.0 / (a + 100.0)


def payout(american: float) -> float:
    """Profit on a 1u stake when the bet wins."""
    a = float(american)
    return 100.0 / (-a) if a < 0 else a / 100.0


def ecdf_prob_positive(residuals: list[float], pred: float) -> float:
    """P(pred + resid > 0) from a sorted residual sample, clamped."""
    if not residuals:
        return 0.5
    i = bisect_right(residuals, -pred)
    return min(max((len(residuals) - i) / len(residuals), 0.01), 0.99)


def load_ml_prices() -> dict:
    """{game_id: (home_price, away_price)} from the single continuous book."""
    from data.db import get_connection
    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT o.game_id, o.home_price, o.away_price
            FROM odds o JOIN games g ON g.game_id = o.game_id
            WHERE g.sport = 'NCAAF' AND o.market = 'h2h'
              AND o.bookmaker = %(b)s
              AND o.home_price IS NOT NULL AND o.away_price IS NOT NULL
        """, {"b": ML_BOOK}).fetchall()
    finally:
        conn.close()
    return {r[0]: (float(r[1]), float(r[2])) for r in rows}


# ── walk-forward prediction pass ──────────────────────────────────────────────

def predict_all(df: pd.DataFrame) -> pd.DataFrame:
    """
    One row per test-season game with pred_margin, pred_total, p_home (from
    the inner-split ECDF), plus the market numbers and actuals.
    """
    out = []
    for season in TEST_SEASONS:
        past = [s for s in ALL_SEASONS if s < season]
        inner = max(past)
        train = df[df["_season"].isin(past)]
        hold = df[df["_season"] == season]

        # margin: main fit on the whole window, residuals from the inner split
        tr_m, m_cols = _matrix(train, MARGIN_FEATURES)
        ho_m, _ = _matrix(hold, MARGIN_FEATURES)
        core = tr_m[tr_m["_season"] != inner]
        inn = tr_m[tr_m["_season"] == inner]
        inner_fit = _fit(core[m_cols], core["_margin"])
        resid = sorted(inn["_margin"] - inner_fit.predict(inn[m_cols]))
        main_fit = _fit(tr_m[m_cols], tr_m["_margin"])
        pm = main_fit.predict(ho_m[m_cols])

        # total: main fit only (probabilities not needed for the gate rule)
        tr_t, t_cols = _matrix(train, TOTAL_FEATURES)
        ho_t, _ = _matrix(hold, TOTAL_FEATURES)
        t_fit = _fit(tr_t[t_cols], tr_t["_total"])
        pt = pd.Series(t_fit.predict(ho_t[t_cols]), index=ho_t.index)

        for j, (i, row) in enumerate(ho_m.iterrows()):
            out.append({
                "season": season, "game_id": row["_game_id"],
                "week": row.get("week"),
                "pred_margin": float(pm[j]),
                "p_home": ecdf_prob_positive(resid, float(pm[j])),
                "pred_total": float(pt[i]) if i in pt.index else np.nan,
                "margin": row["_margin"], "total": row["_total"],
                "spread_home": row["_spread_home"],
                "total_line": row["_total_line"],
            })
        print(f"  fold {season}: {len(ho_m)} games "
              f"(inner residuals n={len(resid)}, sd={np.std(resid):.2f})")
    return pd.DataFrame(out)


# ── reporting ─────────────────────────────────────────────────────────────────

def _cell(s: pd.DataFrame, won: pd.Series, name: str,
          stake: pd.Series | None = None, profit: pd.Series | None = None,
          breakeven: float = BREAKEVEN) -> dict | None:
    n = len(s)
    if n < MIN_BETS:
        return None
    w = int(won.sum())
    wr = w / n
    lo, hi = wilson(w, n)
    if profit is not None:
        roi = float(profit.sum()) / float(stake.sum())
    else:
        roi = wr * (100 / 110) - (1 - wr)
    per = {int(k): round(float(v.mean()), 3)
           for k, v in won.groupby(s["season"]) if len(v) >= 12}

    def half(a, b):
        m = (s["season"] >= a) & (s["season"] <= b)
        return (float(won[m].mean()), int(m.sum())) if m.sum() >= 25 else (float("nan"), 0)

    e, l = half(*EARLY), half(*LATE)
    return {"cell": name, "bets": n, "win_rate": round(wr, 4),
            "roi": round(roi, 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
            "clears": lo > breakeven,
            "early": (round(e[0], 3), e[1]), "late": (round(l[0], 3), l[1]),
            "both": e[0] > breakeven and l[0] > breakeven,
            "per_season": per}


def _print_cells(title: str, cells: list[dict | None],
                 breakeven: float = BREAKEVEN) -> None:
    cells = [c for c in cells if c]
    bar = "-" * 112
    print(f"\n{title}   ({len(cells)} cells with >= {MIN_BETS} bets)")
    print(bar)
    print(f"{'Cell':<44} {'N':>5} {'Win%':>7} {'ROI':>8} {'95% CI':>17} "
          f"{'early':>12} {'late':>12}")
    for c in sorted(cells, key=lambda x: -x["win_rate"]):
        ci = f"[{c['ci_lo']:.1%},{c['ci_hi']:.1%}]"
        e = f"{c['early'][0]:.3f}({c['early'][1]})"
        l = f"{c['late'][0]:.3f}({c['late'][1]})"
        flag = ("  <<< BOTH" if c["clears"] and c["both"]
                else ("  <<<" if c["clears"]
                      else ("  *" if c["win_rate"] > breakeven else "")))
        print(f"{c['cell']:<44} {c['bets']:>5} {c['win_rate']:>6.1%} "
              f"{c['roi']:>+7.1%} {ci:>17} {e:>12} {l:>12}{flag}")
    for c in cells:
        if c["clears"]:
            print(f"    {c['cell']}: per-season {c['per_season']}")


# ── PART 1: moneyline ─────────────────────────────────────────────────────────

def scan_moneyline(pred: pd.DataFrame) -> None:
    ml = load_ml_prices()
    d = pred[pred["game_id"].isin(ml)].copy()
    d["hp"] = d["game_id"].map(lambda g: ml[g][0])
    d["ap"] = d["game_id"].map(lambda g: ml[g][1])
    d["imp_h"] = d["hp"].map(implied)
    d["imp_a"] = d["ap"].map(implied)
    d["edge_h"] = d["p_home"] - d["imp_h"]
    d["edge_a"] = (1 - d["p_home"]) - d["imp_a"]
    d["home_won"] = d["margin"] > 0

    print(f"\n{'=' * 112}")
    print(f"PART 1 -- MONEYLINE (margin regression -> P(win) vs real "
          f"{ML_BOOK} prices; ROI at actual odds)")
    print(f"{'=' * 112}")
    print(f"games with an ML price: {len(d)}   "
          f"overround mean {(d['imp_h'] + d['imp_a']).mean():.3f}")

    # calibration (descriptive): is p_home ordered against reality?
    q = pd.qcut(d["p_home"], 10, duplicates="drop")
    cal = d.groupby(q, observed=True).agg(
        n=("home_won", "size"), p=("p_home", "mean"), won=("home_won", "mean"))
    print("\nCALIBRATION deciles (descriptive -- predicted vs realized home win%)")
    for _, r in cal.iterrows():
        print(f"   p={r['p']:.3f}  won={r['won']:.3f}  n={int(r['n'])}")
    corr = float(np.corrcoef(cal["p"], cal["won"])[0, 1])
    print(f"   decile correlation: {corr:.3f}")

    # bettable ladder: best-edge side, edge >= t, ROI at real prices.
    # ONE family x two price policies (all prices / floor -200) = 10 cells.
    cells = []
    for floor in (None, -200.0):
        for t in (0.02, 0.04, 0.06, 0.08, 0.10):
            pick_home = d["edge_h"] >= d["edge_a"]
            edge = np.where(pick_home, d["edge_h"], d["edge_a"])
            price = np.where(pick_home, d["hp"], d["ap"])
            s = d[(edge >= t) & ((price >= floor) if floor else True)].copy()
            if len(s) < MIN_BETS:
                continue
            ph = s["edge_h"] >= s["edge_a"]
            pr = np.where(ph, s["hp"], s["ap"])
            won = np.where(ph, s["home_won"], ~s["home_won"])
            profit = pd.Series(np.where(won, [payout(x) for x in pr], -1.0),
                               index=s.index)
            # breakeven for a mixed-price book is ROI>0, so flag on CI of ROI
            # is not available -- use win-rate CI vs the sample's own implied
            # mean as descriptive, and let ROI + halves carry the verdict.
            be = float(np.mean([implied(x) for x in pr]))
            cells.append(_cell(s, pd.Series(won, index=s.index),
                               f"edge>={t:.2f}"
                               + (f", price>={floor:+.0f}" if floor else ""),
                               stake=pd.Series(1.0, index=s.index),
                               profit=profit, breakeven=be))
    _print_cells("MONEYLINE edge ladder (breakeven = each cell's own implied "
                 "mean; ROI is the real number)", cells, breakeven=0.5)


# ── PART 2: totals conditional surface ────────────────────────────────────────

def scan_totals(pred: pd.DataFrame) -> None:
    d = pred.dropna(subset=["pred_total", "total_line"]).copy()
    d["dt"] = d["pred_total"] - d["total_line"]
    d = d[d["total"] != d["total_line"]]
    d["over_hit"] = d["total"] > d["total_line"]
    d["won"] = np.where(d["dt"] > 0, d["over_hit"], ~d["over_hit"])

    print(f"\n{'=' * 112}")
    print("PART 2 -- TOTALS (live model): conditional surface of the "
          "disagreement d = pred_total - line")
    print(f"{'=' * 112}")
    print(f"graded games: {len(d)}")

    print("\nMONOTONICITY (descriptive): win rate by |d| band -- real signal "
          "rises with disagreement")
    for a, b in [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10), (10, 13), (13, 99)]:
        s = d[(d["dt"].abs() >= a) & (d["dt"].abs() < b)]
        if len(s) >= 40:
            print(f"   |d| {a:>2}-{b:<3} n={len(s):>5}  win={s['won'].mean():.3f}")

    cells = []
    for g in (6.0, 8.0, 10.0):
        cells.append(_cell(d[d["dt"] >= g], d[d["dt"] >= g]["won"],
                           f"OVER side, d >= +{g:g}"))
        cells.append(_cell(d[d["dt"] <= -g], d[d["dt"] <= -g]["won"],
                           f"UNDER side, d <= -{g:g}"))
    m = d[d["dt"].abs() >= 8.0]
    cells.append(_cell(m[m["total_line"] < 49], m[m["total_line"] < 49]["won"],
                       "|d|>=8, line < 49"))
    cells.append(_cell(m[(m["total_line"] >= 49) & (m["total_line"] < 60)],
                       m[(m["total_line"] >= 49) & (m["total_line"] < 60)]["won"],
                       "|d|>=8, line 49-60"))
    cells.append(_cell(m[m["total_line"] >= 60], m[m["total_line"] >= 60]["won"],
                       "|d|>=8, line >= 60"))
    wk = pd.to_numeric(m["week"], errors="coerce")
    cells.append(_cell(m[wk <= 4], m[wk <= 4]["won"], "|d|>=8, weeks 1-4"))
    cells.append(_cell(m[wk >= 5], m[wk >= 5]["won"], "|d|>=8, weeks 5+"))
    _print_cells("TOTALS cells (one family: direction x gate, plus line/week "
                 "bands at the live gate)", cells)


# ── PART 3: spread conditional surface ────────────────────────────────────────

def scan_spread(pred: pd.DataFrame) -> None:
    d = pred.dropna(subset=["pred_margin", "spread_home"]).copy()
    d["dm"] = d["pred_margin"] + d["spread_home"]      # >0 favours HOME
    d["cover"] = d["margin"] + d["spread_home"]
    d = d[d["cover"] != 0]
    d["won"] = np.where(d["dm"] > 0, d["cover"] > 0, d["cover"] < 0)
    d["pick_home"] = d["dm"] > 0
    # the PICKED team is the favorite when we pick home and home is laying
    # points (spread_home < 0), or pick away while away lays (spread_home > 0)
    d["pick_fav"] = np.where(d["pick_home"], d["spread_home"] < 0,
                             d["spread_home"] > 0)

    print(f"\n{'=' * 112}")
    print("PART 3 -- SPREAD (margin regression, the displaced candidate): "
          "d = pred_margin + spread_home")
    print(f"{'=' * 112}")
    print(f"graded games: {len(d)}")

    print("\nMONOTONICITY (descriptive): win rate by |d| band")
    for a, b in [(0, 2), (2, 4), (4, 6), (6, 8), (8, 10), (10, 99)]:
        s = d[(d["dm"].abs() >= a) & (d["dm"].abs() < b)]
        if len(s) >= 40:
            print(f"   |d| {a:>2}-{b:<3} n={len(s):>5}  win={s['won'].mean():.3f}")

    cells = []
    for g in (5.5, 8.0):
        m = d[d["dm"].abs() >= g]
        cells.append(_cell(m, m["won"], f"|d|>={g:g} (all)"))
        cells.append(_cell(m[m["pick_home"]], m[m["pick_home"]]["won"],
                           f"|d|>={g:g}, pick HOME"))
        cells.append(_cell(m[~m["pick_home"]], m[~m["pick_home"]]["won"],
                           f"|d|>={g:g}, pick AWAY"))
        cells.append(_cell(m[m["pick_fav"]], m[m["pick_fav"]]["won"],
                           f"|d|>={g:g}, pick FAVORITE"))
        cells.append(_cell(m[~m["pick_fav"]], m[~m["pick_fav"]]["won"],
                           f"|d|>={g:g}, pick DOG"))
    m = d[d["dm"].abs() >= 5.5]
    sp = m["spread_home"].abs()
    cells.append(_cell(m[sp < 7], m[sp < 7]["won"], "|d|>=5.5, |spread| < 7"))
    cells.append(_cell(m[(sp >= 7) & (sp < 17)], m[(sp >= 7) & (sp < 17)]["won"],
                       "|d|>=5.5, |spread| 7-17"))
    cells.append(_cell(m[sp >= 17], m[sp >= 17]["won"], "|d|>=5.5, |spread| >= 17"))
    _print_cells("SPREAD cells (one family: gate x side/fav splits, plus "
                 "spread-size bands). MIRROR RULE: a side cell that clears "
                 "while its mirror is flat is a confound", cells)


def main() -> int:
    print(f"building production frames for {ALL_SEASONS} ...")
    df = build_frames(ALL_SEASONS)
    print("\nwalk-forward prediction pass (production features, inner-split "
          "residuals):")
    pred = predict_all(df)
    print(f"\ntotal test-season predictions: {len(pred)}")

    scan_moneyline(pred)
    scan_totals(pred)
    scan_spread(pred)

    print(f"\n{'=' * 112}")
    print("VARIANT ACCOUNTING: ~10 ML cells + ~13 totals cells + ~13 spread "
          "cells = ~36 bettable cells tested.")
    print("At 95% confidence ~1.8 clear by chance alone. Believe nothing that "
          "does not hold in BOTH halves, and no side cell whose mirror is flat.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
