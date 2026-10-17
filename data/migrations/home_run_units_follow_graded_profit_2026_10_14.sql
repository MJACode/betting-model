-- v_model_full_outcome_record forced units to 0 and roi to NULL for one model.
-- That model is retired. Its graded picks keep their real profit, the same
-- way every other model on the view does. Unpriced rows already store NULL
-- profit, and sum() skips those.
--
-- Idempotent: a second run finds the model id gone from the view and returns.
-- Reads the live definition so it does not roll back later patches.

DO $mig$
DECLARE
  d text;
BEGIN
  d := pg_get_viewdef('public.v_model_full_outcome_record'::regclass, true);

  IF position('mlb_prop_batter_hr' in d) = 0 THEN
    RAISE NOTICE 'home-run units case already removed';
    RETURN;
  END IF;

  d := regexp_replace(
    d,
    'CASE\s+WHEN model_id = ''mlb_prop_batter_hr''::text THEN 0::numeric\s+ELSE (round\(COALESCE\(sum\(profit\) FILTER \(WHERE passes\), 0::numeric\), 6\))\s+END AS units',
    '\1 AS units',
    'n');
  d := regexp_replace(
    d,
    'CASE\s+WHEN model_id = ''mlb_prop_batter_hr''::text THEN NULL::numeric\s+ELSE (round\(sum\(profit\) FILTER \(WHERE passes\) / NULLIF\(count\(\*\) FILTER \(WHERE passes AND \(res = ANY \(ARRAY\[''W''::text, ''L''::text, ''P''::text\]\)\) AND decision_odds IS NOT NULL\), 0\)::numeric \* 100::numeric, 1\))\s+END AS roi_pct',
    '\1 AS roi_pct',
    'n');

  IF position('mlb_prop_batter_hr' in d) > 0 THEN
    RAISE EXCEPTION 'home-run units case still present after rewrite';
  END IF;

  EXECUTE 'CREATE OR REPLACE VIEW public.v_model_full_outcome_record AS ' || d;
  EXECUTE 'ALTER VIEW public.v_model_full_outcome_record SET (security_invoker = on)';
  EXECUTE 'GRANT SELECT ON public.v_model_full_outcome_record TO anon, authenticated';
END $mig$;
