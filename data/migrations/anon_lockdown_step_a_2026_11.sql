-- Signal Base anon-key lockdown. HAND APPLIED. Not in ACTIVE_MIGRATIONS.
--
-- Project vvprgnrmzeekokzkrkfu. Matt, 2026-11-18: prep steps A and B; he OKs
-- the production apply. Authenticated grants stay as they are, except
-- tracked_bets. service_role is granted EXECUTE where a function lost PUBLIC,
-- and is otherwise untouched. The worker and Discord use postgres over
-- DATABASE_URL and bypass RLS.
--
-- Idempotent where PostgreSQL allows it (REVOKE, GRANT, ADD COLUMN IF NOT
-- EXISTS, DROP POLICY IF EXISTS). ALTER POLICY is safe to re-run: it sets
-- the role list again. No EXCEPTION handler swallows an error.

-- Step A. Model, picks, record, BYOM and ops off anon.
-- site_public_record_2026_11.sql must already be applied and the website
-- pointed at it. Authenticated SELECT on every relation below is kept.
-- The matview loses anon and keeps authenticated until step D.

BEGIN;

REVOKE ALL ON public.picks FROM anon;
REVOKE ALL ON public.open_picks FROM anon;
REVOKE ALL ON public.confirmed_picks FROM anon;
REVOKE ALL ON public.mv_scored_pick_outcomes FROM anon;
REVOKE ALL ON public.opening_signals FROM anon;
REVOKE ALL ON public.model_registry FROM anon;
REVOKE ALL ON public.model_action_thresholds FROM anon;
REVOKE ALL ON public.model_quality_checks FROM anon;
REVOKE ALL ON public.v_model_full_outcome_picks FROM anon;
REVOKE ALL ON public.v_model_full_outcome_record FROM anon;
REVOKE ALL ON public.v_model_full_record FROM anon;
REVOKE ALL ON public.v_opening_signal_slices FROM anon;
REVOKE ALL ON public.v_opening_vs_live FROM anon;
REVOKE ALL ON public.parlay_correlations FROM anon;
REVOKE ALL ON public.parlay_track_record FROM anon;
REVOKE ALL ON public.results_snapshots FROM anon;
REVOKE ALL ON public.v_public_track_record FROM anon;
REVOKE ALL ON public.v_public_track_record_daily FROM anon;
REVOKE ALL ON public.v_discord_published FROM anon;
REVOKE ALL ON public.v_discord_void_notice FROM anon;
REVOKE ALL ON public.byom_official_legs FROM anon;
REVOKE ALL ON public.byom_game_facts FROM anon;
REVOKE ALL ON public.byom_prop_facts FROM anon;
REVOKE ALL ON public.odds_api_quota FROM anon;
REVOKE ALL ON public.system_health_checks FROM anon;
REVOKE ALL ON public.picks_log FROM anon;

REVOKE SELECT (lock_key, kind, sent_at) ON public.push_sent FROM anon;

ALTER POLICY "allow anon read" ON public.picks TO authenticated;
ALTER POLICY "anon read picks" ON public.picks TO authenticated;
ALTER POLICY "anon read opening_signals" ON public.opening_signals TO authenticated;
ALTER POLICY "anon read model_registry" ON public.model_registry TO authenticated;
ALTER POLICY "anon read model_action_thresholds" ON public.model_action_thresholds TO authenticated;
ALTER POLICY "anon read model_quality_checks" ON public.model_quality_checks TO authenticated;
ALTER POLICY "anon read parlay_correlations" ON public.parlay_correlations TO authenticated;
ALTER POLICY "anon read parlay_track_record" ON public.parlay_track_record TO authenticated;
ALTER POLICY "anon read results_snapshots" ON public.results_snapshots TO authenticated;
ALTER POLICY "anon read byom_official_legs" ON public.byom_official_legs TO authenticated;
ALTER POLICY "anon read byom_game_facts" ON public.byom_game_facts TO authenticated;
ALTER POLICY "anon read byom_prop_facts" ON public.byom_prop_facts TO authenticated;
ALTER POLICY "anon read odds_api_quota" ON public.odds_api_quota TO authenticated;
ALTER POLICY "anon read system_health_checks" ON public.system_health_checks TO authenticated;
ALTER POLICY "anon_read_discord_publish" ON public.push_sent TO authenticated;

REVOKE ALL ON FUNCTION public.byom_backtest(integer, jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_backtest(integer, jsonb) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_bets(integer, jsonb, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_bets(integer, jsonb, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_leg_label(text, text, text, numeric, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_leg_label(text, text, text, numeric, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_legs(integer, jsonb, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_legs(integer, jsonb, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_line_move(text, text, numeric, numeric, numeric, numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_line_move(text, text, numeric, numeric, numeric, numeric) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_player_names(text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_player_names(text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_record(integer, jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_record(integer, jsonb) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_risk_units(numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_risk_units(numeric) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_team_division(text, integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_team_division(text, integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.byom_win_units(numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.byom_win_units(numeric) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_american_decimal(double precision) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_american_decimal(double precision) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_american_implied(double precision) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_american_implied(double precision) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_game_market(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_game_market(text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_label_book(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_label_book(text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_market_edge(double precision, double precision, double precision[], text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_market_edge(double precision, double precision, double precision[], text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_power_fair(double precision[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_power_fair(double precision[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_prop_key(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_prop_key(text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.clv_same_book(double precision, double precision) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.clv_same_book(double precision, double precision) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.custom_model_backtest(jsonb, jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.custom_model_backtest(jsonb, jsonb) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.custom_model_backtest_posted(jsonb, jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.custom_model_backtest_posted(jsonb, jsonb) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.custom_model_picks(jsonb, jsonb, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.custom_model_picks(jsonb, jsonb, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.published_pick_stake(numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.published_pick_stake(numeric, numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric, numeric) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.published_pick_unit_profit(numeric, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.published_pick_unit_profit(numeric, text, numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text, numeric) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.published_pick_unit_risked(numeric, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.published_pick_unit_risked(numeric, text, numeric) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text, numeric) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.sgp_haircuts() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.sgp_haircuts() TO postgres, authenticated, service_role;

-- Read-back. Abort if anon can still read a step A relation or execute a
-- step A function, or if authenticated lost SELECT.
DO $guard$
DECLARE bad text;
BEGIN
  SELECT string_agg(n, ',') INTO bad FROM unnest(ARRAY['picks', 'open_picks', 'confirmed_picks', 'mv_scored_pick_outcomes', 'opening_signals', 'model_registry', 'model_action_thresholds', 'model_quality_checks', 'v_model_full_outcome_picks', 'v_model_full_outcome_record', 'v_model_full_record', 'v_opening_signal_slices', 'v_opening_vs_live', 'parlay_correlations', 'parlay_track_record', 'results_snapshots', 'v_public_track_record', 'v_public_track_record_daily', 'v_discord_published', 'v_discord_void_notice', 'byom_official_legs', 'byom_game_facts', 'byom_prop_facts', 'odds_api_quota', 'system_health_checks', 'picks_log']) n
   WHERE has_table_privilege('anon', 'public.' || n, 'SELECT');
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'anon still reads: %', bad; END IF;
  IF has_column_privilege('anon', 'public.push_sent', 'lock_key', 'SELECT') THEN
    RAISE EXCEPTION 'anon still reads push_sent.lock_key';
  END IF;
  SELECT string_agg(p.oid::regprocedure::text, ',') INTO bad FROM pg_proc p
   WHERE p.pronamespace = 'public'::regnamespace
     AND p.proname = ANY(ARRAY['byom_backtest', 'byom_bets', 'byom_leg_label', 'byom_legs', 'byom_line_move', 'byom_player_names', 'byom_record', 'byom_risk_units', 'byom_team_division', 'byom_win_units', 'clv_american_decimal', 'clv_american_implied', 'clv_game_market', 'clv_label_book', 'clv_market_edge', 'clv_power_fair', 'clv_prop_key', 'clv_same_book', 'custom_model_backtest', 'custom_model_backtest_posted', 'custom_model_picks', 'published_pick_stake', 'published_pick_stake', 'published_pick_unit_profit', 'published_pick_unit_profit', 'published_pick_unit_risked', 'published_pick_unit_risked', 'sgp_haircuts'])
     AND has_function_privilege('anon', p.oid, 'EXECUTE');
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'anon still executes: %', bad; END IF;
  SELECT string_agg(n, ',') INTO bad FROM unnest(ARRAY['picks', 'open_picks', 'confirmed_picks', 'mv_scored_pick_outcomes', 'opening_signals', 'model_registry', 'model_action_thresholds', 'model_quality_checks', 'v_model_full_outcome_picks', 'v_model_full_outcome_record', 'v_model_full_record', 'v_opening_signal_slices', 'v_opening_vs_live', 'parlay_correlations', 'parlay_track_record', 'results_snapshots', 'v_public_track_record', 'v_public_track_record_daily', 'v_discord_published', 'v_discord_void_notice', 'byom_official_legs', 'byom_game_facts', 'byom_prop_facts', 'odds_api_quota', 'system_health_checks', 'picks_log']) n
   WHERE to_regclass('public.' || n) IS NOT NULL
     AND NOT has_table_privilege('authenticated', 'public.' || n, 'SELECT');
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'authenticated lost: %', bad; END IF;
END $guard$;

NOTIFY pgrst, 'reload schema';
COMMIT;
