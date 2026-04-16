"""
scorer.py — Daily scoring: generate BET/AVOID signals for today's games.

For each game scheduled today:
  1. Build feature vector
  2. Get model probability
  3. Compute edge vs. DraftKings implied probability
  4. Apply injury flags and early season filter
  5. Classify as BET (edge ≥ +3%), AVOID (edge ≤ −3%), or no signal
  6. Size bets with Quarter-Kelly formula
  7. Log picks to the picks table

Usage:
    python -m models.scorer                    # score today
    python -m models.scorer --date 2025-04-15  # score a specific date
    python -m models.scorer --dry-run          # preview without writing to DB
"""

import argparse
from datetime import date, datetime
from pathlib import Path
import sys
from typing import Optional

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    BANKROLL,
    BET_EDGE_THRESHOLD,
    AVOID_EDGE_THRESHOLD,
    MIN_MODEL_PROB,
    MODEL_EDGE_THRESHOLDS,
    MAX_EDGE_CAP,
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

# ── Odds Conversion ────────────────────────────────────────────────────────────

def american_to_implied_prob(american_odds: float) -> float:
    """
    Convert American moneyline odds to implied probability.
    Accounts for the vig: we use the raw implied (not vig-stripped) for edge calc.
    """
    if american_odds is None:
        return None
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)


def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to decimal (returns per unit bet including stake)."""
    if american_odds is None:
        return None
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


# ── Kelly Sizing ──────────────────────────────────────────────────────────────

def quarter_kelly(model_prob: float, implied_prob: float,
                  bankroll: float) -> tuple[float, float]:
    """
    Quarter-Kelly bet sizing formula:
        f_q = 0.25 × (P - IP) / (1 - IP)

    Capped at MAX_KELLY_FRACTION × bankroll.

    Args:
        model_prob:   our model's estimated win probability
        implied_prob: bookmaker's implied win probability
        bankroll:     current paper trading bankroll

    Returns:
        (kelly_fraction, recommended_bet_dollars)
    """
    edge = model_prob - implied_prob
    if edge <= 0:
        return 0.0, 0.0

    denominator = 1.0 - implied_prob
    if denominator <= 0:
        return 0.0, 0.0

    f_raw = 0.25 * edge / denominator
    f_capped = min(f_raw, MAX_KELLY_FRACTION)
    bet_dollars = round(f_capped * bankroll, 2)

    return round(f_capped, 6), bet_dollars


# ── Injury Flag Builder ────────────────────────────────────────────────────────

def _build_injury_flag(features: dict, sport: str, pick_side: str) -> tuple[str, str]:
    """
    Derive an injury flag and detail string from the feature vector.
    Returns (flag_code, human_readable_detail).
    """
    side = "home" if pick_side == "home" else "away"
    opp  = "away" if pick_side == "home" else "home"

    flags = []
    details = []

    our_adj = features.get(f"{side}_injury_adj", 0)
    opp_adj = features.get(f"{opp}_injury_adj", 0)
    our_returnee = features.get(f"{side}_has_returnee", 0)

    starter_key = "starter_out" if sport == "MLB" else "goalie_out"
    our_starter_out = features.get(f"{side}_{starter_key}", 0)
    opp_starter_out = features.get(f"{opp}_{starter_key}", 0)

    if our_starter_out:
        flags.append("starter_out")
        label = "starter" if sport == "MLB" else "goalie"
        details.append(f"Our {label} is OUT")

    if our_returnee:
        flags.append("returning")
        details.append("Player returning from IL (ramp factor applied)")

    if opp_adj >= 0.7 and our_adj < 0.3:
        flags.append("opponent_edge")
        details.append(f"Opponent injury burden: {opp_adj:.2f}")

    if not flags:
        return None, None

    flag_code = "combined" if len(flags) > 1 else flags[0]
    return flag_code, " | ".join(details)


# ── Confidence Tier ───────────────────────────────────────────────────────────

def _confidence_tier(edge: float) -> str:
    abs_edge = abs(edge)
    if abs_edge >= 0.08:
        return "HIGH"
    elif abs_edge >= 0.05:
        return "MED"
    else:
        return "LOW"


# ── Pick Label Builder ────────────────────────────────────────────────────────

def _build_pick_label(pick_side: str, home_team: str, away_team: str,
                       market: str, line: float | None = None) -> str:
    """Human-readable pick label including line where applicable."""
    if market in ("h2h", "h2h_3way"):
        team = home_team if pick_side == "home" else away_team
        return f"{team} ML"
    elif market == "totals":
        direction = "Over" if pick_side == "over" else "Under"
        line_str = f" {line}" if line is not None else ""
        return f"{home_team} vs {away_team} {direction}{line_str}"
    elif market == "spreads":
        team = home_team if pick_side == "home" else away_team
        if line is not None:
            spread = line if pick_side == "home" else -line
            sign = "+" if spread > 0 else ""
            return f"{team} {sign}{spread:.1f}"
        return f"{team} {pick_side.title()} Spread"
    return f"{pick_side.upper()}"


# ── Core Scorer ───────────────────────────────────────────────────────────────

def score_game(conn: DBConnection,
               game_id: str,
               model_id: str,
               features: dict,
               bankroll: float,
               dry_run: bool = False) -> list[dict]:
    """
    Score one game with one model. Generates 0, 1, or 2 pick rows
    (BET and/or AVOID signals).

    Returns list of pick dicts ready for DB insert.
    """
    sport, market, _ = MODELS[model_id]
    feature_cols = FEATURE_MAP[model_id]

    # Load model artifact
    artifact = load_model(model_id)
    if artifact is None:
        logger.warning(f"Skipping {game_id}/{model_id} — no trained model")
        return []

    clf          = artifact["model"]
    feat_cols    = artifact.get("feature_cols", feature_cols)

    # Build feature vector (fill missing with 0)
    x = np.array([features.get(c, 0.0) or 0.0 for c in feat_cols],
                  dtype=float).reshape(1, -1)

    # Get model probability
    try:
        probs = clf.predict_proba(x)[0]
        home_prob = float(probs[1])
        away_prob = 1.0 - home_prob
    except Exception as exc:
        logger.error(f"  Prediction error for {game_id}/{model_id}: {exc}")
        return []

    # Get DK odds
    odds = _get_dk_odds(conn, game_id, market)
    if not odds:
        logger.debug(f"  No DK odds for {game_id}/{model_id}")
        return []

    home_team = features.get("home_team", "")
    away_team = features.get("away_team", "")
    game_date = features.get("game_date", "")

    picks = []

    spread_home = odds.get("spread_home")
    total_line  = odds.get("total_line")

    if market in ("h2h", "h2h_3way", "spreads"):
        # ── Evaluate home side ────────────────────────────────────────────────
        home_dk_odds = odds.get("home_price")
        if home_dk_odds is not None:
            home_ip = american_to_implied_prob(home_dk_odds)
            if home_ip:
                home_edge = home_prob - home_ip
                pick = _make_pick(
                    game_id, model_id, sport, game_date,
                    pick_side="home",
                    pick_label=_build_pick_label("home", home_team, away_team, market, spread_home),
                    model_prob=home_prob,
                    dk_implied_prob=home_ip,
                    edge=home_edge,
                    dk_odds=home_dk_odds,
                    scored_line=spread_home,
                    bankroll=bankroll,
                    features=features,
                )
                if pick:
                    picks.append(pick)

        # ── Evaluate away side ─────────────────────────────────────────────────
        away_dk_odds = odds.get("away_price")
        if away_dk_odds is not None:
            away_ip = american_to_implied_prob(away_dk_odds)
            if away_ip:
                away_edge = away_prob - away_ip
                pick = _make_pick(
                    game_id, model_id, sport, game_date,
                    pick_side="away",
                    pick_label=_build_pick_label("away", home_team, away_team, market, spread_home),
                    model_prob=away_prob,
                    dk_implied_prob=away_ip,
                    edge=away_edge,
                    dk_odds=away_dk_odds,
                    scored_line=spread_home,
                    bankroll=bankroll,
                    features=features,
                )
                if pick:
                    picks.append(pick)

    elif market == "totals":
        over_odds  = odds.get("over_price")
        under_odds = odds.get("under_price")

        # Model prob for "home_win" is repurposed as "over" in totals model
        over_prob  = home_prob
        under_prob = away_prob

        for side, model_p, dk_odds_val in [
            ("over",  over_prob,  over_odds),
            ("under", under_prob, under_odds),
        ]:
            if dk_odds_val is None:
                continue
            ip   = american_to_implied_prob(dk_odds_val)
            edge = model_p - ip
            pick = _make_pick(
                game_id, model_id, sport, game_date,
                pick_side=side,
                pick_label=_build_pick_label(side, home_team, away_team, market, total_line),
                model_prob=model_p,
                dk_implied_prob=ip,
                edge=edge,
                dk_odds=dk_odds_val,
                scored_line=total_line,
                bankroll=bankroll,
                features=features,
            )
            if pick:
                picks.append(pick)

    # Write to DB
    if picks and not dry_run:
        _insert_picks(conn, picks)

    return picks


def _make_pick(game_id: str, model_id: str, sport: str, game_date: str,
               pick_side: str, pick_label: str,
               model_prob: float, dk_implied_prob: float, edge: float,
               dk_odds: float, bankroll: float,
               features: dict, scored_line: float | None = None) -> dict | None:
    """
    Classify edge and build pick dict. Returns None if no signal.
    """
    if abs(edge) > MAX_EDGE_CAP:
        logger.debug(f"  Edge {edge*100:+.1f}% exceeds cap — skipping (likely model noise)")
        return None

    bet_thresh   = MODEL_EDGE_THRESHOLDS.get(model_id, BET_EDGE_THRESHOLD)
    avoid_thresh = MODEL_EDGE_THRESHOLDS.get(model_id, AVOID_EDGE_THRESHOLD)

    if edge >= bet_thresh and model_prob >= MIN_MODEL_PROB:
        signal_type = "BET"
    elif edge <= -avoid_thresh:
        signal_type = "AVOID"
    else:
        return None   # no signal zone

    sport_from_model = MODELS[model_id][0]
    kelly_frac, rec_bet = quarter_kelly(model_prob, dk_implied_prob, bankroll)

    inj_flag, inj_detail = _build_injury_flag(features, sport_from_model, pick_side)
    conf_tier = _confidence_tier(edge)

    return {
        "game_id":           game_id,
        "model_id":          model_id,
        "sport":             sport,
        "game_date":         game_date,
        "pick_side":         pick_side,
        "pick_label":        pick_label,
        "model_probability": round(model_prob, 4),
        "dk_implied_prob":   round(dk_implied_prob, 4),
        "edge":              round(edge, 4),
        "dk_odds":           dk_odds,
        "scored_line":       scored_line,
        "kelly_fraction":    kelly_frac,
        "recommended_bet":   rec_bet,
        "bankroll_at_pick":  bankroll,
        "injury_flag":       inj_flag,
        "injury_detail":     inj_detail,
        "signal_type":       signal_type,
        "confidence_tier":   conf_tier,
        "result":            None,
        "profit_flat":       None,
        "profit_kelly":      None,
        "settled_at":        None,
    }


def _get_dk_odds(conn: DBConnection, game_id: str, market: str) -> dict | None:
    """
    Get most recent odds snapshot for a game+market.
    Tries DraftKings first; falls back to sbr_consensus for historical games.
    """
    cols = ["home_price", "away_price", "draw_price",
            "spread_home", "total_line", "over_price", "under_price"]

    # For spreads, filter to standard runline (±1.5 MLB, ±1.5 NHL) to avoid
    # alternate spread lines returned by the Odds API.
    spread_filter = ""
    if market == "spreads":
        spread_filter = "AND ABS(spread_home) = 1.5"

    for bookmaker in ("draftkings", "sbr_consensus"):
        row = conn.execute(f"""
            SELECT home_price, away_price, draw_price,
                   spread_home, total_line, over_price, under_price
            FROM odds
            WHERE game_id   = ?
              AND market    = ?
              AND bookmaker = ?
              {spread_filter}
            ORDER BY snapshot_at DESC
            LIMIT 1
        """, (game_id, market, bookmaker)).fetchone()

        if row:
            return dict(zip(cols, row))

    return None


def _insert_picks(conn: DBConnection, picks: list[dict]) -> None:
    sql = """
        INSERT INTO picks (
            game_id, model_id, sport, game_date, pick_side, pick_label,
            model_probability, dk_implied_prob, edge, dk_odds, scored_line,
            kelly_fraction, recommended_bet, bankroll_at_pick,
            injury_flag, injury_detail, signal_type, confidence_tier
        ) VALUES (
            %(game_id)s, %(model_id)s, %(sport)s, %(game_date)s, %(pick_side)s, %(pick_label)s,
            %(model_probability)s, %(dk_implied_prob)s, %(edge)s, %(dk_odds)s, %(scored_line)s,
            %(kelly_fraction)s, %(recommended_bet)s, %(bankroll_at_pick)s,
            %(injury_flag)s, %(injury_detail)s, %(signal_type)s, %(confidence_tier)s
        )
    """
    conn.executemany(sql, picks)


def check_line_movement(conn: DBConnection, game_date: str) -> list[dict]:
    """
    Compare scored odds against current (latest) odds for today's BET picks.
    Returns list of warning dicts for picks where the line has moved significantly.

    Thresholds:
      - Totals:  line moves 0.5+ against the bet → SKIP
      - Any bet: price moves 10+ cents against us (implied prob shift ≥ 3%) → CAUTION
    """
    picks = conn.execute("""
        SELECT p.pick_id, p.pick_label, p.pick_side, p.model_id,
               p.game_id, p.dk_odds AS scored_price, p.scored_line,
               o.market
        FROM picks p
        JOIN odds o ON o.game_id = p.game_id
            AND o.bookmaker = 'draftkings'
        WHERE p.game_date = ?
          AND p.signal_type = 'BET'
          AND o.market = CASE
              WHEN p.model_id LIKE '%over_under%' THEN 'totals'
              WHEN p.model_id LIKE '%runline%' OR p.model_id LIKE '%puckline%' THEN 'spreads'
              ELSE 'h2h' END
        ORDER BY o.snapshot_at DESC
    """, (game_date,)).fetchall()

    seen = set()
    warnings = []
    for row in picks:
        pick_id, label, side, model_id, game_id, scored_price, scored_line, market = row
        if pick_id in seen:
            continue
        seen.add(pick_id)

        # Get latest odds snapshot
        current = _get_dk_odds(conn, game_id, market)
        if not current:
            continue

        warning = {"pick_label": label, "status": None, "detail": ""}

        if market == "totals":
            cur_line = current.get("total_line")
            if cur_line is not None and scored_line is not None:
                delta = cur_line - scored_line
                # Under: line going DOWN hurts us; Over: line going UP hurts us
                if side == "under" and delta < -0.4:
                    warning["status"] = "SKIP"
                    warning["detail"] = f"Line moved from {scored_line} → {cur_line} (worse for Under)"
                elif side == "over" and delta > 0.4:
                    warning["status"] = "SKIP"
                    warning["detail"] = f"Line moved from {scored_line} → {cur_line} (worse for Over)"

        # Price movement check (all markets)
        cur_price = (
            current.get("over_price") if side == "over" else
            current.get("under_price") if side == "under" else
            current.get("home_price") if side == "home" else
            current.get("away_price")
        )
        if cur_price is not None and scored_price is not None:
            scored_ip = american_to_implied_prob(scored_price) or 0
            cur_ip    = american_to_implied_prob(cur_price) or 0
            ip_shift  = cur_ip - scored_ip   # positive = got more expensive (worse for bettor)
            if ip_shift >= 0.03 and warning["status"] != "SKIP":
                scored_str = f"+{int(scored_price)}" if scored_price > 0 else str(int(scored_price))
                cur_str    = f"+{int(cur_price)}"    if cur_price > 0    else str(int(cur_price))
                warning["status"] = "CAUTION"
                warning["detail"] = f"Price moved {scored_str} → {cur_str} (line steamed {ip_shift*100:.1f}pp against you)"

        if warning["status"]:
            warnings.append(warning)

    return warnings


def _log_pipeline(conn, run_date, status, records_in, records_out,
                  duration_s, error_msg=None):
    conn.execute("""
        INSERT INTO pipeline_log
            (run_date, step, status, records_in, records_out, duration_s, error_msg)
        VALUES (?, 'scoring', ?, ?, ?, ?, ?)
    """, (run_date, status, records_in, records_out, duration_s, error_msg))


# ── Main Daily Run ────────────────────────────────────────────────────────────

def run_scorer(target_date: str = None, dry_run: bool = False) -> dict:
    """
    Score all games scheduled for target_date across all models.

    Args:
        target_date: ISO date string (default: today)
        dry_run:     If True, print picks but don't write to DB

    Returns:
        Summary dict with total picks and breakdown.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    logger.info(f"\n{'═'*60}")
    logger.info(f"Daily Scorer — {target_date}")
    logger.info(f"{'═'*60}")

    start = datetime.now()
    conn = get_connection()

    try:
        # Get current bankroll from last settled pick or default
        bankroll = _get_current_bankroll(conn)
        logger.info(f"Current bankroll: ${bankroll:,.2f}")

        # Fetch today's games
        games = conn.execute("""
            SELECT game_id, sport, season, game_date, home_team, away_team
            FROM games
            WHERE game_date = ?
              AND home_score IS NULL
            ORDER BY sport, game_date
        """, (target_date,)).fetchall()

        if not games:
            logger.info(f"No games found for {target_date}")
            return {"target_date": target_date, "total_picks": 0}

        logger.info(f"Found {len(games)} games for {target_date}")

        # Delete any existing unsettled picks for this date before re-scoring.
        # This prevents duplicates when the scorer runs more than once (e.g. after
        # a line refresh). Settled picks (result IS NOT NULL) are never touched.
        if not dry_run:
            conn.execute("""
                DELETE FROM picks
                WHERE game_date = %s AND result IS NULL
            """, (target_date,))
            logger.info(f"Cleared existing unsettled picks for {target_date}")

        all_picks = []
        for game in games:
            game_id, sport, season, game_date, home_team, away_team = game

            # Build features once per game, reuse across all models for that sport
            odds_mlb_h2h  = _get_dk_odds(conn, game_id, "h2h")
            if sport == "MLB":
                features = build_mlb_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )
            else:  # NHL
                features = build_nhl_game_features(
                    conn, game_id, game_date, home_team, away_team, season,
                    odds_row=odds_mlb_h2h
                )

            if not features:
                continue

            # Run all models for this sport
            relevant_models = [mid for mid, (sp, _, _) in MODELS.items()
                               if sp == sport]

            for model_id in relevant_models:
                picks = score_game(conn, game_id, model_id, features,
                                    bankroll, dry_run=dry_run)
                all_picks.extend(picks)

                for p in picks:
                    signal = p["signal_type"]
                    tier   = p["confidence_tier"]
                    edge_pct = p["edge"] * 100
                    dk_odds_str = (
                        f"+{int(p['dk_odds'])}" if p['dk_odds'] > 0
                        else str(int(p['dk_odds']))
                    )
                    logger.info(
                        f"  [{signal}] {p['pick_label']} | "
                        f"DK={dk_odds_str} | "
                        f"model={p['model_probability']:.3f} | "
                        f"edge={edge_pct:+.1f}% | "
                        f"bet=${p['recommended_bet']:.0f} | "
                        f"[{tier}]"
                    )

        if not dry_run:
            conn.commit()

        bets   = [p for p in all_picks if p["signal_type"] == "BET"]
        avoids = [p for p in all_picks if p["signal_type"] == "AVOID"]

        duration = (datetime.now() - start).total_seconds()
        if not dry_run:
            _log_pipeline(conn, target_date, "success",
                          records_in=len(games),
                          records_out=len(all_picks),
                          duration_s=duration)
            conn.commit()

        logger.success(
            f"\nScoring complete: {len(bets)} BETs | "
            f"{len(avoids)} AVOIDs | {duration:.1f}s"
        )

        return {
            "target_date": target_date,
            "games":       len(games),
            "total_picks": len(all_picks),
            "bets":        len(bets),
            "avoids":      len(avoids),
            "dry_run":     dry_run,
            "duration_s":  duration,
        }

    except Exception as exc:
        conn.rollback()
        duration = (datetime.now() - start).total_seconds()
        _log_pipeline(conn, target_date, "error", 0, 0, duration, str(exc))
        conn.commit()
        logger.error(f"Scorer failed: {exc}")
        raise
    finally:
        conn.close()


def _get_current_bankroll(conn: DBConnection) -> float:
    """Get current bankroll from last pick or fall back to config default."""
    row = conn.execute("""
        SELECT bankroll_at_pick, profit_kelly
        FROM picks
        WHERE result IS NOT NULL
        ORDER BY settled_at DESC
        LIMIT 1
    """).fetchone()

    if row and row[0] is not None and row[1] is not None:
        return row[0] + row[1]

    return BANKROLL


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run daily scorer")
    parser.add_argument("--date",    dest="target_date",
                        help="Target date YYYY-MM-DD (default: today)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview picks without writing to DB")
    args = parser.parse_args()

    result = run_scorer(target_date=args.target_date, dry_run=args.dry_run)
    logger.info(f"\nDone: {result}")
