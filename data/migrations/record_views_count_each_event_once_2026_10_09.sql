-- record_views_count_each_event_once (2026-10-09, mike)
--
-- WHY. mike, 2026-10-09: "Count each fight once." When a model bet one real
-- event under two game ids, the second copy carries condition_status =
-- 'DUPLICATE' (config.DUPLICATE_STATUS; the first two are marked by
-- record_counts_each_event_once_2026_10_09.sql). The two published views
-- count rows, so without this clause they would count both copies. The
-- Discord recap, model_quality, the 250-bet review, the monitor dashboard and
-- the app read the same marker.
--
-- WHY A PATCH AND NOT A REDEFINITION. Same reason as
-- record_strikes_nfl_live_prop_2026_10_04.sql: the live view text is the
-- product of several owners, and copying any one body would roll the others
-- back. This reads the live definition and adds ONE clause before GROUP BY.
-- Must run after every migration that owns the two views.
--
-- IS DISTINCT FROM, not <>: condition_status is NULL on almost every row, and
-- NULL <> 'DUPLICATE' is NULL, which would drop every ordinary pick.
--
-- Guarded on the marker already being in the view text, so a re-run is a
-- no-op. The picks are untouched; only the count changes.
-- ROLLBACK: CREATE OR REPLACE each view with the clause removed.

DO $mig$
DECLARE
  v text;
  d text;
BEGIN
  FOREACH v IN ARRAY ARRAY['v_public_track_record', 'v_public_track_record_daily'] LOOP
    d := pg_get_viewdef(('public.' || v)::regclass, true);

    IF position('DUPLICATE' in d) > 0 THEN
      RAISE NOTICE '%: already counts each event once - skipping', v;
      CONTINUE;
    END IF;

    IF d !~ '\s+GROUP BY ' THEN
      RAISE EXCEPTION '%: no GROUP BY to anchor the clause on', v;
    END IF;

    d := regexp_replace(rtrim(d, E'; \n'), '\s+GROUP BY ',
                        E'\n    AND condition_status IS DISTINCT FROM ''DUPLICATE''::text\n  GROUP BY ');
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', v, d);
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', v);
    EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', v);
    RAISE NOTICE '%: the second copy of one bet no longer counts', v;
  END LOOP;
END $mig$;
