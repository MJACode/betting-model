-- A same-book close that equals the price taken is a CLV push.
--
-- picks.clv_pct is percent at 2 decimal places. abs(clv_pct) < 0.005 is
-- that stored 0.00. The new counts let a beat rate use
-- beats / (clv_settled - clv_push). avg_clv_pct is untouched, so a 0%
-- close still averages in as 0. clv_beat stays clv_pct > 0. Market CLV
-- is not the headline and is not given a push count.
--
-- CREATE OR REPLACE VIEW only. No ALTER TABLE, no UPDATE of picks, no
-- rewrite of results_snapshots. The posted-stake file still runs after
-- this one and stays last. A second pass returns on the view text.
--
-- v_opening_vs_live is not in ACTIVE_MIGRATIONS. to_regclass skips it
-- when the view was never installed. pg_get_viewdef is the live text,
-- so a later column on the record view is kept.

DO $mig$
DECLARE
  d text;
  push_cols text := $push$,
    count(*) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND clv_pct IS NOT NULL AND abs(clv_pct) < 0.005::numeric AND clv_method = 'standard_v2'::text) AS clv_push,
    count(*) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND clv_pct IS NOT NULL AND abs(clv_pct) < 0.005::numeric AND clv_method = 'standard_v2'::text AND prop_market IS NULL AND model_id !~~ '%prop%'::text) AS clv_game_push,
    count(*) FILTER (WHERE (result = ANY (ARRAY['WIN'::text, 'LOSS'::text, 'PUSH'::text])) AND clv_pct IS NOT NULL AND abs(clv_pct) < 0.005::numeric AND clv_method = 'standard_v2'::text AND (prop_market IS NOT NULL OR model_id ~~ '%prop%'::text)) AS clv_prop_push
$push$;
  opening_push text := $op$count(*) FILTER (WHERE clv_pct IS NOT NULL AND abs(clv_pct) < 0.005::numeric) AS clv_push$op$;
BEGIN
  d := pg_get_viewdef('public.v_public_track_record'::regclass, true);
  IF position('AS clv_push' IN d) > 0 THEN
    RAISE NOTICE 'v_public_track_record already counts CLV pushes - skipping';
  ELSIF position('FROM picks p' IN d) = 0 THEN
    RAISE EXCEPTION 'v_public_track_record has no FROM picks p to attach CLV pushes';
  ELSE
    d := replace(d, 'FROM picks p', push_cols || E'\n   FROM picks p');
    IF position('AS clv_push' IN d) = 0 THEN
      RAISE EXCEPTION 'v_public_track_record CLV push counts were not inserted';
    END IF;
    EXECUTE 'CREATE OR REPLACE VIEW public.v_public_track_record AS ' || d;
    EXECUTE 'ALTER VIEW public.v_public_track_record SET (security_invoker = on)';
    EXECUTE 'GRANT SELECT ON public.v_public_track_record TO anon, authenticated';
    RAISE NOTICE 'v_public_track_record counts CLV pushes';
  END IF;

  IF to_regclass('public.v_opening_vs_live') IS NULL THEN
    RAISE NOTICE 'v_opening_vs_live is not installed - skipping';
    RETURN;
  END IF;
  d := pg_get_viewdef('public.v_opening_vs_live'::regclass, true);
  IF position('AS clv_push' IN d) > 0 THEN
    RAISE NOTICE 'v_opening_vs_live already counts CLV pushes - skipping';
    RETURN;
  END IF;
  IF position('AS avg_clv_pct' IN d) = 0 THEN
    RAISE EXCEPTION 'v_opening_vs_live has no avg_clv_pct to extend';
  END IF;
  d := replace(d, 'AS avg_clv_pct', 'AS avg_clv_pct,' || E'\n    ' || opening_push);
  IF position('AS clv_push' IN d) = 0 THEN
    RAISE EXCEPTION 'v_opening_vs_live CLV push count was not inserted';
  END IF;
  EXECUTE 'CREATE OR REPLACE VIEW public.v_opening_vs_live WITH (security_invoker = on) AS ' || d;
  EXECUTE 'GRANT SELECT ON public.v_opening_vs_live TO anon, authenticated';
  RAISE NOTICE 'v_opening_vs_live counts CLV pushes';
END
$mig$;
