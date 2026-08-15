"""
wnba_line_sweep.py — re-derive wnba_over_under / wnba_spread thresholds on
LEAK-FREE (pre-tipoff) DraftKings lines.

WHY THIS EXISTS
---------------
Both models launched 2026-07-19 on cuts taken from a "2026 OOS sweep vs real DK
lines" (O/U 0.60/0.06 = 23 bets 60.9% +14.5%; spread 0.60/0.10 = 34 bets 64.7%
+22.6%). That sweep ran through `build_bulk_wnba_lookups`, which selected the
LATEST odds snapshot per (game_id, market) with no pre-tipoff cutoff. The evening
refresh loop runs to 11pm ET and writes post-start rows as snapshot_type='open',
so 89 of 133 completed 2026 games (67%) were featurized with a totals line that
had already drifted toward the final score — average leak 8.2 points, worst 47
(spreads: 86/133, avg 4.6, worst 41). `total_line` / `spread_home` is the top
feature of both models, so that sweep was partly reading the outcome it was
predicting, and both cuts are invalid. Both models are PAUSED pending this script.

The leak is fixed at the read side by `_is_pregame_snapshot`
(features/feature_engine.py), so this script — which goes through the same bulk
loader — is automatically clean. It exists to produce the numbers needed to
either unpause on a validated cut or confirm the models need feature work.

WHAT IT DOES
------------
1. Scores every completed WNBA game in the requested seasons through the fixed
   bulk feature path (identical code to training/backtest).
2. Grades BOTH sides of every game against the pre-tipoff line and the real
   pre-tipoff DK prices for that side.
3. Sweeps prob x edge and prints the grid, so a cut is chosen from a plateau
   rather than a thin peak (the repeated lesson from sessions 68/74/101).

Run where the DB is reachable (Railway worker or Matt's machine) — the dev
sandbox has neither psycopg2 nor DATABASE_URL:

    python -m scripts.wnba_line_sweep --model wnba_over_under --seasons 2026
    python -m scripts.wnba_line_sweep --model wnba_spread     --seasons 2026
    python -m scripts.wnba_line_sweep --model wnba_over_under --seasons 2026 --csv /tmp/ou.csv

READ THE OUTPUT LIKE THIS
-------------------------
  * Ignore any cell under ~25 bets — WNBA is a short season and thin cells are noise.
  * Prefer a cut whose NEIGHBOURS are also positive (a plateau). A +20% cell
    surrounded by negatives is an artifact, not an edge.
  * If the whole grid is negative, the honest answer is to leave the model paused
    and do feature work — do NOT pick the least-bad cell.
  * The `both_sides` column is a sanity check: a real edge should not be 100%
    one-directional. An all-over or all-under grid usually means the model is
    reading a systematic line offset (the synthetic-vs-real-line covariate shift
    these models are exposed to), not genuine per-game skill.
"""

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection
from features.feature_engine import FEATURE_MAP, _is_pregame_snapshot
from features.wnba_feature_engine import (
    build_bulk_wnba_lookups,
    build_wnba_features_from_bulk,
)
from models.scorer import american_to_implied_prob, american_to_decimal
from models.trainer import load_model

# model_id → (odds market, side-A label, side-B label)
_MARKETS = {
    "wnba_over_under": ("totals", "over", "under"),
    "wnba_spread": ("spreads", "home", "away"),
}


def _fetch_games(conn, seasons: list[int]) -> list[dict]:
    """Completed WNBA games in the requested seasons (season = calendar year)."""
    placeholders = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT game_id, game_date, home_team, away_team,
               home_score, away_score, commence_time
        FROM games
        WHERE sport = 'WNBA'
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


def _pregame_odds(conn, market: str) -> dict:
    """
    (game_id) → latest genuinely PRE-TIPOFF DK odds row for this market.

    Deliberately independent of the bulk loader's odds dict so the grading prices
    are verified pre-tipoff here too — a leaked price would distort ROI even if
    the feature line were clean.
    """
    rows = conn.execute("""
        SELECT o.game_id, o.snapshot_at, g.commence_time,
               o.total_line, o.spread_home, o.over_price, o.under_price,
               o.home_price, o.away_price
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'WNBA'
          AND o.market = %s
          AND o.bookmaker = 'draftkings'
          AND o.snapshot_type != 'in_play'
        ORDER BY o.game_id, o.snapshot_at DESC
    """, (market,)).fetchall()

    out: dict = {}
    for (gid, snap, commence, total_line, spread_home,
         over_p, under_p, home_p, away_p) in rows:
        if gid in out:
            continue                                    # newest-first: first kept
        if not _is_pregame_snapshot(snap, commence):
            continue                                    # post-tipoff → leaked
        out[gid] = dict(total_line=total_line, spread_home=spread_home,
                        over_price=over_p, under_price=under_p,
                        home_price=home_p, away_price=away_p,
                        snapshot_at=snap)
    return out


def _side_rows(model_id: str, game: dict, prob_a: float, odds: dict) -> list[dict]:
    """
    Emit one row per bettable side, with the model prob, the real pre-tipoff
    price, the edge, and whether that side actually won.

    Grading conventions (must match paper_tracker / the record views):
      totals  — over wins iff (home+away) > total_line; scored_line is the total
      spreads — scored_line is the HOME spread; home covers iff
                (home-away) + spread_home > 0, away covers iff
                -(home-away) - spread_home > 0     [the session-87 sign fix]
    Exact-push games are dropped (lines are x.5 so this should be empty).
    """
    market, label_a, label_b = _MARKETS[model_id]
    rows: list[dict] = []

    if market == "totals":
        line = odds.get("total_line")
        if line is None:
            return rows
        actual = game["home_score"] + game["away_score"]
        if actual == float(line):
            return rows
        won = {label_a: actual > float(line), label_b: actual < float(line)}
        price = {label_a: odds.get("over_price"), label_b: odds.get("under_price")}
    else:
        line = odds.get("spread_home")
        if line is None:
            return rows
        margin = game["home_score"] - game["away_score"]
        home_cover = margin + float(line)
        if home_cover == 0:
            return rows
        won = {label_a: home_cover > 0, label_b: home_cover < 0}
        price = {label_a: odds.get("home_price"), label_b: odds.get("away_price")}

    prob = {label_a: prob_a, label_b: 1.0 - prob_a}

    for side in (label_a, label_b):
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
            line=float(line), model_prob=prob[side], dk_odds=float(american),
            implied=implied, edge=prob[side] - implied,
            won=bool(won[side]), stake=stake, profit=profit,
        ))
    return rows


def build_side_table(model_id: str, seasons: list[int]) -> pd.DataFrame:
    """Score every completed game and return one row per bettable side."""
    artifact = load_model(model_id)
    if not artifact:
        raise SystemExit(f"No active model artifact for {model_id} — train it first.")
    clf = artifact["model"]
    feature_cols = FEATURE_MAP[model_id]

    conn = get_connection()
    try:
        games = _fetch_games(conn, seasons)
        if not games:
            raise SystemExit(f"No completed WNBA games found for seasons {seasons}.")
        market = _MARKETS[model_id][0]
        odds_by_game = _pregame_odds(conn, market)
        logger.info(f"{len(games)} completed games; "
                    f"{len(odds_by_game)} have a pre-tipoff {market} line")
        bulk = build_bulk_wnba_lookups(conn, seasons)
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
        feats = build_wnba_features_from_bulk(
            bulk, game["game_id"], game["game_date"],
            game["home_team"], game["away_team"], season,
            # Feed the verified pre-tipoff line as the odds row so the model sees
            # exactly what live scoring would have seen before tipoff.
            odds_row=odds,
        )
        if not feats:
            skipped_no_features += 1
            continue

        X = pd.DataFrame([{c: feats.get(c) for c in feature_cols}])[feature_cols]
        if X.isnull().all(axis=1).iloc[0]:
            skipped_no_features += 1
            continue

        prob_a = float(clf.predict_proba(X)[0][1])
        rows.extend(_side_rows(model_id, game, prob_a, odds))

    logger.info(f"skipped: {skipped_no_odds} no pre-tipoff line, "
                f"{skipped_no_features} no features")
    return pd.DataFrame(rows)


def sweep(df: pd.DataFrame, min_bets: int) -> pd.DataFrame:
    """Grid prob x edge over the side table; flat $100 stakes at real DK prices."""
    prob_floors = [round(x, 2) for x in np.arange(0.50, 0.76, 0.02)]
    edge_floors = [round(x, 2) for x in np.arange(0.00, 0.21, 0.02)]

    out = []
    for pf in prob_floors:
        for ef in edge_floors:
            sel = df[(df.model_prob >= pf) & (df.edge >= ef)]
            if len(sel) < min_bets:
                continue
            staked = sel.stake.sum()
            profit = sel.profit.sum()
            wins = int(sel.won.sum())
            n_side = sel.side.nunique()
            out.append(dict(
                min_prob=pf, min_edge=ef, bets=len(sel),
                wins=wins, losses=len(sel) - wins,
                win_pct=round(100.0 * wins / len(sel), 1),
                units=round(profit / 100.0, 2),
                roi_pct=round(100.0 * profit / staked, 2),
                both_sides=(n_side > 1),
                top_side=sel.side.value_counts().idxmax(),
            ))
    return pd.DataFrame(out).sort_values("roi_pct", ascending=False)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=sorted(_MARKETS))
    ap.add_argument("--seasons", nargs="+", type=int, default=[2026])
    ap.add_argument("--min-bets", type=int, default=25,
                    help="hide cells thinner than this (default 25)")
    ap.add_argument("--csv", help="also write the raw side table here")
    args = ap.parse_args()

    df = build_side_table(args.model, args.seasons)
    if df.empty:
        raise SystemExit("No gradable sides — check that games have pre-tipoff lines.")

    if args.csv:
        df.to_csv(args.csv, index=False)
        logger.info(f"wrote side table → {args.csv}")

    print(f"\n=== {args.model} — LEAK-FREE sweep, seasons {args.seasons} ===")
    print(f"{len(df)} bettable sides across {df.game_id.nunique()} games")
    print(f"model prob range: {df.model_prob.min():.3f} – {df.model_prob.max():.3f}")

    # A model that never reaches its live prob floor can't produce picks at all —
    # that is the wnba_over_under "0 picks" symptom, so surface it explicitly.
    for bar in (0.60, 0.65):
        n = int((df.model_prob >= bar).sum())
        print(f"  sides at prob >= {bar:.2f}: {n}")

    grid = sweep(df, args.min_bets)
    if grid.empty:
        print(f"\nNo cell reaches {args.min_bets} bets — sample too thin to cut on.")
        return

    print(f"\n--- top cells (>= {args.min_bets} bets, by ROI) ---")
    print(grid.head(20).to_string(index=False))

    best = grid.iloc[0]
    if best.roi_pct <= 0:
        print("\nVERDICT: every cell is negative on clean lines. Leave the model "
              "PAUSED — this needs feature work, not a re-cut. Do not ship the "
              "least-bad cell.")
    else:
        print(f"\nBest cell: {best.min_prob:.2f}/{best.min_edge:.2f} = "
              f"{int(best.bets)} bets {int(best.wins)}-{int(best.losses)} "
              f"{best.roi_pct:+.2f}% ROI")
        print("Before unpausing: confirm the neighbouring cells are also positive "
              "(a plateau, not a peak), and that both_sides is True.")


if __name__ == "__main__":
    main()
