-- abort_deploy_killed_evening_2026_10_16 (2026-10-16)
--
-- ONE-OFF. Evening pipeline_runs row 06b9db72a43c4323ad5ed84abf00b591
-- started 2026-10-16T03:50:00.440389+00:00 and was still unfinished when
-- re-read the same day (the only pipeline_runs row with finished_at NULL).
-- The worker was replaced during that pass. tracking.run_ledger._abort_orphans
-- only closes the run_kind that is starting, and no evening start_run
-- happens again until the next evening window, so refresh_pass_completion
-- stays on its stuck>0 branch while later hourlies finish.
--
-- Same stamp as _abort_orphans: finished_at set, ok false,
-- failed_steps 'aborted'. steps_total stays NULL so a later reader can
-- still tell an abort from a pass that finished its chain.
--
-- Guard: this run_id, still evening, still unfinished. A second pass
-- updates 0. Does not touch any other row. Does not touch picks,
-- thresholds, calibration, or pauses. Does not post to Discord.
--
-- Applied by the worker ACTIVE_MIGRATIONS pass (pipeline Step 0c2 /
-- refresh_pass apply-view-migrations), not by a direct production write.
-- The boot sweep in scheduler.abort_orphaned_refresh_runs closes the
-- next deploy-killed refresh row; this file closes the one already open.
DO $mig$
DECLARE
    n INTEGER;
BEGIN
    IF to_regclass('public.pipeline_runs') IS NULL THEN
        RETURN;
    END IF;
    UPDATE pipeline_runs
       SET finished_at = to_char(
               NOW() AT TIME ZONE 'UTC',
               'YYYY-MM-DD"T"HH24:MI:SS.US"+00:00"'),
           ok = FALSE,
           failed_steps = 'aborted'
     WHERE run_id = '06b9db72a43c4323ad5ed84abf00b591'
       AND run_kind = 'evening'
       AND finished_at IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    IF n > 0 THEN
        RAISE NOTICE 'abort_deploy_killed_evening_2026_10_16: closed % row', n;
    END IF;
END $mig$;
