-- demote_ncaaf_over_under_platt_2026_09_26 (2026-09-26, mike)
--
-- Michael Alksninis, explicit approval 2026-09-26 ET: "Demote
-- ncaaf_over_under Platt map." Updated-By: mike.
--
-- The map promoted 2026-09-19 17:45 ET (Platt a=1.0, b=-0.281555) is in
-- the decision path. _decide reads the calibrated probability. On the
-- residual ECDF that sends +8 over to raw 0.6503 / calibrated 0.5838
-- (fails the 0.65 floor) and -8.09 under to raw 0.7111 / calibrated
-- 0.6501 (clears). An over needs +10.72 points to clear the same floor.
-- Measured after the promotion: 18 under BETs, 0 over BETs.
--
-- This is demote() for that one row: promoted = FALSE and every
-- promoted_* value cleared, promoted_at stamped. The candidate columns
-- (a, b, method, applied) stay; the nightly fit rewrites those and does
-- not promote. The scorer's load_calibrations(promoted_only=True) then
-- misses this model, and apply_calibration returns the raw probability.
--
-- Pinned to this promotion. A later map with a different promoted_at or
-- promoted_b is a new model update and is not cleared on the next pass.
-- Does not touch picks, the +/-8 gate, MODEL_PROB_THRESHOLDS, or
-- PAUSED_MODELS. No other model_id.
--
-- Applied by the worker ACTIVE_MIGRATIONS pass (pipeline Step 0c2 /
-- refresh_pass apply-view-migrations). The Supabase MCP is read-only.
DO $$
DECLARE
    n INTEGER;
BEGIN
    IF to_regclass('public.model_calibration') IS NULL THEN
        RETURN;
    END IF;
    UPDATE model_calibration
    SET promoted = FALSE,
        promoted_a = NULL,
        promoted_b = NULL,
        promoted_method = NULL,
        promoted_helps = NULL,
        promoted_transfers = NULL,
        promoted_at = now()::text
    WHERE model_id = 'ncaaf_over_under'
      AND promoted IS TRUE
      AND promoted_method = 'platt'
      AND promoted_a = 1.0
      AND promoted_b = -0.281555
      AND promoted_at = '2026-09-19T17:45:14.751731-04:00';
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'demote_ncaaf_over_under_platt: % row', n;
    END IF;
END $$;
