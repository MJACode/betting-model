"""
mlb_over_under_sweep.py — re-derive the `mlb_over_under` threshold on real
DraftKings totals prices, with a mechanical plateau check.

WHY THIS EXISTS
---------------
`mlb_over_under` is paused. Its last honest-era graded record (the NaN-line
fix from 2026-07-05 onward) did not clear a cut, and
`scripts/calibrated_threshold_sweep` can only replay LIVE GRADED PICKS — every
row in `picks` was produced by the current artifact, so a sweep on those
predictions measures a model that a 2019-2025 / holdout-2026 retrain would
replace. A cut swept on a dead model's predictions is a leftover, not a cut.

This is the totals twin of `scripts/mlb_runline_sweep.py`. A model retrained
on 2019-2025 with 2026 held out is scored here against real pre-game DK
totals prices. `--artifact` is how a `--no-register` retrain stays honest:
the sweep loads THAT pickle, not the live `model_registry` row.

    python -m scripts.mlb_over_under_sweep --seasons 2026
    python -m scripts.mlb_over_under_sweep --seasons 2026 --csv /tmp/ou.csv
    python -m scripts.mlb_over_under_sweep --seasons 2026 --artifact models/saved/_baseline/mlb_over_under_….pkl

Run it where the DB is reachable (Railway worker or Matt's machine) — the
dev sandbox has neither psycopg2 nor DATABASE_URL.

READ THE OUTPUT LIKE THIS
-------------------------
  * The `PROB REACH` block is the first thing to check. If the model never
    reaches a candidate prob floor, that floor is unusable no matter how good
    its ROI looks — that is how `mlb_runline` went dormant.
  * Ignore thin cells. A 15-bet +30% cell is noise.
  * Take a cut from a PLATEAU, not a peak. `nbrs+` counts how many of a
    cell's 8 neighbours are also positive.
  * Check `over_pct`. A grid that is 100% one side is a systematic lean, not
    per-game skill.
  * If the whole grid is negative, the honest answer is that the model needs
    feature work and should stay off. Do NOT ship the least-bad cell.

Nothing here writes a threshold, pauses, or unpauses. That is a model update
and needs a person's name on it (§1b).
"""

import argparse
import pickle
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
config.assert_retrain_allowed("MLB", what="threshold sweep")
from data.db import get_connection
from features.feature_engine import (
    FEATURE_MAP,
    HANDICAP_SPARSE_FEATURES,
    _build_bulk_mlb_lookups,
    _build_mlb_features_from_bulk,
    _is_pregame_snapshot,
    feature_matrix,
)
from models.scorer import american_to_implied_prob, american_to_decimal
from models.trainer import load_model

# Grid bounds and the plateau check are market-agnostic. Importing them keeps
# ONE definition of "what a trustworthy cell looks like" rather than a totals
# copy that can drift from runline / F5 (scripts/mlb_f5_sweep.py does the same).
from scripts.mlb_runline_sweep import (
    EDGE_FLOORS,
    PROB_FLOORS,
    plateau_score,
)

MODEL_ID = "mlb_over_under"


def _load_artifact(path: str | None = None) -> dict:
    """Active registry model, or a just-trained pickle that was not registered.

    A `--no-register` retrain writes to `models/saved/_baseline/` and leaves
    `model_registry` alone. The honest 2019-2025 / holdout-2026 sweep has to
    score THAT pickle, not the live in-sample artifact `load_model` would
    return. `--artifact` is how; omitting it keeps a live-artifact CLI path.
    """
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = Path(__file__).resolve().parent.parent / p
        if not p.is_file():
            raise SystemExit(f"artifact not found: {p}")
        with open(p, "rb") as f:
            artifact = pickle.load(f)
        logger.info(f"loaded candidate artifact {p}")
        return artifact
    artifact = load_model(MODEL_ID)
    if not artifact:
        raise SystemExit(f"No active model artifact for {MODEL_ID} — train it first.")
    return artifact


def _fetch_games(conn, seasons: list[int]) -> list[dict]:
    """Completed MLB games in the requested seasons."""
    placeholders = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT game_id, game_date, home_team, away_team,
               home_score, away_score, commence_time
        FROM games
        WHERE sport = 'MLB'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND CAST(SUBSTR(game_date, 1, 4) AS INTEGER) IN ({placeholders})
        ORDER BY game_date, game_id
    """, seasons).fetchall()
    return [
        dict(game_id=r[0], game_date=r[1], home_team=r[2], away_team=r[3],
             home_score=float(r[4]), away_score=float(r[5]), commence_time=r[6])
        for r in rows
    ]


def _pregame_odds(conn) -> dict:
    """
    (game_id) → newest genuinely PRE-GAME DK totals row.

    Same leak bound as `mlb_runline_sweep._pregame_odds` and the bulk loader:
    `snapshot_type != 'in_play'` is not enough — the evening refresh has written
    post-start rows as `open`, so `_is_pregame_snapshot` is the real cutoff.

    Deliberately independent of the bulk loader's odds dict so the GRADING
    prices are verified pre-game here too — a post-start price would distort ROI
    even when the feature line is clean (the session-106 leak class).
    """
    rows = conn.execute("""
        SELECT o.game_id, o.snapshot_at, g.commence_time,
               o.total_line, o.over_price, o.under_price
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'MLB'
          AND o.market = 'totals'
          AND o.bookmaker = 'draftkings'
          AND o.snapshot_type != 'in_play'
          AND o.total_line IS NOT NULL
        ORDER BY o.game_id, o.snapshot_at DESC
    """).fetchall()

    out: dict = {}
    for gid, snap, commence, total_line, over_p, under_p in rows:
        if gid in out:
            continue                                   # newest-first: first kept
        if not _is_pregame_snapshot(snap, commence):
            continue                                   # post-start → leaked
        out[gid] = dict(total_line=total_line, over_price=over_p,
                        under_price=under_p, snapshot_at=snap)
    return out


def _side_rows(game: dict, prob_over: float, odds: dict) -> list[dict]:
    """
    One row per bettable side with the model prob, real pre-game price, edge and
    whether that side actually won.

    Grading convention — MUST match paper_tracker._compute_result and
    features.feature_engine._compute_target for market='totals':
        over  wins iff (home + away) > total_line
        under wins iff (home + away) < total_line
    `scored_line` is the total. A push (exact line) emits no row — training
    drops those as target=None, so scoring them as losses would understate
    every cut. Model P(over) is the classifier's class-1 probability (the
    scorer repurposes home_prob as over_prob).

    THE PRICE FLOOR IS PART OF THE SWEEP, not a filter applied afterwards.
    `config.min_odds_for` is what the scorer enforces, so a cell measured on
    bets below it is measured on bets the scorer REFUSES (the 2026-08-31
    lesson in scripts/mlb_f5_sweep.py / calibrated_threshold_sweep).
    """
    line = odds.get("total_line")
    if line is None:
        return []

    total = game["home_score"] + game["away_score"]
    if total == float(line):
        return []                                       # push

    won = {"over": total > float(line), "under": total < float(line)}
    price = {"over": odds.get("over_price"), "under": odds.get("under_price")}
    prob = {"over": prob_over, "under": 1.0 - prob_over}
    floor = config.min_odds_for(MODEL_ID)

    rows: list[dict] = []
    for side in ("over", "under"):
        american = price[side]
        if american is None:
            continue
        if floor is not None and american < floor:
            continue
        implied = american_to_implied_prob(american)
        if not implied:
            continue
        stake = 100.0
        profit = (stake * (american_to_decimal(american) - 1.0)
                  if won[side] else -stake)
        rows.append(dict(
            game_id=game["game_id"], game_date=game["game_date"], side=side,
            total_line=float(line), model_prob=prob[side],
            dk_odds=float(american), implied=implied,
            edge=prob[side] - implied, won=bool(won[side]),
            stake=stake, profit=profit,
        ))
    return rows


def build_side_table(seasons: list[int],
                     artifact_path: str | None = None) -> pd.DataFrame:
    """Score every completed game and return one row per bettable side."""
    artifact = _load_artifact(artifact_path)
    clf = artifact["model"]
    # Artifact list wins: FEATURE_MAP growing must not reshape an old pickle.
    feature_cols = list(artifact.get("feature_cols") or FEATURE_MAP[MODEL_ID])

    conn = get_connection()
    try:
        games = _fetch_games(conn, seasons)
        if not games:
            raise SystemExit(f"No completed MLB games found for seasons {seasons}.")
        odds_by_game = _pregame_odds(conn)
        logger.info(f"{len(games)} completed games; "
                    f"{len(odds_by_game)} have a pre-game DK total")
        bulk = _build_bulk_mlb_lookups(
            conn, seasons,
            include_handicap=any(c in HANDICAP_SPARSE_FEATURES for c in feature_cols),
        )
    finally:
        conn.close()

    rows: list[dict] = []
    skipped_no_odds = skipped_no_features = 0

    for game in games:
        odds = odds_by_game.get(game["game_id"])
        if not odds:
            skipped_no_odds += 1
            continue

        season = int(game["game_date"][:4])
        feats = _build_mlb_features_from_bulk(
            bulk, game["game_id"], game["game_date"],
            game["home_team"], game["away_team"], season,
            # Feed the verified pre-game totals row so the model sees exactly
            # what live scoring would have seen. `total_line` is the top
            # totals feature, and feeding NaN here is the 2026-07-05 bug —
            # so this must never be omitted.
            odds_row=odds,
        )
        if not feats:
            skipped_no_features += 1
            continue

        X = feature_matrix(feats, feature_cols)
        if X.isnull().all(axis=1).iloc[0]:
            skipped_no_features += 1
            continue

        prob_over = float(clf.predict_proba(X)[0][1])
        rows.extend(_side_rows(game, prob_over, odds))

    logger.info(f"skipped: {skipped_no_odds} no pre-game total, "
                f"{skipped_no_features} no features")
    return pd.DataFrame(rows)


def sweep(df: pd.DataFrame, min_bets: int) -> pd.DataFrame:
    """Grid prob x edge over the side table; flat $100 stakes at real DK prices."""
    out = []
    for pf in PROB_FLOORS:
        for ef in EDGE_FLOORS:
            sel = df[(df.model_prob >= pf) & (df.edge >= ef)]
            if len(sel) == 0:
                continue
            staked = sel.stake.sum()
            profit = sel.profit.sum()
            wins = int(sel.won.sum())
            over = int((sel.side == "over").sum())
            out.append(dict(
                min_prob=pf, min_edge=ef, bets=len(sel),
                wins=wins, losses=len(sel) - wins,
                win_pct=round(100.0 * wins / len(sel), 1),
                units=round(profit / 100.0, 2),
                roi_pct=round(100.0 * profit / staked, 2),
                over_pct=round(100.0 * over / len(sel), 0),
                thin=len(sel) < min_bets,
            ))
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", nargs="+", type=int, default=[2026],
                    help="seasons to sweep (default 2026 — the holdout season "
                         "for the honest retrain)")
    ap.add_argument("--min-bets", type=int, default=30,
                    help="cells thinner than this are excluded from the "
                         "recommendation (default 30)")
    ap.add_argument("--csv", help="also write the raw side table here")
    ap.add_argument("--artifact", default=None,
                    help="measure this .pkl instead of the registered active "
                         "one — for a --no-register retrain that must not swap live")
    args = ap.parse_args()

    df = build_side_table(args.seasons, artifact_path=args.artifact)
    if df.empty:
        raise SystemExit("No gradable sides — check that games have pre-game totals.")

    if args.csv:
        df.to_csv(args.csv, index=False)
        logger.info(f"wrote side table → {args.csv}")

    print(f"\n=== {MODEL_ID} — sweep on real DK totals prices, "
          f"seasons {args.seasons} ===")
    print(f"{len(df)} bettable sides across {df.game_id.nunique()} games")

    # ── PROB REACH ────────────────────────────────────────────────────────────
    # The dormancy check. A prob floor the model never reaches cannot produce a
    # single pick, however good its ROI looks in the grid.
    print(f"\n--- PROB REACH (model prob range "
          f"{df.model_prob.min():.3f} – {df.model_prob.max():.3f}) ---")
    for bar in (0.50, 0.55, 0.59, 0.60, 0.65, 0.68, 0.70):
        n = int((df.model_prob >= bar).sum())
        flag = "  <-- UNREACHABLE" if n == 0 else ""
        print(f"  sides at prob >= {bar:.2f}: {n:5d}{flag}")

    grid = sweep(df, args.min_bets)
    if grid.empty:
        print("\nNo gradable cells at all.")
        return

    usable = grid[~grid.thin]
    if usable.empty:
        print(f"\nNo cell reaches {args.min_bets} bets — sample too thin to cut on.")
        return

    usable = usable.sort_values("roi_pct", ascending=False)
    print(f"\n--- top cells (>= {args.min_bets} bets, by ROI) ---")
    show = usable.head(20).copy()
    show["nbrs+"] = [f"{plateau_score(grid, r.min_prob, r.min_edge)[0]}"
                     f"/{plateau_score(grid, r.min_prob, r.min_edge)[1]}"
                     for r in show.itertuples()]
    print(show[["min_prob", "min_edge", "bets", "wins", "losses", "win_pct",
                "units", "roi_pct", "over_pct", "nbrs+"]].to_string(index=False))

    best = usable.iloc[0]
    if best.roi_pct <= 0:
        print("\nVERDICT: every cell with real volume is negative. The honest "
              "answer is that this model needs FEATURE work, not a re-cut — "
              "leave it off and do not ship the least-bad cell.")
        return

    pos, tot = plateau_score(grid, best.min_prob, best.min_edge)
    print(f"\nBest cell: {best.min_prob:.2f}/{best.min_edge:.2f} = "
          f"{int(best.bets)} bets {int(best.wins)}-{int(best.losses)} "
          f"{best.roi_pct:+.2f}% ROI  ({int(best.over_pct)}% over)")
    print(f"Plateau: {pos}/{tot} neighbouring cells are also positive.")
    if tot and pos / tot >= 0.6:
        print("VERDICT: this sits on a plateau — safe to ship as the cut, and it "
              "IS reachable (see PROB REACH above). Re-sweep after ~40 settled "
              "forward picks.")
    else:
        print("VERDICT: this is a PEAK, not a plateau — its neighbours flip "
              "negative one grid step away. Shipping it would be fitting noise "
              "(the session-74/87 mistake). Prefer a lower-ROI cell with "
              "positive neighbours, or leave the model off.")


if __name__ == "__main__":
    main()
