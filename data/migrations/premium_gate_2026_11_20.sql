-- Premium gate, part 1 (Matt, 2026-11-20: "Premium gate yes - comped account
-- are considered premium". There is no free tier, only a free trial).
--
-- After the anon lockdown, every signed-in account could still read model and
-- Stats data: ~70 SELECT policies said USING (true) for authenticated. Signing
-- up is free, so that was the leak. This turns each of them into
--   USING ((SELECT public.has_app_access()))
-- which passes an active or trialing subscription, or an unexpired comped or
-- app_review grant (founders hold comped grants). An account without access
-- gets 0 rows, not an error, so a screen fails soft.
--
-- The (SELECT ...) wrapper makes Postgres run has_app_access() once per
-- statement as an InitPlan, not once per row.
--
-- Views in public are security_invoker, so they follow their base tables.
-- Not covered here (part 2): mv_scored_pick_outcomes, a materialized view with
-- no RLS, and its four readers.
--
-- Ops and telemetry tables the app never reads lose the authenticated grant.
-- The worker, Discord and the dashboard connect as postgres and bypass both.
--
-- One DO block, applied by the worker on every pass. A pass with nothing left
-- to change issues no DDL. Undo: premium_gate_2026_11_20_undo.sql (not active).

DO $gate$
DECLARE
  r record;
  -- Relations a signed-in account without access may still read with USING
  -- (true). Empty on purpose: there is no free tier. Add a name here only with
  -- Matt's approval.
  keep_open constant text[] := ARRAY[]::text[];
  -- Read by nothing under mobile/src (grep, 2026-11-20). The worker, Discord
  -- and the dashboard use postgres.
  ops constant text[] := ARRAY[
    'odds_api_quota', 'system_health_checks', 'model_quality_checks',
    'results_snapshots', 'picks_log', 'pipeline_log', 'dk_line_observations',
    'live_credit_telemetry', 'live_feed_probe', 'live_trigger_events',
    'golf_players', 'golf_rounds', 'golf_tournaments', 'golf_odds'];
  t text;
BEGIN
  IF to_regprocedure('public.has_app_access()') IS NULL THEN
    RAISE EXCEPTION 'premium gate: public.has_app_access() is missing';
  END IF;

  FOR r IN
    SELECT p.polname, c.relname
      FROM pg_policy p
      JOIN pg_class c ON c.oid = p.polrelid
     WHERE c.relnamespace = 'public'::regnamespace
       AND p.polcmd IN ('r', '*')
       AND p.polpermissive
       AND pg_get_expr(p.polqual, p.polrelid) = 'true'
       AND (cardinality(p.polroles) = 0
            OR 'authenticated'::regrole = ANY (p.polroles))
       AND NOT c.relname = ANY (keep_open)
     ORDER BY c.relname, p.polname
  LOOP
    EXECUTE format(
      'ALTER POLICY %I ON public.%I TO authenticated '
      'USING ((SELECT public.has_app_access()))', r.polname, r.relname);
  END LOOP;

  FOREACH t IN ARRAY ops LOOP
    IF to_regclass('public.' || t) IS NOT NULL
       AND has_table_privilege('authenticated', ('public.' || t)::regclass, 'SELECT')
    THEN
      EXECUTE format('REVOKE ALL ON public.%I FROM authenticated', t);
    END IF;
  END LOOP;

  -- Read-back: no permissive SELECT policy open to signed-in users remains,
  -- and anon still reads only the website record.
  IF EXISTS (
    SELECT 1 FROM pg_policy p JOIN pg_class c ON c.oid = p.polrelid
     WHERE c.relnamespace = 'public'::regnamespace
       AND p.polcmd IN ('r', '*') AND p.polpermissive
       AND pg_get_expr(p.polqual, p.polrelid) = 'true'
       AND (cardinality(p.polroles) = 0
            OR 'authenticated'::regrole = ANY (p.polroles)
            OR 'anon'::regrole = ANY (p.polroles))
       AND NOT c.relname = ANY (keep_open))
  THEN
    RAISE EXCEPTION 'premium gate: an open SELECT policy remains';
  END IF;
END
$gate$;
