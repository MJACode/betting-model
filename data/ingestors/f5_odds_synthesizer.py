"""
f5_odds_synthesizer.py — Generate synthetic F5 odds rows for historical training.

For historical games we have F5 scores (home_score_f5, away_score_f5) but no
F5 odds from SBR or The Odds API. Training the F5 O/U and F5 RL models requires
a target variable, which in turn requires a line.

This script:
  1. Computes the calibration factor from actual F5 data:
         factor = mean(home_score_f5 + away_score_f5) / mean(full_game_total)
  2. Generates synthetic totals_1st_5_innings rows:
         total_line = full_game_total * factor
  3. Generates synthetic spreads_1st_5_innings rows:
         spread_home = -0.5  (standard DraftKings F5 runline)
  4. Inserts them with bookmaker = 'sbr_consensus' so the bulk feature loader
     picks them up (it already filters for sbr_consensus as fallback).

Rows are only inserted for games that don't already have F5 odds in the DB.
Re-running is safe — existing rows are left untouched.

Usage:
    python -m data.ingestors.f5_odds_synthesizer           # generate + insert
    python -m data.ingestors.f5_odds_synthesizer --dry-run # show stats only
    python -m data.ingestors.f5_odds_synthesizer --calibrate-only
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import F5_TOTAL_FACTOR
from data.db import get_connection, DBConnection


def _compute_calibration_factor(conn: DBConnection) -> float:
    """
    Compute mean(f5_total) / mean(full_game_total) from all historical games
    that have both F5 scores and full-game totals odds.

    Returns the calibration factor (e.g. 0.543).
    """
    rows = conn.execute("""
        SELECT g.home_score_f5 + g.away_score_f5  AS f5_total,
               o.total_line                        AS fg_total
        FROM games g
        JOIN odds o
          ON o.game_id = g.game_id
         AND o.market  = 'totals'
         AND o.bookmaker IN ('sbr_consensus', 'draftkings')
        WHERE g.sport          = 'MLB'
          AND g.home_score_f5  IS NOT NULL
          AND g.away_score_f5  IS NOT NULL
          AND o.total_line     IS NOT NULL
          AND g.home_score_f5 + g.away_score_f5 > 0
    """).fetchall()

    if not rows:
        logger.warning("No games found for calibration — using default F5_TOTAL_FACTOR from config")
        return F5_TOTAL_FACTOR

    f5_totals  = [r[0] for r in rows]
    fg_totals  = [r[1] for r in rows]
    factor = sum(f5_totals) / sum(fg_totals)

    logger.info(
        f"Calibration: {len(rows):,} games | "
        f"avg F5 runs={sum(f5_totals)/len(f5_totals):.3f} | "
        f"avg FG total={sum(fg_totals)/len(fg_totals):.3f} | "
        f"factor={factor:.4f}"
    )
    return factor


def _games_needing_synthesis(conn: DBConnection) -> list[dict]:
    """
    Return all MLB games that have:
      - F5 scores
      - A full-game totals odds row (to derive the synthetic F5 line from)
      - No existing synthetic F5 totals odds row

    We generate both totals_1st_5_innings AND spreads_1st_5_innings for each
    qualifying game.
    """
    rows = conn.execute("""
        SELECT g.game_id,
               g.game_date,
               o.total_line,
               o.snapshot_type,
               o.snapshot_at,
               o.bookmaker
        FROM games g
        JOIN odds o
          ON o.game_id  = g.game_id
         AND o.market   = 'totals'
         AND o.bookmaker IN ('sbr_consensus', 'draftkings')
        WHERE g.sport          = 'MLB'
          AND g.home_score_f5  IS NOT NULL
          AND g.away_score_f5  IS NOT NULL
          AND o.total_line     IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM odds o2
              WHERE o2.game_id  = g.game_id
                AND o2.market   = 'totals_1st_5_innings'
          )
        ORDER BY g.game_id, o.snapshot_at DESC
    """).fetchall()

    # Deduplicate: one row per game_id (latest odds row wins)
    seen = set()
    games = []
    for r in rows:
        game_id = r[0]
        if game_id not in seen:
            seen.add(game_id)
            games.append({
                "game_id":       game_id,
                "game_date":     r[1],
                "total_line":    float(r[2]),
                "snapshot_type": r[3],
                "snapshot_at":   r[4],
                "bookmaker":     r[5],
            })
    return games


def _build_synthetic_rows(games: list[dict], factor: float) -> tuple[list[dict], list[dict]]:
    """
    Build synthetic totals_1st_5_innings and spreads_1st_5_innings odds rows.
    Prices (home_price, over_price, etc.) are NULL — we don't have synthetic prices.
    bookmaker = 'sbr_consensus' so the bulk feature loader picks them up.
    """
    totals_rows  = []
    spreads_rows = []

    for g in games:
        f5_total_line = round(g["total_line"] * factor * 2) / 2  # round to nearest 0.5

        base = {
            "game_id":       g["game_id"],
            "sport":         "MLB",
            "bookmaker":     "sbr_consensus",
            "snapshot_type": g["snapshot_type"],
            "snapshot_at":   g["snapshot_at"],
            "home_price":    None,
            "away_price":    None,
            "draw_price":    None,
            "spread_home":   None,
            "total_line":    None,
            "over_price":    None,
            "under_price":   None,
        }

        totals_rows.append({
            **base,
            "market":     "totals_1st_5_innings",
            "total_line": f5_total_line,
        })

        spreads_rows.append({
            **base,
            "market":      "spreads_1st_5_innings",
            "spread_home": -0.5,
        })

    return totals_rows, spreads_rows


def _insert_rows(conn: DBConnection, rows: list[dict]) -> int:
    """Insert synthetic odds rows. Returns count inserted."""
    if not rows:
        return 0

    sql = """
        INSERT INTO odds (
            game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
            home_price, away_price, draw_price,
            spread_home, total_line, over_price, under_price
        ) VALUES (
            %(game_id)s, %(sport)s, %(market)s, %(bookmaker)s, %(snapshot_type)s, %(snapshot_at)s,
            %(home_price)s, %(away_price)s, %(draw_price)s,
            %(spread_home)s, %(total_line)s, %(over_price)s, %(under_price)s
        )
    """
    conn.executemany(sql, rows)
    return len(rows)


def run_synthesizer(dry_run: bool = False, calibrate_only: bool = False) -> dict:
    """
    Main entry point. Computes factor, generates synthetic rows, inserts them.

    Returns summary dict.
    """
    conn = get_connection()
    try:
        factor = _compute_calibration_factor(conn)

        if calibrate_only:
            logger.info(f"Calibrate-only mode. Factor = {factor:.4f}. No rows written.")
            return {"factor": factor, "games": 0, "totals_inserted": 0, "spreads_inserted": 0}

        games = _games_needing_synthesis(conn)
        logger.info(f"Games needing F5 synthesis: {len(games):,}")

        if not games:
            logger.info("Nothing to do — all eligible games already have F5 odds rows.")
            return {"factor": factor, "games": 0, "totals_inserted": 0, "spreads_inserted": 0}

        totals_rows, spreads_rows = _build_synthetic_rows(games, factor)

        # Sample a few to show what we're generating
        for g, t, s in zip(games[:3], totals_rows[:3], spreads_rows[:3]):
            logger.info(
                f"  {g['game_id']} | FG total={g['total_line']:.1f} → "
                f"F5 line={t['total_line']:.1f} | RL spread={s['spread_home']:.1f}"
            )
        if len(games) > 3:
            logger.info(f"  ... and {len(games)-3:,} more")

        if dry_run:
            logger.info(f"Dry-run: would insert {len(totals_rows):,} totals + {len(spreads_rows):,} spreads rows")
            return {
                "factor":           factor,
                "games":            len(games),
                "totals_inserted":  0,
                "spreads_inserted": 0,
            }

        n_totals  = _insert_rows(conn, totals_rows)
        n_spreads = _insert_rows(conn, spreads_rows)
        conn.commit()

        logger.success(
            f"Synthesis complete: {n_totals:,} totals_1st_5_innings rows + "
            f"{n_spreads:,} spreads_1st_5_innings rows inserted "
            f"(factor={factor:.4f})"
        )
        return {
            "factor":           factor,
            "games":            len(games),
            "totals_inserted":  n_totals,
            "spreads_inserted": n_spreads,
        }

    except Exception as exc:
        conn.rollback()
        logger.error(f"Synthesizer failed: {exc}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate synthetic F5 odds for training")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be inserted without writing to DB")
    parser.add_argument("--calibrate-only", action="store_true",
                        help="Just print the calibration factor, no inserts")
    args = parser.parse_args()

    result = run_synthesizer(dry_run=args.dry_run, calibrate_only=args.calibrate_only)
    logger.info(f"Done: {result}")
