"""
ou_threshold_sweep.py — ONE-OFF analysis artifact (2026-07-11 session).

Emits EVERY side (over + under) of every completed 2025 MLB game for
mlb_over_under with the edge gate disabled, so prob x edge threshold cuts
can be swept offline. 2025 is the out-of-sample season for the live model
v20260704_104508 (trained 2019-2024 + 2026, holdout 2025).

Runs on GitHub Actions (needs DATABASE_URL) via .github/workflows/ou_sweep.yml,
which commits the output CSVs back to the working branch. Both this script and
the workflow are deleted once the sweep is done — see the CLAUDE.md session log.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

# Disable the edge gate so run_backtest emits every side as a BET row.
# MODEL_EDGE_THRESHOLDS is the same dict object the backtester reads at runtime.
config.MODEL_EDGE_THRESHOLDS["mlb_over_under"] = -9.99

from data.db import get_connection            # noqa: E402
from models.backtester import run_backtest    # noqa: E402


def main() -> None:
    out = Path(__file__).parent.parent / "analysis"
    out.mkdir(exist_ok=True)

    df = run_backtest("mlb_over_under", 2025)
    df.to_csv(out / "ou_sweep_2025_all_sides.csv.gz", index=False, compression="gzip")
    print(f"emitted {len(df)} side-rows -> analysis/ou_sweep_2025_all_sides.csv.gz")

    # Scores + the exact totals line the backtester used (draftkings preferred
    # over sbr_consensus, latest snapshot — mirrors _build_bulk_mlb_lookups),
    # so the offline analysis can grade pushes (total == line) properly.
    conn = get_connection()
    try:
        games = conn.execute("""
            SELECT game_id, game_date, home_score, away_score
            FROM games
            WHERE sport = 'MLB' AND season = 2025 AND home_score IS NOT NULL
        """).fetchall()
        lines = conn.execute("""
            SELECT DISTINCT ON (game_id) game_id, total_line, over_price, under_price
            FROM odds
            WHERE market = 'totals'
              AND bookmaker IN ('draftkings', 'sbr_consensus')
              AND snapshot_type != 'in_play'
              AND game_id LIKE 'MLB_2025%%'
            ORDER BY game_id,
                     CASE bookmaker WHEN 'draftkings' THEN 0 ELSE 1 END,
                     snapshot_at DESC
        """).fetchall()
    finally:
        conn.close()

    import csv
    import gzip

    with gzip.open(out / "ou_sweep_2025_games.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["game_id", "game_date", "home_score", "away_score"])
        w.writerows(games)
    with gzip.open(out / "ou_sweep_2025_lines.csv.gz", "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["game_id", "total_line", "over_price", "under_price"])
        w.writerows(lines)
    print(f"dumped {len(games)} games, {len(lines)} totals lines")

    # Quick validation against the session-94 reference at the current cut
    # (0.57/0.05 = 366 bets, 59.3% win, +13.9% flat ROI).
    cur = df[(df.model_prob >= 0.57) & (df.edge >= 0.05)]
    wins = int((cur.result == "WIN").sum())
    print(f"cut 0.57/0.05: rows={len(cur)} wins={wins} "
          f"win%={wins / max(len(cur), 1):.3f} "
          f"flat_pnl={cur.profit_flat.sum():+.0f}")


if __name__ == "__main__":
    main()
