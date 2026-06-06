"""
live_prop_odds_ingestor.py — Phase 3 of the live (in-play) betting build.

In-play counterpart to prop_odds_ingestor.py. Fires when a pitching_change or
due_up_change trigger lands. Writes to `player_prop_odds` with
snapshot_type='in_play'.

Per-event endpoint costs 1 credit per market per region. Batter prop fetches
are the cost driver — 7 credits per fetch regardless of how many players we
care about (the API does not filter by player). So we only fire on
due_up_change for batters who have an open prop position.

Status: OUT OF SCOPE this round. The live build targets game-level moneyline +
totals only — there are NO live prop models trained yet, so there is nothing to
score live prop odds against. The trigger orchestrator deliberately does NOT
dispatch to this module (pitching_change / due_up_change triggers are consumed
but not acted on). Re-enable this once live prop models exist.
"""

# TODO(future — when live prop models exist):
#   - fetch_pitcher_props_live(game_id, player_id) — 5 pitcher markets
#   - fetch_batter_props_live(game_id, player_id) — 7 batter markets (filtered client-side)
#   - Insert with snapshot_type='in_play'
