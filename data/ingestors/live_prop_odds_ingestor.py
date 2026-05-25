"""
live_prop_odds_ingestor.py — Phase 3 of the live (in-play) betting build.

In-play counterpart to prop_odds_ingestor.py. Fires when a pitching_change or
due_up_change trigger lands. Writes to `player_prop_odds` with
snapshot_type='in_play'.

Per-event endpoint costs 1 credit per market per region. Batter prop fetches
are the cost driver — 7 credits per fetch regardless of how many players we
care about (the API does not filter by player). So we only fire on
due_up_change for batters who have an open prop position.

Status: SCAFFOLD — depends on Phase 1 trigger stream + tier upgrade.
"""

# TODO(phase-3):
#   - fetch_pitcher_props_live(game_id, player_id) — 5 pitcher markets
#   - fetch_batter_props_live(game_id, player_id) — 7 batter markets (filtered client-side)
#   - Insert with snapshot_type='in_play'
