-- Build Your Own Model: the staking functions, inlined.
--
-- 2026-11-05, measured in production: the NBA points-over record for
-- 2025-26 timed out at the 3s anon limit (official 1,966 ms + close
-- 1,276 ms). The plan, rebuilt by hand, spent 2,620 of 2,710 ms in one
-- Aggregate: byom_win_units and byom_risk_units over 16,582 rows.
--
-- A SQL function with a SET clause is never inlined, so each call saves
-- and restores search_path, and byom_win_units called byom_risk_units
-- three more times: four full calls per row. The same arithmetic over the
-- same 33,164 rows took 4,283 ms through the functions and 211 ms inline.
--
-- So the two are redefined with no SET clause, and the planner inlines
-- them into byom_legs. Every name inside is schema-qualified
-- (pg_catalog.abs, pg_catalog.trunc, public.byom_risk_units), and LEAST
-- is SQL syntax, so the body resolves the same under any search_path.
-- The staking is unchanged: 1u to win, risk capped at 3u (stake_for).
--
-- The Supabase advisor reports a function with no fixed search_path
-- (function_search_path_mutable). That is the price of inlining here,
-- and it is safe for a body with only qualified names and no table.
--
-- Skips once both functions carry byom_units_inline_v1 and no SET.
-- byom_official_legs_2026_11_04.sql does not re-create them: its skip
-- counts the five functions that carry byom_official_legs_v1, not these.
-- CREATE OR REPLACE keeps the grants. Does not write picks.

DO $mig$
BEGIN
  IF (SELECT count(*) FROM pg_proc p
       WHERE p.oid IN (to_regprocedure('public.byom_risk_units(numeric)'),
                       to_regprocedure('public.byom_win_units(numeric)'))
         AND position('byom_units_inline_v1' in p.prosrc) > 0
         AND p.proconfig IS NULL) = 2
  THEN
    RAISE NOTICE 'byom units inline already present - skipping';
    RETURN;
  END IF;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_risk_units(p_price numeric)
  RETURNS numeric LANGUAGE sql IMMUTABLE
  AS $body$
    -- byom_official_legs_v1, byom_units_inline_v1: no SET, so it inlines.
    SELECT CASE
      WHEN p_price IS NULL OR p_price <> pg_catalog.trunc(p_price)
           OR pg_catalog.abs(p_price) < 100
        THEN NULL
      WHEN p_price > 0 THEN LEAST(100 / p_price, 3)
      ELSE LEAST(pg_catalog.abs(p_price) / 100, 3)
    END
  $body$;
  $fn$;

  EXECUTE $fn$
  CREATE OR REPLACE FUNCTION public.byom_win_units(p_price numeric)
  RETURNS numeric LANGUAGE sql IMMUTABLE
  AS $body$
    -- byom_official_legs_v1, byom_units_inline_v1. The win on a capped
    -- risk, so the two agree.
    SELECT CASE
      WHEN public.byom_risk_units(p_price) IS NULL THEN NULL
      WHEN p_price > 0 THEN public.byom_risk_units(p_price) * p_price / 100
      ELSE public.byom_risk_units(p_price) * 100 / pg_catalog.abs(p_price)
    END
  $body$;
  $fn$;
END
$mig$;
