-- custom_model_backtest_posted (2026-11-03, mike: "everything must be
-- units", one basis everywhere).
--
-- The custom-model backtest grades every scored pick (BET, AVOID and
-- dead-zone NONE) through custom_model_picks, and still does. Its summary,
-- custom_model_backtest, returns units at 1u RISKED per pick (profit_units),
-- which is not the basis the app's Record tab, Discord #results and the
-- built-in model pages use. This function returns that same matched set's
-- units on the PUBLISHED stake (CLAUDE.md §2): published_pick_unit_profit and
-- published_pick_unit_risked at COALESCE(decision_odds, dk_odds), 1u to win,
-- risk capped at 3u, a pick with no price at the bare 1u.
--
-- Read-only: a STABLE function over custom_model_picks, which reads
-- mv_scored_pick_outcomes. It writes nothing and changes no existing
-- function, view or row. plpgsql, so creating it does not depend on the
-- posted-stake functions existing yet (they are the next file); they
-- exist in production since 2026-10-17.
--
-- Idempotent: returns on a catalog read once the function exists. The app
-- calls it beside custom_model_backtest and keeps the 1u-risked figures
-- until it answers.

DO $mig$
BEGIN
  IF to_regprocedure('public.custom_model_backtest_posted(jsonb, jsonb)') IS NOT NULL THEN
    RETURN;
  END IF;

  CREATE FUNCTION public.custom_model_backtest_posted(
    p_rules jsonb,
    p_filters jsonb DEFAULT '{}'::jsonb
  )
  RETURNS TABLE (units numeric, risked numeric)
  LANGUAGE plpgsql
  STABLE
  SET search_path = public, pg_temp
  AS $fn$
  BEGIN
    RETURN QUERY
    SELECT
      COALESCE(sum(public.published_pick_unit_profit(
        COALESCE(c.decision_odds, c.dk_odds), c.result)), 0)::numeric,
      COALESCE(sum(public.published_pick_unit_risked(
        COALESCE(c.decision_odds, c.dk_odds), c.result)), 0)::numeric
    FROM public.custom_model_picks(p_rules, p_filters, 2147483647) c;
  END;
  $fn$;

  REVOKE ALL ON FUNCTION public.custom_model_backtest_posted(jsonb, jsonb) FROM PUBLIC;
  GRANT EXECUTE ON FUNCTION public.custom_model_backtest_posted(jsonb, jsonb) TO anon, authenticated;
END
$mig$;
