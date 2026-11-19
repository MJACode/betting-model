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
-- Undo step A only. Run undo B first if B was applied.
-- site_public_record is kept.
BEGIN;
GRANT SELECT ON public.picks TO anon;
GRANT SELECT ON public.open_picks TO anon;
GRANT SELECT ON public.confirmed_picks TO anon;
GRANT SELECT ON public.mv_scored_pick_outcomes TO anon;
GRANT SELECT ON public.opening_signals TO anon;
GRANT SELECT ON public.model_registry TO anon;
GRANT SELECT ON public.model_action_thresholds TO anon;
GRANT SELECT ON public.model_quality_checks TO anon;
GRANT SELECT ON public.v_model_full_outcome_picks TO anon;
GRANT SELECT ON public.v_model_full_outcome_record TO anon;
GRANT SELECT ON public.v_model_full_record TO anon;
GRANT SELECT ON public.v_opening_signal_slices TO anon;
GRANT SELECT ON public.v_opening_vs_live TO anon;
GRANT SELECT ON public.parlay_correlations TO anon;
GRANT SELECT ON public.parlay_track_record TO anon;
GRANT SELECT ON public.results_snapshots TO anon;
GRANT SELECT ON public.v_public_track_record TO anon;
GRANT SELECT ON public.v_public_track_record_daily TO anon;
GRANT SELECT ON public.v_discord_published TO anon;
GRANT SELECT ON public.v_discord_void_notice TO anon;
GRANT SELECT ON public.byom_official_legs TO anon;
GRANT SELECT ON public.byom_game_facts TO anon;
GRANT SELECT ON public.byom_prop_facts TO anon;
GRANT SELECT ON public.odds_api_quota TO anon;
GRANT SELECT ON public.system_health_checks TO anon;
GRANT SELECT ON public.picks_log TO anon;
GRANT SELECT (lock_key, kind, sent_at) ON public.push_sent TO anon;
ALTER POLICY "allow anon read" ON public.picks TO public;
ALTER POLICY "anon read picks" ON public.picks TO anon, authenticated;
ALTER POLICY "anon read opening_signals" ON public.opening_signals TO anon, authenticated;
ALTER POLICY "anon read model_registry" ON public.model_registry TO anon, authenticated;
ALTER POLICY "anon read model_action_thresholds" ON public.model_action_thresholds TO anon, authenticated;
ALTER POLICY "anon read model_quality_checks" ON public.model_quality_checks TO anon, authenticated;
ALTER POLICY "anon read parlay_correlations" ON public.parlay_correlations TO anon, authenticated;
ALTER POLICY "anon read parlay_track_record" ON public.parlay_track_record TO anon, authenticated;
ALTER POLICY "anon read results_snapshots" ON public.results_snapshots TO anon, authenticated;
ALTER POLICY "anon read byom_official_legs" ON public.byom_official_legs TO anon, authenticated;
ALTER POLICY "anon read byom_game_facts" ON public.byom_game_facts TO anon, authenticated;
ALTER POLICY "anon read byom_prop_facts" ON public.byom_prop_facts TO anon, authenticated;
ALTER POLICY "anon read odds_api_quota" ON public.odds_api_quota TO anon, authenticated;
ALTER POLICY "anon read system_health_checks" ON public.system_health_checks TO anon, authenticated;
ALTER POLICY "anon_read_discord_publish" ON public.push_sent TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_backtest(integer, jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_bets(integer, jsonb, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_leg_label(text, text, text, numeric, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_legs(integer, jsonb, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_line_move(text, text, numeric, numeric, numeric, numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_line_move(text, text, numeric, numeric, numeric, numeric) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.byom_player_names(text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_record(integer, jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_risk_units(numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_team_division(text, integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.byom_team_division(text, integer, text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.byom_win_units(numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_american_decimal(double precision) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_american_decimal(double precision) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.clv_american_implied(double precision) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_american_implied(double precision) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.clv_game_market(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_game_market(text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.clv_label_book(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_label_book(text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.clv_market_edge(double precision, double precision, double precision[], text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_market_edge(double precision, double precision, double precision[], text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.clv_power_fair(double precision[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_power_fair(double precision[]) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.clv_prop_key(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_prop_key(text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.clv_same_book(double precision, double precision) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.clv_same_book(double precision, double precision) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.custom_model_backtest(jsonb, jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.custom_model_backtest_posted(jsonb, jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.custom_model_picks(jsonb, jsonb, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.custom_model_picks(jsonb, jsonb, integer) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric, numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.published_pick_stake(numeric, numeric) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text, numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_profit(numeric, text, numeric) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text, numeric) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.published_pick_unit_risked(numeric, text, numeric) TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.sgp_haircuts() TO anon, authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;
