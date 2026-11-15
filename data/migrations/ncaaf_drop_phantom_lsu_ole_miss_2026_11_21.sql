-- ncaaf_drop_phantom_lsu_ole_miss_2026_11_21 (2026-11-15)
--
-- ONE-OFF. The Odds API historical snapshot 2025-12-01T16:55:37Z (ledger
-- row pulled 2026-11-14 21:58:14Z, snapshot_date 2025-12-01 hour 17)
-- contained one event dated a year ahead:
--
--   2026-11-21T17:00:00Z  LSU Tigers @ Ole Miss Rebels
--   id 38f9a9237c998cf91210a3d8f7d59a7a
--
-- run_historical_odds_range mints a games row for every event, so that
-- became NCAAF_2026-11-21_lsu_ole-miss (data_source=live, week NULL,
-- created 2026-11-14 21:58:14Z, updated 21:58:45Z by the 2025-12-03 hour-3
-- snapshot of the same event). DraftKings was not on the event, so the
-- DK gate stored no odds. Measured 2026-11-15: 0 rows in odds, picks,
-- picks_log, player_prop_odds, latest_odds, latest_prop_odds, and the
-- other game_id children listed below.
--
-- The schedule row is the real game. ESPN's 2026 Ole Miss schedule has
-- Wofford at 2026-11-21T17:00Z (STATUS_SCHEDULED) and LSU at Ole Miss on
-- 2026-09-19 (STATUS_FINAL). CFBD's row, refreshed 2026-11-14 13:05Z, is
-- NCAAF_2026-11-21_wofford_ole-miss. LSU's 2026-11-21 game is at Tennessee.
--
-- Do not re-point anything onto the Wofford row: a price labelled LSU is
-- not a price for Wofford. If a child appears before this runs, leave the
-- phantom so the delete cannot orphan it; ncaaf_game_identity stays STALE
-- until that child is moved by hand. A second pass is a no-op.
--
-- NEVER deletes the Wofford row. NEVER deletes a pick.
DO $$
DECLARE
    phantom TEXT := 'NCAAF_2026-11-21_lsu_ole-miss';
    real_id TEXT := 'NCAAF_2026-11-21_wofford_ole-miss';
    tbl     TEXT;
    n       INTEGER;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM games
         WHERE game_id = phantom AND sport = 'NCAAF'
           AND home_team = 'Ole Miss' AND away_team = 'LSU'
           AND game_date = '2026-11-21'
           AND home_score IS NULL AND away_score IS NULL
           AND data_source = 'live'
    ) OR NOT EXISTS (
        SELECT 1 FROM games
         WHERE game_id = real_id AND sport = 'NCAAF'
           AND home_team = 'Ole Miss' AND away_team = 'Wofford'
           AND game_date = '2026-11-21'
    ) THEN
        RETURN;
    END IF;

    FOREACH tbl IN ARRAY ARRAY[
        'odds', 'picks', 'picks_log', 'player_prop_odds', 'latest_odds',
        'latest_prop_odds', 'opening_signals', 'public_betting', 'lineup_slots',
        'plays', 'player_game_log', 'alt_game_lines', 'alt_game_line_fetches',
        'live_game_state', 'live_pick_features', 'live_trigger_events',
        'live_credit_telemetry', 'ncaaf_team_game_log', 'ncaaf_player_game_log',
        'ncaaf_qb_game', 'ncaaf_moneyline_decisions', 'ncaaf_derivative_fetches',
        'ncaaf_live_states', 'kalshi_ncaaf_events', 'game_weather',
        'game_weather_issued', 'game_market_gate', 'tracked_bets',
        'capper_picks', 'dk_live_reads', 'scoreboard_splits'
    ]
    LOOP
        IF to_regclass('public.' || tbl) IS NULL THEN
            CONTINUE;
        END IF;
        EXECUTE format('SELECT count(*) FROM %I WHERE game_id = $1', tbl)
            INTO n USING phantom;
        IF n > 0 THEN
            RETURN;
        END IF;
    END LOOP;

    DELETE FROM games
     WHERE game_id = phantom
       AND sport = 'NCAAF'
       AND home_team = 'Ole Miss' AND away_team = 'LSU'
       AND game_date = '2026-11-21'
       AND home_score IS NULL AND away_score IS NULL
       AND data_source = 'live';
END $$;
