"""
live_scorer.py — Phase 4 of the live (in-play) betting build.

In-play counterpart to models/scorer.py. Unlike the pre-game scorer (which
LOCKS each game at first pitch), this scorer fires precisely WHILE a game is in
progress: it is dispatched by the trigger orchestrator when a state change
(inning/score) lands, and only scores games whose live snapshot is 'Live'.

For each live model it:
  - builds the combined (pre-game context + current state) feature row,
  - predicts: moneyline → P(home wins | state); totals → Poisson λ for the
    final total, scored by Poisson-CDF vs the live DK total line,
  - compares to the live DK implied prob to get an edge,
  - classifies BET/AVOID/NONE with the LIVE thresholds and Kelly-sizes,
  - writes picks with is_live=True, inning_at_pick, score_diff_at_pick.

Dedup: the same (game_id, model_id, pick_side, inning_at_pick,
score_diff_at_pick) state never double-inserts, so re-firing on an unchanged
state is a no-op. Settlement (tracking/paper_tracker.py) handles these picks on
the final game outcome with no extra code — see _market_for_pick there.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    LIVE_MODELS, LIVE_MODEL_EDGE_THRESHOLDS, LIVE_MODEL_PROB_THRESHOLDS,
    MAX_EDGE_CAP,
)
from data.db import DBConnection
from data.ingestors.live_odds_ingestor import live_odds_lookup
from features.live_game_features import LIVE_FEATURE_MAP, build_live_state_row
from models.trainer import load_model
from models.scorer import (
    american_to_implied_prob, quarter_kelly, _confidence_tier,
    _build_pick_label, _build_injury_flag, _poisson_over_prob, _insert_picks,
)


def _classify(model_id: str, model_prob: float, edge: float) -> str:
    """BET / AVOID / NONE using the LIVE thresholds."""
    bet_thresh = LIVE_MODEL_EDGE_THRESHOLDS.get(model_id, 0.05)
    prob_thresh = LIVE_MODEL_PROB_THRESHOLDS.get(model_id, 0.55)
    if edge >= bet_thresh and model_prob >= prob_thresh:
        return "BET"
    if edge <= -bet_thresh:
        return "AVOID"
    return "NONE"


def _existing_live_keys(conn: DBConnection, game_id: str) -> set:
    """Keys of unsettled live picks already written for this game (dedup)."""
    rows = conn.execute("""
        SELECT model_id, pick_side, inning_at_pick, score_diff_at_pick
        FROM picks
        WHERE game_id = ? AND is_live = TRUE AND result IS NULL
    """, (game_id,)).fetchall()
    return {(r[0], r[1], r[2], r[3]) for r in rows}


def _make_live_pick(feat: dict, model_id: str, sport: str, market: str,
                    pick_side: str, pick_label: str,
                    model_prob: float, dk_odds: float | None,
                    bankroll: float, inning_at_pick: int, score_diff_at_pick: int,
                    scored_line: float | None) -> dict | None:
    """Build a live pick dict (or None if edge exceeds the noise cap)."""
    implied = american_to_implied_prob(dk_odds)
    if implied is None:
        return None
    edge = model_prob - implied
    if abs(edge) > MAX_EDGE_CAP:
        return None

    signal_type = _classify(model_id, model_prob, edge)
    if signal_type == "NONE":
        kelly_frac, rec_bet = 0.0, 0.0
    else:
        kelly_frac, rec_bet = quarter_kelly(model_prob, implied, bankroll)

    inj_flag, inj_detail = _build_injury_flag(feat, sport, pick_side)

    return {
        "game_id":           feat["game_id"],
        "model_id":          model_id,
        "sport":             sport,
        "game_date":         feat["game_date"],
        "pick_side":         pick_side,
        "pick_label":        pick_label,
        "model_probability": round(model_prob, 4),
        "dk_implied_prob":   round(implied, 4),
        "edge":              round(edge, 4),
        "dk_odds":           dk_odds,
        "scored_line":       scored_line,
        "kelly_fraction":    kelly_frac,
        "recommended_bet":   rec_bet,
        "bankroll_at_pick":  bankroll,
        "injury_flag":       inj_flag,
        "injury_detail":     inj_detail,
        "signal_type":       signal_type,
        "confidence_tier":   _confidence_tier(edge),
        "game_time":         None,
        "is_live":           True,
        "inning_at_pick":    inning_at_pick,
        "score_diff_at_pick": score_diff_at_pick,
    }


def run_live_scorer(conn: DBConnection, game_id: str, state: dict,
                    bankroll: float, dry_run: bool = False) -> list[dict]:
    """
    Score one in-progress game with the live models. Returns the pick dicts
    written (empty when the game is not Live, no live odds are available, or
    every pick is a dedup/no-edge skip).
    """
    if (state.get("abstract_game_state") or "") != "Live":
        return []

    feat = build_live_state_row(conn, game_id, state)
    if feat is None:
        return []

    home_team = feat.get("home_team", "")
    away_team = feat.get("away_team", "")
    inning_at_pick = int(state.get("inning") or 0)
    score_diff_at_pick = int(state.get("home_score") or 0) - int(state.get("away_score") or 0)

    existing = _existing_live_keys(conn, game_id)
    picks: list[dict] = []

    for model_id, (sport, market, model_type, _desc) in LIVE_MODELS.items():
        art = load_model(model_id)
        if art is None:
            logger.debug(f"live: no trained model {model_id} — skipping")
            continue

        feat_cols = art["feature_cols"]
        mdl = art["model"]
        x = np.array([feat.get(c, 0.0) or 0.0 for c in feat_cols], dtype=float).reshape(1, -1)

        odds = live_odds_lookup(conn, game_id, market)
        if not odds:
            continue   # graceful degrade — no live DK line → no pick (F5 pattern)

        candidates = []   # (pick_side, pick_label, model_prob, dk_odds, scored_line)
        if market == "h2h":
            home_prob = float(mdl.predict_proba(x)[0][1])
            candidates.append(("home", _build_pick_label("home", home_team, away_team, "h2h"),
                               home_prob, odds.get("home_price"), None))
            candidates.append(("away", _build_pick_label("away", home_team, away_team, "h2h"),
                               1.0 - home_prob, odds.get("away_price"), None))
        else:  # totals
            line = odds.get("total_line")
            if line is None:
                continue
            lam = float(np.clip(mdl.predict(x)[0], 1e-6, None))
            p_over = _poisson_over_prob(lam, line)
            candidates.append(("over", _build_pick_label("over", home_team, away_team, "totals", line),
                               p_over, odds.get("over_price"), line))
            candidates.append(("under", _build_pick_label("under", home_team, away_team, "totals", line),
                               1.0 - p_over, odds.get("under_price"), line))

        for pick_side, label, prob, dk_odds, scored_line in candidates:
            if dk_odds is None:
                continue
            if (model_id, pick_side, inning_at_pick, score_diff_at_pick) in existing:
                continue   # already wrote this exact state's pick
            pick = _make_live_pick(feat, model_id, sport, market, pick_side, label,
                                   prob, dk_odds, bankroll,
                                   inning_at_pick, score_diff_at_pick, scored_line)
            if pick is not None:
                picks.append(pick)
                existing.add((model_id, pick_side, inning_at_pick, score_diff_at_pick))

    if picks and not dry_run:
        _insert_picks(conn, picks)
        conn.commit()

    bets = sum(1 for p in picks if p["signal_type"] == "BET")
    if picks:
        logger.info(f"live: {game_id} inn {inning_at_pick} "
                    f"({score_diff_at_pick:+d}) → {len(picks)} picks, {bets} BET"
                    + (" [dry-run]" if dry_run else ""))
    return picks
