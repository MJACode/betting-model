"""
live_game_features.py — Phase 2 of the live (in-play) betting build.

Builds the state-vector feature row for live model scoring. Mirrors the
pre-game builders in features/feature_engine.py but takes a current game state
as input instead of pre-game team/pitcher stats.

State features (per row):
    inning, inning_half_top, outs, bases_state (0-7 enum),
    score_diff, home_team_at_bat, abs_score_diff,
    pitcher_pitch_count, pitcher_tto (times-through-order), is_high_leverage

Layered on top of the pre-game features already used by feature_engine.py
(starter ERA, team wRC+, weather, etc.) so a live model has BOTH the live
state and the pre-game context.

Status: SCAFFOLD — needs the `plays` table from retrosheet_ingestor first.
"""

# TODO(phase-2):
#   - build_live_state_row(game_id, snapshot) — for live scoring
#   - build_live_training_rows(season) — joins plays + games + pre-game features
#   - Reuse: _build_bulk_mlb_lookups from feature_engine.py for pre-game context
#   - bases_state enum: '000'=0, '100'=1, '010'=2, '110'=3, ..., '111'=7
