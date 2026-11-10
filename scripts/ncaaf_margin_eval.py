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

THE TOTALS MODEL IS THE MEAN OF ELEVEN FITS (mike, 2026-11-10), and fitting it
is separate from registering it:
    python -m scripts.ncaaf_margin_eval --fit-totals              # writes the artifact, registers nothing
    python -m scripts.ncaaf_margin_eval --register-totals VERSION # after the artifact is merged and deployed
    python -m scripts.ncaaf_margin_eval --walk-forward-totals     # the average against each single seed
`--frame FILE` reads a pickled training frame instead of the database, for
the two fitting commands. See fit_totals and docs/sports/ncaaf.md.
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


def _fit(X: pd.DataFrame, y: pd.Series, random_state: int = 42):
    from xgboost import XGBRegressor
    model = XGBRegressor(
        n_estimators=700, learning_rate=0.03, max_depth=5,
        subsample=0.8, colsample_bytree=0.8, min_child_weight=5,
        objective="reg:squarederror", n_jobs=-1, random_state=random_state)
    model.fit(X, y)
    return model


# The totals model is the mean of these eleven fits. The fit above subsamples
# rows and columns at 0.8, so its prediction for one game moves about 1.5
# points with the seed (standard deviation across these same eleven,
# docs/ncaaf_market_audit.md section 4) against a gate of 8. They are the
# seeds that audit measured, in its order; 42 is the single fit that ran live
# from 2026-08-25. Changing this list is a model update.
TOTALS_SEEDS = (42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9)


def _fit_seed_average(X: pd.DataFrame, y: pd.Series, seeds=TOTALS_SEEDS):
    """`_fit` once per seed, same settings, behind one `predict` (their mean)."""
    from models.seed_average import SeedAverage
    return SeedAverage([_fit(X, y, random_state=s) for s in seeds], seeds=seeds)


def load_frame(seasons: list[int], frame_path=None) -> pd.DataFrame:
    """The training frame for `seasons`: built from the database, or read from
    a pickle `build_frames` produced earlier.

    The file is for fitting on a machine with no database access, from a frame
    the repo's own builder already wrote. Rows keep the file's order, because
    the fit subsamples rows and their order is part of the draw. A season the
    file does not hold is refused: fitting on fewer seasons than were asked for
    would produce a different model under the same name.
    """
    if frame_path is None:
        return build_frames(seasons)
    df = pd.read_pickle(frame_path)
    want = sorted(set(int(s) for s in seasons))
    have = set(int(s) for s in df["_season"].unique())
    missing = [s for s in want if s not in have]
    if missing:
        raise SystemExit(f"{frame_path} holds no rows for season(s) {missing}; "
                         f"it has {sorted(have)}. Refusing to fit on fewer seasons.")
    out = df[df["_season"].isin(want)].copy()
    print(f"Frame: {len(out)} rows for {want}, read from {frame_path} "
          f"(a file, not the database)")
    return out


# The inputs the pipeline may serve as MISSING (features.feature_engine
# .SPARSE_OK_FEATURES), by how they go missing in production: a game with no
# `game_weather` row yet (run_pipeline's ncaaf-weather step covers games 7
# days out; the totals rule scores any game DraftKings prices), and a game
# whose venue is not known yet (its elevation is then missing; dome and grass
# are served as 0, so blanking all three is the cautious reading). A served
# missing value is NaN, and a tree
# sends NaN wherever its training rows taught it to. Rows that lack these are
# rare in training (one row with no weather in the frame of 2026-11-10), so
# the direction is close to arbitrary and has to be MEASURED on every fit:
# see missing_input_shift.
MISSING_INPUT_GROUPS = {
    "weather": ("wx_temp_f", "wx_wind_mph", "wx_precip_mm"),
    "venue": ("venue_elevation_ft", "is_dome_game", "is_grass"),
}
assert ({c for g in MISSING_INPUT_GROUPS.values() for c in g}
        == set(TOTAL_FEATURES) & set(SPARSE_OK_FEATURES)), (
    "a totals feature that may be served missing is in no MISSING_INPUT_GROUPS "
    "group, so nothing measures what its absence does")


def _blank(X: pd.DataFrame, features, fill: dict | None = None) -> pd.DataFrame:
    """A copy of X with `features` missing (NaN), or set to `fill[feature]`."""
    Z = X.copy()
    for c in features:
        if c in Z.columns:
            Z[c] = np.nan if fill is None else fill[c]
    return Z


def missing_input_shift(model, X: pd.DataFrame, line, gate: float) -> dict:
    """How far `model`'s prediction moves when inputs that may be served
    missing ARE missing, on the rows of X that have all of them.

    Per group: the mean and standard deviation of (prediction with the group
    missing - prediction as stored), and how many games sit at the gate before
    and after. A mean as large as the gate means a missing input, on its own,
    reads as a bet; register_totals refuses such an artifact.
    """
    feats = [c for g in MISSING_INPUT_GROUPS.values() for c in g if c in X.columns]
    line = pd.Series(np.asarray(line, dtype=float), index=X.index)
    keep = X[feats].notna().all(axis=1) & line.notna()
    X, line = X[keep], line[keep].to_numpy()
    base = np.asarray(model.predict(X), dtype=float)
    groups = dict(MISSING_INPUT_GROUPS)
    groups["weather+venue"] = groups["weather"] + groups["venue"]
    out = {}
    for name, cols in groups.items():
        cols = [c for c in cols if c in X.columns]
        moved = np.asarray(model.predict(_blank(X, cols)), dtype=float)
        d = moved - base
        out[name] = {
            "features": cols,
            "mean": float(d.mean()) if len(d) else 0.0,
            "sd": float(d.std()) if len(d) else 0.0,
            "at_gate_before": int((np.abs(base - line) >= gate).sum()),
            "at_gate_after": int((np.abs(moved - line) >= gate).sum()),
        }
    return {"rows": int(len(X)), "groups": out}


def units_at_minus_110(wins: int, bets: int) -> float:
    """Units on `bets` decided bets at -110, one unit to win: a win is +1 and a
    loss is -1.1 (the published stake, CLAUDE.md section 2)."""
    return float(wins - 1.1 * (bets - wins))


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


def walk_forward_totals(all_seasons: list[int], test_seasons: list[int],
                        gate: float | None = None, frame_path=None) -> dict:
    """Walk-forward for the TOTALS market (same structure as spread version),
    on the model that ships: the mean of the TOTALS_SEEDS fits.

    Each test season is predicted by eleven fits on EARLIER seasons only, and
    the record is the average's. Each member is graded on its own as well
    (`by_seed`), because the reason for averaging is that one seed's record is
    a draw: the same four seasons read 51.5% to 56.4% by seed
    (docs/ncaaf_market_audit.md section 4). `seed_sd_*` is the spread of one
    game's eleven predictions (sample standard deviation), pooled over every
    predicted game.

    `gate` defaults to the totals gate (T_THRESHOLD). It used to default to
    5.5, the spread model's number, so `--walk-forward` printed the totals
    record at a gate the totals model has never used.
    """
    from loguru import logger

    gate = T_THRESHOLD if gate is None else gate
    df = load_frame(sorted(set(all_seasons) | set(test_seasons)), frame_path)

    per_season = []
    game_sds: list[float] = []
    for season in sorted(test_seasons):
        past = [s for s in all_seasons if s < season]
        if not past:
            continue

        tr, cols = _matrix(df[df["_season"].isin(past)], TOTAL_FEATURES)
        ho, _ = _matrix(df[df["_season"] == season], TOTAL_FEATURES)
        ho = ho.dropna(subset=["_total_line"])
        if tr.empty or ho.empty:
            logger.warning(f"Totals {season}: no usable rows")
            continue

        model = _fit_seed_average(tr[cols], tr["_total"])
        per_member = model.member_predictions(ho[cols])
        pred = model.predict(ho[cols])
        rows = sweep_total(pred, ho["_total_line"], ho["_total"])
        at_gate = next((r for r in rows if r["threshold"] == gate), None)
        best = verdict(rows)
        by_seed = {
            seed: next((r for r in sweep_total(member, ho["_total_line"], ho["_total"],
                                               thresholds=[gate])), None)
            for seed, member in zip(model.seeds, per_member)
        }
        if len(per_member) > 1:
            game_sds.extend(np.std(per_member, axis=0, ddof=1).tolist())

        # The same games as if scored before their weather forecast existed:
        # with the weather missing (what the scorer is served), and with it
        # set to typical weather (the training seasons' medians).
        wx = [c for c in MISSING_INPUT_GROUPS["weather"] if c in cols]
        typical = {c: float(tr[c].median()) for c in wx}
        p_missing = np.asarray(model.predict(_blank(ho[cols], wx)), dtype=float)
        p_typical = np.asarray(model.predict(_blank(ho[cols], wx, fill=typical)), dtype=float)
        no_forecast = {
            "missing": sweep_total(p_missing, ho["_total_line"], ho["_total"],
                                   thresholds=[gate])[0],
            "typical": sweep_total(p_typical, ho["_total_line"], ho["_total"],
                                   thresholds=[gate])[0],
            "missing_shift": float(np.mean(p_missing - pred)),
            "typical_shift": float(np.mean(p_typical - pred)),
        }

        per_season.append({
            "season": season,
            "train_seasons": past,
            "train_rows": len(tr),
            "games": len(ho),
            "at_gate": at_gate,
            "best": best,
            "by_seed": by_seed,
            "no_forecast": no_forecast,
            "model_rmse": rmse(pred, ho["_total"]),
            "line_rmse": rmse(ho["_total_line"], ho["_total"]),
        })

    return {"gate": gate, "seasons": per_season, "seeds": list(TOTALS_SEEDS),
            "games": len(game_sds),
            "seed_sd_mean": float(np.mean(game_sds)) if game_sds else None,
            "seed_sd_p95": float(np.quantile(game_sds, 0.95)) if game_sds else None}


def _record(rows: list[dict | None]) -> tuple[int, int]:
    """(wins, decided bets) summed over gate rows; a missing row counts nothing."""
    wins = sum(r["wins"] for r in rows if r)
    bets = sum(r["bets"] for r in rows if r)
    return wins, bets


def _fmt_record(wins: int, bets: int) -> str:
    wl = f"{wins}-{bets - wins}"
    rate = f"{wins / bets:.1%}" if bets else "-"
    return f"{wl:>9} {rate:>6} {units_at_minus_110(wins, bets):>+7.1f}"


def _print_totals_seed_evidence(res: dict) -> None:
    """The average against each single seed, from one walk-forward run."""
    gate, seasons, seeds = res["gate"], res["seasons"], res["seeds"]
    if not seasons:
        return
    bar = "=" * 78
    print("")
    print(bar)
    print(f"TOTALS: the mean of {len(seeds)} seeds against one fit. Each season fitted on")
    print(f"earlier seasons only; bet when |predicted total - stored close| >= {gate}; graded")
    print("at -110, units to win one (a win +1, a loss -1.1).")
    print(bar)
    print(f"{'season':>7} | {'the average':^24} | {'seed 42 alone':^24}")
    print(f"{'':>7} | {'W-L':>9} {'win%':>6} {'units':>7} | {'W-L':>9} {'win%':>6} {'units':>7}")
    for s in seasons:
        a = _record([s["at_gate"]])
        b = _record([s["by_seed"].get(42)])
        print(f"{s['season']:>7} | {_fmt_record(*a)} | {_fmt_record(*b)}")
    a = _record([s["at_gate"] for s in seasons])
    b = _record([s["by_seed"].get(42) for s in seasons])
    print("-" * 78)
    print(f"{'POOLED':>7} | {_fmt_record(*a)} | {_fmt_record(*b)}")

    print("")
    print("Each seed on its own, pooled over the same seasons:")
    pooled = {seed: _record([s["by_seed"].get(seed) for s in seasons]) for seed in seeds}
    for seed in seeds:
        print(f"  seed {seed:>2} | {_fmt_record(*pooled[seed])}")
    ranked = sorted(pooled.items(), key=lambda kv: units_at_minus_110(*kv[1]))
    (worst_seed, worst), (best_seed, best) = ranked[0], ranked[-1]
    print(f"  worst: seed {worst_seed} {worst[0]}-{worst[1] - worst[0]} "
          f"({units_at_minus_110(*worst):+.1f} units); best: seed {best_seed} "
          f"{best[0]}-{best[1] - best[0]} ({units_at_minus_110(*best):+.1f} units)")
    if res.get("seed_sd_mean") is not None:
        print("")
        print(f"Seed-to-seed standard deviation of one game's prediction, over "
              f"{res['games']} games:")
        print(f"  mean {res['seed_sd_mean']:.2f} points, 95th percentile "
              f"{res['seed_sd_p95']:.2f} (the gate is {gate})")

    if all("no_forecast" in s for s in seasons):
        games = sum(s["games"] for s in seasons)

        def pooled_shift(key):
            return sum(s["no_forecast"][key] * s["games"] for s in seasons) / games

        print("")
        print("The same games as if scored BEFORE their weather forecast existed (the")
        print("forecast step covers 7 days; a served game with no weather row is missing")
        print("all three weather inputs). Mean shift is against the prediction as stored.")
        print(f"  {'':<34} {'W-L':>9} {'win%':>6} {'units':>7}   mean shift")
        print(f"  {'weather as stored':<34} "
              f"{_fmt_record(*_record([s['at_gate'] for s in seasons]))}")
        for key, label in (("missing", "weather missing"),
                           ("typical", "weather set to the training median")):
            rec = _record([s["no_forecast"][key] for s in seasons])
            print(f"  {label:<34} {_fmt_record(*rec)}   "
                  f"{pooled_shift(key + '_shift'):+.2f} points")
        print("  weather missing, by season: " + ", ".join(
            f"{s['season']} {s['no_forecast']['missing']['wins']}-"
            f"{s['no_forecast']['missing']['bets'] - s['no_forecast']['missing']['wins']}"
            for s in seasons))


def _print_walk_forward(res: dict, market: str = "SPREAD") -> None:
    gate = res["gate"]
    seasons = res["seasons"]
    bar = "=" * 72
    print("")
    print(bar)
    print(f"WALK-FORWARD ({market}) — each season predicted by a model trained ONLY on")
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
            print("     record is CONSISTENT with having no edge. Forward results")
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


T_THRESHOLD = float(os.environ.get("NCAAF_TOTAL_D_THRESHOLD", "8.0"))


TOTALS_MODEL_ID = "ncaaf_over_under"
SAVED_DIR = Path(__file__).parent.parent / "models" / "saved"


def fit_totals(train_seasons: list[int], holdout: int, frame_path=None,
               out_dir=None) -> dict:
    """
    Fit the production TOTALS artifact for `ncaaf_over_under` and write it.
    It registers NOTHING: `register_totals` does that, later, by version.

    THE MODEL IS THE MEAN OF ELEVEN FITS (TOTALS_SEEDS; mike, 2026-11-10).
    Everything read off the fit is therefore read off the AVERAGE:

    - an EVAL fit (eleven seeds) on the train seasons only, whose averaged
      holdout predictions give the honest out-of-sample residuals P(over) is
      computed from at score time, the record at the gate, and the kill line;
    - a FINAL fit (eleven seeds) on train + holdout, which is what scores.

    WHY TWO STEPS. This used to write the .pkl and switch `model_registry` in
    one go. The worker deploys from git, so from that moment until the next
    deploy the active row named a file the worker did not have. The order is
    now: fit, commit the artifact, merge and deploy, then register.

    Gate is T_THRESHOLD (default 8.0 points of disagreement with the market
    total), chosen because it was independently the best gate in ALL FOUR
    walk-forward test seasons on corrected snapshots, on the single fit of
    2026-08-25 (seed 42):

        2022 116/206 56.3% +7.5%   <- did not inform the choice
        2023  81/143 56.6% +8.1%
        2024  51/ 90 56.7% +8.2%
        2025  47/ 89 52.8% +0.8%
        pooled 295/528 55.9% +6.7%   95% CI [51.6%, 60.1%]

    That table was one draw: on the frame stored 2026-11-10 the same four
    seasons read 51.5% (seed 42, 244-230) to 56.4% by seed.
    `--walk-forward-totals` prints the average's record beside every single
    seed's. Measured 2026-11-10 for the mean of the eleven, at the stored
    close, -110:

        2022  70/136 51.5%
        2023  76/138 55.1%
        2024  50/ 80 62.5%
        2025  39/ 72 54.2%
        pooled 235/426 55.2%   95% CI [50.4%, 59.9%]   +24.9 units to win one

    HONEST STATUS: the CI does NOT clear the 52.38% breakeven, and for the
    average 8.0 is the best gate in hindsight in 2024 and 2025 only (2022 is
    below breakeven at 8). The gate was not re-chosen with the model; it is
    the one the single fit shipped with. 2022 is the weakest season.
    """
    from datetime import date, datetime
    import pickle

    from features.ncaaf_feature_engine import total_over_prob

    df = load_frame(train_seasons + [holdout], frame_path)
    train = df[df["_season"].isin(train_seasons)]
    hold = df[df["_season"] == holdout]

    tr, cols = _matrix(train, TOTAL_FEATURES)
    ho, _ = _matrix(hold, TOTAL_FEATURES)
    ho_lined = ho.dropna(subset=["_total_line"])

    eval_model = _fit_seed_average(tr[cols], tr["_total"])
    pred_all = eval_model.predict(ho[cols])
    residuals = sorted(float(a - p) for a, p in zip(ho["_total"], pred_all))

    pred = eval_model.predict(ho_lined[cols])
    rows = sweep_total(pred, ho_lined["_total_line"], ho_lined["_total"])
    _print_sweep(f"TOTALS (eval fit, mean of {len(eval_model)} seeds)", rows,
                 line_rmse=rmse(ho_lined["_total_line"], ho_lined["_total"]),
                 model_rmse=rmse(pred, ho_lined["_total"]))

    at_gate = [r for r in rows if r["threshold"] == T_THRESHOLD]
    if not at_gate or not at_gate[0]["bets"]:
        raise SystemExit(f"No bets at the {T_THRESHOLD} gate on the eval fit — "
                         "refusing to write an artifact.")
    gate = at_gate[0]
    if (gate["win_rate"] or 0) <= BREAKEVEN:
        raise SystemExit(
            f"Eval fit is {gate['win_rate']:.4f} at the {T_THRESHOLD} gate, at or "
            f"below the {BREAKEVEN} breakeven — refusing to write an artifact. The "
            "gate no longer reproduces the walk-forward; re-run "
            "--walk-forward-totals.")

    full = pd.concat([tr, ho])
    final_model = _fit_seed_average(full[cols], full["_total"])
    # What the model that SHIPS does with a game served without its weather or
    # venue inputs, on the holdout season's games (in-sample for the final
    # fit, which is fine: this measures where the trees send a missing value,
    # not accuracy).
    shift = missing_input_shift(final_model, ho_lined[cols], ho_lined["_total_line"],
                                T_THRESHOLD)

    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    prob_over = total_over_prob(residuals, T_THRESHOLD)
    prob_under = 1.0 - total_over_prob(residuals, -T_THRESHOLD)
    n = gate["bets"]
    wr = gate["win_rate"] or 0.0
    roi = (wr * (100 / 110) - (1 - wr)) if n else 0.0
    seasons_fitted = sorted(set(train_seasons + [holdout]))
    artifact = {
        "kind": "total_regression",
        "model": final_model,            # models.seed_average.SeedAverage
        "feature_cols": cols,
        "residuals": residuals,          # sorted OOS (actual - pred) totals, the AVERAGE's
        "market": "totals",
        "d_threshold": T_THRESHOLD,
        "prob_at_threshold": prob_over,              # P(over) at +gate
        "prob_under_at_threshold": prob_under,       # P(under) at -gate
        "train_seasons": seasons_fitted,
        "version": version,
        "seeds": list(final_model.seeds),
        # How far a missing weather or venue input moves this model's
        # prediction (missing_input_shift). register_totals reads it.
        "missing_input_shift": shift,
        # The model_registry row register_totals writes. Carried in the file so
        # registering later needs the version and nothing else.
        "registry": {
            "trained_on": date.today().isoformat(),
            "train_seasons": str(seasons_fitted),
            "holdout_season": holdout,
            "holdout_accuracy": round(wr, 4),
            "holdout_roi": round(roi, 4),
            "holdout_picks": n,
            "notes": (f"total regression, mean of {len(final_model)} seeds | "
                      f"gate d>={T_THRESHOLD} | OOS-residual ECDF"),
        },
    }
    out_dir = Path(out_dir) if out_dir is not None else SAVED_DIR
    out = out_dir / f"{TOTALS_MODEL_ID}_{version}.pkl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(artifact, f)

    per_member = eval_model.member_predictions(ho[cols])
    game_sd = (np.std(per_member, axis=0, ddof=1) if len(per_member) > 1
               else np.zeros(per_member.shape[1]))
    wins = gate["wins"]
    nl = chr(10)
    print(f"{nl}Wrote {out} ({out.stat().st_size:,} bytes), version {version}.")
    print(f"  members: {len(final_model)} fits, seeds {list(final_model.seeds)}")
    print(f"  fitted on {seasons_fitted}; eval fit on {sorted(set(train_seasons))}, "
          f"holdout {holdout}")
    print(f"  holdout record at the +/-{T_THRESHOLD} gate: {wins}-{n - wins} "
          f"({wr:.1%}), {units_at_minus_110(wins, n):+.1f} units at -110 to win one")
    print(f"  residuals: {len(residuals)}, mean {float(np.mean(residuals)):+.3f} points")
    print(f"  seed-to-seed standard deviation of one holdout game's prediction: "
          f"mean {float(game_sd.mean()):.2f} points, 95th percentile "
          f"{float(np.quantile(game_sd, 0.95)):.2f}")
    print(f"  P(over) at +{T_THRESHOLD} = {prob_over:.4f}   "
          f"P(under) at -{T_THRESHOLD} = {prob_under:.4f}")
    print(f"  The probability floor in config (MODEL_PROB_THRESHOLDS and "
          f"ACTION_THRESHOLDS,{nl}  '{TOTALS_MODEL_ID}') must sit at or under "
          f"{min(prob_over, prob_under):.4f}, the weaker arm, so it{nl}  never "
          f"suppresses a pick the gate admits. The scorer enforces the gate itself.")
    print(f"{nl}  A game served with an input missing (no weather forecast yet, or no "
          f"known venue),{nl}  on {shift['rows']} holdout games, against the prediction "
          f"as stored:")
    for name, g in shift["groups"].items():
        print(f"    {name:<14} missing: {g['mean']:+6.2f} points on average (sd "
              f"{g['sd']:.2f}); at the gate {g['at_gate_before']} -> {g['at_gate_after']}")
    worst_name, worst = _worst_missing_input(shift)
    refused = abs(worst["mean"]) >= T_THRESHOLD
    if refused:
        print(f"  REGISTRATION WILL BE REFUSED: with the {worst_name} inputs missing the "
              f"prediction moves{nl}  {worst['mean']:+.1f} points, as far as the "
              f"{T_THRESHOLD} gate, so a missing input alone reads as a bet.")
    reg = artifact["registry"]
    print(f"{nl}NOT registered. --register-totals {version} would deactivate the "
          f"active row and write:")
    print(f"  model_id={TOTALS_MODEL_ID} version={version} "
          f"trained_on={reg['trained_on']}")
    print(f"  train_seasons={reg['train_seasons']} holdout_season={reg['holdout_season']}")
    print(f"  holdout_accuracy={reg['holdout_accuracy']} holdout_roi={reg['holdout_roi']} "
          f"holdout_picks={reg['holdout_picks']}")
    print(f"  model_path=models/saved/{out.name}")
    print(f"  notes={reg['notes']}")
    print(f"{nl}Order: commit the artifact (add it to the keep-lists in .gitignore and "
          f"models/saved/MANIFEST.md),{nl}merge and let the worker deploy, and only then "
          f"run --register-totals {version}.")
    if refused:
        print("As it stands that last step refuses this artifact (above): settle what "
              f"the model does{nl}with a game that has no weather forecast or venue yet "
              "before it can go live.")
    return {"version": version, "path": out, "artifact": artifact, "gate": gate}


def _worst_missing_input(shift: dict) -> tuple[str, dict]:
    """The group whose absence moves the prediction furthest on average."""
    return max(shift["groups"].items(), key=lambda kv: abs(kv[1]["mean"]))


def _tracked_by_git(path: Path) -> bool | None:
    """True if git tracks `path`, False if it is in a checkout and untracked,
    None if that cannot be told (no git, or the file is in no checkout)."""
    import subprocess
    path = Path(path)
    try:
        proc = subprocess.run(["git", "ls-files", "--error-unmatch", path.name],
                              cwd=path.parent, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except OSError:
        return None
    if proc.returncode == 0:
        return True
    return False if proc.returncode == 1 else None


def register_totals(version: str, saved_dir=None,
                    accept_missing_input_shift: bool = False) -> str:
    """
    Make a fitted totals artifact the active `ncaaf_over_under`. A PRODUCTION
    WRITE, and a model update: it changes which file scores.

    Run it only after the artifact is committed, merged and deployed, because
    the worker opens the path this row names. What can be checked from here is
    checked: the file exists, is the totals artifact of that version, and git
    tracks it (an untracked file is in no deploy). Whether the deploy has
    finished cannot be seen from this machine.

    REFUSED when a missing input alone would read as a bet: the artifact's own
    measurement (missing_input_shift) says that with its weather or venue
    inputs missing the prediction moves, on average, as far as the gate. The
    scorer serves a game that way when it has no weather forecast yet, and a
    pick locks the first time the gate is crossed. `accept_missing_input_shift`
    registers it anyway, for when serving has been changed so the model never
    sees such a row; an artifact that never measured it is refused the same way.

    The bytes are copied into `model_artifacts` BEFORE the row that names them
    is written, the same order models/trainer._register_model uses, so the
    worker can restore the file if a container ever lacks it.
    """
    import pickle

    from loguru import logger

    saved = Path(saved_dir) if saved_dir is not None else SAVED_DIR
    path = saved / f"{TOTALS_MODEL_ID}_{version}.pkl"
    if not path.exists():
        raise SystemExit(f"No artifact for version {version}: {path} does not exist. "
                         "Fit it with --fit-totals, commit, merge and deploy first.")
    with open(path, "rb") as f:
        artifact = pickle.load(f)
    if not isinstance(artifact, dict) or artifact.get("kind") != "total_regression":
        raise SystemExit(f"{path.name} is not a total_regression artifact — "
                         "refusing to register it.")
    if artifact.get("version") != version or "registry" not in artifact:
        raise SystemExit(f"{path.name} says it is version {artifact.get('version')!r} "
                         "or carries no registry row — refusing to register it.")
    if _tracked_by_git(path) is False:
        raise SystemExit(f"{path.name} is not tracked by git. The worker deploys from "
                         "git, so a registry row naming it would point at a file the "
                         "worker does not have. Commit, merge and deploy it first.")
    if not accept_missing_input_shift:
        shift = artifact.get("missing_input_shift")
        gate = float(artifact.get("d_threshold") or 0.0)
        if not shift or not shift.get("groups"):
            raise SystemExit(
                f"{path.name} did not measure what a missing weather or venue input "
                "does to its prediction — refusing to register it. Refit it with "
                "--fit-totals, which measures it.")
        name, worst = _worst_missing_input(shift)
        if abs(worst["mean"]) >= gate:
            raise SystemExit(
                f"{path.name}: with the {name} inputs missing its prediction moves "
                f"{worst['mean']:+.1f} points on average ({worst['at_gate_before']} -> "
                f"{worst['at_gate_after']} of {shift['rows']} holdout games at the "
                f"{gate} gate). The scorer serves a game that way when it has no "
                "weather forecast or no known venue yet, so a missing input alone "
                "would read as a bet, and a pick locks at the first crossing. "
                "Refusing to register. Settle what the model does with such a game "
                "first (docs/sports/ncaaf.md), or pass --accept-missing-input-shift "
                "if serving now guarantees those inputs.")

    reg = artifact["registry"]
    model_path = f"models/saved/{path.name}"

    from data.db import get_connection
    from models.trainer import _store_artifact

    conn = get_connection()
    try:
        _store_artifact(conn, TOTALS_MODEL_ID, version, path.resolve())
        conn.execute("""
            UPDATE model_registry SET is_active = 0
            WHERE model_id = 'ncaaf_over_under' AND is_active = 1
        """)
        conn.execute("""
            INSERT INTO model_registry (
                model_id, version, trained_on, train_seasons, holdout_season,
                holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                is_active, model_path, notes
            ) VALUES ('ncaaf_over_under', %s, %s, %s, %s, %s, %s, %s, NULL, 1, %s, %s)
            ON CONFLICT (model_id, version) DO UPDATE SET
                trained_on       = EXCLUDED.trained_on,
                holdout_accuracy = EXCLUDED.holdout_accuracy,
                holdout_roi      = EXCLUDED.holdout_roi,
                holdout_picks    = EXCLUDED.holdout_picks,
                is_active        = 1,
                model_path       = EXCLUDED.model_path,
                notes            = EXCLUDED.notes
        """, (version, reg["trained_on"], reg["train_seasons"], reg["holdout_season"],
              reg["holdout_accuracy"], reg["holdout_roi"], reg["holdout_picks"],
              model_path, reg["notes"]))
        conn.commit()
    finally:
        conn.close()

    logger.success(f"Registered {TOTALS_MODEL_ID} v{version} ({reg['notes']})")
    print(f"Active {TOTALS_MODEL_ID} is now {model_path}.")
    print("Then: python -m data.threshold_sync")
    return version


def _build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seasons", nargs="+", type=int,
                    default=[2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024])
    ap.add_argument("--holdout", type=int, default=2025)
    ap.add_argument("--fit-totals", action="store_true",
                    help="Fit the production TOTALS artifact (mean of eleven "
                         "seeds; gate NCAAF_TOTAL_D_THRESHOLD, default 8.0) and "
                         "write it. Registers nothing: see --register-totals")
    ap.add_argument("--register-totals", metavar="VERSION",
                    help="Make a fitted totals artifact the active model. A "
                         "production write: run it after the artifact is "
                         "committed, merged and deployed")
    ap.add_argument("--accept-missing-input-shift", action="store_true",
                    help="With --register-totals: register an artifact whose "
                         "prediction moves as far as the gate when its weather or "
                         "venue inputs are missing. Only once serving guarantees "
                         "the model never sees such a game")
    ap.add_argument("--walk-forward-totals", nargs="*", type=int, metavar="SEASON",
                    help="Totals only: the mean of eleven seeds against each "
                         "single seed, each season fitted on PRIOR seasons "
                         "(default: 2022 2023 2024 2025)")
    ap.add_argument("--frame", metavar="FILE",
                    help="Read the training frame from this pickle (one "
                         "build_frames wrote) instead of the database. For "
                         "--fit-totals and --walk-forward-totals only")
    ap.add_argument("--fit", action="store_true",
                    help="Fit + register the production margin artifact "
                         "(only after the harness verdict passed)")
    ap.add_argument("--walk-forward", nargs="*", type=int, metavar="SEASON",
                    help="Honest multi-season record: each season predicted by "
                         "a model trained only on PRIOR seasons "
                         "(default: 2023 2024 2025)")
    return ap


if __name__ == "__main__":
    ap = _build_parser()
    args = ap.parse_args()
    if args.frame and not (args.fit_totals or args.walk_forward_totals is not None):
        ap.error("--frame is read by --fit-totals and --walk-forward-totals only")
    if args.register_totals:
        register_totals(args.register_totals,
                        accept_missing_input_shift=args.accept_missing_input_shift)
        sys.exit(0)
    if args.walk_forward_totals is not None:
        tests = args.walk_forward_totals or [2022, 2023, 2024, 2025]
        pool = sorted(set(args.seasons + [args.holdout] + tests))
        res = walk_forward_totals(pool, tests, frame_path=args.frame)
        _print_walk_forward(res, market="TOTALS")
        _print_totals_seed_evidence(res)
        sys.exit(0)
    if args.walk_forward is not None:
        tests = args.walk_forward or [2023, 2024, 2025]
        pool = sorted(set(args.seasons + [args.holdout] + tests))
        _print_walk_forward(walk_forward(pool, tests), market="SPREAD")
        res = walk_forward_totals(pool, tests)
        _print_walk_forward(res, market="TOTALS")
        _print_totals_seed_evidence(res)
        sys.exit(0)
    if args.fit_totals:
        fit_totals(args.seasons, args.holdout, frame_path=args.frame)
        sys.exit(0)
    if args.fit:
        fit_and_register(args.seasons, args.holdout)
        sys.exit(0)
    sys.exit(main(args.seasons, args.holdout))
