-- One stake for the Discord #results post and the app Record tab.
--
-- Measured 2026-10-16 on the posted record through 2026-10-15 (439-377-2,
-- 818 settled, every pick priced, game_date from 2026-09-01):
--   stake_for (1u to win, risk capped at 3): +22.6501u, risked 917.1090,
--     ROI 2.4697%  — results_snapshots all_time, and the #results line
--     "+22.65u · +2.5% ROI"
--   profit_flat / $100 flat risk: +2785.85 dollars, staked 81800,
--     ROI 3.4057%, equity +27.8585u — v_public_track_record, shown as
--     "+3.4%" and an equity curve ending at "+27.9u"
-- Same picks. The flat book risks $100 on every bet. The posted stake
-- risks whatever the price requires to win 1 unit.
--
-- The definition kept is the posted stake. It is the stake on the card
-- ("1.1u to win 1u") and the stake the results channel already books.
-- profit_flat and staked_flat stay on the views: the Models tab and the
-- Yesterday modal still read the flat book. The Record tab reads units
-- and risked, which these functions compute.
--
-- Does not rewrite results_snapshots, picks, or push_sent. Does not post.
-- Idempotent: the functions are created once, and each view is patched
-- once. One statement, so data/view_migrations.py can execute it.

DO $mig$
DECLARE
  view_name text;
  d text;
  cols text := $cols$,
    COALESCE(sum(published_pick_unit_profit(COALESCE(decision_odds, dk_odds), result)), 0) AS units,
    COALESCE(sum(published_pick_unit_risked(COALESCE(decision_odds, dk_odds), result)), 0) AS risked
   $cols$;
BEGIN
  IF to_regprocedure('public.published_pick_stake(numeric)') IS NULL THEN
    CREATE FUNCTION public.published_pick_stake(price numeric, OUT risk numeric, OUT win numeric)
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $stake$
      SELECT
        CASE
          WHEN price IS NULL OR price = 0 THEN 1.0
          WHEN (1.0 / (CASE WHEN price > 0 THEN price / 100.0
                            ELSE 100.0 / abs(price) END)) > 3.0 THEN 3.0
          ELSE 1.0 / (CASE WHEN price > 0 THEN price / 100.0
                           ELSE 100.0 / abs(price) END)
        END,
        CASE
          WHEN price IS NULL OR price = 0 THEN 1.0
          WHEN (1.0 / (CASE WHEN price > 0 THEN price / 100.0
                            ELSE 100.0 / abs(price) END)) > 3.0
            THEN 3.0 * (CASE WHEN price > 0 THEN price / 100.0
                             ELSE 100.0 / abs(price) END)
          ELSE 1.0
        END
    $stake$;
  END IF;

  IF to_regprocedure('public.published_pick_unit_profit(numeric, text)') IS NULL THEN
    CREATE FUNCTION public.published_pick_unit_profit(price numeric, result text)
    RETURNS numeric
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $profit$
      SELECT CASE result
        WHEN 'WIN' THEN (public.published_pick_stake(price)).win
        WHEN 'LOSS' THEN - (public.published_pick_stake(price)).risk
        ELSE 0
      END
    $profit$;
  END IF;

  IF to_regprocedure('public.published_pick_unit_risked(numeric, text)') IS NULL THEN
    CREATE FUNCTION public.published_pick_unit_risked(price numeric, result text)
    RETURNS numeric
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $risked$
      SELECT CASE
        WHEN result = 'PUSH' THEN 0
        ELSE (public.published_pick_stake(price)).risk
      END
    $risked$;
  END IF;

  GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text) TO anon, authenticated;
  GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text) TO anon, authenticated;

  FOREACH view_name IN ARRAY ARRAY[
    'v_public_track_record', 'v_public_track_record_daily'
  ] LOOP
    d := pg_get_viewdef(('public.' || view_name)::regclass, true);
    IF position('published_pick_unit_profit' in d) > 0 THEN
      RAISE NOTICE '%: posted-stake units already present', view_name;
      CONTINUE;
    END IF;
    IF position('FROM picks p' in d) = 0 THEN
      RAISE EXCEPTION '%: no FROM picks p to attach posted-stake units', view_name;
    END IF;
    d := replace(d, 'FROM picks p', cols || 'FROM picks p');
    IF position('published_pick_unit_profit' in d) = 0 THEN
      RAISE EXCEPTION '%: posted-stake units were not inserted', view_name;
    END IF;
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', view_name, d);
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', view_name);
    EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', view_name);
    RAISE NOTICE '%: posted-stake units added', view_name;
  END LOOP;
END $mig$;
