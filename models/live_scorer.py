"""
live_scorer.py — Phase 4 of the live (in-play) betting build.

In-play counterpart to models/scorer.py. The pre-game scorer skips games whose
commence_time has passed; this module scores ONLY games that are currently in
progress (latest live_game_state snapshot is abstract_game_state='Live').

Per live game it runs the LIVE_MODELS registry:
    mlb_live_win_prob    vs the in-play DK h2h prices (both sides)
    mlb_live_total_runs  vs the in-play DK total: the model predicts runs in
                         the REMAINDER, so P(over L) = P(rest > L − current)
                         via the Poisson CDF
    mlb_live_runline     vs the in-play DK spread — ONLY when the live line is
                         exactly home −1.5 (the model's fixed target)

Pick rows are written with is_live=true plus inning_at_pick and
score_diff_at_pick. Only BET/AVOID signals are written (no NONE rows — a live
game would otherwise generate hundreds of dead rows per day). Each scoring
pass deletes the game's unsettled live picks first, so the latest state always
wins — the live analog of the pre-game signal-flip rule. Settlement flows
through the standard game-level path in paper_tracker (market resolved via
LIVE_MODELS); CLV capture skips live picks (an in-play price has no meaningful
"closing line" comparison).

Staleness guards: scoring is skipped when the newest game-state snapshot is
older than LIVE_STATE_MAX_AGE_SEC (poller died) or the newest in-play odds
snapshot is older than LIVE_ODDS_MAX_AGE_SEC (line has moved since).
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    LIVE_MODELS,
    LIVE_ODDS_MAX_AGE_SEC,
    LIVE_STATE_MAX_AGE_SEC,
    MAX_EDGE_CAP,
    MODEL_EDGE_THRESHOLDS,
    MODEL_PROB_THRESHOLDS,
)
from data.db import get_connection, DBConnection
from features.live_game_features import build_live_state_row
from models.scorer import (
    _build_pick_label,
    _confidence_tier,
    _get_current_bankroll,
    _insert_picks,
    _link_for_side,
    _poisson_over_prob,
    american_to_implied_prob,
    quarter_kelly,
)
from models.trainer import load_model


# ── Helpers ───────────────────────────────────────────────────────────────────

def _age_seconds(iso_ts: Optional[str]) -> Optional[float]:
    """Seconds since an ISO timestamp (assumed UTC when naive). None on parse error."""
    if not iso_ts:
        return None
    try:
        ts = datetime.fromisoformat(str(iso_ts).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds()
    except Exception:
        return None


def _latest_live_state(conn: DBConnection, game_id: str) -> Optional[dict]:
    cols = ["inning", "inning_half", "outs", "bases_state",
            "home_score", "away_score", "abstract_game_state", "snapshot_at"]
    row = conn.execute(f"""
        SELECT {', '.join(cols)}
        FROM live_game_state
        WHERE game_id = %s
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id,)).fetchone()
    return dict(zip(cols, row)) if row else None


def _get_live_dk_odds(conn: DBConnection, game_id: str,
                      market: str) -> Optional[dict]:
    """
    Latest in-play DK snapshot for a game+market, or None when absent/stale.
    Unlike the pre-game `_get_dk_odds`, this REQUIRES snapshot_type='in_play'
    and never falls back to sbr_consensus.
    """
    cols = ["home_price", "away_price", "spread_home", "total_line",
            "over_price", "under_price", "snapshot_at",
            "home_link", "away_link", "over_link", "under_link"]
    row = conn.execute(f"""
        SELECT {', '.join(cols)}
        FROM odds
        WHERE game_id = %s
          AND market = %s
          AND bookmaker = 'draftkings'
          AND snapshot_type = 'in_play'
        ORDER BY snapshot_at DESC
        LIMIT 1
    """, (game_id, market)).fetchone()
    if not row:
        return None
    odds = dict(zip(cols, row))
    age = _age_seconds(odds.get("snapshot_at"))
    if age is None or age > LIVE_ODDS_MAX_AGE_SEC:
        logger.debug(f"  {game_id}/{market}: in-play odds stale "
                     f"({age and int(age)}s old) — skipping")
        return None
    return odds


def classify_live_signal(model_id: str, model_prob: float,
                         edge: float) -> Optional[str]:
    """
    BET / AVOID / None for live picks. NONE-zone picks return None (not
    written) — pure so it can be unit-tested.
    """
    if abs(edge) > MAX_EDGE_CAP:
        return None
    bet_thresh  = MODEL_EDGE_THRESHOLDS.get(model_id, 0.10)
    prob_thresh = MODEL_PROB_THRESHOLDS.get(model_id, 0.65)
    if edge >= bet_thresh and model_prob >= prob_thresh:
        return "BET"
    if edge <= -bet_thresh:
        return "AVOID"
    return None


def _make_live_pick(game_id: str, model_id: str, game_date: str,
                    pick_side: str, pick_label: str,
                    model_prob: float, dk_odds: float,
                    scored_line: Optional[float],
                    bankroll: float, state: dict,
                    commence_time: Optional[str],
                    dk_bet_link: Optional[str]) -> Optional[dict]:
    """Build a live pick dict, or None when the signal is in the dead zone."""
    implied = american_to_implied_prob(dk_odds)
    if implied is None:
        return None
    edge = model_prob - implied

    signal = classify_live_signal(model_id, model_prob, edge)
    if signal is None:
        return None

    kelly_frac, rec_bet = (quarter_kelly(model_prob, implied, bankroll)
                           if signal == "BET" else (0.0, 0.0))

    score_diff = None
    if state.get("home_score") is not None and state.get("away_score") is not None:
        score_diff = int(state["home_score"]) - int(state["away_score"])

    return {
        "game_id":            game_id,
        "model_id":           model_id,
        "sport":              LIVE_MODELS[model_id][0],
        "game_date":          game_date,
        "pick_side":          pick_side,
        "pick_label":         pick_label,
        "model_probability":  round(model_prob, 4),
        "dk_implied_prob":    round(implied, 4),
        "edge":               round(edge, 4),
        "dk_odds":            dk_odds,
        "scored_line":        scored_line,
        "kelly_fraction":     kelly_frac,
        "recommended_bet":    rec_bet,
        "bankroll_at_pick":   bankroll,
        "injury_flag":        None,
        "injury_detail":      None,
        "signal_type":        signal,
        "confidence_tier":    _confidence_tier(edge),
        "game_time":          commence_time,
        "dk_bet_link":        dk_bet_link,
        "is_live":            True,
        "inning_at_pick":     state.get("inning"),
        "score_diff_at_pick": score_diff,
    }


# ── Per-model scoring ─────────────────────────────────────────────────────────

def _score_live_model(conn: DBConnection, model_id: str, artifact: dict,
                      game: dict, state: dict, pregame: dict,
                      bankroll: float) -> list[dict]:
    """Score one live model for one in-progress game. Returns 0..2 pick dicts."""
    sport, market, model_type, _ = LIVE_MODELS[model_id]
    game_id   = game["game_id"]
    home_team = game["home_team"]
    away_team = game["away_team"]

    odds = _get_live_dk_odds(conn, game_id, market)
    if not odds:
        return []

    row = build_live_state_row(state, pregame, model_id)
    if row is None:
        return []

    feat_cols = artifact["feature_cols"]
    x = np.array([[np.nan if row.get(c) is None else float(row[c])
                   for c in feat_cols]], dtype=float)

    clf = artifact["model"]
    picks: list[dict] = []
    label_suffix = " (live)"

    if model_type == "binary":
        try:
            p_home = float(clf.predict_proba(x)[0][1])
        except Exception as exc:
            logger.error(f"  {game_id}/{model_id}: prediction error: {exc}")
            return []

        if market == "spreads":
            # The model's fixed target is "home wins by 2+" — only meaningful
            # against a live home −1.5 line. DK in-play run lines move; skip
            # any other number rather than score the wrong proposition.
            if odds.get("spread_home") is None or float(odds["spread_home"]) != -1.5:
                return []

        for side, prob, price in [("home", p_home, odds.get("home_price")),
                                  ("away", 1.0 - p_home, odds.get("away_price"))]:
            if price is None:
                continue
            label = _build_pick_label(side, home_team, away_team, market,
                                      odds.get("spread_home")) + label_suffix
            pick = _make_live_pick(
                game_id, model_id, game["game_date"], side, label,
                prob, price, odds.get("spread_home"), bankroll, state,
                game.get("commence_time"), _link_for_side(odds, side))
            if pick:
                picks.append(pick)

    else:  # poisson — expected runs in the remainder of the game
        line = odds.get("total_line")
        if line is None:
            return []
        try:
            lam = float(np.clip(clf.predict(x)[0], 1e-6, None))
        except Exception as exc:
            logger.error(f"  {game_id}/{model_id}: prediction error: {exc}")
            return []

        current_total = row["total_runs"]
        rest_line = float(line) - current_total
        if rest_line < 0:
            # Over already clinched — no bettable proposition.
            return []
        p_over = _poisson_over_prob(lam, rest_line)

        for side, prob, price in [("over", p_over, odds.get("over_price")),
                                  ("under", 1.0 - p_over, odds.get("under_price"))]:
            if price is None:
                continue
            label = _build_pick_label(side, home_team, away_team, market,
                                      line) + label_suffix
            pick = _make_live_pick(
                game_id, model_id, game["game_date"], side, label,
                prob, price, line, bankroll, state,
                game.get("commence_time"), _link_for_side(odds, side))
            if pick:
                picks.append(pick)

    return picks


# ── Entry point ───────────────────────────────────────────────────────────────

def run_live_scorer(target_date: Optional[str] = None,
                    game_ids: Optional[set[str]] = None,
                    dry_run: bool = False) -> dict:
    """
    Score every in-progress game (or just `game_ids`) with all live models.
    Safe to call repeatedly — each pass replaces the game's unsettled live picks.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    conn = get_connection()
    summary = {"target_date": target_date, "games_scored": 0,
               "picks": 0, "bets": 0, "avoids": 0}
    try:
        artifacts = {}
        for model_id in LIVE_MODELS:
            art = load_model(model_id)
            if art:
                artifacts[model_id] = art
        if not artifacts:
            logger.warning("Live scorer: no trained live models registered — "
                           "run `python -m models.trainer --all-live` first")
            return summary

        bankroll = _get_current_bankroll(conn)

        now_utc = datetime.now(timezone.utc).isoformat()
        rows = conn.execute("""
            SELECT game_id, game_date, season, home_team, away_team, commence_time
            FROM games
            WHERE sport = 'MLB'
              AND game_date = %s
              AND home_score IS NULL
              AND commence_time IS NOT NULL
              AND commence_time <= %s
        """, (target_date, now_utc)).fetchall()
        games = [dict(zip(["game_id", "game_date", "season", "home_team",
                           "away_team", "commence_time"], r)) for r in rows]
        if game_ids is not None:
            games = [g for g in games if g["game_id"] in game_ids]

        if not games:
            logger.info(f"Live scorer: no started games for {target_date}")
            return summary

        from features.feature_engine import build_mlb_game_features
        from models.scorer import _get_dk_odds

        all_picks: list[dict] = []
        for game in games:
            state = _latest_live_state(conn, game["game_id"])
            if not state or state.get("abstract_game_state") != "Live":
                continue
            age = _age_seconds(state.get("snapshot_at"))
            if age is None or age > LIVE_STATE_MAX_AGE_SEC:
                logger.debug(f"  {game['game_id']}: state snapshot stale — skipping")
                continue

            pregame = build_mlb_game_features(
                conn, game["game_id"], game["game_date"],
                game["home_team"], game["away_team"], game["season"],
                odds_row=_get_dk_odds(conn, game["game_id"], "h2h"))
            if not pregame:
                continue

            game_picks: list[dict] = []
            for model_id, artifact in artifacts.items():
                game_picks.extend(_score_live_model(
                    conn, model_id, artifact, game, state, pregame, bankroll))

            if not dry_run:
                # Replace this game's unsettled live picks with the fresh set —
                # the live analog of the pre-game signal-flip rule.
                conn.execute("""
                    DELETE FROM picks
                    WHERE game_id = %s AND result IS NULL AND is_live = TRUE
                """, (game["game_id"],))
                if game_picks:
                    _insert_picks(conn, game_picks)
            summary["games_scored"] += 1

            for p in game_picks:
                logger.info(
                    f"  [LIVE {p['signal_type']}] {p['pick_label']} | "
                    f"inning {p['inning_at_pick']} | DK={p['dk_odds']:+.0f} | "
                    f"model={p['model_probability']:.3f} | "
                    f"edge={p['edge']*100:+.1f}% | bet=${p['recommended_bet']:.0f}")
            all_picks.extend(game_picks)

        if not dry_run:
            conn.commit()

        summary["picks"]  = len(all_picks)
        summary["bets"]   = sum(1 for p in all_picks if p["signal_type"] == "BET")
        summary["avoids"] = sum(1 for p in all_picks if p["signal_type"] == "AVOID")
        logger.success(f"Live scorer: {summary['games_scored']} game(s), "
                       f"{summary['bets']} BET / {summary['avoids']} AVOID")
        return summary
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Score in-progress games with live models")
    parser.add_argument("--date",    default=None, help="Date to score (YYYY-MM-DD)")
    parser.add_argument("--game-id", default=None, help="Restrict to one game_id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ids = {args.game_id} if args.game_id else None
    run_live_scorer(target_date=args.date, game_ids=ids, dry_run=args.dry_run)
