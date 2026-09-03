"""Re-derive the `mlb_f5_moneyline` cut on real DK first-five prices, out of sample.

WHY THIS EXISTS
---------------
`mlb_f5_moneyline` was retrained 2026-09-03 (v20260903_163809) after
`mlb_pitcher_stats` was rebuilt — the old table carried each starter's
SEASON-FINAL ERA on every start, and `d_starter_era` + `d_starter_era_last3`
were 40% of the model. `docs/team_stats_leak.md` has the evidence.

**Its threshold did not survive that.** `ACTION_THRESHOLDS` holds 0.74/0.00,
derived by `scripts/calibrated_threshold_sweep` from the model's LIVE GRADED
RECORD. That tool cannot be used here: every graded pick in `picks` was produced
by the OLD artifact, so replaying them measures a model that no longer exists.
A cut swept on a dead model's predictions is not a cut, it is a leftover.

So this follows the `mlb_runline_sweep` pattern instead — score a held-out
season with the NEW artifact and sweep those predictions against real prices.
`config.PAUSED_MODELS` names exactly that route as the runline unpause path,
for exactly this reason.

WHY 2026 IS THE RIGHT SEASON, AND THE ONE CAVEAT
------------------------------------------------
2026 is the ONLY season carrying DK first-five moneyline prices — 1,425 priced
games; 2019-2025 have none at all. It is also the season held out of the
retrain. So for once the sweep season and the out-of-sample season are the same
season, which is the strongest form this measurement can take here.

The caveat, stated rather than buried: it is ONE season and one draw. A cut
taken from it is PROVISIONAL and is validated by the paper phase, not by this
script. §2's go-live gate (>=50 settled picks, positive flat ROI, calibration
<=5%) is what actually clears the model, and a retrain resets it.

    python -m scripts.mlb_f5_sweep
    python -m scripts.mlb_f5_sweep --seasons 2026 --csv /tmp/f5.csv

READ THE OUTPUT LIKE THIS
-------------------------
  * **PROB REACH first.** If the model never reaches a candidate floor, that
    floor is unusable however good its ROI looks — that is precisely how
    `mlb_runline` went dormant for six weeks while looking live in config.
  * **Plateau, not peak** (sessions 68/74/87/101). A cell whose neighbours flip
    negative one grid step away is noise. The neighbourhood is printed.
  * **A negative grid is an allowed answer.** If nothing clears, the honest
    result is that the model stays where it is and needs feature work. Do NOT
    ship the least-bad cell.

Nothing here writes a threshold. That is a model update and needs a person's
name on it (§1b).
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection
from features.feature_engine import (
    FEATURE_MAP,
    _build_bulk_mlb_lookups,
    _build_mlb_features_from_bulk,
    _is_pregame_snapshot,
)
from models.scorer import american_to_decimal, american_to_implied_prob
from models.trainer import load_model

# The grid, the flat-stake sweep and the plateau check are market-agnostic —
# they take a side table and know nothing about run lines. Importing them keeps
# ONE definition of "what a trustworthy cell looks like" rather than two that
# can drift apart (§1b).
from scripts.mlb_runline_sweep import (
    EDGE_FLOORS,
    PROB_FLOORS,
    plateau_score,
    sweep,
)

MODEL_ID = "mlb_f5_moneyline"


def _fetch_games(conn, seasons: list[int]) -> list[dict]:
    """Completed MLB games that have a FIRST-FIVE result.

    `home_score_f5` is the target's source, and a game without it cannot be
    graded — it is not a loss, it is not a row.
    """
    placeholders = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT game_id, game_date, home_team, away_team,
               home_score, away_score, home_score_f5, away_score_f5,
               commence_time, first_pitch_at
        FROM games
        WHERE sport = 'MLB'
          AND home_score_f5 IS NOT NULL
          AND away_score_f5 IS NOT NULL
          AND CAST(SUBSTR(game_date, 1, 4) AS INTEGER) IN ({placeholders})
        ORDER BY game_date, game_id
    """, seasons).fetchall()
    return [
        dict(game_id=r[0], game_date=r[1], home_team=r[2], away_team=r[3],
             home_score=r[4], away_score=r[5],
             home_score_f5=float(r[6]), away_score_f5=float(r[7]),
             commence_time=r[8], first_pitch_at=r[9])
        for r in rows
    ]


def _pregame_odds(conn) -> dict:
    """(game_id) → newest genuinely PRE-GAME DK first-five moneyline row.

    Bounded on the ACTUAL first pitch where it is trustworthy, not only on the
    scheduled `commence_time`, which runs ~16 minutes late against reality — the
    permissive direction, and the one that makes a backtest look clever. Uses
    the same `_is_pregame_snapshot` the feature engine does, so the grading
    price is held to the same standard as the features.
    """
    rows = conn.execute("""
        SELECT o.game_id, o.snapshot_at, g.commence_time, g.first_pitch_at,
               o.home_price, o.away_price
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'MLB'
          AND o.market = 'h2h_1st_5_innings'
          AND o.bookmaker = 'draftkings'
          AND COALESCE(o.snapshot_type, '') != 'in_play'
          AND o.home_price IS NOT NULL
          AND o.away_price IS NOT NULL
        ORDER BY o.game_id, o.snapshot_at DESC
    """).fetchall()

    out: dict = {}
    for gid, snap, commence, first_pitch, home_p, away_p in rows:
        if gid in out:
            continue                                   # newest-first: first kept
        if not _is_pregame_snapshot(snap, commence, first_pitch):
            continue                                   # post-start → leaked
        out[gid] = dict(home_price=home_p, away_price=away_p, snapshot_at=snap)
    return out


def _side_rows(game: dict, prob_home: float, odds: dict) -> list[dict]:
    """One row per bettable side: model prob, real pre-game price, edge, result.

    A first-five TIE is a PUSH and produces no row. That matches
    `_derive_target`, which returns None on `home_score_f5 == away_score_f5`
    rather than scoring it as a loss — grading a push as a loss would understate
    every cut in the grid by roughly the tie rate.
    """
    if game["home_score_f5"] == game["away_score_f5"]:
        return []

    home_won = game["home_score_f5"] > game["away_score_f5"]
    won = {"home": home_won, "away": not home_won}
    price = {"home": odds.get("home_price"), "away": odds.get("away_price")}
    prob = {"home": prob_home, "away": 1.0 - prob_home}

    rows: list[dict] = []
    for side in ("home", "away"):
        american = price[side]
        if american is None:
            continue
        implied = american_to_implied_prob(american)
        if not implied:
            continue
        stake = 100.0
        profit = (stake * (american_to_decimal(american) - 1.0)
                  if won[side] else -stake)
        rows.append(dict(
            game_id=game["game_id"], game_date=game["game_date"], side=side,
            model_prob=prob[side], dk_odds=float(american), implied=implied,
            edge=prob[side] - implied, won=bool(won[side]),
            stake=stake, profit=profit,
        ))
    return rows


def build_side_table(seasons: list[int]) -> pd.DataFrame:
    """Score every gradeable game with the ACTIVE artifact; one row per side."""
    artifact = load_model(MODEL_ID)
    if not artifact:
        raise SystemExit(f"No active model artifact for {MODEL_ID} — train it first.")
    clf = artifact["model"]
    feature_cols = FEATURE_MAP[MODEL_ID]

    conn = get_connection()
    try:
        games = _fetch_games(conn, seasons)
        if not games:
            raise SystemExit(f"No completed MLB games with an F5 result in {seasons}.")
        odds_by_game = _pregame_odds(conn)
        logger.info(f"{len(games)} games with an F5 result; "
                    f"{len(odds_by_game)} have a pre-game DK first-five price")
        bulk = _build_bulk_mlb_lookups(conn, seasons)
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
        # F5 models are featurised from the FULL-GAME h2h row, not the F5 one
        # -- `build_training_dataset` does exactly this
        # (`feat_odds = ... bulk['odds'].get((game_id, 'h2h'))`). Feeding the F5
        # price here instead would score every game on a feature vector the
        # model was never trained against.
        feats = _build_mlb_features_from_bulk(
            bulk, game["game_id"], game["game_date"],
            game["home_team"], game["away_team"], season,
            odds_row=bulk["odds"].get((game["game_id"], "h2h")))
        if not feats:
            skipped_no_features += 1
            continue

        X = pd.DataFrame([{c: feats.get(c) for c in feature_cols}])[feature_cols]
        # Mirror training's `dropna(subset=strict_cols)`. ALL 25 f5 features are
        # strict -- none is in SPARSE_OK_FEATURES -- so a row with any null was
        # never in the training population and must not be scored here either.
        # (It also keeps the frame numeric: one None makes the column `object`
        # and XGBoost refuses it outright.)
        X = X.apply(pd.to_numeric, errors="coerce")
        if X.isnull().any(axis=1).iloc[0]:
            skipped_no_features += 1
            continue

        prob_home = float(clf.predict_proba(X)[0][1])
        rows.extend(_side_rows(game, prob_home, odds))

    logger.info(f"skipped: {skipped_no_odds} no pre-game F5 price, "
                f"{skipped_no_features} no features")
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", nargs="+", type=int, default=[2026],
                    help="default 2026 — the only season with DK F5 prices, "
                         "and the season held out of the retrain")
    ap.add_argument("--min-bets", type=int, default=30,
                    help="cells below this are marked thin and never endorsed")
    ap.add_argument("--csv", help="also write the raw side table here")
    args = ap.parse_args()

    df = build_side_table(args.seasons)
    if df.empty:
        raise SystemExit("No gradeable sides — nothing to sweep.")
    if args.csv:
        df.to_csv(args.csv, index=False)

    print(f"\n=== {MODEL_ID} — sweep on real DK first-five prices, "
          f"seasons {args.seasons} ===")
    print(f"{len(df)} bettable sides across {df.game_id.nunique()} games\n")

    # PROB REACH. A floor the model never reaches is unusable however good its
    # ROI looks -- this is the check that would have caught mlb_runline going
    # dormant six weeks before anyone noticed.
    print("PROB REACH — how often the model even reaches each floor")
    for pf in PROB_FLOORS:
        n = int((df.model_prob >= pf).sum())
        bar = "#" * min(40, n // 10)
        print(f"  p >= {pf:.2f}  {n:5d} sides  {bar}")
    print(f"  max model probability observed: {df.model_prob.max():.3f}")

    grid = sweep(df, args.min_bets)
    if grid.empty:
        raise SystemExit("Grid is empty at every cell.")

    live = grid[~grid.thin].sort_values("roi_pct", ascending=False)
    print(f"\nTOP CELLS with >= {args.min_bets} bets")
    if live.empty:
        print("  NONE — every cell is thin. One season does not support a cut.")
    else:
        print(live.head(12).to_string(index=False))

        best = live.iloc[0]
        pos, tot = plateau_score(grid, best.min_prob, best.min_edge)
        print(f"\nBEST CELL  prob >= {best.min_prob:.2f}, edge >= {best.min_edge:.2f}"
              f"  |  {int(best.bets)} bets, {best.win_pct}%, "
              f"{best.roi_pct:+.2f}% ROI, {best.units:+.2f}u")
        print(f"PLATEAU    {pos}/{tot} neighbouring cells positive")
        if tot and pos / tot < 0.5:
            print("  ^ ISOLATED PEAK — the neighbourhood does not agree. "
                  "This is the shape sessions 74 and 87 had to retract.")

        # A TIME SPLIT KILLS MOST FALSE POSITIVES, and it belongs in the method
        # rather than in a follow-up. Every situational edge in the NCAAF search
        # that looked strong pooled collapsed once split early/late.
        sel = df[(df.model_prob >= best.min_prob) & (df.edge >= best.min_edge)]
        cut = sel.game_date.sort_values().iloc[len(sel) // 2]
        print("\nTIME SPLIT of the best cell (a cut that only works in one "
              "half is not a cut)")
        for label, part in (("first half ", sel[sel.game_date <= cut]),
                            ("second half", sel[sel.game_date > cut])):
            if part.empty:
                print(f"  {label}: no bets")
                continue
            roi = 100.0 * part.profit.sum() / part.stake.sum()
            w = int(part.won.sum())
            print(f"  {label}: {len(part):3d} bets  {w:3d}-{len(part) - w:<3d} "
                  f"{100.0 * w / len(part):5.1f}%  {roi:+7.2f}% ROI")

    print(f"\nCurrent cut in config: "
          f"{__import__('config').ACTION_THRESHOLDS.get(MODEL_ID)}")
    print("\nNothing was written. A threshold change is a model update and "
          "needs a person's name on it (§1b).")


if __name__ == "__main__":
    main()
