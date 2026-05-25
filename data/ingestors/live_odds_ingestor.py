"""
live_odds_ingestor.py — Phase 3 of the live (in-play) betting build.

Mirrors data/ingestors/odds_ingestor.py but tagged for in-play snapshots.
Called by live_trigger_orchestrator when an FG-tier trigger fires.

Writes to the existing `odds` table with snapshot_type='in_play'. Settlement
and pre-game scoring queries that filter `snapshot_type IN ('open', 'close')`
will naturally exclude these.

Status: SCAFFOLD — Phase 1 only produces the trigger stream this would consume.
"""

# TODO(phase-3):
#   - fetch_in_play_odds(game_id, markets=['h2h','spreads','totals']) — bulk endpoint
#   - fetch_in_play_f5(game_id) — per-event endpoint, only innings 1-5
#   - Insert with snapshot_type='in_play'
#   - Track credit cost per call → live_credit_telemetry
#   - Reuse _parse_outcomes / _parse_spread_outcomes from odds_ingestor.py
