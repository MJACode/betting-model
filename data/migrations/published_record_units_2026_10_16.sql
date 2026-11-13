-- The two record views gain units and risked.
--
-- The functions are the previous file, published_pick_units_2026_10_17.sql,
-- and the three-argument pair is pick_stake_units_2026_11_06.sql, the file
-- before that. This file does not create them. If this patch raises, those
-- commits are already done and settlement still has the functions.
--
-- Both sums FILTER to WIN/LOSS/PUSH. The view WHERE does not. A void
-- (NO_ACTION) or an ungraded row (result NULL) is in the FROM and must
-- not enter the sum. The function also returns 0 for those results, so
-- either guard alone keeps them out.
--
-- Each pick is staked at its own stake_units (2026-11-06, mike: units to
-- win, 1..3; NULL is the flat 1u, so every earlier pick grades exactly as
-- it did). A view that still calls the two-argument pair is switched to
-- the three-argument one.
--
-- profit_flat and staked_flat stay: the Models tab and Yesterday still
-- read the flat book. Does not rewrite snapshots, picks, or push_sent.
-- Does not post. Idempotent: a view that already sums the function with
-- the pick's stake is left alone.

DO $mig$
DECLARE
  view_name text;
  d text;
  cols text := $cols$,
    COALESCE(sum(published_pick_unit_profit(COALESCE(decision_odds, dk_odds), result, stake_units)) FILTER (WHERE result IN ('WIN', 'LOSS', 'PUSH')), 0) AS units,
    COALESCE(sum(published_pick_unit_risked(COALESCE(decision_odds, dk_odds), result, stake_units)) FILTER (WHERE result IN ('WIN', 'LOSS', 'PUSH')), 0) AS risked
   $cols$;
BEGIN
  FOREACH view_name IN ARRAY ARRAY[
    'v_public_track_record', 'v_public_track_record_daily'
  ] LOOP
    d := pg_get_viewdef(('public.' || view_name)::regclass, true);
    IF position('result, stake_units)' in d) > 0 THEN
      RAISE NOTICE '%: posted-stake units already present', view_name;
      CONTINUE;
    END IF;
    IF position('published_pick_unit_profit' in d) > 0 THEN
      -- The two-argument calls of an earlier pass: pass the pick's stake.
      d := replace(d, 'published_pick_unit_profit(COALESCE(decision_odds, dk_odds), result)',
                      'published_pick_unit_profit(COALESCE(decision_odds, dk_odds), result, stake_units)');
      d := replace(d, 'published_pick_unit_risked(COALESCE(decision_odds, dk_odds), result)',
                      'published_pick_unit_risked(COALESCE(decision_odds, dk_odds), result, stake_units)');
      IF position('published_pick_unit_profit(COALESCE(decision_odds, dk_odds), result)' in d) > 0
         OR position('published_pick_unit_risked(COALESCE(decision_odds, dk_odds), result)' in d) > 0
         OR position('result, stake_units)' in d) = 0 THEN
        RAISE EXCEPTION '%: a two-argument posted-stake call is left', view_name;
      END IF;
    ELSE
      IF position('FROM picks p' in d) = 0 THEN
        RAISE EXCEPTION '%: no FROM picks p to attach posted-stake units', view_name;
      END IF;
      d := replace(d, 'FROM picks p', cols || 'FROM picks p');
      IF position('published_pick_unit_profit' in d) = 0 THEN
        RAISE EXCEPTION '%: posted-stake units were not inserted', view_name;
      END IF;
    END IF;
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', view_name, d);
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', view_name);
    EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', view_name);
    RAISE NOTICE '%: posted-stake units added', view_name;
  END LOOP;
END $mig$;
