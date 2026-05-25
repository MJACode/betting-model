"""
live_scorer.py — Phase 4 of the live (in-play) betting build.

In-play counterpart to models/scorer.py. Crucial difference: this scorer does
NOT lock at first pitch — it scores precisely WHEN a game is in progress.

The pre-game scorer skips at scorer.py:895:
    if commence_time and commence_time <= now_utc: skip
This module inverts that — it only scores games whose commence_time has passed
and which still have abstract_game_state = 'Live'.

Each pick is written with is_live=true plus inning_at_pick and
score_diff_at_pick stamped so settlement and dashboards can distinguish live
from pre-game picks. Settlement (tracking/paper_tracker.py) handles both
naturally — the actual final game result is the same outcome either way.

Status: SCAFFOLD — depends on Phase 2 live models being trained.
"""

# TODO(phase-4):
#   - run_live_scorer(game_id, state) — dispatched by trigger orchestrator
#   - Mirrors run_scorer() but:
#       * No commence_time lock (the opposite — we score only LIVE games)
#       * Reads state from live_game_state instead of pre-game features
#       * Calls live_game_features.build_live_state_row for the input vector
#       * Writes picks with is_live=true, inning_at_pick=state.inning,
#         score_diff_at_pick=state.home_score - state.away_score
#   - Settlement: paper_tracker.py already settles on game-end final score —
#     no settlement changes needed.
