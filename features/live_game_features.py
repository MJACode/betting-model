"""
live_game_features.py — Phase 2 of the live (in-play) betting build.

Builds the state-vector feature row for live model scoring AND the training
matrix for the live win-probability models. Mirrors the pre-game builders in
features/feature_engine.py but layers the CURRENT game state on top of the
pre-game context (starter ERA, team wRC+, weather, ...), so a live model knows
both "who is better" and "where we are in the game".

Two markets this round:
    mlb_live_moneyline   — classifier, target home_won
    mlb_live_over_under  — Poisson, target final total runs

State features (per row):
    inning, inning_half_top, outs, bases_code (0..7),
    score_diff (home - away), abs_score_diff, home_batting, current_total_runs

Training rows come from the `plays` table (state BEFORE each play, label =
final game outcome). Live-scoring rows come from the latest `live_game_state`
snapshot. Both encodings are identical, so train/serve match structurally.

No look-ahead bias: the pre-game context is as-of pre-first-pitch (ASOF /
exact-date / strictly-before lookups in feature_engine); the only future info
is the label, which is correct.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LIVE_MODELS, LIVE_TRAIN_STRIDE, LIVE_TRAIN_MAX_ROWS
from data.db import get_connection, DBConnection
from features.feature_engine import (
    _build_bulk_mlb_lookups, _build_mlb_features_from_bulk, build_mlb_game_features,
    MLB_H2H_FEATURES, MLB_TOTALS_FEATURES,
)

RANDOM_STATE = 42   # matches models/trainer.py for reproducible subsampling


# ── Feature column groups ─────────────────────────────────────────────────────

LIVE_STATE_FEATURES = [
    "inning", "inning_half_top", "outs", "bases_code",
    "score_diff", "abs_score_diff", "home_batting",
    "current_total_runs",   # informative for totals; harmless for moneyline
]

# Live models reuse the EXISTING pre-game feature vectors and add the live state.
LIVE_ML_FEATURES     = LIVE_STATE_FEATURES + MLB_H2H_FEATURES
LIVE_TOTALS_FEATURES = LIVE_STATE_FEATURES + MLB_TOTALS_FEATURES

LIVE_FEATURE_MAP = {
    "mlb_live_moneyline":  LIVE_ML_FEATURES,
    "mlb_live_over_under": LIVE_TOTALS_FEATURES,
}

_META_COLS = ["game_id", "game_date", "sport", "season", "home_team", "away_team"]


# ── Pure helpers (unit-tested) ────────────────────────────────────────────────

def bases_code(bases_state: str) -> int:
    """
    Encode a '1B-2B-3B' binary string as a 0..7 enum.
    LSB = first base: '000'->0, '100'->1, '010'->2, '110'->3,
                      '001'->4, '101'->5, '011'->6, '111'->7.
    """
    if not bases_state or len(bases_state) < 3:
        return 0
    b1, b2, b3 = (c == "1" for c in bases_state[:3])
    return int(b1) + 2 * int(b2) + 4 * int(b3)


def state_cols(inning, inning_half, outs, bases_state,
               home_score, away_score) -> dict:
    """Build the live-state feature columns from raw game-state values."""
    half = (inning_half or "").lower()
    home = int(home_score or 0)
    away = int(away_score or 0)
    return {
        "inning":             int(inning or 0),
        "inning_half_top":    int(half == "top"),
        "outs":               int(outs or 0),
        "bases_code":         bases_code(bases_state or "000"),
        "score_diff":         home - away,
        "abs_score_diff":     abs(home - away),
        "home_batting":       int(half == "bottom"),
        "current_total_runs": home + away,
    }


# ── Training matrix ───────────────────────────────────────────────────────────

def build_live_training_rows(model_id: str, seasons: list[int]) -> pd.DataFrame:
    """
    Build the live-model training matrix from the `plays` table joined to
    per-game pre-game features. Subsamples ~2.4M plays down to state-change
    rows (× stride, capped at LIVE_TRAIN_MAX_ROWS) so it stays tractable.

    Returns DataFrame[_META_COLS + LIVE_FEATURE_MAP[model_id] + 'target'],
    with null-feature rows dropped (same convention as build_training_dataset).
    """
    if model_id not in LIVE_MODELS:
        raise ValueError(f"Unknown live model: {model_id}")
    sport, market, _model_type, _ = LIVE_MODELS[model_id]
    feature_cols = LIVE_FEATURE_MAP[model_id]

    conn = get_connection()
    try:
        bulk = _build_bulk_mlb_lookups(conn, seasons)

        placeholders = ",".join(["%s"] * len(seasons))
        play_rows = conn.execute(f"""
            SELECT p.game_id, p.play_index, p.inning, p.half_inning,
                   p.outs_before, p.bases_before,
                   p.score_home_before, p.score_away_before,
                   g.season, g.game_date, g.home_team, g.away_team,
                   g.home_score, g.away_score, g.home_win
            FROM plays p
            JOIN games g ON g.game_id = p.game_id
            WHERE p.season IN ({placeholders})
              AND g.home_score IS NOT NULL
              AND p.home_won IS NOT NULL
            ORDER BY p.game_id, p.play_index
        """, list(seasons)).fetchall()
    finally:
        conn.close()

    if not play_rows:
        logger.warning(f"No plays found for {model_id} seasons {seasons} "
                       f"(has the PBP backfill run?)")
        return pd.DataFrame()

    cols = ["game_id", "play_index", "inning", "half_inning",
            "outs_before", "bases_before", "score_home_before", "score_away_before",
            "season", "game_date", "home_team", "away_team",
            "home_score", "away_score", "home_win"]
    plays = pd.DataFrame(play_rows, columns=cols)
    logger.info(f"Live {model_id}: {len(plays):,} raw plays loaded")

    # ── Subsample 1: keep only state-CHANGE rows (drop consecutive duplicates) ─
    # Matches inference distribution — the live scorer fires on inning/score
    # changes, never on every pitch.
    state_tuple = list(zip(
        plays["inning"], plays["half_inning"], plays["outs_before"],
        plays["bases_before"], plays["score_home_before"], plays["score_away_before"],
    ))
    plays = plays.assign(_state=state_tuple)
    prev = plays.groupby("game_id", sort=False)["_state"].shift()
    plays = plays[plays["_state"] != prev].drop(columns="_state").reset_index(drop=True)
    logger.info(f"  {len(plays):,} after state-change dedupe")

    # ── Subsample 2: deterministic stride ─────────────────────────────────────
    if LIVE_TRAIN_STRIDE > 1:
        plays = plays.iloc[::LIVE_TRAIN_STRIDE].reset_index(drop=True)
        logger.info(f"  {len(plays):,} after stride {LIVE_TRAIN_STRIDE}")

    # ── Subsample 3: hard cap (seeded random sample) ──────────────────────────
    if len(plays) > LIVE_TRAIN_MAX_ROWS:
        plays = plays.sample(n=LIVE_TRAIN_MAX_ROWS,
                             random_state=RANDOM_STATE).reset_index(drop=True)
        logger.info(f"  {len(plays):,} after MAX_ROWS cap")

    # ── Build feature rows; cache the pre-game vector per game ────────────────
    pregame_cache: dict[str, dict | None] = {}
    rows = []
    for r in plays.itertuples(index=False):
        gid = r.game_id
        if gid not in pregame_cache:
            # For totals, inject the pre-game total line as context; moneyline
            # doesn't use it. Use the same bulk odds the pre-game models train on.
            odds_row = bulk["odds"].get((gid, "totals")) if market == "totals" else None
            try:
                pre = _build_mlb_features_from_bulk(
                    bulk, gid, r.game_date, r.home_team, r.away_team,
                    int(r.season), odds_row)
            except Exception as exc:           # noqa: BLE001 — skip a bad game
                logger.debug(f"  pre-game build failed for {gid}: {exc}")
                pre = None
            pregame_cache[gid] = pre
        pre = pregame_cache[gid]
        if pre is None:
            continue

        st = state_cols(r.inning, r.half_inning, r.outs_before, r.bases_before,
                        r.score_home_before, r.score_away_before)

        if market == "h2h":
            target = int(r.home_win == 1)
        else:  # totals — final total runs (Poisson)
            target = float((r.home_score or 0) + (r.away_score or 0))

        rows.append({**pre, **st, "target": target})

    if not rows:
        logger.warning(f"No live training rows assembled for {model_id}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    keep = _META_COLS + [c for c in feature_cols if c in df.columns] + ["target"]
    df = df[[c for c in keep if c in df.columns]]

    num_cols = [c for c in df.columns if c not in _META_COLS + ["target"]]
    before = len(df)
    df = df.dropna(subset=num_cols)
    dropped = before - len(df)
    if dropped:
        logger.info(f"  Dropped {dropped} rows with null features ({dropped/before:.1%})")

    logger.success(f"{model_id}: {len(df):,} live training rows "
                   f"(target mean {df['target'].mean():.3f})")
    return df


# ── Live-scoring single row ───────────────────────────────────────────────────

def build_live_state_row(conn: DBConnection, game_id: str,
                         live_state: dict) -> dict | None:
    """
    Build one combined (pre-game + live-state) feature dict for live scoring.

    live_state is the latest live_game_state snapshot dict with keys:
        inning, inning_half, outs, bases_state, home_score, away_score, ...

    Returns a flat dict with every column both live models need, or None if the
    game metadata is missing. The live scorer selects per-model columns via
    LIVE_FEATURE_MAP.
    """
    meta = conn.execute("""
        SELECT sport, season, game_date, home_team, away_team
        FROM games WHERE game_id = ?
    """, (game_id,)).fetchone()
    if not meta:
        logger.warning(f"build_live_state_row: no games row for {game_id}")
        return None
    sport, season, game_date, home_team, away_team = meta
    if sport != "MLB":
        return None

    # Pre-game total line as context for the totals feature (latest non-in-play).
    total_row = conn.execute("""
        SELECT total_line, spread_home FROM odds
        WHERE game_id = ? AND market = 'totals'
          AND snapshot_type IN ('open', 'close')
        ORDER BY snapshot_at DESC LIMIT 1
    """, (game_id,)).fetchone()
    odds_row = {"total_line": total_row[0], "spread_home": None} if total_row else None

    pre = build_mlb_game_features(conn, game_id, game_date,
                                  home_team, away_team, int(season), odds_row)
    if pre is None:
        return None

    st = state_cols(
        live_state.get("inning"), live_state.get("inning_half"),
        live_state.get("outs"), live_state.get("bases_state"),
        live_state.get("home_score"), live_state.get("away_score"),
    )
    return {**pre, **st}
