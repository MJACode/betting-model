"""
ou_threshold_sweep.py — ONE-OFF analysis artifact (2026-07-11 session 101c).

Round 2: emits EVERY side (over + under) of every completed 2026 MLB game for
mlb_over_under with the edge gate disabled — i.e. what the CURRENT model
(v20260704_104508) would have scored all season through the FIXED feature path
(total_line populated; bullpen data backfilled). Answers "what would the 2026
record have been without the NaN-line bug."

CAVEAT: the current model was TRAINED on 2019-2024 + 2026 (holdout 2025), so
2026 predictions are partly IN-SAMPLE and will read optimistic.

Runs on GitHub Actions (needs DATABASE_URL) via .github/workflows/ou_sweep.yml,
which commits the output CSVs back to the working branch. Both this script and
the workflow are deleted once the analysis is done — see the CLAUDE.md log.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

# Disable the edge gate so run_backtest emits every side as a BET row.
config.MODEL_EDGE_THRESHOLDS["mlb_over_under"] = -9.99

from data.db import get_connection            # noqa: E402
from models.backtester import run_backtest    # noqa: E402

SEASON = 2026


def main() -> None:
    out = Path(__file__).parent.parent / "analysis"
    out.mkdir(exist_ok=True)

    df = run_backtest("mlb_over_under", SEASON)
    df.to_csv(out / f"ou_sweep_{SEASON}_all_sides.csv.gz", index=False, compression="gzip")
    print(f"emitted {len(df)} side-rows -> analysis/ou_sweep_{SEASON}_all_sides.csv.gz")

    # Scores + the exact totals line the backtester used (draftkings preferred,
    # latest snapshot — mirrors _build_bulk_mlb_lookups) for push-aware grading.
    conn = get_connection()
    try:
        games = conn.execute(f"""
            SELECT game_id, game_date, home_score, away_score
            FROM games
            WHERE sport = 'MLB' AND season = {SEASON} AND home_score IS NOT NULL
        """).fetchall()
        lines = conn.execute(f"""
            SELECT DISTINCT ON (game_id) game_id, total_line, over_price, under_price
            FROM odds
            WHERE market = 'totals'
              AND bookmaker IN ('draftkings', 'sbr_consensus')
              AND snapshot_type != 'in_play'
              AND game_id LIKE 'MLB_{SEASON}%%'
            ORDER BY game_id,
                     CASE bookmaker WHEN 'draftkings' THEN 0 ELSE 1 END,
                     snapshot_at DESC
        """).fetchall()
    finally:
        conn.close()

    import csv
    import gzip

    with gzip.open(out / f"ou_sweep_{SEASON}_games.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["game_id", "game_date", "home_score", "away_score"])
        w.writerows(games)
    with gzip.open(out / f"ou_sweep_{SEASON}_lines.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["game_id", "total_line", "over_price", "under_price"])
        w.writerows(lines)
    print(f"dumped {len(games)} games, {len(lines)} totals lines")

    cur = df[(df.model_prob >= 0.59) & (df.edge >= 0.07)]
    wins = int((cur.result == "WIN").sum())
    print(f"cut 0.59/0.07: rows={len(cur)} wins={wins} "
          f"win%={wins / max(len(cur), 1):.3f} flat_pnl={cur.profit_flat.sum():+.0f}")


if __name__ == "__main__":
    main()
