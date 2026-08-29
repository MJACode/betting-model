"""
live_game_features.py — Phase 2 of the live (in-play) betting build.

Builds the feature row for live win-probability models. Every row is
    [ in-game STATE features ] + [ pre-game CONTEXT features ]

The state features are derived through ONE shared pure function
(`state_features`) from both data sources:
  - training:  the `plays` table (state BEFORE each play — backfilled from the
               same MLB Stats API live feed the poller reads)
  - serving:   the latest `live_game_state` snapshot written by the poller
so the vector at training time is structurally identical to the vector at
inference time — no parser drift between train and serve.

Pre-game context reuses the existing engines:
  - training:  `_build_bulk_mlb_lookups` + `_build_mlb_features_from_bulk`
               (one row per game, merged onto every play of that game)
  - serving:   `build_mlb_game_features` (per-game path, ~15 games/day)
Both paths only read data with `as_of_date <= game_date` — no look-ahead.

Live models (config.LIVE_MODELS):
    mlb_live_total_runs  poisson  target = runs scored in the REMAINDER of the
                                  game (final_total − total_before). At score
                                  time P(over L) = P(rest > L − current_total)
                                  via the Poisson CDF — the live line never
                                  enters the feature vector, so there is no
                                  line leakage between train and serve.

mlb_live_win_prob (binary, home_won) and mlb_live_runline (binary, home by 2+)
were RETIRED 2026-08-30 — both were badly overconfident in production and their
features, labels and map entries went with them. See config.LIVE_MODELS.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LIVE_MODELS
from data.db import get_connection, DBConnection


# ── Feature Column Groups ─────────────────────────────────────────────────────

# In-game state — derivable identically from `plays` (train) and
# `live_game_state` (serve). Order matters: it defines the model input layout.
LIVE_STATE_FEATURES = [
    "inning",
    "is_top_inning",
    "outs",
    "on_1b", "on_2b", "on_3b",
    "score_diff",          # home − away
    "total_runs",          # home + away (drives the totals model)
    "half_innings_left",   # regulation half-innings remaining incl. current
]

# Pre-game context subsets — all columns exist in the dict returned by
# build_mlb_game_features / _build_mlb_features_from_bulk.
#
# The H2H context list lived here for mlb_live_win_prob and mlb_live_runline,
# both RETIRED 2026-08-30 (config.LIVE_MODELS). Kept because the pre-game
# builder still emits these columns and a revived win-probability model would
# start from this same layout — but deliberately NOT wired into
# LIVE_FEATURE_MAP, so nothing consumes it today.
LIVE_PREGAME_H2H_CONTEXT = [
    "d_team_era", "d_bullpen_era", "d_woba", "d_wrc_plus",
    "d_starter_era", "d_starter_era_last3",
    "home_win_pct", "away_win_pct", "d_run_differential",
]

LIVE_PREGAME_TOTALS_CONTEXT = [
    "home_team_era", "away_team_era",
    "home_bullpen_era", "away_bullpen_era",
    "home_runs_last_10", "away_runs_last_10",
    "wind_out_component", "temp_f", "is_dome_game",
]

LIVE_FEATURE_MAP = {
    "mlb_live_total_runs": LIVE_STATE_FEATURES + LIVE_PREGAME_TOTALS_CONTEXT,
}


# ── Shared state-vector builder (pure) ────────────────────────────────────────

def parse_bases(bases_state: Optional[str]) -> tuple[int, int, int]:
    """'101' → (1, 0, 1). Anything malformed → bases empty."""
    if not bases_state or len(bases_state) != 3:
        return 0, 0, 0
    return tuple(1 if c == "1" else 0 for c in bases_state)  # type: ignore[return-value]


def half_innings_left(inning: int, is_top: bool) -> int:
    """
    Regulation half-innings remaining INCLUDING the current one.
    Top 1st → 18, bottom 9th → 1, extras clamp to 1 (sudden-death analog).
    """
    completed = (inning - 1) * 2 + (0 if is_top else 1)
    return max(18 - completed, 1)


def state_features(inning: Optional[int],
                   half_inning: Optional[str],
                   outs: Optional[int],
                   bases_state: Optional[str],
                   score_home: Optional[int],
                   score_away: Optional[int]) -> Optional[dict]:
    """
    The ONE state encoder used by both training rows and live scoring.
    Returns None when the state is unusable (missing inning/score).
    """
    if inning is None or score_home is None or score_away is None:
        return None
    is_top = (half_inning or "").lower() == "top"
    on_1b, on_2b, on_3b = parse_bases(bases_state)
    outs_clamped = min(max(int(outs or 0), 0), 2)
    return {
        "inning":            int(inning),
        "is_top_inning":     int(is_top),
        "outs":              outs_clamped,
        "on_1b":             on_1b,
        "on_2b":             on_2b,
        "on_3b":             on_3b,
        "score_diff":        int(score_home) - int(score_away),
        "total_runs":        int(score_home) + int(score_away),
        "half_innings_left": half_innings_left(int(inning), is_top),
    }


# ── Targets (pure) ────────────────────────────────────────────────────────────

def compute_live_target(model_id: str,
                        home_won: Optional[int],
                        final_home: Optional[int],
                        final_away: Optional[int],
                        total_before: int) -> Optional[float]:
    """
    Per-play training label for each live model. None = row unusable.

    `home_won` is unused since the two binary live models were retired
    (2026-08-30) — kept in the signature because the plays table carries it and
    any revived win-probability model needs exactly this label.
    """
    if final_home is None or final_away is None:
        return None

    if model_id == "mlb_live_total_runs":
        rest = (final_home + final_away) - total_before
        # Negative rest means a state glitch in the PBP feed — drop the row.
        return float(rest) if rest >= 0 else None

    raise ValueError(f"Unknown live model_id: {model_id}")


# ── Serving path ──────────────────────────────────────────────────────────────

def build_live_state_row(state: dict, pregame_features: dict,
                         model_id: str) -> Optional[dict]:
    """
    Merge a live_game_state snapshot dict with pre-game features into the
    feature row for one live model. `state` keys match the live_game_state
    columns (inning, inning_half, outs, bases_state, home_score, away_score).
    """
    st = state_features(
        state.get("inning"), state.get("inning_half"), state.get("outs"),
        state.get("bases_state"), state.get("home_score"), state.get("away_score"),
    )
    if st is None:
        return None
    row = dict(st)
    for col in LIVE_FEATURE_MAP[model_id]:
        if col not in row:
            row[col] = pregame_features.get(col)
    return row


# ── Training path ─────────────────────────────────────────────────────────────

_PLAY_COLS = [
    "game_id", "inning", "half_inning", "outs_before", "bases_before",
    "score_home_before", "score_away_before", "home_won",
]


def build_live_training_dataset(model_id: str,
                                seasons: list[int],
                                sample_frac: float = 1.0) -> pd.DataFrame:
    """
    One row per play (≈ one per plate appearance) across the given seasons:
    state-before features + that game's pre-game context + target.

    Memory strategy: plays are loaded per season into a slim DataFrame, the
    per-game pre-game context is built once per game from the bulk lookups,
    and the two are merged on game_id — never one dict per play.
    """
    if model_id not in LIVE_MODELS:
        raise ValueError(f"Unknown live model_id: {model_id}. "
                         f"Available: {list(LIVE_MODELS.keys())}")

    from features.feature_engine import (
        _build_bulk_mlb_lookups, _build_mlb_features_from_bulk,
    )

    feature_cols = LIVE_FEATURE_MAP[model_id]
    pregame_cols = [c for c in feature_cols if c not in LIVE_STATE_FEATURES]

    conn = get_connection()
    try:
        # Completed games for these seasons — gives final scores for targets
        # and the team/date metadata for pre-game context.
        placeholders = ",".join(["%s"] * len(seasons))
        games = conn.execute(f"""
            SELECT game_id, game_date, season, home_team, away_team,
                   home_score, away_score, home_win
            FROM games
            WHERE sport = 'MLB'
              AND season IN ({placeholders})
              AND home_score IS NOT NULL
        """, list(seasons)).fetchall()
        game_meta = {
            r[0]: dict(zip(
                ["game_id", "game_date", "season", "home_team", "away_team",
                 "home_score", "away_score", "home_win"], r))
            for r in games
        }
        logger.info(f"{model_id}: {len(game_meta)} completed games "
                    f"in seasons {seasons}")

        bulk = _build_bulk_mlb_lookups(conn, list(seasons))

        # Pre-game context — one row per game.
        pregame_rows = []
        for gid, m in game_meta.items():
            odds_row = bulk["odds"].get((gid, "h2h"))
            feat = _build_mlb_features_from_bulk(
                bulk, gid, m["game_date"], m["home_team"], m["away_team"],
                m["season"], odds_row)
            pregame_rows.append({
                "game_id": gid,
                "game_date": m["game_date"],
                "season": m["season"],
                **{c: feat.get(c) for c in pregame_cols},
            })
        df_pregame = pd.DataFrame(pregame_rows)

        # Plays — loaded per season to keep peak memory bounded.
        season_frames = []
        for season in seasons:
            rows = conn.execute(f"""
                SELECT {', '.join(_PLAY_COLS)}
                FROM plays
                WHERE season = %s
            """, (season,)).fetchall()
            if rows:
                season_frames.append(pd.DataFrame(rows, columns=_PLAY_COLS))
        if not season_frames:
            logger.warning(f"{model_id}: no plays found for seasons {seasons} "
                           f"— run the PBP backfill first "
                           f"(python -m data.ingestors.mlb_pbp_ingestor --backfill ...)")
            return pd.DataFrame()
        df_plays = pd.concat(season_frames, ignore_index=True)
        del season_frames
    finally:
        conn.close()

    # Keep only plays whose game we have metadata for.
    df_plays = df_plays[df_plays["game_id"].isin(game_meta.keys())]
    if sample_frac < 1.0:
        df_plays = df_plays.sample(frac=sample_frac, random_state=42)
    logger.info(f"{model_id}: {len(df_plays)} plays after game join"
                + (f" (sampled {sample_frac:.0%})" if sample_frac < 1.0 else ""))

    # Vectorized state features — same math as state_features().
    df_plays = df_plays.dropna(
        subset=["inning", "score_home_before", "score_away_before"])
    inning = df_plays["inning"].astype(int)
    is_top = (df_plays["half_inning"].fillna("").str.lower() == "top").astype(int)
    sh = df_plays["score_home_before"].astype(int)
    sa = df_plays["score_away_before"].astype(int)
    bases = df_plays["bases_before"].fillna("000").astype(str)

    df = pd.DataFrame({
        "game_id":           df_plays["game_id"].values,
        "inning":            inning.values,
        "is_top_inning":     is_top.values,
        "outs":              df_plays["outs_before"].fillna(0).astype(int)
                                      .clip(0, 2).values,
        "on_1b":             (bases.str[0] == "1").astype(int).values,
        "on_2b":             (bases.str[1] == "1").astype(int).values,
        "on_3b":             (bases.str[2] == "1").astype(int).values,
        "score_diff":        (sh - sa).values,
        "total_runs":        (sh + sa).values,
        "home_won":          df_plays["home_won"].values,
    })
    df["half_innings_left"] = np.maximum(
        18 - ((df["inning"] - 1) * 2 + (1 - df["is_top_inning"])), 1)

    # Targets.
    finals = pd.DataFrame([
        {"game_id": gid, "_final_home": m["home_score"],
         "_final_away": m["away_score"], "_home_win": m["home_win"]}
        for gid, m in game_meta.items()
    ])
    df = df.merge(finals, on="game_id", how="left")

    if model_id == "mlb_live_win_prob":
        df["target"] = df["home_won"]
        # Fall back to the games-table label when the play row wasn't stamped.
        df["target"] = df["target"].fillna(df["_home_win"])
    elif model_id == "mlb_live_runline":
        df["target"] = ((df["_final_home"] - df["_final_away"]) >= 2).astype(float)
    else:  # mlb_live_total_runs
        df["target"] = (df["_final_home"] + df["_final_away"]) - df["total_runs"]
        df = df[df["target"] >= 0]   # drop PBP state glitches

    df = df.dropna(subset=["target"])
    df = df.drop(columns=["home_won", "_final_home", "_final_away", "_home_win"])

    # Merge pre-game context.
    df = df.merge(df_pregame, on="game_id", how="left")

    keep = ["game_id", "game_date", "season"] + feature_cols + ["target"]
    df = df[[c for c in keep if c in df.columns]]
    logger.info(f"{model_id}: training matrix {len(df)} rows × "
                f"{len(feature_cols)} features")
    return df
