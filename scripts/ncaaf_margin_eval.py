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


# ── Walk-forward (the honest multi-season record) ─────────────────────────────

def walk_forward(all_seasons: list[int], test_seasons: list[int],
                 gate: float | None = None) -> dict:
    """
    Train-on-the-past, bet-the-future, one season at a time.

    The single-holdout run answers "does this work on 2025?" — but 2023 and
    2024 sit INSIDE that model's training window, so their apparent record is
    memory, not a track record. Here each test season S is predicted by a model
    fit ONLY on seasons < S, which is the same information a bettor would have
    had walking into that September. Three honest seasons instead of one.

    Two numbers come out, and the difference between them matters:
      - AT THE GATE: the fixed ±5.5 cut applied to every season. For 2023/2024
        this is a clean test (neither season informed the choice); for 2025 it
        is the cut that was SELECTED on 2025, so that season's number is
        optimistic by construction. Judge stability on the early seasons.
      - BEST PER SEASON: the best threshold in hindsight for each season. If
        the best cut jumps around wildly between seasons, the "edge" is a
        moving target and the fixed gate will not hold up forward.
    """
    from loguru import logger

    gate = D_THRESHOLD if gate is None else gate
    df = build_frames(sorted(set(all_seasons) | set(test_seasons)))

    per_season = []
    for season in sorted(test_seasons):
        past = [s for s in all_seasons if s < season]
        if not past:
            logger.warning(f"{season}: no prior seasons available — skipped")
            continue

        tr, cols = _matrix(df[df["_season"].isin(past)], MARGIN_FEATURES)
        ho, _ = _matrix(df[df["_season"] == season], MARGIN_FEATURES)
        ho = ho.dropna(subset=["_spread_home"])
        if tr.empty or ho.empty:
            logger.warning(f"{season}: no usable rows — skipped")
            continue

        model = _fit(tr[cols], tr["_margin"])
        pred = model.predict(ho[cols])
        rows = sweep_spread(pred, ho["_spread_home"], ho["_margin"])
        at_gate = next((r for r in rows if r["threshold"] == gate), None)
        best = verdict(rows)

        per_season.append({
            "season": season,
            "train_seasons": past,
            "train_rows": len(tr),
            "games": len(ho),
            "at_gate": at_gate,
            "best": best,
            "model_rmse": rmse(pred, ho["_margin"]),
            "line_rmse": rmse(-ho["_spread_home"], ho["_margin"]),
        })

    return {"gate": gate, "seasons": per_season}


def _print_walk_forward(res: dict) -> None:
    gate = res["gate"]
    seasons = res["seasons"]
    bar = "=" * 72
    print("")
    print(bar)
    print("WALK-FORWARD — each season predicted by a model trained ONLY on")
    print(f"prior seasons. Betting gate: |predicted margin - line| >= {gate} pts.")
    print(bar)
    print("")
    print(f"{'season':>7} {'trained on':>13} {'bets':>6} {'wins':>6} "
          f"{'win%':>7} {'ROI@-110':>9}  {'RMSE m/mkt':>12}")

    tot_bets = tot_wins = 0
    for s in seasons:
        span = f"{min(s['train_seasons'])}-{max(s['train_seasons'])}"
        g = s["at_gate"]
        if not g or not g["bets"]:
            print(f"{s['season']:>7} {span:>13} {0:>6} {'-':>6} {'-':>7} {'-':>9}")
            continue
        wr = g["win_rate"]
        roi = wr * (100 / 110) - (1 - wr)
        tot_bets += g["bets"]
        tot_wins += g["wins"]
        print(f"{s['season']:>7} {span:>13} {g['bets']:>6} {g['wins']:>6} "
              f"{wr:>6.1%} {roi:>+8.1%}  "
              f"{s['model_rmse']:>5.2f}/{s['line_rmse']:<5.2f}")

    if tot_bets:
        wr = tot_wins / tot_bets
        roi = wr * (100 / 110) - (1 - wr)
        se = (wr * (1 - wr) / tot_bets) ** 0.5
        lo, hi = wr - 1.96 * se, wr + 1.96 * se
        print("-" * 72)
        print(f"{'POOLED':>7} {'':>13} {tot_bets:>6} {tot_wins:>6} "
              f"{wr:>6.1%} {roi:>+8.1%}")
        print("")
        print(f"  95% CI on the pooled win rate: [{lo:.1%}, {hi:.1%}]  "
              f"(breakeven {BREAKEVEN:.2%})")
        if lo > BREAKEVEN:
            print("  -> the whole interval clears breakeven. That is a real result.")
        elif wr >= BREAKEVEN:
            print("  -> above breakeven, but the interval still contains it: the")
            print("     record is CONSISTENT with having no edge. Paper trading")
            print("     settles it, not more backtesting.")
        else:
            print("  -> below breakeven pooled. The single-season pass does NOT")
            print("     replicate out-of-sample. Treat the model as unproven.")

    print("")
    print("Best threshold in hindsight, per season (stability check):")
    for s in seasons:
        b = s["best"]
        if b:
            print(f"  {s['season']}: +/-{b['threshold']} -> {b['wins']}/{b['bets']} "
                  f"= {b['win_rate']:.1%}")
        else:
            print(f"  {s['season']}: no threshold clears {BREAKEVEN:.2%} "
                  f"with >= {MIN_BETS} bets")
    print("")
    print("  Cuts clustering near each other = the gate is a real feature of the")
    print(f"  market. Cuts scattering = +/-{gate} was fitted to one season.")



# ── Fit + register (run AFTER the harness verdict passed) ─────────────────────

# The disagreement gate the 2025 holdout validated (140/261 = 53.6% at ±5.5).
# Provisional pending the neighbor-cell review; env-overridable so a re-cut is
# config, not code.
import os
D_THRESHOLD = float(os.environ.get("NCAAF_SPREAD_D_THRESHOLD", "5.5"))


def fit_and_register(train_seasons: list[int], holdout: int) -> str:
    """
    Fit the production margin artifact and register it as `ncaaf_spread`.

    Two fits, on purpose:
    - an EVAL fit (train seasons only) whose holdout predictions give the
      honest out-of-sample residual distribution — the thing P(cover) is
      computed from at score time. In-sample residuals would be too tight and
      every probability correspondingly overconfident.
    - the FINAL fit on train + holdout (all information available today) —
      the model that actually scores 2026 games.

    The artifact carries kind="margin_regression": the scorer routes it to the
    margin path (predict margin from fundamentals, disagree with DK's live
    spread, probability from the OOS residual ECDF).
    """
    from datetime import date, datetime
    import pickle

    from loguru import logger
    from data.db import get_connection
    from features.ncaaf_feature_engine import margin_cover_prob

    df = build_frames(train_seasons + [holdout])
    train = df[df["_season"].isin(train_seasons)]
    hold = df[df["_season"] == holdout]

    tr, cols = _matrix(train, MARGIN_FEATURES)
    ho, _ = _matrix(hold, MARGIN_FEATURES)
    ho_lined = ho.dropna(subset=["_spread_home"])

    eval_model = _fit(tr[cols], tr["_margin"])
    pred_all = eval_model.predict(ho[cols])
    residuals = sorted(float(a - p) for a, p in zip(ho["_margin"], pred_all))

    pred = eval_model.predict(ho_lined[cols])
    rows = sweep_spread(pred, ho_lined["_spread_home"], ho_lined["_margin"])
    _print_sweep("SPREAD (eval fit — must reproduce the harness verdict)", rows,
                 line_rmse=rmse(-ho_lined["_spread_home"], ho_lined["_margin"]),
                 model_rmse=rmse(pred, ho_lined["_margin"]))
    best = verdict(rows)
    if best is None:
        raise SystemExit("Eval fit no longer clears the kill line — refusing to "
                         "register. Re-run the plain harness and investigate.")

    at_gate = [r for r in rows if r["threshold"] == D_THRESHOLD]
    gate = at_gate[0] if at_gate else best

    full = pd.concat([tr, ho])
    final_model = _fit(full[cols], full["_margin"])

    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    prob_at_gate = margin_cover_prob(residuals, D_THRESHOLD)
    artifact = {
        "kind": "margin_regression",
        "model": final_model,
        "feature_cols": cols,
        "residuals": residuals,          # sorted OOS (actual − pred) margins
        "market": "spreads",
        "d_threshold": D_THRESHOLD,
        "prob_at_threshold": prob_at_gate,
        "train_seasons": sorted(set(train_seasons + [holdout])),
        "version": version,
    }
    out = Path(__file__).parent.parent / "models" / "saved" / f"ncaaf_spread_{version}.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(artifact, f)

    n = gate["bets"]
    wr = gate["win_rate"] or 0.0
    roi = (wr * (100 / 110) - (1 - wr)) if n else 0.0
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE model_registry SET is_active = 0
            WHERE model_id = 'ncaaf_spread' AND is_active = 1
        """)
        conn.execute("""
            INSERT INTO model_registry (
                model_id, version, trained_on, train_seasons, holdout_season,
                holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                is_active, model_path, notes
            ) VALUES ('ncaaf_spread', %s, %s, %s, %s, %s, %s, %s, NULL, 1, %s, %s)
        """, (version, date.today().isoformat(),
              str(sorted(set(train_seasons + [holdout]))), holdout,
              round(wr, 4), round(roi, 4), n,
              (out.relative_to(Path(__file__).parent.parent)).as_posix(),
              f"margin regression | gate d>={D_THRESHOLD} | OOS-residual ECDF"))
        conn.commit()
    finally:
        conn.close()

    logger.success(f"Registered ncaaf_spread v{version} (margin regression)")
    print(f"\nP(cover) at the ±{D_THRESHOLD} gate = {prob_at_gate:.4f}")
    print("config MODEL_PROB_THRESHOLDS['ncaaf_spread'] should be set to this")
    print("value (currently provisional) — a pick fires when the ECDF prob")
    print("clears it, which is the same event as |disagreement| >= the gate.")
    print(f"\nCommit the artifact so the worker can score:")
    print(f"  git add -f {out.relative_to(Path(__file__).parent.parent).as_posix()} && "
          f"git commit -m 'NCAAF spread margin artifact v{version}'")
    return version


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seasons", nargs="+", type=int,
                    default=[2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024])
    ap.add_argument("--holdout", type=int, default=2025)
    ap.add_argument("--fit", action="store_true",
                    help="Fit + register the production margin artifact "
                         "(only after the harness verdict passed)")
    ap.add_argument("--walk-forward", nargs="*", type=int, metavar="SEASON",
                    help="Honest multi-season record: each season predicted by "
                         "a model trained only on PRIOR seasons "
                         "(default: 2023 2024 2025)")
    args = ap.parse_args()
    if args.walk_forward is not None:
        tests = args.walk_forward or [2023, 2024, 2025]
        pool = sorted(set(args.seasons + [args.holdout] + tests))
        _print_walk_forward(walk_forward(pool, tests))
        sys.exit(0)
    if args.fit:
        fit_and_register(args.seasons, args.holdout)
        sys.exit(0)
    sys.exit(main(args.seasons, args.holdout))
