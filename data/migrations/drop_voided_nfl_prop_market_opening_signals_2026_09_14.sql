-- drop_voided_nfl_prop_market_opening_signals_2026_09_14 (2026-09-14, mike)
--
-- ONE-OFF. Same residue as drop_voided_nfl_wind_opening_signals_2026_09_14:
-- capture_opening_signals INSERTs with ON CONFLICT (lock_key) DO NOTHING, so
-- deleting a pick does not retract its shadow-track row. The three
-- nfl_prop_market BETs below were written 137-180h early vs
-- NFL_PROP_MAX_LEAD_HOURS=24 and DELETED in mike's 2026-09-11 26-row one-off;
-- their captures stayed. Re-measured production 2026-09-14 (Supabase):
--
--     NFL_2026_01_TB_CIN:nfl_prop_market:joeburrow:player_pass_completions
--     NFL_2026_01_NO_DET:nfl_prop_market:tylershough:player_pass_attempts
--     NFL_2026_01_DEN_KC:nfl_prop_market:bonix:player_pass_tds
--
-- Exactly those three leftovers; 18 other nfl_prop_market captures still have
-- a standing non-VOID BET and MUST stay. Match on the synthesised lock_key
-- (tracking.publish_keys.lock_key_sql), not game_id+model_id: this model
-- writes one pick per proposition (player_key + prop_market, player_id NULL),
-- so a standing BET on the same game would otherwise hide a leftover.
--
-- Guard: model is nfl_prop_market and no standing (non-VOID) BET shares
-- os.lock_key. A second pass deletes 0. Any later leftover of the same shape
-- goes too. Does not touch picks. Does not restore the 26 deleted rows.
-- Does not write push_sent or Discord.
--
-- Applied by the worker ACTIVE_MIGRATIONS pass (pipeline Step 0c2 /
-- refresh_pass apply-view-migrations), not by the read-only Supabase MCP.
DO $$
DECLARE
    n INTEGER;
BEGIN
    DELETE FROM opening_signals os
     WHERE os.model_id = 'nfl_prop_market'
       AND NOT EXISTS (
           SELECT 1
             FROM picks p
            WHERE p.signal_type = 'BET'
              AND COALESCE(p.condition_status, '') <> 'VOID'
              AND (p.game_id || ':' || p.model_id
                   || COALESCE(':' || p.player_id, '')
                   || COALESCE(':' || p.player_key, '')
                   || COALESCE(':' || p.prop_market, '')
                  ) = os.lock_key
       );
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'drop_voided_nfl_prop_market_opening_signals: % leftover capture(s) deleted', n;
    END IF;
END $$;
