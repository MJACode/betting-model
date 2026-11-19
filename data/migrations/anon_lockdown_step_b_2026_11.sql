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

-- Step B. Everything else off anon, plus tracked_bets owner policies.
-- Afterwards anon keeps site_public_record, log_app_error, log_app_timings
-- and save_device_push_token (signed-out opt-out). Authenticated access is
-- unchanged apart from tracked_bets.
-- Run at least 24 hours after step A unless Matt says otherwise.

BEGIN;

REVOKE ALL ON public.alt_game_lines FROM anon;
REVOKE ALL ON public.fighters FROM anon;
REVOKE ALL ON public.games FROM anon;
REVOKE ALL ON public.injury_status_current FROM anon;
REVOKE ALL ON public.latest_odds FROM anon;
REVOKE ALL ON public.latest_prop_odds FROM anon;
REVOKE ALL ON public.lineup_slots FROM anon;
REVOKE ALL ON public.mlb_pitcher_stats FROM anon;
REVOKE ALL ON public.mlb_team_stats FROM anon;
REVOKE ALL ON public.nba_first_basket_games FROM anon;
REVOKE ALL ON public.nba_first_basket_players FROM anon;
REVOKE ALL ON public.nba_player_dnp FROM anon;
REVOKE ALL ON public.nba_player_game_log FROM anon;
REVOKE ALL ON public.nba_team_q1_games FROM anon;
REVOKE ALL ON public.nba_team_stats FROM anon;
REVOKE ALL ON public.ncaab_player_game_log FROM anon;
REVOKE ALL ON public.ncaabw_player_game_log FROM anon;
REVOKE ALL ON public.ncaaf_player_game_log FROM anon;
REVOKE ALL ON public.ncaaf_team_stats FROM anon;
REVOKE ALL ON public.ncaaf_teams FROM anon;
REVOKE ALL ON public.nfl_player_game_log FROM anon;
REVOKE ALL ON public.nfl_team_game_stats FROM anon;
REVOKE ALL ON public.nhl_goalie_game_log FROM anon;
REVOKE ALL ON public.nhl_skater_game_log FROM anon;
REVOKE ALL ON public.nhl_team_game_log FROM anon;
REVOKE ALL ON public.nhl_team_stats FROM anon;
REVOKE ALL ON public.odds FROM anon;
REVOKE ALL ON public.player_game_log FROM anon;
REVOKE ALL ON public.player_handedness FROM anon;
REVOKE ALL ON public.player_news FROM anon;
REVOKE ALL ON public.player_positions FROM anon;
REVOKE ALL ON public.player_prop_odds FROM anon;
REVOKE ALL ON public.player_savant_stats FROM anon;
REVOKE ALL ON public.public_betting FROM anon;
REVOKE ALL ON public.team_period_results FROM anon;
REVOKE ALL ON public.team_stats_board_cache FROM anon;
REVOKE ALL ON public.ufc_fight_log FROM anon;
REVOKE ALL ON public.umpires FROM anon;
REVOKE ALL ON public.v_fighter_season_totals_ufc FROM anon;
REVOKE ALL ON public.v_latest_dk_odds FROM anon;
REVOKE ALL ON public.v_latest_inplay_odds_all_books FROM anon;
REVOKE ALL ON public.v_latest_odds_all_books FROM anon;
REVOKE ALL ON public.v_latest_prop_odds_all_books FROM anon;
REVOKE ALL ON public.v_mlb_tonight_matchups FROM anon;
REVOKE ALL ON public.v_nba_first_basket_player_season FROM anon;
REVOKE ALL ON public.v_nba_first_basket_team_season FROM anon;
REVOKE ALL ON public.v_nba_team_q1_season FROM anon;
REVOKE ALL ON public.v_nhl_player_prop_odds FROM anon;
REVOKE ALL ON public.v_player_season_totals_mlb FROM anon;
REVOKE ALL ON public.v_player_season_totals_nba FROM anon;
REVOKE ALL ON public.v_player_season_totals_ncaab FROM anon;
REVOKE ALL ON public.v_player_season_totals_ncaabw FROM anon;
REVOKE ALL ON public.v_player_season_totals_ncaaf FROM anon;
REVOKE ALL ON public.v_player_season_totals_nfl FROM anon;
REVOKE ALL ON public.v_player_season_totals_nhl FROM anon;
REVOKE ALL ON public.v_player_season_totals_wnba FROM anon;
REVOKE ALL ON public.v_team_season_record_mlb FROM anon;
REVOKE ALL ON public.v_team_season_totals_nhl FROM anon;
REVOKE ALL ON public.v_wnba_tonight_matchups FROM anon;
REVOKE ALL ON public.wnba_player_game_log FROM anon;
REVOKE ALL ON public.wnba_team_stats FROM anon;
REVOKE ALL ON public.live_scoreboard FROM anon;
REVOKE ALL ON public.scoreboard_splits FROM anon;
REVOKE ALL ON public.v_ncaaf_scoreboard_latest FROM anon;
REVOKE ALL ON public.ncaaf_live_states FROM anon;
REVOKE ALL ON public.live_game_state FROM anon;
REVOKE ALL ON public.latest_live_game_state FROM anon;
REVOKE ALL ON public.v_live_game_state_latest FROM anon;
REVOKE ALL ON public.game_weather FROM anon;
REVOKE ALL ON public.golf_players FROM anon;
REVOKE ALL ON public.golf_rounds FROM anon;
REVOKE ALL ON public.golf_tournaments FROM anon;
REVOKE ALL ON public.device_push_tokens FROM anon;
REVOKE ALL ON public.dk_line_observations FROM anon;
REVOKE ALL ON public.feedback FROM anon;
REVOKE ALL ON public.golf_odds FROM anon;
REVOKE ALL ON public.injuries FROM anon;
REVOKE ALL ON public.linked_sportsbook_accounts FROM anon;
REVOKE ALL ON public.live_credit_telemetry FROM anon;
REVOKE ALL ON public.live_feed_probe FROM anon;
REVOKE ALL ON public.live_trigger_events FROM anon;
REVOKE ALL ON public.mlb_bullpen_stats FROM anon;
REVOKE ALL ON public.ncaaf_team_game_log FROM anon;
REVOKE ALL ON public.ncaaf_venues FROM anon;
REVOKE ALL ON public.nfl_snap_counts FROM anon;
REVOKE ALL ON public.nhl_goalie_stats FROM anon;
REVOKE ALL ON public.nhl_skater_stats FROM anon;
REVOKE ALL ON public.pipeline_log FROM anon;
REVOKE ALL ON public.plays FROM anon;
REVOKE ALL ON public.synced_bets FROM anon;
REVOKE ALL ON public.tracked_bets FROM anon;

REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon;
GRANT USAGE ON SEQUENCE public.tracked_bets_id_seq TO authenticated;
-- New objects from postgres must not arrive open. Tables repeat the
-- 2026-09-03 sweep. Sequences and PUBLIC function execute are new here.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon;

ALTER POLICY "anon read alt_game_lines" ON public.alt_game_lines TO authenticated;
ALTER POLICY "anon read fighters" ON public.fighters TO authenticated;
ALTER POLICY "allow anon read" ON public.games TO authenticated;
ALTER POLICY "anon read games" ON public.games TO authenticated;
ALTER POLICY "anon read injury_status_current" ON public.injury_status_current TO authenticated;
ALTER POLICY "anon read latest_odds" ON public.latest_odds TO authenticated;
ALTER POLICY "anon read latest_prop_odds" ON public.latest_prop_odds TO authenticated;
ALTER POLICY "anon read lineup_slots" ON public.lineup_slots TO authenticated;
ALTER POLICY "anon read mlb_pitcher_stats" ON public.mlb_pitcher_stats TO authenticated;
ALTER POLICY "anon read mlb_team_stats" ON public.mlb_team_stats TO authenticated;
ALTER POLICY "anon read nba_first_basket_games" ON public.nba_first_basket_games TO authenticated;
ALTER POLICY "anon read nba_first_basket_players" ON public.nba_first_basket_players TO authenticated;
ALTER POLICY "anon read nba_player_dnp" ON public.nba_player_dnp TO authenticated;
ALTER POLICY "anon read nba_player_game_log" ON public.nba_player_game_log TO authenticated;
ALTER POLICY "anon read nba_team_q1_games" ON public.nba_team_q1_games TO authenticated;
ALTER POLICY "anon read nba_team_stats" ON public.nba_team_stats TO authenticated;
ALTER POLICY "anon read ncaab_player_game_log" ON public.ncaab_player_game_log TO authenticated;
ALTER POLICY "anon read ncaabw_player_game_log" ON public.ncaabw_player_game_log TO authenticated;
ALTER POLICY "anon read ncaaf_player_game_log" ON public.ncaaf_player_game_log TO authenticated;
ALTER POLICY "anon read ncaaf_team_stats" ON public.ncaaf_team_stats TO authenticated;
ALTER POLICY "anon read ncaaf_teams" ON public.ncaaf_teams TO authenticated;
ALTER POLICY "anon read nfl_player_game_log" ON public.nfl_player_game_log TO authenticated;
ALTER POLICY "anon read nfl_team_game_stats" ON public.nfl_team_game_stats TO authenticated;
ALTER POLICY "anon read nhl_goalie_game_log" ON public.nhl_goalie_game_log TO authenticated;
ALTER POLICY "anon read nhl_skater_game_log" ON public.nhl_skater_game_log TO authenticated;
ALTER POLICY "anon read nhl_team_game_log" ON public.nhl_team_game_log TO authenticated;
ALTER POLICY "anon read nhl_team_stats" ON public.nhl_team_stats TO authenticated;
ALTER POLICY "allow anon read" ON public.odds TO authenticated;
ALTER POLICY "anon read odds" ON public.odds TO authenticated;
ALTER POLICY "anon read player_game_log" ON public.player_game_log TO authenticated;
ALTER POLICY "anon read player_handedness" ON public.player_handedness TO authenticated;
ALTER POLICY "anon read player_news" ON public.player_news TO authenticated;
ALTER POLICY "anon read player_positions" ON public.player_positions TO authenticated;
ALTER POLICY "anon read player_prop_odds" ON public.player_prop_odds TO authenticated;
ALTER POLICY "anon read player_savant_stats" ON public.player_savant_stats TO authenticated;
ALTER POLICY "anon read public_betting" ON public.public_betting TO authenticated;
ALTER POLICY "anon read team_period_results" ON public.team_period_results TO authenticated;
ALTER POLICY "team_stats_board_cache_read" ON public.team_stats_board_cache TO authenticated;
ALTER POLICY "anon read ufc_fight_log" ON public.ufc_fight_log TO authenticated;
ALTER POLICY "anon read umpires" ON public.umpires TO authenticated;
ALTER POLICY "anon read wnba_player_game_log" ON public.wnba_player_game_log TO authenticated;
ALTER POLICY "anon read wnba_team_stats" ON public.wnba_team_stats TO authenticated;
ALTER POLICY "anon read live_scoreboard" ON public.live_scoreboard TO authenticated;
ALTER POLICY "anon read scoreboard_splits" ON public.scoreboard_splits TO authenticated;
ALTER POLICY "anon read ncaaf_live_states" ON public.ncaaf_live_states TO authenticated;
ALTER POLICY "anon read live_game_state" ON public.live_game_state TO authenticated;
ALTER POLICY "anon read latest_live_game_state" ON public.latest_live_game_state TO authenticated;
ALTER POLICY "allow anon read" ON public.game_weather TO authenticated;
ALTER POLICY "anon read game_weather" ON public.game_weather TO authenticated;
ALTER POLICY "anon read golf_players" ON public.golf_players TO authenticated;
ALTER POLICY "anon read golf_rounds" ON public.golf_rounds TO authenticated;
ALTER POLICY "anon read golf_tournaments" ON public.golf_tournaments TO authenticated;

REVOKE ALL ON FUNCTION public.fighter_window_totals_ufc(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.fighter_window_totals_ufc(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_h2h_stat_values_mlb(integer[], text, text, text[], text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_mlb(integer[], text, text, text[], text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_h2h_stat_values_nba(integer[], text, text[], text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_nba(integer[], text, text[], text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_h2h_stat_values_ncaab(integer[], text, text[], text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaab(integer[], text, text[], text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_h2h_stat_values_ncaabw(integer[], text, text[], text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaabw(integer[], text, text[], text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_h2h_stat_values_ncaaf(integer[], text, text[], text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_ncaaf(integer[], text, text[], text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_h2h_stat_values_nfl(integer[], text, text[], text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_nfl(integer[], text, text[], text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_h2h_stat_values_wnba(integer[], text, text[], text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_h2h_stat_values_wnba(integer[], text, text[], text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_recent_games_mlb(integer, text, integer, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_recent_games_mlb(integer, text, integer, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_recent_games_nba(integer, integer, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_recent_games_nba(integer, integer, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_recent_games_ncaab(integer, integer, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaab(integer, integer, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_recent_games_ncaabw(integer, integer, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaabw(integer, integer, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_recent_games_ncaaf(integer, integer, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_recent_games_ncaaf(integer, integer, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_recent_games_nfl(integer, integer, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_recent_games_nfl(integer, integer, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_recent_games_wnba(integer, integer, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_recent_games_wnba(integer, integer, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_season_stat_values_mlb(integer, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_mlb(integer, text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_season_stat_values_nba(integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nba(integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_season_stat_values_ncaab(integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaab(integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_season_stat_values_ncaabw(integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaabw(integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_season_stat_values_ncaaf(integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_ncaaf(integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_season_stat_values_nfl(integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nfl(integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_season_stat_values_wnba(integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_wnba(integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_stat_values_nhl(integer, text, text, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_stat_values_nhl(integer, text, text, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_vs_defense_nba(text, text, text, integer[], integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_vs_defense_nba(text, text, text, integer[], integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_vs_defense_nfl(text, text, text, integer[], integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_vs_defense_nfl(text, text, text, integer[], integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_vs_defense_wnba(text, text, text, integer[], integer, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_vs_defense_wnba(text, text, text, integer[], integer, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_mlb(integer, text, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_mlb(integer, text, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_nba(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_nba(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_ncaab(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaab(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_ncaabw(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaabw(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_ncaaf(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_ncaaf(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_nfl(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_nfl(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_nhl(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_nhl(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.player_window_totals_wnba(integer, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.player_window_totals_wnba(integer, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.position_defense_ranks_nfl(integer[], text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.position_defense_ranks_nfl(integer[], text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.position_vs_opponent_mlb(integer[], text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_mlb(integer[], text, text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.position_vs_opponent_nba(integer[], text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_nba(integer[], text, text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.position_vs_opponent_ncaaf(integer[], text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_ncaaf(integer[], text, text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.position_vs_opponent_nfl(integer[], text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_nfl(integer[], text, text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.position_vs_opponent_wnba(integer[], text, text, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.position_vs_opponent_wnba(integer[], text, text, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.team_stats_board(text, integer) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.team_stats_board(text, integer) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public._jsonb_text_array(jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public._jsonb_text_array(jsonb) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.feedback_mark_read(text, bigint) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.feedback_mark_read(text, bigint) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.feedback_messages_for_thread(text, bigint) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.feedback_messages_for_thread(text, bigint) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.feedback_submit(text, text, text, text, text, bigint, uuid) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.feedback_submit(text, text, text, text, text, bigint, uuid) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.feedback_threads_for_device(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.feedback_threads_for_device(text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.feedback_unread_count(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.feedback_unread_count(text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.log_picks_changes() FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.log_picks_changes() TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.log_sgp_price(text, text, integer, numeric, integer, integer, jsonb, text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.log_sgp_price(text, text, integer, numeric, integer, integer, jsonb, text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.member_books_get(text) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.member_books_get(text) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.member_books_set(text, text[]) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.member_books_set(text, text[]) TO postgres, authenticated, service_role;
REVOKE ALL ON FUNCTION public.save_device_push_token(text, text, text, boolean, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.save_device_push_token(text, text, text, boolean, text) TO postgres, anon, authenticated, service_role;

-- notification_inbox and notification_sport_prefs are authenticated-only
-- (draft PR for the inbox). If they already exist, anon loses every grant.
-- If they do not exist yet, this is a no-op.
DO $inbox$
BEGIN
  IF to_regclass('public.notification_inbox') IS NOT NULL THEN
    EXECUTE 'REVOKE ALL ON TABLE public.notification_inbox FROM anon';
  END IF;
  IF to_regclass('public.notification_sport_prefs') IS NOT NULL THEN
    EXECUTE 'REVOKE ALL ON TABLE public.notification_sport_prefs FROM anon';
  END IF;
END $inbox$;

-- tracked_bets. DEFAULT auth.uid() fills the column the shipping app does
-- not send, so builds 14401 and 14601 keep inserting. A client that sends
-- another user's id fails the check. The column is kept on undo.
-- Legacy rows with user_id NULL are filled only when that device_id maps
-- to exactly one account in app_timings or feedback_threads. Anything
-- still NULL is deleted by untrack_tracked_bet when the caller is that
-- device and no other account has used it. The worker then stops alerting.
ALTER TABLE public.tracked_bets
    ADD COLUMN IF NOT EXISTS user_id uuid NULL DEFAULT auth.uid()
    REFERENCES auth.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS tracked_bets_user_id_idx
    ON public.tracked_bets (user_id);

DO $backfill$
DECLARE src text := '';
BEGIN
  IF to_regclass('public.app_timings') IS NOT NULL THEN
    src := 'SELECT device_id, user_id FROM public.app_timings'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF to_regclass('public.feedback_threads') IS NOT NULL THEN
    IF src <> '' THEN src := src || ' UNION '; END IF;
    src := src || 'SELECT device_id, user_id FROM public.feedback_threads'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF src = '' THEN RETURN; END IF;
  EXECUTE
    'UPDATE public.tracked_bets tb SET user_id = mapped.user_id FROM ('
    || 'SELECT device_id, min(user_id::text)::uuid AS user_id FROM ('
    || src || ') seen GROUP BY device_id '
    || 'HAVING count(DISTINCT user_id) = 1) mapped '
    || 'WHERE tb.user_id IS NULL AND tb.device_id = mapped.device_id';
END $backfill$;
DROP POLICY IF EXISTS "anon insert tracked_bets" ON public.tracked_bets;
DROP POLICY IF EXISTS "anon delete tracked_bets" ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_insert ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_select ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_delete ON public.tracked_bets;
REVOKE ALL ON public.tracked_bets FROM anon;
REVOKE ALL ON public.tracked_bets FROM authenticated;
GRANT SELECT, INSERT, DELETE ON public.tracked_bets TO authenticated;
CREATE POLICY tracked_bets_owner_insert ON public.tracked_bets
    FOR INSERT TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));
CREATE POLICY tracked_bets_owner_select ON public.tracked_bets
    FOR SELECT TO authenticated
    USING (user_id = (SELECT auth.uid()));
CREATE POLICY tracked_bets_owner_delete ON public.tracked_bets
    FOR DELETE TO authenticated
    USING (user_id = (SELECT auth.uid()));

-- Direct DELETE cannot see a legacy NULL user_id row. This function can,
-- and only when no other account is stored for that device.
CREATE OR REPLACE FUNCTION public.untrack_tracked_bet(
    p_device_id text, p_pick_id bigint)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
  uid uuid := auth.uid();
  other_owner boolean := false;
BEGIN
  IF uid IS NULL THEN
    RAISE EXCEPTION 'untrack_tracked_bet: sign in required' USING ERRCODE = '42501';
  END IF;
  IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{8,64}$' THEN
    RAISE EXCEPTION 'untrack_tracked_bet: bad device id' USING ERRCODE = '22023';
  END IF;
  IF to_regclass('public.app_timings') IS NOT NULL THEN
    EXECUTE
      'SELECT EXISTS (SELECT 1 FROM public.app_timings'
      || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
      INTO other_owner USING p_device_id, uid;
  END IF;
  IF NOT other_owner AND to_regclass('public.feedback_threads') IS NOT NULL THEN
    EXECUTE
      'SELECT EXISTS (SELECT 1 FROM public.feedback_threads'
      || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
      INTO other_owner USING p_device_id, uid;
  END IF;
  IF other_owner THEN
    DELETE FROM public.tracked_bets
     WHERE pick_id = p_pick_id AND device_id = p_device_id AND user_id = uid;
    RETURN;
  END IF;
  DELETE FROM public.tracked_bets
   WHERE pick_id = p_pick_id AND device_id = p_device_id
     AND (user_id = uid OR user_id IS NULL);
END $fn$;
REVOKE ALL ON FUNCTION public.untrack_tracked_bet(text, bigint) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.untrack_tracked_bet(text, bigint)
    TO postgres, authenticated, service_role;

-- Anon may read only site_public_record and execute only the two loggers
-- plus save_device_push_token.
-- An extension function installed in public would trip this. Stop and ask
-- rather than widening the revoke.
DO $guard$
DECLARE bad text;
BEGIN
  SELECT string_agg(c.relname, ',') INTO bad
    FROM pg_class c
   WHERE c.relnamespace = 'public'::regnamespace
     AND c.relkind IN ('r', 'v', 'm', 'p', 'f')
     AND c.relname <> 'site_public_record'
     AND (has_table_privilege('anon', c.oid, 'SELECT')
          OR has_table_privilege('anon', c.oid, 'INSERT')
          OR has_table_privilege('anon', c.oid, 'UPDATE')
          OR has_table_privilege('anon', c.oid, 'DELETE'));
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'anon still has table privs on: %', bad;
  END IF;
  SELECT string_agg(p.oid::regprocedure::text, ',') INTO bad
    FROM pg_proc p
   WHERE p.pronamespace = 'public'::regnamespace
     AND p.proname NOT IN ('log_app_error', 'log_app_timings', 'save_device_push_token')
     AND has_function_privilege('anon', p.oid, 'EXECUTE');
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'anon still executes: %', bad;
  END IF;
  IF NOT has_table_privilege('anon', 'public.site_public_record', 'SELECT') THEN
    RAISE EXCEPTION 'anon lost site_public_record';
  END IF;
  IF NOT has_table_privilege('authenticated', 'public.games', 'SELECT') THEN
    RAISE EXCEPTION 'authenticated lost games';
  END IF;
END $guard$;

NOTIFY pgrst, 'reload schema';
COMMIT;
