"""
live_trigger_orchestrator.py — Phase 3 of the live (in-play) betting build.

Consumes `live_trigger_events` rows (produced by live_game_state_poller) and
dispatches Odds API calls per the cadence rules. Debounces rapid events so a
3-run inning produces at most one FG odds fetch per LIVE_FG_DEBOUNCE_SEC.

Cadence rules (from plan):

    Market tier        | When to fetch
    -------------------+--------------------------------------------------------
    FG ML/O/U/RL       | inning_change OR score_change (debounced)
    F5                 | inning_change OR score_change, STOP after inning 5
    Pitcher props      | pitching_change OR every 2 innings
    Batter props       | due_up_change for that batter only

Status: SCAFFOLD — not yet wired. Phase 1 (poller) produces the event stream
this consumes; Phase 2 builds the live odds ingestors this dispatches to.
"""

# TODO(phase-3):
#   - Build the event consumer loop: poll live_trigger_events WHERE dispatched_at IS NULL
#   - Apply cadence rules per market tier
#   - Call live_odds_ingestor.fetch_for_game(game_id, markets=[...])
#   - Stamp dispatched_at on consumed events
#   - Honor LIVE_DAILY_CREDIT_CAP — stop dispatching when burn budget hit
#   - Log to live_credit_telemetry (Phase 3 adds this table)
