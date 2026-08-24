"""
NCAAF margin/total regression — the pre-committed LAST modelling attempt.

Binary cover/total classification holds out at AUC ~0.50 on a healthy
6,000+-row matrix (spread 0.502 / totals 0.490, v20260823 runs), across two
train windows and two feature sets. This harness reframes the target instead
of adding features: regress the MARGIN (home − away) and the TOTAL directly
from fundamentals, then bet only where the model and the closing line
disagree by more than a threshold. It uses the information the binary target
throws away — magnitude and key-number structure.

The market number is deliberately NOT a regression feature: a regression
given the line learns margin ≈ line and the disagreements collapse to zero.
The line enters only afterwards, as the thing to disagree with.

PRE-COMMITTED KILL LINE (written 2026-08-24, BEFORE this ever ran): if no
disagreement threshold reaches 52.38% (the −110 breakeven) with ≥ 50 bets on
the 2025 holdout, NCAAF model development is CLOSED — no re-cuts, no feature
hunts on the same information. The next direction is market-structure
research (the NFL §28 opener pattern applied to NCAAF), not another model.

Run on a machine with DB access:
    python -m scripts.ncaaf_margin_eval
    python -m scripts.ncaaf_margin_eval --seasons 2015 2016 2017 2018 2019 2021 2022 2023 2024 --holdout 2025
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.feature_engine import (  # noqa: E402
    NCAAF_H2H_FEATURES, NCAAF_TOTALS_FEATURES, SPARSE_OK_FEATURES)

BREAKEVEN = 0.5238          # win rate needed at -110
MIN_BETS = 50               # a "threshold that works" must carry real volume
THRESHOLDS = [round(t * 0.5, 1) for t in range(0, 17)]   # 0.0 .. 8.0 points

# Fundamentals only — no market numbers (see module docstring).
MARGIN_FEATURES = list(NCAAF_H2H_FEATURES)
TOTAL_FEATURES = [c for c in NCAAF_TOTALS_FEATURES if c != "total_line"]
assert "spread_home" not in MARGIN_FEATURES
assert "total_line" not in TOTAL_FEATURES


# ── Pure evaluation helpers (unit-tested) ─────────────────────────────────────

def sweep_spread(pred_margin, spread_home, actual_margin,
                 thresholds=THRESHOLDS) -> list[dict]:
    """
    For each disagreement threshold: bet the side the model favours vs the
    closing spread, grade against the actual margin. `spread_home` is the HOME
    spread (home covers iff actual_margin + spread_home > 0 — the §29
    convention; equality is a push and is excluded from the record).
    Disagreement d = pred_margin + spread_home: positive → home side.
    """
    pred_margin = np.asarray(pred_margin, dtype=float)
    spread_home = np.asarray(spread_home, dtype=float)
    actual_margin = np.asarray(actual_margin, dtype=float)
    d = pred_margin + spread_home
    cover = actual_margin + spread_home           # >0 home covers, <0 away, ==0 push
    out = []
    for t in thresholds:
        sel = np.abs(d) >= t if t > 0 else np.abs(d) > 0
        picks = np.sign(d[sel])
        result = np.sign(cover[sel])
        decided = result != 0
        wins = int(np.sum(picks[decided] == result[decided]))
        n = int(np.sum(decided))
        out.append({"threshold": t, "bets": n, "wins": wins,
                    "pushes": int(np.sum(~decided)),
                    "win_rate": (wins / n) if n else None})
    return out


def sweep_total(pred_total, total_line, actual_total,
                thresholds=THRESHOLDS) -> list[dict]:
    """Same shape for totals: d = pred_total − line; positive → over."""
    pred_total = np.asarray(pred_total, dtype=float)
    total_line = np.asarray(total_line, dtype=float)
    actual_total = np.asarray(actual_total, dtype=float)
    d = pred_total - total_line
    res = actual_total - total_line
    out = []
    for t in thresholds:
        sel = np.abs(d) >= t if t > 0 else np.abs(d) > 0
        picks = np.sign(d[sel])
        result = np.sign(res[sel])
        decided = result != 0
        wins = int(np.sum(picks[decided] == result[decided]))
        n = int(np.sum(decided))
        out.append({"threshold": t, "bets": n, "wins": wins,
                    "pushes": int(np.sum(~decided)),
                    "win_rate": (wins / n) if n else None})
    return out


def verdict(rows: list[dict], breakeven: float = BREAKEVEN,
            min_bets: int = MIN_BETS) -> dict | None:
    """The best threshold that clears the kill line, or None (= dead)."""
    passing = [r for r in rows
               if r["bets"] >= min_bets and r["win_rate"] is not None
               and r["win_rate"] >= breakeven]
    if not passing:
        return None
    return max(passing, key=lambda r: (r["win_rate"], r["bets"]))


def rmse(a, b) -> float:
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    return float(np.sqrt(np.mean((a - b) ** 2)))


# ── Dataset (DB) ──────────────────────────────────────────────────────────────

def build_frames(seasons: list[int]) -> pd.DataFrame:
    """
    One row per completed, non-bowl, FBS-vs-FBS NCAAF game across `seasons`:
    fundamentals-only features + actual margin/total + the closing spread and
    total (read from the odds lookup, NOT fed to the model). Reuses the exact
    bulk path training uses, so there is no engine drift.
    """
    from loguru import logger
    from data.db import get_connection
    from features.ncaaf_feature_engine import (
        build_bulk_ncaaf_lookups, build_ncaaf_features_from_bulk)

    conn = get_connection()
    try:
        placeholders = ",".join(["%s"] * len(seasons))
        games = conn.execute(f"""
            SELECT game_id, season, game_date, home_team, away_team,
                   home_score, away_score
            FROM games
            WHERE sport = 'NCAAF' AND season IN ({placeholders})
              AND home_score IS NOT NULL
            ORDER BY game_date
        """, seasons).fetchall()
        bulk = build_bulk_ncaaf_lookups(conn, seasons)
    finally:
        conn.close()

    rows = []
    for game_id, season, game_date, home, away, hs, as_ in games:
        feat = build_ncaaf_features_from_bulk(
            bulk, game_id, game_date, home, away, season, None)
        if feat is None or feat.get("is_bowl"):
            continue
        sp = (bulk["odds"].get((game_id, "spreads")) or {}).get("spread_home")
        tl = (bulk["odds"].get((game_id, "totals")) or {}).get("total_line")
        feat.update({
            "_season": season, "_game_id": game_id,
            "_margin": float(hs) - float(as_),
            "_total": float(hs) + float(as_),
            "_spread_home": float(sp) if sp is not None else np.nan,
            "_total_line": float(tl) if tl is not None else np.nan,
        })
        rows.append(feat)

    df = pd.DataFrame(rows)
    logger.info(f"NCAAF regression frame: {len(df)} rows across {seasons}")
    return df


def _matrix(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, list[str]]:
    """Strict dropna on core features; SPARSE_OK columns pass through as NaN."""
    cols = [c for c in feature_cols if c in df.columns]
    strict = [c for c in cols if c not in SPARSE_OK_FEATURES]
    out = df.dropna(subset=strict).copy()
    for c in cols:
        out[c] = pd.to_numeric(out[c], errors="coerce")
    return out, cols


def _fit(X: pd.DataFrame, y: pd.Series):
    from xgboost import XGBRegressor
    model = XGBRegressor(
        n_estimators=700, learning_rate=0.03, max_depth=5,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        objective="reg:squarederror", n_jobs=-1, random_state=42)
    model.fit(X, y)
    return model


def _print_sweep(name: str, rows: list[dict], line_rmse: float,
                 model_rmse: float) -> None:
    print(f"\n── {name} ──")
    print(f"  holdout RMSE: model {model_rmse:.2f} vs closing line {line_rmse:.2f} "
          f"(the market benchmark — a model far worse here has no tail to bet)")
    print(f"  {'thresh':>6} {'bets':>6} {'wins':>6} {'win%':>7}")
    for r in rows:
        wr = f"{r['win_rate']:.1%}" if r["win_rate"] is not None else "—"
        flag = "  ← clears kill line" if (r["bets"] >= MIN_BETS and r["win_rate"]
                                          and r["win_rate"] >= BREAKEVEN) else ""
        print(f"  {r['threshold']:>6} {r['bets']:>6} {r['wins']:>6} {wr:>7}{flag}")
    best = verdict(rows)
    if best:
        print(f"  VERDICT: PASSES at ±{best['threshold']} — "
              f"{best['wins']}/{best['bets']} = {best['win_rate']:.1%} "
              f"(breakeven {BREAKEVEN:.2%}, min {MIN_BETS} bets)")
    else:
        print(f"  VERDICT: FAILS the kill line — no threshold ≥ {BREAKEVEN:.2%} "
              f"with ≥ {MIN_BETS} bets")


def main(train_seasons: list[int], holdout: int) -> int:
    df = build_frames(train_seasons + [holdout])
    train = df[df["_season"].isin(train_seasons)]
    hold = df[df["_season"] == holdout]

    any_pass = False

    # ── Spread (margin regression) ────────────────────────────────────────────
    tr, cols = _matrix(train, MARGIN_FEATURES)
    ho, _ = _matrix(hold, MARGIN_FEATURES)
    ho = ho.dropna(subset=["_spread_home"])
    print(f"\nSpread: {len(tr)} train rows, {len(ho)} holdout rows with a line")
    m = _fit(tr[cols], tr["_margin"])
    pred = m.predict(ho[cols])
    rows = sweep_spread(pred, ho["_spread_home"], ho["_margin"])
    _print_sweep("SPREAD (margin vs closing spread)", rows,
                 line_rmse=rmse(-ho["_spread_home"], ho["_margin"]),
                 model_rmse=rmse(pred, ho["_margin"]))
    any_pass |= verdict(rows) is not None

    # ── Totals (total-points regression) ──────────────────────────────────────
    tr, cols = _matrix(train, TOTAL_FEATURES)
    ho, _ = _matrix(hold, TOTAL_FEATURES)
    ho = ho.dropna(subset=["_total_line"])
    print(f"\nTotals: {len(tr)} train rows, {len(ho)} holdout rows with a line")
    m = _fit(tr[cols], tr["_total"])
    pred = m.predict(ho[cols])
    rows = sweep_total(pred, ho["_total_line"], ho["_total"])
    _print_sweep("TOTALS (predicted total vs closing line)", rows,
                 line_rmse=rmse(ho["_total_line"], ho["_total"]),
                 model_rmse=rmse(pred, ho["_total"]))
    any_pass |= verdict(rows) is not None

    print("\n════════════════════════════════════════════════════════")
    if any_pass:
        print("At least one market clears the pre-committed kill line — next step:")
        print("wire the regression into the trainer/scorer properly and validate")
        print("the passing threshold as a real model (registry, backtest, paper).")
    else:
        print("KILL LINE FIRED on the reframed target as well. Per the")
        print("pre-commitment: NCAAF model development is CLOSED. The next")
        print("direction is market-structure research (the NFL §28 opener")
        print("pattern on NCAAF), not another model on the same information.")
    return 0 if any_pass else 1


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seasons", nargs="+", type=int,
                    default=[2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024])
    ap.add_argument("--holdout", type=int, default=2025)
    args = ap.parse_args()
    sys.exit(main(args.seasons, args.holdout))
