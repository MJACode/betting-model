"""
paper_tracker.py — Morning result settler for paper trading picks.

Runs each morning after games complete to:
  1. Find picks from the previous day that have no result yet
  2. Look up final scores from the games table
  3. Compute WIN / LOSS / PUSH for each pick
  4. Update profit_flat, profit_kelly, result, settled_at in the picks table
  5. Log performance summary

Usage:
    python -m tracking.paper_tracker              # settle yesterday's picks
    python -m tracking.paper_tracker --date 2025-04-15
    python -m tracking.paper_tracker --summary    # print running P&L
"""

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import MODELS
from data.db import get_connection
from models.scorer import american_to_decimal


# ── Result Computation ────────────────────────────────────────────────────────

def _compute_result(pick_side: str, market: str,
                     home_score: float, away_score: float,
                     home_win: int, home_win_reg: int,
                     went_to_ot: int,
                     dk_odds: float, spread_home: float,
                     total_line: float,
                     rec_bet: float) -> tuple[str, float, float]:
    """
    Determine final result for one pick.

    Returns:
        (result: str, profit_flat: float, profit_kelly: float)
        result is 'WIN' | 'LOSS' | 'PUSH' | 'NO_ACTION'
    """
    if home_score is None or away_score is None:
        return "NO_ACTION", 0.0, 0.0

    total  = home_score + away_score
    margin = home_score - away_score

    won = None

    if market == "h2h":
        if pick_side == "home":
            won = (home_win == 1)
        elif pick_side == "away":
            won = (home_win == 0)

    elif market == "h2h_3way":
        # Regulation only
        if pick_side == "home":
            won = (home_win_reg == 1)
        elif pick_side == "away":
            # Away wins in regulation if reg_result=0 AND not a tie (no OT)
            won = (home_win_reg == 0 and not went_to_ot)
        elif pick_side == "draw":
            won = (went_to_ot == 1)

    elif market == "totals":
        if total_line is None:
            return "NO_ACTION", 0.0, 0.0
        if total == total_line:
            return "PUSH", 0.0, 0.0
        if pick_side == "over":
            won = (total > total_line)
        elif pick_side == "under":
            won = (total < total_line)

    elif market == "spreads":
        if spread_home is None:
            return "NO_ACTION", 0.0, 0.0
        covered_margin = margin + spread_home
        if covered_margin == 0:
            return "PUSH", 0.0, 0.0
        if pick_side == "home":
            won = (covered_margin > 0)
        elif pick_side == "away":
            won = (covered_margin < 0)

    if won is None:
        return "NO_ACTION", 0.0, 0.0

    # Compute P&L
    decimal = american_to_decimal(dk_odds)
    if decimal is None:
        return "NO_ACTION", 0.0, 0.0

    if won:
        profit_flat   = round(100.0 * (decimal - 1), 2)
        profit_kelly  = round(rec_bet * (decimal - 1), 2)
        return "WIN", profit_flat, profit_kelly
    else:
        return "LOSS", -100.0, round(-rec_bet, 2)


def _market_for_pick(model_id: str) -> str:
    """Map model_id to its odds market key."""
    return MODELS[model_id][1] if model_id in MODELS else "h2h"


# ── Settler ───────────────────────────────────────────────────────────────────

def settle_picks(game_date: str = None) -> dict:
    """
    Settle all unsettled picks from game_date (default: yesterday).

    Returns:
        Summary dict with wins, losses, pushes, and P&L.
    """
    if game_date is None:
        game_date = (date.today() - timedelta(days=1)).isoformat()

    logger.info(f"Settling picks for {game_date}...")

    conn = get_connection()

    try:
        # Find unsettled picks for this date
        picks = conn.execute("""
            SELECT p.pick_id, p.game_id, p.model_id, p.pick_side,
                   p.dk_odds, p.recommended_bet,
                   g.home_score, g.away_score,
                   g.home_win, g.home_win_reg, g.went_to_ot,
                   o_spread.spread_home,
                   o_total.total_line
            FROM picks p
            LEFT JOIN games g ON p.game_id = g.game_id
            LEFT JOIN (
                SELECT game_id, spread_home
                FROM odds
                WHERE market = 'spreads'
                ORDER BY snapshot_at DESC
            ) o_spread ON p.game_id = o_spread.game_id
            LEFT JOIN (
                SELECT game_id, total_line
                FROM odds
                WHERE market = 'totals'
                ORDER BY snapshot_at DESC
            ) o_total ON p.game_id = o_total.game_id
            WHERE p.game_date = ?
              AND p.result IS NULL
              AND g.home_score IS NOT NULL
        """, (game_date,)).fetchall()

        if not picks:
            logger.info(f"No unsettled picks found for {game_date}")
            conn.close()
            return {"game_date": game_date, "settled": 0}

        logger.info(f"Found {len(picks)} unsettled picks")

        wins = losses = pushes = no_actions = 0
        total_profit_flat  = 0.0
        total_profit_kelly = 0.0
        settled_at = datetime.utcnow().isoformat()

        for row in picks:
            (pick_id, game_id, model_id, pick_side,
             dk_odds, rec_bet,
             home_score, away_score,
             home_win, home_win_reg, went_to_ot,
             spread_home, total_line) = row

            market = _market_for_pick(model_id)

            result, profit_flat, profit_kelly = _compute_result(
                pick_side, market,
                home_score, away_score,
                home_win, home_win_reg, went_to_ot,
                dk_odds, spread_home, total_line,
                rec_bet or 0.0,
            )

            conn.execute("""
                UPDATE picks
                SET result       = ?,
                    profit_flat  = ?,
                    profit_kelly = ?,
                    settled_at   = ?
                WHERE pick_id = ?
            """, (result, profit_flat, profit_kelly, settled_at, pick_id))

            if result == "WIN":
                wins += 1
                total_profit_flat  += profit_flat
                total_profit_kelly += profit_kelly
            elif result == "LOSS":
                losses += 1
                total_profit_flat  += profit_flat
                total_profit_kelly += profit_kelly
            elif result == "PUSH":
                pushes += 1
            else:
                no_actions += 1

        conn.commit()

        n_settled = wins + losses + pushes
        win_rate = wins / max(wins + losses, 1)
        flat_roi = total_profit_flat / max((wins + losses) * 100, 1)

        logger.success(
            f"\n{'═'*50}\n"
            f"  Settled: {game_date}\n"
            f"  Results: {wins}W / {losses}L / {pushes}P / {no_actions}N\n"
            f"  Win Rate: {win_rate:.1%}\n"
            f"  Flat P&L: ${total_profit_flat:+,.2f} (ROI: {flat_roi:.1%})\n"
            f"  Kelly P&L: ${total_profit_kelly:+,.2f}\n"
            f"{'═'*50}"
        )

        return {
            "game_date":     game_date,
            "settled":       n_settled,
            "wins":          wins,
            "losses":        losses,
            "pushes":        pushes,
            "no_actions":    no_actions,
            "profit_flat":   round(total_profit_flat, 2),
            "profit_kelly":  round(total_profit_kelly, 2),
            "win_rate":      round(win_rate, 4),
            "flat_roi":      round(flat_roi, 4),
        }

    except Exception as exc:
        conn.rollback()
        logger.error(f"Settlement failed: {exc}")
        raise
    finally:
        conn.close()


# ── Performance Summary ───────────────────────────────────────────────────────

def print_performance_summary(days: int = 30) -> dict:
    """
    Print running P&L and performance metrics for the last N days.
    """
    cutoff = (date.today() - timedelta(days=days)).isoformat()

    conn = get_connection()
    try:
        # Overall stats
        overall = conn.execute("""
            SELECT
                COUNT(*) as total_picks,
                SUM(CASE WHEN result = 'WIN'  THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN result = 'LOSS' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN result = 'PUSH' THEN 1 ELSE 0 END) as pushes,
                SUM(profit_flat)  as total_flat_pnl,
                SUM(profit_kelly) as total_kelly_pnl,
                AVG(edge)         as avg_edge,
                bankroll_at_pick
            FROM picks
            WHERE game_date >= ?
              AND result IS NOT NULL
              AND signal_type = 'BET'
        """, (cutoff,)).fetchone()

        # Per-model breakdown
        by_model = conn.execute("""
            SELECT model_id,
                   COUNT(*) as picks,
                   SUM(CASE WHEN result='WIN' THEN 1 ELSE 0 END) as wins,
                   SUM(profit_flat) as flat_pnl,
                   SUM(profit_kelly) as kelly_pnl,
                   AVG(edge) as avg_edge
            FROM picks
            WHERE game_date >= ?
              AND result IS NOT NULL
              AND signal_type = 'BET'
            GROUP BY model_id
            ORDER BY flat_pnl DESC
        """, (cutoff,)).fetchall()

        # Current bankroll
        current_bankroll = conn.execute("""
            SELECT bankroll_at_pick + COALESCE(profit_kelly, 0)
            FROM picks
            WHERE result IS NOT NULL
            ORDER BY settled_at DESC
            LIMIT 1
        """).fetchone()

        # Running bankroll history (for chart)
        bankroll_history = conn.execute("""
            SELECT game_date,
                   SUM(profit_kelly) OVER (ORDER BY settled_at) as cumulative_kelly
            FROM picks
            WHERE game_date >= ?
              AND result IS NOT NULL
              AND signal_type = 'BET'
            ORDER BY settled_at
        """, (cutoff,)).fetchall()

    finally:
        conn.close()

    # Print
    logger.info(f"\n{'═'*60}")
    logger.info(f"  PAPER TRADING SUMMARY (last {days} days)")
    logger.info(f"{'═'*60}")

    if overall and overall[0]:
        total, wins, losses, pushes, flat_pnl, kelly_pnl, avg_edge, _ = overall
        decided = max(wins + losses, 1)
        logger.info(f"  Total Picks:  {total}")
        logger.info(f"  Record:       {wins}W / {losses}L / {pushes}P")
        logger.info(f"  Win Rate:     {wins/decided:.1%}")
        logger.info(f"  Flat P&L:     ${flat_pnl:+,.2f} (ROI: {flat_pnl/(decided*100):.1%})")
        logger.info(f"  Kelly P&L:    ${kelly_pnl:+,.2f}")
        logger.info(f"  Avg Edge:     {avg_edge:.2%}" if avg_edge else "")
        if current_bankroll and current_bankroll[0]:
            logger.info(f"  Bankroll:     ${current_bankroll[0]:,.2f}")

    if by_model:
        logger.info(f"\n  {'Model':<30} {'Picks':>5} {'W/L':>7} {'Flat P&L':>10} {'Avg Edge':>9}")
        logger.info(f"  {'-'*63}")
        for row in by_model:
            mid, picks, wins, flat_pnl, kelly_pnl, avg_edge = row
            losses = picks - wins if wins else picks
            wl = f"{wins}/{losses}" if wins is not None else "–"
            logger.info(f"  {mid:<30} {picks:>5} {wl:>7} "
                         f"${flat_pnl or 0:>9,.2f} {avg_edge or 0:>8.2%}")

    logger.info(f"{'═'*60}\n")

    return {
        "total_picks":    overall[0] if overall else 0,
        "wins":           overall[1] if overall else 0,
        "losses":         overall[2] if overall else 0,
        "flat_pnl":       overall[4] if overall else 0.0,
        "kelly_pnl":      overall[5] if overall else 0.0,
        "by_model":       [dict(zip(
            ["model_id","picks","wins","flat_pnl","kelly_pnl","avg_edge"], r
        )) for r in (by_model or [])],
        "bankroll_history": [{"date": r[0], "cumulative_kelly": r[1]}
                              for r in (bankroll_history or [])],
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper trader result settler")
    parser.add_argument("--date",    help="Game date to settle YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--summary", action="store_true", help="Print P&L summary")
    parser.add_argument("--days",    type=int, default=30, help="Days for summary")
    args = parser.parse_args()

    if args.summary:
        print_performance_summary(days=args.days)
    else:
        result = settle_picks(game_date=args.date)
        logger.info(f"Done: {result}")
