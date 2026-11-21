-- record_matches_sheet (2026-11-21, Matt)
--
-- WHY. Matt, 2026-11-21: the "SignalBase Record History" Google sheet is the
-- source of truth for the published record (mike: "use this as the single
-- source of truth"), and "Google is right" where it and the record disagreed.
-- Diffed pick by pick that day, the sheet and v_public_track_record held the
-- same 1,704 graded posted picks and disagreed in exactly two ways:
--
--   1. The sheet counts every pick at 1u TO WIN. The record used each pick's
--      own picks.stake_units (NCAAB agreement sizing, mike 2026-11-06), so four
--      NCAAB bets counted at 2u: +2.00, +2.00, +2.00 and -2.50 against the
--      sheet's +1.00, +1.00, +1.00 and -1.25 (-1.75 units net on the sheet).
--      Matt: "Record + stop 2u picks".
--   2. The sheet counts ufc_total_rounds' one posted bet (Mario Pinto vs Ryan
--      Spann Under 1.5, 2026-09-05, WIN, +1.0 units), which
--      record_strikes_ufc_retired_2026_11_13.sql struck. Matt: "Yes, put it
--      back". That file is retired from ACTIVE_MIGRATIONS in the same change.
--
-- WHAT. Three parts, each behind a catalog read so a second pass changes
-- nothing and fires no DDL (tests/test_ddl_guard.py):
--
--   a. published_pick_stake(numeric, numeric) ignores its second argument and
--      returns the one-argument stake, the flat 1u to win with risk capped at
--      3u. The three-argument unit functions, and every view that calls them,
--      follow. pick_stake_units_2026_11_06.sql only creates that function when
--      it is missing, so it does not put the stake back.
--   b. The UFC strike clause comes out of v_public_track_record and
--      v_public_track_record_daily. v_public_track_record_model_daily and the
--      model-health views rebuild from those two views' text on the next pass
--      (their marks are an md5 of it), so they follow by themselves.
--   c. site_public_record_rows() (the website) stops dropping
--      site_retired_models: the record view is the one place a model is taken
--      out, as on Discord. No row of site_retired_models is deleted.
--
-- Does not rewrite picks, results_snapshots or push_sent, and does not post.
-- ROLLBACK: recreate published_pick_stake(numeric, numeric) from
-- pick_stake_units_2026_11_06.sql, put record_strikes_ufc_retired_2026_11_13.sql
-- back in ACTIVE_MIGRATIONS, and restore the NOT EXISTS clause in
-- site_public_record_rows() from site_public_record_2026_11.sql.

DO $mig$
DECLARE
  v text;
  d text;
  nd text;
  f text;
BEGIN
  -- a. flat stake --------------------------------------------------------------
  IF to_regprocedure('public.published_pick_stake(numeric, numeric)') IS NOT NULL
     AND to_regprocedure('public.published_pick_stake(numeric)') IS NOT NULL
     AND position('record_matches_sheet' IN
                  pg_get_functiondef(to_regprocedure('public.published_pick_stake(numeric, numeric)'))) = 0 THEN
    CREATE OR REPLACE FUNCTION public.published_pick_stake(price numeric, units numeric,
                                                           OUT risk numeric, OUT win numeric)
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $stake$
      -- record_matches_sheet: flat 1u to win on every pick; units is ignored.
      SELECT s.risk, s.win FROM public.published_pick_stake(price) s
    $stake$;
    RAISE NOTICE 'published_pick_stake(numeric, numeric) is now the flat 1u stake';
  END IF;

  -- b. the UFC strike out of the two record views ---------------------------------
  FOREACH v IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    IF to_regclass('public.' || v) IS NULL THEN
      CONTINUE;
    END IF;
    d := pg_get_viewdef(('public.' || v)::regclass, true);
    IF position('ufc_total_rounds' IN d) = 0 THEN
      CONTINUE;
    END IF;
    nd := regexp_replace(rtrim(d, E'; \n'),
                         '\s+AND\s+model_id\s+<>\s+''ufc_(moneyline|total_rounds|method_of_victory)''::text',
                         '', 'g');
    IF position('ufc_total_rounds' IN nd) > 0 THEN
      RAISE EXCEPTION '%: the UFC strike is not in the expected form; not changed', v;
    END IF;
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', v, nd);
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', v);
    EXECUTE format('GRANT SELECT ON public.%I TO authenticated', v);
    IF to_regclass('public.picks') IS NULL
       OR has_table_privilege('anon', 'public.picks', 'SELECT') THEN
      EXECUTE format('GRANT SELECT ON public.%I TO anon', v);
    END IF;
    RAISE NOTICE '%: the retired UFC models are back in the published record', v;
  END LOOP;

  -- c. the website record follows the record view ----------------------------
  IF to_regprocedure('public.site_public_record_rows()') IS NOT NULL THEN
    f := pg_get_functiondef(to_regprocedure('public.site_public_record_rows()'));
    IF position('site_retired_models' IN f) > 0 THEN
      CREATE OR REPLACE FUNCTION public.site_public_record_rows()
      RETURNS TABLE(sport text, picks integer, wins integer, losses integer, pushes integer,
                    units numeric, risked numeric, first_date date, last_date date)
      LANGUAGE sql
      STABLE
      SECURITY DEFINER
      SET search_path = public, pg_temp
      AS $rows$
        SELECT r.sport,
               sum(r.picks)::integer, sum(r.wins)::integer, sum(r.losses)::integer, sum(r.pushes)::integer,
               round(sum(r.units), 2), round(sum(r.risked), 2),
               min(r.first_date)::date, max(r.last_date)::date
          FROM public.v_public_track_record r
         GROUP BY r.sport
      $rows$;
      RAISE NOTICE 'site_public_record_rows() now reads the record view as it stands';
    END IF;
  END IF;
END $mig$;
