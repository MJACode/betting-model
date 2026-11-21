-- site_public_record runs as the caller. The rows stay in
-- site_public_record_rows(), the SECURITY DEFINER function from #1501.
--
-- The hand file site_public_record_2026_11.sql created this view with
-- security_invoker off. Supabase's security_definer_view lint flags that.
-- An invoker view that read v_public_track_record itself is what refused
-- anon after step A (42501 on v_discord_published, about 26 minutes).
-- The function is the read. This file only changes the view option and
-- keeps the same ten columns.
--
-- Skip: reloptions contain security_invoker (the values the linter
-- accepts) AND the view definition still calls site_public_record_rows
-- and still has refreshed_at. Step A does not change either. Anon
-- grants are not the skip. A later pass returns before any DDL.
--
-- Anon SELECT is granted only while it is missing, or while picks is
-- missing or anon can still read picks. CREATE OR REPLACE keeps a grant
-- that is already there, and this file does not revoke anon. After step
-- A the website grant stays. One DO block.

DO $mig$
BEGIN
  IF to_regclass('public.site_public_record') IS NOT NULL THEN
    IF EXISTS (
         SELECT 1
           FROM pg_catalog.pg_class c,
                unnest(coalesce(c.reloptions, ARRAY[]::text[])) AS opt
          WHERE c.oid = 'public.site_public_record'::regclass
            AND lower(opt) IN (
              'security_invoker=1',
              'security_invoker=true',
              'security_invoker=yes',
              'security_invoker=on'
            )
       )
       AND position(
             'site_public_record_rows'
             in pg_get_viewdef('public.site_public_record'::regclass, true)
           ) > 0
       AND position(
             'refreshed_at'
             in pg_get_viewdef('public.site_public_record'::regclass, true)
           ) > 0
    THEN
      RAISE NOTICE 'site_public_record already security_invoker - skipping';
      RETURN;
    END IF;
  END IF;

  IF to_regprocedure('public.site_public_record_rows()') IS NULL THEN
    RAISE NOTICE 'site_public_record_rows is missing - skipping';
    RETURN;
  END IF;

  EXECUTE $ddl$
    CREATE OR REPLACE VIEW public.site_public_record
    WITH (security_invoker = true, security_barrier = true) AS
    SELECT f.sport, f.picks, f.wins, f.losses, f.pushes,
           f.units::numeric(12, 2) AS units,
           f.risked::numeric(12, 2) AS risked,
           f.first_date, f.last_date,
           now() AS refreshed_at
      FROM public.site_public_record_rows() f
  $ddl$;
  ALTER VIEW public.site_public_record
    SET (security_invoker = true, security_barrier = true);
  REVOKE ALL ON public.site_public_record FROM PUBLIC;
  GRANT SELECT ON public.site_public_record TO authenticated;
  IF to_regclass('public.picks') IS NULL
     OR has_table_privilege('anon', 'public.picks', 'SELECT')
     OR NOT has_table_privilege('anon', 'public.site_public_record', 'SELECT') THEN
    GRANT SELECT ON public.site_public_record TO anon;
  END IF;
  GRANT EXECUTE ON FUNCTION public.site_public_record_rows() TO anon;
  GRANT EXECUTE ON FUNCTION public.site_public_record_rows() TO authenticated;
  COMMENT ON VIEW public.site_public_record IS
    'Website record row. Settled published picks, one row per sport, no model id. security_invoker on. Rows come from site_public_record_rows().';

  IF NOT EXISTS (
       SELECT 1
         FROM pg_catalog.pg_class c,
              unnest(coalesce(c.reloptions, ARRAY[]::text[])) AS opt
        WHERE c.oid = 'public.site_public_record'::regclass
          AND lower(opt) IN (
            'security_invoker=1',
            'security_invoker=true',
            'security_invoker=yes',
            'security_invoker=on'
          )
     )
     OR position(
          'site_public_record_rows'
          in pg_get_viewdef('public.site_public_record'::regclass, true)
        ) = 0
     OR position(
          'refreshed_at'
          in pg_get_viewdef('public.site_public_record'::regclass, true)
        ) = 0
  THEN
    RAISE EXCEPTION 'site_public_record invoker rewrite did not land';
  END IF;
END
$mig$;
