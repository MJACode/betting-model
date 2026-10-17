-- record_strikes_nfl_live_prop (2026-10-04, mike)
--
-- WHY. mike, 2026-10-04: "I want these stricken from the record. It was never a
-- good model. Remove this model." nfl_live_prop (NFL in-play: pass attempts
-- 09-09 -> 09-20, then rushing attempts "Under N Carries" from 09-21) is RETIRED
-- in config.RETIRED_MODELS and its whole settled record is struck through
-- config.RECORD_EXCLUSIONS -- the second of the two explicit exits CLAUDE.md 1c
-- allows, named and attributed there.
--
-- Record at the strike, published window (>= 2026-09-01), BETs only:
--   7-17, -10.27 units over 24 settled (pass attempts 6-16, carries 1-1).
--
-- WHY A PATCH AND NOT A REDEFINITION. The live view text is the product of
-- several owners (clv no-vig, the decision-price gate, the paused-row marker);
-- copying any one owner's body would silently roll the others back. So this
-- reads the live definition and adds ONE clause before GROUP BY, the shape
-- score_off_any_book_line_2026_09_12.sql uses for the price gate.
--
-- The picks themselves are untouched: still in `picks`, still graded, still
-- in the sweep views (CLAUDE.md 7). Only the PUBLISHED record drops them.
--
-- Guarded on the model id, so a re-run is a no-op.
-- ROLLBACK: CREATE OR REPLACE each view with the clause removed.

DO $mig$
DECLARE
  v text;
  d text;
BEGIN
  FOREACH v IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    d := pg_get_viewdef(('public.' || v)::regclass, true);

    IF position('nfl_live_prop' in d) > 0 THEN
      RAISE NOTICE '%: nfl_live_prop already struck - skipping', v;
      CONTINUE;
    END IF;

    IF d !~ '\s+GROUP BY ' THEN
      RAISE EXCEPTION '%: no GROUP BY to anchor the strike on', v;
    END IF;

    d := regexp_replace(rtrim(d, E'; \n'), '\s+GROUP BY ',
                        E'\n    AND model_id <> ''nfl_live_prop''::text\n  GROUP BY ');
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', v, d);
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', v);
    EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', v);
    RAISE NOTICE '%: nfl_live_prop struck from the published record', v;
  END LOOP;
END $mig$;
