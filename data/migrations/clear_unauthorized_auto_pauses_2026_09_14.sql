-- clear_unauthorized_auto_pauses_2026_09_14 (2026-09-14, mike)
--
-- NOTHING AUTOPAUSES. Real money is on every live model. A pause needs
-- mike's explicit approval in config.PAUSED_MODELS with Updated-By:.
--
-- The 250-bet review wrote these two rows on 2026-09-11 with nobody
-- approving them. Measured against production 2026-09-14 (Supabase
-- execute_sql on Betting Model / vvprgnrmzeekokzkrkfu):
--
--     mlb_prop_batter_runs   paused_at 2026-09-11T11:45:00Z
--                            milestone 250, 63 bets, roi_pct -13.01
--     mlb_prop_pitcher_k     paused_at 2026-09-11T11:45:00Z
--                            milestone 250, 68 bets, roi_pct -20.48
--
-- Those were the ONLY rows in model_auto_pauses (COUNT(*) = 2). This
-- therefore clears the whole table. A second pass deletes 0. Does not
-- touch picks, threshold_reviews (the ledger of what the review
-- REPORTED stays), config.PAUSED_MODELS, or ACTION_THRESHOLDS.
--
-- After this pass + the review write-path removal, both models are live
-- again unless listed in config.PAUSED_MODELS. The scorer still reads
-- the table; empty is identity (no auto-pause).
--
-- Applied by the worker ACTIVE_MIGRATIONS pass (pipeline Step 0c2 /
-- refresh_pass apply-view-migrations), not by the read-only Supabase MCP.
DO $$
DECLARE
    n INTEGER;
BEGIN
    IF to_regclass('public.model_auto_pauses') IS NULL THEN
        RETURN;
    END IF;
    DELETE FROM model_auto_pauses;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'clear_unauthorized_auto_pauses: % row(s) deleted', n;
    END IF;
END $$;
