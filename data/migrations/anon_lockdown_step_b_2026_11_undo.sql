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
-- Undo step B. Keeps tracked_bets.user_id and its index.
-- Does not give anon back the step A relations.
--
-- SEQUENCE GRANTS ARE NOT IN THIS FILE. Anon held rwU on 67
-- sequences, not on every sequence in public. GRANT ON ALL
-- would open the other 16. The documented rollback for
-- sequences, and for any grant this file does not name, is:
--   python -m scripts.restore_acl_from_snapshot --label pre_step_a_20261118
-- which reads ops.acl_snapshot taken before step A.
BEGIN;
-- Inverse of the default-privilege statements in step B.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT ALL ON TABLES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    GRANT EXECUTE ON FUNCTIONS TO anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres
    GRANT EXECUTE ON FUNCTIONS TO PUBLIC;
DO $drop_other_schemas$
DECLARE s text;
BEGIN
  FOR s IN
    SELECT n.nspname FROM pg_namespace n
     WHERE n.nspname <> 'public'
       AND n.nspname <> 'information_schema'
       AND n.nspname NOT LIKE 'pg_%'
  LOOP
    EXECUTE format(
      'ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA %I '
      'REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC', s);
  END LOOP;
END
$drop_other_schemas$;
-- The plain grant sweep revokes anon on new tables again.
-- Run it after this undo if that 2026-09-03 default should stay.
GRANT SELECT ON public.alt_game_lines TO anon;
GRANT SELECT ON public.fighters TO anon;
GRANT SELECT ON public.games TO anon;
GRANT SELECT ON public.injury_status_current TO anon;
GRANT SELECT ON public.latest_odds TO anon;
GRANT SELECT ON public.latest_prop_odds TO anon;
GRANT SELECT ON public.lineup_slots TO anon;
GRANT SELECT ON public.mlb_pitcher_stats TO anon;
GRANT SELECT ON public.mlb_team_stats TO anon;
GRANT SELECT ON public.nba_first_basket_games TO anon;
GRANT SELECT ON public.nba_first_basket_players TO anon;
GRANT SELECT ON public.nba_player_dnp TO anon;
GRANT SELECT ON public.nba_player_game_log TO anon;
GRANT SELECT ON public.nba_team_q1_games TO anon;
GRANT SELECT ON public.nba_team_stats TO anon;
GRANT SELECT ON public.ncaab_player_game_log TO anon;
GRANT SELECT ON public.ncaabw_player_game_log TO anon;
GRANT SELECT ON public.ncaaf_player_game_log TO anon;
GRANT SELECT ON public.ncaaf_team_stats TO anon;
GRANT SELECT ON public.ncaaf_teams TO anon;
GRANT SELECT ON public.nfl_player_game_log TO anon;
GRANT SELECT ON public.nfl_team_game_stats TO anon;
GRANT SELECT ON public.nhl_goalie_game_log TO anon;
GRANT SELECT ON public.nhl_skater_game_log TO anon;
GRANT SELECT ON public.nhl_team_game_log TO anon;
GRANT SELECT ON public.nhl_team_stats TO anon;
GRANT SELECT ON public.odds TO anon;
GRANT SELECT ON public.player_game_log TO anon;
GRANT SELECT ON public.player_handedness TO anon;
GRANT SELECT ON public.player_news TO anon;
GRANT SELECT ON public.player_positions TO anon;
GRANT SELECT ON public.player_prop_odds TO anon;
GRANT SELECT ON public.player_savant_stats TO anon;
GRANT SELECT ON public.public_betting TO anon;
GRANT SELECT ON public.team_period_results TO anon;
GRANT SELECT ON public.team_stats_board_cache TO anon;
GRANT SELECT ON public.ufc_fight_log TO anon;
GRANT SELECT ON public.umpires TO anon;
GRANT SELECT ON public.v_fighter_season_totals_ufc TO anon;
GRANT SELECT ON public.v_latest_dk_odds TO anon;
GRANT SELECT ON public.v_latest_inplay_odds_all_books TO anon;
GRANT SELECT ON public.v_latest_odds_all_books TO anon;
GRANT SELECT ON public.v_latest_prop_odds_all_books TO anon;
GRANT SELECT ON public.v_mlb_tonight_matchups TO anon;
GRANT SELECT ON public.v_nba_first_basket_player_season TO anon;
GRANT SELECT ON public.v_nba_first_basket_team_season TO anon;
GRANT SELECT ON public.v_nba_team_q1_season TO anon;
GRANT SELECT ON public.v_nhl_player_prop_odds TO anon;
GRANT SELECT ON public.v_player_season_totals_mlb TO anon;
GRANT SELECT ON public.v_player_season_totals_nba TO anon;
GRANT SELECT ON public.v_player_season_totals_ncaab TO anon;
GRANT SELECT ON public.v_player_season_totals_ncaabw TO anon;
GRANT SELECT ON public.v_player_season_totals_ncaaf TO anon;
GRANT SELECT ON public.v_player_season_totals_nfl TO anon;
GRANT SELECT ON public.v_player_season_totals_nhl TO anon;
GRANT SELECT ON public.v_player_season_totals_wnba TO anon;
GRANT SELECT ON public.v_team_season_record_mlb TO anon;
GRANT SELECT ON public.v_team_season_totals_nhl TO anon;
GRANT SELECT ON public.v_wnba_tonight_matchups TO anon;
GRANT SELECT ON public.wnba_player_game_log TO anon;
GRANT SELECT ON public.wnba_team_stats TO anon;
GRANT SELECT ON public.live_scoreboard TO anon;
GRANT SELECT ON public.scoreboard_splits TO anon;
GRANT SELECT ON public.v_ncaaf_scoreboard_latest TO anon;
GRANT SELECT ON public.ncaaf_live_states TO anon;
GRANT SELECT ON public.live_game_state TO anon;
GRANT SELECT ON public.latest_live_game_state TO anon;
GRANT SELECT ON public.v_live_game_state_latest TO anon;
GRANT SELECT ON public.game_weather TO anon;
GRANT SELECT ON public.golf_players TO anon;
GRANT SELECT ON public.golf_rounds TO anon;
GRANT SELECT ON public.golf_tournaments TO anon;
GRANT SELECT ON public.device_push_tokens TO anon;
GRANT SELECT ON public.dk_line_observations TO anon;
GRANT SELECT ON public.feedback TO anon;
GRANT SELECT ON public.golf_odds TO anon;
GRANT SELECT ON public.injuries TO anon;
GRANT SELECT ON public.linked_sportsbook_accounts TO anon;
GRANT SELECT ON public.live_credit_telemetry TO anon;
GRANT SELECT ON public.live_feed_probe TO anon;
GRANT SELECT ON public.live_trigger_events TO anon;
GRANT SELECT ON public.mlb_bullpen_stats TO anon;
GRANT SELECT ON public.ncaaf_team_game_log TO anon;
GRANT SELECT ON public.ncaaf_venues TO anon;
GRANT SELECT ON public.nfl_snap_counts TO anon;
GRANT SELECT ON public.nhl_goalie_stats TO anon;
GRANT SELECT ON public.nhl_skater_stats TO anon;
GRANT SELECT ON public.pipeline_log TO anon;
GRANT SELECT ON public.plays TO anon;
GRANT SELECT ON public.synced_bets TO anon;
GRANT DELETE, INSERT, REFERENCES, SELECT, TRIGGER ON public.tracked_bets TO anon, authenticated;
DROP FUNCTION IF EXISTS public.untrack_tracked_bet(text, bigint);
DROP FUNCTION IF EXISTS public.clear_my_tracked_bets(text);
ALTER POLICY "anon read alt_game_lines" ON public.alt_game_lines TO anon, authenticated;
ALTER POLICY "anon read fighters" ON public.fighters TO anon, authenticated;
ALTER POLICY "allow anon read" ON public.games TO public;
ALTER POLICY "anon read games" ON public.games TO anon, authenticated;
ALTER POLICY "anon read injury_status_current" ON public.injury_status_current TO anon, authenticated;
ALTER POLICY "anon read latest_odds" ON public.latest_odds TO anon, authenticated;
ALTER POLICY "anon read latest_prop_odds" ON public.latest_prop_odds TO anon, authenticated;
ALTER POLICY "anon read lineup_slots" ON public.lineup_slots TO anon, authenticated;
ALTER POLICY "anon read mlb_pitcher_stats" ON public.mlb_pitcher_stats TO anon, authenticated;
ALTER POLICY "anon read mlb_team_stats" ON public.mlb_team_stats TO anon, authenticated;
ALTER POLICY "anon read nba_first_basket_games" ON public.nba_first_basket_games TO anon, authenticated;
ALTER POLICY "anon read nba_first_basket_players" ON public.nba_first_basket_players TO anon, authenticated;
ALTER POLICY "anon read nba_player_dnp" ON public.nba_player_dnp TO anon, authenticated;
ALTER POLICY "anon read nba_player_game_log" ON public.nba_player_game_log TO anon, authenticated;
ALTER POLICY "anon read nba_team_q1_games" ON public.nba_team_q1_games TO anon, authenticated;
ALTER POLICY "anon read nba_team_stats" ON public.nba_team_stats TO anon, authenticated;
ALTER POLICY "anon read ncaab_player_game_log" ON public.ncaab_player_game_log TO anon, authenticated;
ALTER POLICY "anon read ncaabw_player_game_log" ON public.ncaabw_player_game_log TO anon, authenticated;
ALTER POLICY "anon read ncaaf_player_game_log" ON public.ncaaf_player_game_log TO anon, authenticated;
ALTER POLICY "anon read ncaaf_team_stats" ON public.ncaaf_team_stats TO anon, authenticated;
ALTER POLICY "anon read ncaaf_teams" ON public.ncaaf_teams TO anon, authenticated;
ALTER POLICY "anon read nfl_player_game_log" ON public.nfl_player_game_log TO anon, authenticated;
ALTER POLICY "anon read nfl_team_game_stats" ON public.nfl_team_game_stats TO anon, authenticated;
ALTER POLICY "anon read nhl_goalie_game_log" ON public.nhl_goalie_game_log TO anon, authenticated;
ALTER POLICY "anon read nhl_skater_game_log" ON public.nhl_skater_game_log TO anon, authenticated;
ALTER POLICY "anon read nhl_team_game_log" ON public.nhl_team_game_log TO anon, authenticated;
ALTER POLICY "anon read nhl_team_stats" ON public.nhl_team_stats TO anon, authenticated;
ALTER POLICY "allow anon read" ON public.odds TO public;
ALTER POLICY "anon read odds" ON public.odds TO anon, authenticated;
ALTER POLICY "anon read player_game_log" ON public.player_game_log TO anon, authenticated;
ALTER POLICY "anon read player_handedness" ON public.player_handedness TO anon, authenticated;
ALTER POLICY "anon read player_news" ON public.player_news TO anon, authenticated;
ALTER POLICY "anon read player_positions" ON public.player_positions TO anon, authenticated;
ALTER POLICY "anon read player_prop_odds" ON public.player_prop_odds TO anon, authenticated;
ALTER POLICY "anon read player_savant_stats" ON public.player_savant_stats TO anon, authenticated;
ALTER POLICY "anon read public_betting" ON public.public_betting TO anon, authenticated;
ALTER POLICY "anon read team_period_results" ON public.team_period_results TO anon, authenticated;
ALTER POLICY "team_stats_board_cache_read" ON public.team_stats_board_cache TO anon, authenticated;
ALTER POLICY "anon read ufc_fight_log" ON public.ufc_fight_log TO anon, authenticated;
ALTER POLICY "anon read umpires" ON public.umpires TO anon, authenticated;
ALTER POLICY "anon read wnba_player_game_log" ON public.wnba_player_game_log TO anon, authenticated;
ALTER POLICY "anon read wnba_team_stats" ON public.wnba_team_stats TO anon, authenticated;
ALTER POLICY "anon read live_scoreboard" ON public.live_scoreboard TO anon, authenticated;
ALTER POLICY "anon read scoreboard_splits" ON public.scoreboard_splits TO anon, authenticated;
ALTER POLICY "anon read ncaaf_live_states" ON public.ncaaf_live_states TO anon, authenticated;
ALTER POLICY "anon read live_game_state" ON public.live_game_state TO anon, authenticated;
ALTER POLICY "anon read latest_live_game_state" ON public.latest_live_game_state TO anon, authenticated;
ALTER POLICY "allow anon read" ON public.game_weather TO public;
ALTER POLICY "anon read game_weather" ON public.game_weather TO anon, authenticated;
ALTER POLICY "anon read golf_players" ON public.golf_players TO anon, authenticated;
ALTER POLICY "anon read golf_rounds" ON public.golf_rounds TO anon, authenticated;
ALTER POLICY "anon read golf_tournaments" ON public.golf_tournaments TO anon, authenticated;
DROP POLICY IF EXISTS tracked_bets_owner_insert ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_select ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_delete ON public.tracked_bets;
CREATE POLICY "anon insert tracked_bets" ON public.tracked_bets
  FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon delete tracked_bets" ON public.tracked_bets
  FOR DELETE TO anon, authenticated USING (true);
GRANT EXECUTE ON FUNCTION public.fighter_window_totals_ufc(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_mlb(integer[], text, text, text[], text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_nba(integer[], text, text[], text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaab(integer[], text, text[], text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaabw(integer[], text, text[], text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaaf(integer[], text, text[], text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_nfl(integer[], text, text[], text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_wnba(integer[], text, text[], text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_mlb(integer, text, integer, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_nba(integer, integer, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaab(integer, integer, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaabw(integer, integer, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaaf(integer, integer, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_nfl(integer, integer, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_wnba(integer, integer, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_mlb(integer, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nba(integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaab(integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaabw(integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaaf(integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nfl(integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_wnba(integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_stat_values_nhl(integer, text, text, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_vs_defense_nba(text, text, text, integer[], integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_vs_defense_nfl(text, text, text, integer[], integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_vs_defense_wnba(text, text, text, integer[], integer, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_mlb(integer, text, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_nba(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaab(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaabw(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaaf(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_nfl(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_nhl(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_wnba(integer, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.position_defense_ranks_nfl(integer[], text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_mlb(integer[], text, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_nba(integer[], text, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_ncaaf(integer[], text, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_nfl(integer[], text, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_wnba(integer[], text, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.team_stats_board(text, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public._jsonb_text_array(jsonb) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_mark_read(text, bigint) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_messages_for_thread(text, bigint) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_submit(text, text, text, text, text, bigint, uuid) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_threads_for_device(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.feedback_unread_count(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.log_picks_changes() TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.log_picks_changes() TO PUBLIC;
GRANT EXECUTE ON FUNCTION public.log_sgp_price(text, text, integer, numeric, integer, integer, jsonb, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.member_books_get(text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.member_books_set(text, text[]) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.save_device_push_token(text, text, text, boolean, text) TO anon, authenticated;
NOTIFY pgrst, 'reload schema';
COMMIT;
