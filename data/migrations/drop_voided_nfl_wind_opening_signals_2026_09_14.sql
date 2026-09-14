-- drop_voided_nfl_wind_opening_signals_2026_09_14 (2026-09-14, mike)
--
-- ONE-OFF. capture_opening_signals INSERTs with ON CONFLICT (lock_key)
-- DO NOTHING, so deleting a pick does not retract its shadow-track row.
-- The six Week-1 nfl_wind_totals BETs (MAX_FIRE_LEAD / long-lead void)
-- were VOIDED 2026-09-07 and DELETED 2026-09-11; their captures stayed.
-- Measured against production 2026-09-14 (Supabase):
--
--     NFL_2026_01_BUF_HOU:nfl_wind_totals   locked 2026-09-05 12:22 ET
--     NFL_2026_01_CLE_JAX:nfl_wind_totals   locked 2026-09-05 12:22 ET
--     NFL_2026_01_BAL_IND:nfl_wind_totals   locked 2026-09-05 14:22 ET
--     NFL_2026_01_NYJ_TEN:nfl_wind_totals   locked 2026-09-06 08:00 ET
--     NFL_2026_01_DAL_NYG:nfl_wind_totals   locked 2026-09-06 08:00 ET
--     NFL_2026_01_TB_CIN:nfl_wind_totals    locked 2026-09-06 12:03 ET
--
-- Standing nfl_wind_totals pick that MUST stay, capture included:
--     pick_id 1969489  DEN @ KC Under 43.5  lock_key NFL_2026_01_DEN_KC:nfl_wind_totals
--     created 2026-09-11 01:00:17+00  condition_status OK
--
-- Guard: model is nfl_wind_totals, lock_key is not DEN@KC, and no standing
-- (non-VOID) BET remains on that game. A second pass deletes 0. Any later
-- leftover of the same shape (capture, no standing pick) is the same class
-- and goes too. Does not touch picks. Does not restore the 26 deleted rows.
-- Does not write push_sent or Discord.
--
-- Applied by the worker ACTIVE_MIGRATIONS pass (pipeline Step 0c2 /
-- refresh_pass apply-view-migrations), not by the read-only Supabase MCP.
DO $$
DECLARE
    n INTEGER;
BEGIN
    DELETE FROM opening_signals os
     WHERE os.model_id = 'nfl_wind_totals'
       AND os.lock_key <> 'NFL_2026_01_DEN_KC:nfl_wind_totals'
       AND NOT EXISTS (
           SELECT 1
             FROM picks p
            WHERE p.game_id = os.game_id
              AND p.model_id = os.model_id
              AND p.signal_type = 'BET'
              AND COALESCE(p.condition_status, '') <> 'VOID'
       );
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'drop_voided_nfl_wind_opening_signals: % leftover capture(s) deleted', n;
    END IF;
END $$;
