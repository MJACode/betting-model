-- record_strikes_ufc_retired (2026-11-13, mike)
--
-- WHY. mike, 2026-11-13, asked to "Ignore and delete any existing models" for
-- UFC, and answered "yes" when told that retiring them takes their one posted
-- bet off the published record. The three old UFC models (ufc_moneyline,
-- ufc_total_rounds, ufc_method_of_victory) are in config.RETIRED_MODELS
-- (#1293). Retiring alone did NOT take them off these two views: the views
-- count every posted BET and exclude only config.RECORD_EXCLUSIONS (read on
-- production after #1293 merged: v_public_track_record still held
-- ufc_total_rounds 1-0, +1.0 units). So the three are struck through
-- RECORD_EXCLUSIONS, the second of CLAUDE.md 1c's two exits, as
-- nfl_live_prop was (record_strikes_nfl_live_prop_2026_10_04.sql).
--
-- Record at the strike, published window (>= 2026-09-01), BETs posted:
--   ufc_total_rounds 1-0, +1.0 units (Mario Pinto vs Ryan Spann Under 1.5,
--   the 2026-09-05 card); ufc_moneyline one NO_ACTION; ufc_method_of_victory
--   none.
--
-- WHY A PATCH. As the nfl_live_prop strike: the live view text has several
-- owners, so this reads it and adds ONE clause before GROUP BY.
-- The picks stay in `picks`, graded, and in the sweep views.
-- Guarded on the clause, so a re-run is a no-op. The replacement text is ONE
-- escape string: Postgres does not join E'' literals placed on separate lines
-- (the first version of this file failed on production, 2026-11-13).
-- ROLLBACK: CREATE OR REPLACE each view with the clause removed.

DO $mig$
DECLARE
  v text;
  d text;
BEGIN
  FOREACH v IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    d := pg_get_viewdef(('public.' || v)::regclass, true);

    IF position('ufc_total_rounds' in d) > 0 THEN
      RAISE NOTICE '%: the retired UFC models are already struck - skipping', v;
      CONTINUE;
    END IF;

    IF d !~ '\s+GROUP BY ' THEN
      RAISE EXCEPTION '%: no GROUP BY to anchor the strike on', v;
    END IF;

    d := regexp_replace(rtrim(d, E'; \n'), '\s+GROUP BY ',
                        E'\n    AND model_id <> ''ufc_moneyline''::text\n    AND model_id <> ''ufc_total_rounds''::text\n    AND model_id <> ''ufc_method_of_victory''::text\n  GROUP BY ');
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', v, d);
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', v);
    EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', v);
    RAISE NOTICE '%: the retired UFC models struck from the published record', v;
  END LOOP;
END $mig$;
