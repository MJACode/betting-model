"""
backtester.py — Historical simulation of picks against SBR odds data.

Runs the full model pipeline against the holdout season to measure:
  • Win rate / accuracy
  • Flat-bet ROI ($100/bet)
  • Kelly-bet ROI (quarter-Kelly sizing)
  • Calibration (predicted prob vs. actual win rate)
  • Breakdown by confidence tier, sport, and market

Usage:
    python -m models.backtester --model mlb_moneyline --season 2024
    python -m models.backtester --all --season 2024
    python -m models.backtester --all --season 2024 --out backtest_results.csv
"""

import argparse
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BANKROLL,
    BET_EDGE_THRESHOLD,
    AVOID_EDGE_THRESHOLD,
    MODEL_EDGE_THRESHOLDS,
    MAX_KELLY_FRACTION,
    MIN_GAMES_BASELINE,
    MODELS,
    SPORTS,
)
from data.db import get_connection, DBConnection
from features.feature_engine import (
    FEATURE_MAP,
    build_mlb_game_features,
    build_nhl_game_features,
)
from models.trainer import load_model
from models.scorer import (
    american_to_implied_prob,
    american_to_decimal,
    quarter_kelly,
    _confidence_tier,
    _build_pick_label,
)


# ── Go-Live Gate Thresholds ──────────────────────────────────────────────────

GO_LIVE_MIN_PICKS    = 100    # must have ≥100 picks in backtest
GO_LIVE_MIN_ROI      = 0.00   # must show positive flat ROI
GO_LIVE_MAX_CAL_ERR  = 0.05   # calibration error ≤5%


# ── Core Backtest ─────────────────────────────────────────────────────────────

def run_backtest(model_id: str, season: int,
                 db_path: str = None) -> pd.DataFrame:
    """
    Simulate the full pick pipeline for one model on all completed games
    in the given season. Uses SBR or Odds API odds stored in the DB.

    Returns:
        DataFrame with one row per pick signal (BET or AVOID),
        including ground-truth results and P&L.
    """
    if model_id not in MODELS:
        raise ValueError(f"Unknown model_id: {model_id}")

    sport, market, description = MODELS[model_id]
    feature_cols = FEATURE_MAP[model_id]

    conn = get_connection()

    # Load trained model
    artifact = load_model(model_id)
    if artifact is None:
        conn.close()
        raise ValueError(f"No trained model found for {model_id}. "
                         f"Run: python -m models.trainer --model {model_id}")

    clf       = artifact["model"]
    feat_cols = artifact.get("feature_cols", feature_cols)

    # Fetch all completed games for this sport/season
    games = conn.execute("""
        SELECT game_id, sport, season, game_date, home_team, away_team,
               home_score, away_score, home_win, home_win_reg,
               went_to_ot, regulation_tie
        FROM games
        WHERE sport = ?
          AND season = ?
          AND home_score IS NOT NULL
        ORDER BY game_date
    """, (sport, season)).fetchall()

    if not games:
        conn.close()
        logger.warning(f"No completed games for {sport} season {season}")
        return pd.DataFrame()

    logger.info(f"Backtesting {model_id} on {season}: {len(games)} games")

    rows = []
    bankroll = float(BANKROLL)

    for game_row in games:
        (game_id, sp, s, game_date, home_team, away_team,
         home_score, away_score, home_win, home_win_reg,
         went_to_ot, reg_tie) = game_row

        # Build features
        odds_context = _get_odds_context(conn, game_id, market)

        if sp == "MLB":
            features = build_mlb_game_features(
                conn, game_id, game_date, home_team, away_team, season,
                odds_row=odds_context
            )
        else:
            features = build_nhl_game_features(
                conn, game_id, game_date, home_team, away_team, season,
                odds_row=odds_context
            )

        if not features:
            continue

        # Early season gate
        if features.get("is_early_season", 0):
            continue

        # Build feature vector — skip games with any null feature.
        # Filling null pitcher/team stats with 0.0 puts the model completely
        # out of distribution (ERA=0 is historically unprecedented) and generates
        # garbage predictions. Consistent with training, which also drops null rows.
        feat_vals = [features.get(c) for c in feat_cols]
        if any(v is None for v in feat_vals):
            continue
        x = np.array(feat_vals, dtype=float).reshape(1, -1)

        try:
            probs = clf.predict_proba(x)[0]
        except Exception as exc:
            logger.debug(f"Prediction error {game_id}: {exc}")
            continue

        home_prob = float(probs[1])
        away_prob = 1.0 - home_prob

        # Get DK odds for this game
        dk_odds = _get_dk_odds_for_market(conn, game_id, market)
        if not dk_odds:
            continue

        # Evaluate each side
        for pick_side, model_p, dk_odds_val in _iter_sides(
            market, home_prob, away_prob, dk_odds
        ):
            if dk_odds_val is None:
                continue

            ip   = american_to_implied_prob(dk_odds_val)
            if ip is None:
                continue

            edge = model_p - ip

            # Signal classification — use per-model threshold if defined
            bet_thresh   = MODEL_EDGE_THRESHOLDS.get(model_id, BET_EDGE_THRESHOLD)
            avoid_thresh = MODEL_EDGE_THRESHOLDS.get(model_id, AVOID_EDGE_THRESHOLD)

            if edge >= bet_thresh:
                signal_type = "BET"
            elif edge <= -avoid_thresh:
                signal_type = "AVOID"
            else:
                continue  # no signal

            kelly_frac, rec_bet = quarter_kelly(model_p, ip, bankroll)
            conf_tier = _confidence_tier(edge)

            # Compute ground-truth outcome for this pick
            total_line  = dk_odds.get("total_line")  if dk_odds else None
            spread_home = dk_odds.get("spread_home") if dk_odds else None
            won, result, profit_flat, profit_kelly = _evaluate_result(
                pick_side, market, home_score, away_score,
                home_win, home_win_reg, went_to_ot, dk_odds_val,
                rec_bet, signal_type,
                total_line=total_line, spread_home=spread_home,
            )

            # Update bankroll (Kelly bets only for BET signals)
            if signal_type == "BET" and result == "WIN":
                bankroll += profit_kelly
            elif signal_type == "BET" and result == "LOSS":
                bankroll += profit_kelly  # profit_kelly is negative

            rows.append({
                "game_id":        game_id,
                "model_id":       model_id,
                "sport":          sport,
                "season":         season,
                "game_date":      game_date,
                "home_team":      home_team,
                "away_team":      away_team,
                "market":         market,
                "pick_side":      pick_side,
                "pick_label":     _build_pick_label(pick_side, home_team, away_team, market),
                "model_prob":     round(model_p, 4),
                "dk_implied_prob": round(ip, 4),
                "edge":           round(edge, 4),
                "dk_odds":        dk_odds_val,
                "kelly_fraction": round(kelly_frac, 6),
                "recommended_bet": round(rec_bet, 2),
                "bankroll_at_pick": round(bankroll, 2),
                "signal_type":    signal_type,
                "confidence_tier": conf_tier,
                "result":         result,
                "won":            won,
                "profit_flat":    round(profit_flat, 2),
                "profit_kelly":   round(profit_kelly, 2),
            })

    conn.close()

    if not rows:
        logger.warning(f"No signals generated for {model_id} season {season}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    logger.success(f"Generated {len(df)} pick signals for {model_id} {season}")
    return df


def _iter_sides(market: str, home_prob: float, away_prob: float,
                dk_odds: dict):
    """Yield (side, model_prob, dk_odds) tuples for all relevant sides."""
    if market in ("h2h", "h2h_3way", "spreads"):
        yield "home", home_prob, dk_odds.get("home_price")
        yield "away", away_prob, dk_odds.get("away_price")
    elif market == "totals":
        yield "over",  home_prob, dk_odds.get("over_price")
        yield "under", away_prob, dk_odds.get("under_price")


def _get_odds_context(conn: DBConnection, game_id: str,
                       market: str) -> dict | None:
    """Get opening-line odds for feature context (total_line, spread_home)."""
    row = conn.execute("""
        SELECT home_price, away_price, spread_home, total_line, over_price, under_price
        FROM odds
        WHERE game_id   = ?
          AND market    = ?
        ORDER BY snapshot_at ASC
        LIMIT 1
    """, (game_id, "h2h" if market == "h2h_3way" else market)).fetchone()

    if not row:
        return None

    return {
        "home_price":  row[0],
        "away_price":  row[1],
        "spread_home": row[2],
        "total_line":  row[3],
        "over_price":  row[4],
        "under_price": row[5],
    }


def _get_dk_odds_for_market(conn: DBConnection,
                              game_id: str, market: str) -> dict | None:
    """Get closing-line (or latest) odds for evaluation."""
    row = conn.execute("""
        SELECT home_price, away_price, draw_price,
               spread_home, total_line, over_price, under_price
        FROM odds
        WHERE game_id   = ?
          AND market    = ?
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, market)).fetchone()

    if not row:
        return None

    cols = ["home_price", "away_price", "draw_price",
            "spread_home", "total_line", "over_price", "under_price"]
    return dict(zip(cols, row))


def _evaluate_result(pick_side: str, market: str,
                      home_score: float, away_score: float,
                      home_win: int, home_win_reg: int,
                      went_to_ot: int,
                      dk_odds: float, rec_bet: float,
                      signal_type: str,
                      total_line: float = None,
                      spread_home: float = None) -> tuple[int, str, float, float]:
    """
    Determine if the pick won or lost and compute P&L.

    Returns:
        (won: 0/1, result: str, profit_flat: float, profit_kelly: float)
    """
    total = home_score + away_score
    margin = home_score - away_score

    if market in ("h2h",):
        if pick_side == "home":
            won = int(home_win == 1)
        else:
            won = int(home_win == 0)

    elif market == "h2h_3way":
        if pick_side == "home":
            won = int(home_win_reg == 1)
        elif pick_side == "away":
            won = int(home_win_reg == 0 and not went_to_ot)
        else:
            won = 0

    elif market == "totals":
        if total_line is None:
            won = 0
        elif pick_side == "over":
            won = int(total > total_line)   # push (==) counts as no win
        else:  # "under"
            won = int(total < total_line)

    elif market == "spreads":
        if spread_home is None:
            won = 0
        elif pick_side == "home":
            # home covers if margin exceeds spread (e.g. -1.5 → must win by 2+)
            won = int(margin + spread_home > 0)
        else:  # "away"
            won = int(margin + spread_home < 0)

    else:
        won = 0

    if signal_type == "AVOID":
        # AVOID signals: "win" = our model was right (team we're avoiding loses)
        won = 1 - won

    decimal_odds = american_to_decimal(dk_odds) if dk_odds else None

    if won == 1:
        result = "WIN"
        profit_flat   = 100.0 * (decimal_odds - 1) if decimal_odds else 0.0
        profit_kelly  = rec_bet * (decimal_odds - 1) if decimal_odds else 0.0
    else:
        result = "LOSS"
        profit_flat  = -100.0
        profit_kelly = -rec_bet

    return won, result, profit_flat, profit_kelly


# ── Summary Statistics ─────────────────────────────────────────────────────────

def compute_backtest_summary(df: pd.DataFrame) -> dict:
    """
    Compute aggregate performance metrics from backtest DataFrame.
    """
    if df.empty:
        return {}

    bets   = df[df["signal_type"] == "BET"]
    avoids = df[df["signal_type"] == "AVOID"]

    summary = {
        "total_picks":   len(df),
        "bets":          len(bets),
        "avoids":        len(avoids),
    }

    if len(bets) > 0:
        bet_wins = bets["won"].sum()
        summary.update({
            "bet_win_rate":      round(bet_wins / len(bets), 4),
            "bet_flat_roi":      round(bets["profit_flat"].sum() / (100 * len(bets)), 4),
            "bet_kelly_roi":     round(bets["profit_kelly"].sum() /
                                        bets["recommended_bet"].sum(), 4)
                                  if bets["recommended_bet"].sum() > 0 else 0.0,
            "bet_total_profit_flat":   round(bets["profit_flat"].sum(), 2),
            "bet_total_profit_kelly":  round(bets["profit_kelly"].sum(), 2),
            "avg_edge":          round(bets["edge"].mean(), 4),
            "avg_model_prob":    round(bets["model_prob"].mean(), 4),
        })

    # Calibration
    if len(bets) > 10:
        summary["calibration_error"] = round(
            _calibration_error(bets["model_prob"].values, bets["won"].values), 4
        )

    # Tier breakdown
    for tier in ["HIGH", "MED", "LOW"]:
        tier_df = bets[bets["confidence_tier"] == tier]
        if len(tier_df) > 0:
            summary[f"{tier.lower()}_picks"] = len(tier_df)
            summary[f"{tier.lower()}_win_rate"] = round(tier_df["won"].mean(), 4)
            summary[f"{tier.lower()}_roi"] = round(
                tier_df["profit_flat"].sum() / (100 * len(tier_df)), 4
            )

    # Go/No-Go assessment
    min_picks_ok = summary.get("bets", 0) >= GO_LIVE_MIN_PICKS
    roi_ok       = summary.get("bet_flat_roi", -1) >= GO_LIVE_MIN_ROI
    cal_ok       = summary.get("calibration_error", 1) <= GO_LIVE_MAX_CAL_ERR

    summary["go_live_ready"] = min_picks_ok and roi_ok and cal_ok
    summary["go_live_blockers"] = []
    if not min_picks_ok:
        summary["go_live_blockers"].append(
            f"Insufficient picks: {summary.get('bets',0)} < {GO_LIVE_MIN_PICKS}"
        )
    if not roi_ok:
        summary["go_live_blockers"].append(
            f"Negative flat ROI: {summary.get('bet_flat_roi',0):.1%}"
        )
    if not cal_ok:
        summary["go_live_blockers"].append(
            f"Calibration error too high: {summary.get('calibration_error',1):.1%} > {GO_LIVE_MAX_CAL_ERR:.1%}"
        )

    return summary


def _calibration_error(probs: np.ndarray, outcomes: np.ndarray,
                        n_bins: int = 10, min_samples: int = 20) -> float:
    """Mean absolute calibration error. Requires min_samples per bin to avoid
    noise from tiny extreme-probability bins (1-5 samples always produce 0.0
    or 1.0 actual rates by chance, inflating the metric artificially)."""
    bin_edges = np.linspace(0, 1, n_bins + 1)
    errors = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        mask = (probs >= lo) & (probs < hi)
        if mask.sum() < min_samples:
            continue
        errors.append(abs(probs[mask].mean() - outcomes[mask].mean()))
    return float(np.mean(errors)) if errors else 0.0


# ── Full Backtest Runner ───────────────────────────────────────────────────────

def run_full_backtest(model_ids: list[str] = None,
                       season: int = None) -> dict:
    """
    Run backtest for all (or specified) models and print a summary table.
    """
    if model_ids is None:
        model_ids = list(MODELS.keys())

    results = {}
    all_dfs = []

    for mid in model_ids:
        sport_cfg = SPORTS[MODELS[mid][0]]
        s = season or sport_cfg["test_season"]

        logger.info(f"\n{'─'*50}")
        logger.info(f"Model: {mid} | Season: {s}")

        try:
            df = run_backtest(mid, s)
            if df.empty:
                continue

            summary = compute_backtest_summary(df)
            results[mid] = summary
            all_dfs.append(df)

            _print_summary(mid, s, summary)

        except Exception as exc:
            logger.error(f"Backtest failed for {mid}: {exc}")
            results[mid] = {"error": str(exc)}

    # Aggregate across all models
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        overall  = compute_backtest_summary(combined)
        logger.info(f"\n{'═'*60}")
        logger.info("OVERALL BACKTEST SUMMARY")
        logger.info(f"{'═'*60}")
        _print_summary("ALL MODELS", season or "2024", overall)
        results["_overall"] = overall

    return results


def _print_summary(model_id: str, season: int | str, summary: dict) -> None:
    logger.info(f"{'─'*50}")
    logger.info(f"  {model_id} | Season {season}")
    logger.info(f"  Picks:      {summary.get('bets', 0)} BETs | "
                f"{summary.get('avoids', 0)} AVOIDs")
    logger.info(f"  Win Rate:   {summary.get('bet_win_rate', 0):.1%}")
    logger.info(f"  Flat ROI:   {summary.get('bet_flat_roi', 0):.2%}")
    logger.info(f"  Kelly ROI:  {summary.get('bet_kelly_roi', 0):.2%}")
    logger.info(f"  Cal Error:  {summary.get('calibration_error', 'n/a')}")
    go_live = summary.get("go_live_ready", False)
    status  = "✅ GO-LIVE READY" if go_live else "⛔ NOT READY"
    logger.info(f"  Go-Live:    {status}")
    if not go_live:
        for blocker in summary.get("go_live_blockers", []):
            logger.info(f"              → {blocker}")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run backtest")
    parser.add_argument("--model",  help="Model ID (default: all)")
    parser.add_argument("--all",    action="store_true")
    parser.add_argument("--season", type=int, help="Backtest season")
    parser.add_argument("--out",    help="Save results CSV to path")
    args = parser.parse_args()

    model_ids = list(MODELS.keys()) if (args.all or not args.model) else [args.model]
    results   = run_full_backtest(model_ids=model_ids, season=args.season)

    if args.out:
        # Save all pick-level data
        all_dfs = []
        for mid in model_ids:
            sport_cfg = SPORTS[MODELS[mid][0]]
            s = args.season or sport_cfg["test_season"]
            try:
                df = run_backtest(mid, s)
                if not df.empty:
                    all_dfs.append(df)
            except Exception:
                pass

        if all_dfs:
            combined = pd.concat(all_dfs, ignore_index=True)
            combined.to_csv(args.out, index=False)
            logger.success(f"Saved backtest results to {args.out}")
