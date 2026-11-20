-- Premium gate, part 2: the scored-picks matview and its readers.
--
-- mv_scored_pick_outcomes is a materialized view (~100k graded picks with
-- model probability and edge). A matview cannot carry RLS, so part 1's policies
-- do not reach it, and its four app-facing readers run as the caller:
-- v_model_full_outcome_picks, v_model_full_outcome_record (invoker views) and
-- custom_model_backtest, custom_model_backtest_posted, custom_model_picks
-- (invoker functions). About ten ACTIVE_MIGRATIONS files redefine those views
-- and functions behind their own skip guards, so wrapping them here would fight
-- those files every pass.
--
-- Instead, a PostgREST pre-request check: before each API request, PostgREST
-- calls public.premium_pre_request() as the request's role. For a signed-in
-- caller without has_app_access() it refuses exactly these six endpoints with
-- 42501. Everything else returns at once; anon returns at once (anon has no
-- grant on any of the six since lockdown step A).
--
-- PostgREST calls it as anon too, so anon keeps EXECUTE: without it every anon
-- request, including the website's site_public_record, would fail.
--
-- One DO block in ACTIVE_MIGRATIONS. A pass with nothing to change issues no
-- DDL: the function is (re)created only when its marker is missing, and the
-- role setting only when it is not already this function.
-- Undo: premium_gate_matview_2026_11_20_undo.sql (not active).

DO $gate2$
DECLARE
  cur text;
BEGIN
  IF to_regprocedure('public.premium_pre_request()') IS NULL
     OR position('premium_pre_request v1' IN
                 (SELECT prosrc FROM pg_proc
                   WHERE oid = to_regprocedure('public.premium_pre_request()'))) = 0
  THEN
    EXECUTE $ddl$
      CREATE OR REPLACE FUNCTION public.premium_pre_request()
      RETURNS void
      LANGUAGE plpgsql
      SET search_path = ''
      AS $fn$
      -- premium_pre_request v1 (premium_gate_matview_2026_11_20.sql)
      DECLARE
        p text;
      BEGIN
        IF current_user::text <> 'authenticated' THEN
          RETURN;
        END IF;
        p := coalesce(current_setting('request.path', true), '');
        IF p !~ '^/(rest/v1/)?(rpc/)?(mv_scored_pick_outcomes|v_model_full_outcome_picks|v_model_full_outcome_record|custom_model_backtest|custom_model_backtest_posted|custom_model_picks)/?$' THEN
          RETURN;
        END IF;
        IF public.has_app_access() THEN
          RETURN;
        END IF;
        RAISE EXCEPTION 'premium access required'
          USING ERRCODE = '42501',
                HINT = 'An active subscription, trial or comped grant is required.';
      END
      $fn$
    $ddl$;
    REVOKE ALL ON FUNCTION public.premium_pre_request() FROM PUBLIC;
    GRANT EXECUTE ON FUNCTION public.premium_pre_request()
        TO anon, authenticated, service_role, postgres;
  END IF;

  -- PostgREST's login role. Absent on a scratch cluster: nothing to set there.
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticator') THEN
    RETURN;
  END IF;

  SELECT s.cfg INTO cur
    FROM pg_db_role_setting rs
    JOIN pg_roles r ON r.oid = rs.setrole
    CROSS JOIN LATERAL unnest(rs.setconfig) AS s(cfg)
   WHERE r.rolname = 'authenticator'
     AND rs.setdatabase = 0
     AND s.cfg LIKE 'pgrst.db_pre_request=%';
  IF cur IS DISTINCT FROM 'pgrst.db_pre_request=public.premium_pre_request' THEN
    ALTER ROLE authenticator SET pgrst.db_pre_request = 'public.premium_pre_request';
    NOTIFY pgrst, 'reload config';
  END IF;
END
$gate2$;
