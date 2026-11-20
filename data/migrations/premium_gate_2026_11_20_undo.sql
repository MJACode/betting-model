-- Undo for premium_gate_2026_11_20.sql. HAND APPLIED. Not in ACTIVE_MIGRATIONS.
-- Remove premium_gate_2026_11_20.sql from ACTIVE_MIGRATIONS first, or the
-- worker's next pass applies the gate again.
--
-- Every SELECT policy gated on has_app_access() goes back to USING (true) for
-- authenticated, and the ops tables get their authenticated SELECT back. That
-- is the state of 2026-11-20 after anon-lockdown step B (snapshot
-- pre_step_b_20261120 in ops.acl_snapshot holds the exact policies).

DO $undo$
DECLARE
  r record;
  t text;
BEGIN
  FOR r IN
    SELECT p.polname, c.relname
      FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid
     WHERE c.relnamespace = 'public'::regnamespace
       AND p.polcmd IN ('r', '*')
       AND pg_get_expr(p.polqual, p.polrelid) LIKE '%has_app_access()%'
  LOOP
    EXECUTE format('ALTER POLICY %I ON public.%I TO authenticated USING (true)',
                   r.polname, r.relname);
  END LOOP;
  FOREACH t IN ARRAY ARRAY[
    'odds_api_quota', 'system_health_checks', 'model_quality_checks',
    'results_snapshots', 'picks_log', 'pipeline_log', 'dk_line_observations',
    'live_credit_telemetry', 'live_feed_probe', 'live_trigger_events',
    'golf_players', 'golf_rounds', 'golf_tournaments', 'golf_odds'] LOOP
    IF to_regclass('public.' || t) IS NOT NULL THEN
      EXECUTE format('GRANT SELECT ON public.%I TO authenticated', t);
    END IF;
  END LOOP;
END
$undo$;
