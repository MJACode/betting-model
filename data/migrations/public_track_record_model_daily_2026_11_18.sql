-- public.v_public_track_record_model_daily: the published record, per model per day.
--
-- Matt, 2026-11-18: the Picks filter sheet gets a Model section, each chip
-- carrying the model's record and a hot / cold tag over its last 7 days
-- (lib/modelHeat.ts). v_public_track_record is per (sport, model) with no
-- date, and v_public_track_record_daily is per (date, sport) with no model.
-- This is the second one split by model, and nothing else.
--
-- IT IS BUILT FROM THE DAILY VIEW'S OWN DEFINITION, not a copy of it. The
-- record views' WHERE clause has been rewritten by eight migrations (live
-- date, strikes, duplicates, posted stake, the Discord lock ...), and a
-- hand-copied third view would drift from the other two the first time one
-- of them changed. So this file reads pg_get_viewdef of the daily view, adds
-- model_id to its SELECT and its GROUP BY, and creates the result. If either
-- edit finds nothing to change, it creates nothing and says so (a NOTICE):
-- a wrong view is worse than a missing one, and the app falls back to no tag.
--
-- The skip compares this view's comment to the md5 of the daily view's
-- definition, so a pass after the daily view changes rebuilds this one. It
-- runs before published_record_units_2026_10_16.sql (that file stays last),
-- so on a fresh database it follows that file's patch one pass later.
--
-- security_invoker, SELECT for anon and authenticated, every other privilege
-- revoked by name (default privileges grant ALL). Reads picks and
-- v_discord_published, like the daily view. Writes nothing. One statement.

DO $mig$
DECLARE
  daily_def text;
  marker text;
  body text;
BEGIN
  IF to_regclass('public.v_public_track_record_daily') IS NULL THEN
    RAISE NOTICE 'v_public_track_record_model_daily waits for v_public_track_record_daily';
    RETURN;
  END IF;

  daily_def := pg_get_viewdef('public.v_public_track_record_daily'::regclass, true);
  marker := 'v_public_track_record_model_daily ' || md5(daily_def);

  IF to_regclass('public.v_public_track_record_model_daily') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.v_public_track_record_model_daily'), 'pg_class'), '')
         = marker
     AND has_table_privilege('anon', 'public.v_public_track_record_model_daily', 'SELECT')
     AND has_table_privilege('authenticated', 'public.v_public_track_record_model_daily', 'SELECT')
  THEN
    RETURN;
  END IF;

  body := regexp_replace(daily_def, '^\s*SELECT\s+game_date,\s+sport,', 'SELECT game_date, sport, model_id,');
  IF body = daily_def THEN
    RAISE NOTICE 'v_public_track_record_model_daily: the daily view no longer starts SELECT game_date, sport; not created';
    RETURN;
  END IF;
  IF body !~ 'GROUP BY game_date, sport\s' THEN
    RAISE NOTICE 'v_public_track_record_model_daily: the daily view no longer groups by game_date, sport; not created';
    RETURN;
  END IF;
  body := regexp_replace(body, 'GROUP BY game_date, sport(\s)', 'GROUP BY game_date, sport, model_id\1');
  body := regexp_replace(body, ';\s*$', '');

  EXECUTE 'CREATE OR REPLACE VIEW public.v_public_track_record_model_daily WITH (security_invoker = on) AS ' || body;
  EXECUTE format('COMMENT ON VIEW public.v_public_track_record_model_daily IS %L', marker);
  REVOKE ALL ON public.v_public_track_record_model_daily FROM PUBLIC;
  REVOKE ALL ON public.v_public_track_record_model_daily FROM anon;
  REVOKE ALL ON public.v_public_track_record_model_daily FROM authenticated;
  GRANT SELECT ON public.v_public_track_record_model_daily TO anon, authenticated;
END
$mig$;
