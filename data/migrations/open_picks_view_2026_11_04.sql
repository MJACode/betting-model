-- public.open_picks: every open pick in one view, for any Claude chat.
--
-- mike, 2026-11-04: no pasting anywhere, ever. docs/mobile_picks_prompt.md
-- held a prompt and a query for a person to paste into a claude.ai project.
-- It went stale whenever the query changed and only a person could refresh
-- it. The query lives here now. Any Claude chat with the Supabase connector
-- reads this view when asked for the open picks.
--
-- One row per open BET, as the app, Discord and push show it (CLAUDE.md 1b):
--   * not graded, pre-game, the game not started, no date horizon;
--   * not VOID, not the DUPLICATE copy, not written while its model was
--     paused, and its model not paused now;
--   * Discord has posted it. The app shows a bet once the channel has it, and
--     the producer posts only a bet that cleared its model's cut in
--     model_action_thresholds at the decided price. A posted bet keeps the
--     cuts it was written under (the app's passesActionFilter), so no cut is
--     re-applied here. A bet that clears its cut but is not posted yet is
--     not in the view, as it is not in the app.
--
-- The columns are fixed: CREATE OR REPLACE VIEW cannot rename, drop or
-- reorder them. A new column goes on the end. tests/test_open_picks_view.py
-- pins the list, the clauses and the two name lists (the app's model names,
-- Discord's book names).
--
-- The skip compares the view's comment to a marker that is the hash of the
-- view body, so a changed body is applied on the next pass. It also waits,
-- without raising, until published_pick_stake and v_discord_published exist:
-- on a fresh database this file runs before the posted-stake functions.
--
-- security_invoker, so the caller's own grants on picks, games,
-- model_action_thresholds and v_discord_published apply. SELECT only. Does
-- not write picks, push_sent or the record. One statement.

DO $mig$
BEGIN
  IF to_regprocedure('public.published_pick_stake(numeric)') IS NULL
     OR to_regclass('public.v_discord_published') IS NULL
     OR to_regclass('public.model_action_thresholds') IS NULL THEN
    RAISE NOTICE 'open_picks waits for published_pick_stake and v_discord_published';
    RETURN;
  END IF;

  IF to_regclass('public.open_picks') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.open_picks'), 'pg_class'), '')
         = 'open_picks 28e0bb477645'
     AND has_table_privilege('anon', 'public.open_picks', 'SELECT')
     AND has_table_privilege('authenticated', 'public.open_picks', 'SELECT')
  THEN
    RETURN;
  END IF;

  EXECUTE $view$
    CREATE OR REPLACE VIEW public.open_picks
    WITH (security_invoker = on) AS
    SELECT
           p.sport AS sport,
           -- The game's date and start, in Eastern time. A game with no start
           -- time on file keeps the pick's own game_date and no start.
           COALESCE(to_char(g.commence_time::timestamptz AT TIME ZONE 'America/New_York',
                            'YYYY-MM-DD'),
                    p.game_date) AS game_date,
           to_char(g.commence_time::timestamptz AT TIME ZONE 'America/New_York',
                   'FMHH12:MI AM') || ' ET' AS start_time_et,
           CASE
             WHEN g.home_team IS NULL AND g.away_team IS NULL THEN NULL
             WHEN p.sport = 'GOLF' THEN g.home_team
             WHEN p.sport = 'UFC' THEN g.away_team || ' vs ' || g.home_team
             ELSE g.away_team || ' @ ' || g.home_team
           END AS matchup,
           -- The pick as stored (CLAUDE.md 00). Never rebuilt from the line:
           -- a spread's stored line is the HOME number. One token is dropped:
           -- the sizing figure older NFL wind and opener labels end in
           -- ("LA @ WAS Under 47.5 · 0.87u"). It is not the stake; the stake
           -- column is (mike, 2026-11-04: one unit basis). Same pattern as
           -- tracking/pick_integrity._STAKE_TOKEN. Every other label, and
           -- the bet itself, is returned word for word.
           regexp_replace(p.pick_label, '\s*·\s*\d+(?:\.\d+)?u(?!\s*[^\s·])', '', 'g') AS pick,
           -- The price the pick was decided at (decision_odds since
           -- 2026-09-09, DraftKings before), and the book it was decided at.
           ROUND(COALESCE(p.decision_odds, p.dk_odds))::integer AS price,
           CASE lower(b.book_key)
             WHEN 'draftkings' THEN 'DraftKings'
             WHEN 'dk' THEN 'DraftKings'
             WHEN 'fanduel' THEN 'FanDuel'
             WHEN 'fd' THEN 'FanDuel'
             WHEN 'betmgm' THEN 'BetMGM'
             WHEN 'mgm' THEN 'BetMGM'
             WHEN 'williamhill_us' THEN 'Caesars'
             WHEN 'caesars' THEN 'Caesars'
             WHEN 'czr' THEN 'Caesars'
             WHEN 'espnbet' THEN 'ESPN BET'
             WHEN 'espn' THEN 'ESPN BET'
             WHEN 'betrivers' THEN 'BetRivers'
             WHEN 'br' THEN 'BetRivers'
             WHEN 'bovada' THEN 'Bovada'
             WHEN 'bov' THEN 'Bovada'
             WHEN 'pinnacle' THEN 'Pinnacle'
             WHEN 'pin' THEN 'Pinnacle'
             WHEN 'fanatics' THEN 'Fanatics'
             WHEN 'hardrockbet' THEN 'Hard Rock Bet'
             WHEN 'ballybet' THEN 'Bally Bet'
             WHEN 'betparx' THEN 'betPARX'
             WHEN 'rebet' THEN 'ReBet'
             WHEN 'fliff' THEN 'Fliff'
             ELSE b.book_key
           END AS book,
           -- The stake every published surface books: 1u to win at that
           -- price, risk capped at 3u, a bare 1u when there is no price.
           -- Same text as Discord's fmt_stake: two decimals, zeros trimmed.
           CASE
             WHEN COALESCE(p.decision_odds, p.dk_odds) IS NULL
                  OR COALESCE(p.decision_odds, p.dk_odds) = 0 THEN '1u'
             ELSE trim_scale(ROUND(s.risk, 2))::text || 'u to win '
                  || trim_scale(ROUND(s.win, 2))::text || 'u'
           END AS stake,
           ROUND(s.risk, 2) AS risk_units,
           ROUND(s.win, 2) AS to_win_units,
           -- The model's name as the app shows it (mobile/src/lib/modelMeta.ts).
           CASE p.model_id
             WHEN 'mlb_moneyline' THEN 'MLB Moneyline'
             WHEN 'mlb_over_under' THEN 'MLB Totals'
             WHEN 'mlb_runline' THEN 'MLB Spreads'
             WHEN 'mlb_spread_market' THEN 'MLB Spreads'
             WHEN 'mlb_total_market' THEN 'MLB Totals'
             WHEN 'mlb_total_public_fade' THEN 'MLB Totals Fade'
             WHEN 'mlb_f5_moneyline' THEN 'MLB First 5 Moneyline'
             WHEN 'mlb_f5_over_under' THEN 'MLB First 5 Totals'
             WHEN 'mlb_f5_runline' THEN 'MLB First 5 Spreads'
             WHEN 'mlb_live_win_prob' THEN 'MLB Live Moneyline'
             WHEN 'mlb_live_total_runs' THEN 'MLB Live Totals'
             WHEN 'mlb_live_runline' THEN 'MLB Live Spreads'
             WHEN 'mlb_prop_pitcher_k' THEN 'MLB Pitcher Strikeouts'
             WHEN 'mlb_prop_pitcher_hits' THEN 'MLB Hits Allowed'
             WHEN 'mlb_prop_pitcher_er' THEN 'MLB Earned Runs'
             WHEN 'mlb_prop_pitcher_outs' THEN 'MLB Pitcher Outs'
             WHEN 'mlb_prop_pitcher_walks' THEN 'MLB Pitcher Walks'
             WHEN 'mlb_prop_batter_hits' THEN 'MLB Hits'
             WHEN 'mlb_prop_batter_tb' THEN 'MLB Total Bases'
             WHEN 'mlb_prop_batter_hr' THEN 'MLB Home Runs'
             WHEN 'mlb_prop_batter_rbi' THEN 'MLB RBIs'
             WHEN 'mlb_prop_batter_runs' THEN 'MLB Runs Scored'
             WHEN 'mlb_prop_batter_sb' THEN 'MLB Stolen Bases'
             WHEN 'mlb_prop_batter_walks' THEN 'MLB Batter Walks'
             WHEN 'wnba_moneyline' THEN 'WNBA Moneyline'
             WHEN 'wnba_over_under' THEN 'WNBA Totals'
             WHEN 'wnba_spread' THEN 'WNBA Spreads'
             WHEN 'wnba_prop_player_points' THEN 'WNBA Points'
             WHEN 'wnba_prop_player_rebounds' THEN 'WNBA Rebounds'
             WHEN 'wnba_prop_player_assists' THEN 'WNBA Assists'
             WHEN 'wnba_prop_market' THEN 'WNBA Props'
             WHEN 'wnba_prop_player_threes' THEN 'WNBA Threes'
             WHEN 'wnba_prop_player_pra' THEN 'WNBA Pts + Reb + Ast'
             WHEN 'nba_moneyline' THEN 'NBA Moneyline'
             WHEN 'nba_over_under' THEN 'NBA Totals'
             WHEN 'nba_spread' THEN 'NBA Spreads'
             WHEN 'nba_prop_player_points' THEN 'NBA Points'
             WHEN 'nba_prop_player_rebounds' THEN 'NBA Rebounds'
             WHEN 'nba_prop_player_assists' THEN 'NBA Assists'
             WHEN 'nba_prop_player_threes' THEN 'NBA Threes'
             WHEN 'nba_prop_player_pra' THEN 'NBA Pts + Reb + Ast'
             WHEN 'nba_prop_player_blocks' THEN 'NBA Blocks'
             WHEN 'nba_prop_player_steals' THEN 'NBA Steals'
             WHEN 'nba_prop_player_turnovers' THEN 'NBA Turnovers'
             WHEN 'nba_prop_player_dd' THEN 'NBA Double-Double'
             WHEN 'nba_prop_market' THEN 'NBA Props'
             WHEN 'nba_prop_projection' THEN 'NBA Projected Props'
             WHEN 'nba_total_luck' THEN 'NBA Totals'
             WHEN 'nba_team_total_luck' THEN 'NBA Team Totals'
             WHEN 'nba_first_half_total_luck' THEN 'NBA First Half Totals'
             WHEN 'nba_q1_trend' THEN 'NBA First Quarter Spreads'
             WHEN 'nba_live_spread_q12' THEN 'NBA Early Live Spreads'
             WHEN 'ncaab_live_spread_h1' THEN 'NCAAB Early Live Spreads'
             WHEN 'ncaab_live_spread_h2' THEN 'NCAAB Late Live Spreads'
             WHEN 'ncaab_live_total_h2' THEN 'NCAAB Late Live Totals'
             WHEN 'ufc_moneyline' THEN 'UFC Moneyline'
             WHEN 'ufc_total_rounds' THEN 'UFC Totals'
             WHEN 'ufc_method_of_victory' THEN 'UFC Method of Victory'
             WHEN 'nhl_moneyline' THEN 'NHL Moneyline'
             WHEN 'nhl_moneyline_regulation' THEN 'NHL 3-Way Moneyline'
             WHEN 'nhl_over_under' THEN 'NHL Totals'
             WHEN 'nhl_puckline' THEN 'NHL Spreads'
             WHEN 'nhl_prop_blocked_shots' THEN 'NHL Blocked Shots'
             WHEN 'nhl_prop_saves' THEN 'NHL Saves'
             WHEN 'nhl_prop_shots_on_goal' THEN 'NHL Shots on Goal'
             WHEN 'nhl_prop_assists' THEN 'NHL Assists'
             WHEN 'ncaaf_spread' THEN 'NCAAF Spreads'
             WHEN 'ncaaf_spread_premium' THEN 'NCAAF Premium Spreads'
             WHEN 'ncaaf_live_win_prob' THEN 'NCAAF Live Moneyline'
             WHEN 'ncaaf_live_total' THEN 'NCAAF Live Totals'
             WHEN 'ncaaf_moneyline' THEN 'NCAAF Moneyline'
             WHEN 'ncaaf_over_under' THEN 'NCAAF Totals'
             WHEN 'ncaab_total_blend' THEN 'NCAAB Totals'
             WHEN 'ncaab_spread_market' THEN 'NCAAB Spreads'
             WHEN 'ncaab_moneyline_own_spread' THEN 'NCAAB Moneyline'
             WHEN 'ncaab_moneyline_first_post' THEN 'NCAAB Opening Moneyline'
             WHEN 'ncaab_first_half_spread' THEN 'NCAAB First Half Spreads'
             WHEN 'ncaab_first_half_total' THEN 'NCAAB First Half Totals'
             WHEN 'ncaabw_total_blend' THEN 'NCAABW Totals'
             WHEN 'ncaabw_live_total_ht' THEN 'NCAABW Live Totals'
             WHEN 'nfl_wind_totals' THEN 'NFL Totals'
             WHEN 'nfl_opener_spread' THEN 'NFL Spreads'
             WHEN 'nfl_prop_market' THEN 'NFL Props'
             WHEN 'nfl_live_leader_ml' THEN 'NFL Live Moneyline'
             WHEN 'nfl_live_prop' THEN 'NFL Live Rush Attempts'
             WHEN 'nfl_prop_pass_yards' THEN 'NFL Passing Yards'
             WHEN 'nfl_prop_pass_attempts' THEN 'NFL Pass Attempts'
             WHEN 'nfl_prop_pass_completions' THEN 'NFL Pass Completions'
             WHEN 'nfl_prop_pass_tds' THEN 'NFL Passing Touchdowns'
             WHEN 'nfl_prop_rush_yards' THEN 'NFL Rushing Yards'
             WHEN 'nfl_prop_rush_attempts' THEN 'NFL Rush Attempts'
             WHEN 'nfl_prop_rec_yards' THEN 'NFL Receiving Yards'
             WHEN 'nfl_prop_receptions' THEN 'NFL Receptions'
             WHEN 'nfl_prop_rush_rec_yards' THEN 'NFL Rush + Receiving Yards'
             WHEN 'nfl_prop_anytime_td' THEN 'NFL Anytime TD'
             WHEN 'nfl_prop_tackles_assists' THEN 'NFL Tackles + Assists'
             WHEN 'nfl_prop_sacks' THEN 'NFL Sacks'
             WHEN 'golf_outright' THEN 'Golf Outright'
             WHEN 'golf_top10' THEN 'Golf Top 10'
             WHEN 'golf_top20' THEN 'Golf Top 20'
             WHEN 'golf_make_cut' THEN 'Golf Make Cut'
             WHEN 'golf_matchup' THEN 'Golf Matchups'
             ELSE p.model_id
           END AS model,
           -- When the pick was decided: created_at is when the number existed.
           to_char(p.created_at::timestamptz AT TIME ZONE 'America/New_York',
                   'YYYY-MM-DD FMHH12:MI AM') || ' ET' AS decided_at_et,
           p.pick_id AS pick_id,
           p.model_id AS model_id
    FROM public.picks p
    JOIN public.model_action_thresholds t ON t.model_id = p.model_id
    LEFT JOIN public.games g ON g.game_id = p.game_id
    CROSS JOIN LATERAL public.published_pick_stake(COALESCE(p.decision_odds, p.dk_odds)) s
    CROSS JOIN LATERAL (
      SELECT COALESCE(NULLIF(p.decision_book, ''),
                      CASE WHEN p.dk_odds IS NOT NULL THEN 'draftkings' END) AS book_key
    ) b
    WHERE p.signal_type = 'BET'
      -- Open: not graded. A VOID is result NO_ACTION, so it is out here too.
      AND p.result IS NULL
      -- Pre-game only. In-play picks have their own boards and channels.
      AND (p.is_live IS NULL OR p.is_live = FALSE)
      AND p.model_id NOT LIKE '%\_live\_%'
      -- The game has not started. No date horizon (CLAUDE.md 1b): a pick is
      -- open however far ahead it was written. A game with no start time is
      -- bounded to today's Eastern date, as the Discord producer bounds it.
      AND (g.commence_time IS NULL
           OR g.commence_time::timestamptz > now())
      AND (g.commence_time IS NOT NULL
           OR p.game_date >= to_char(now() AT TIME ZONE 'America/New_York', 'YYYY-MM-DD'))
      -- Never a pick: voided, the second copy of one bet, or written while
      -- its model was paused (CLAUDE.md 1c).
      AND (p.condition_status IS NULL OR p.condition_status <> 'VOID')
      AND p.condition_status IS DISTINCT FROM 'DUPLICATE'
      AND p.downgrade_reason IS DISTINCT FROM 'model paused'
      -- A paused model is not offered, posted or not (passesActionFilter).
      -- A retired model has no row in the table, so the join drops it.
      AND t.paused = FALSE
      -- Discord has posted it: the app, Discord and push show the same picks
      -- (CLAUDE.md 1b), and the app shows a bet once the channel has it. The
      -- producer posted it only after it cleared its model's cut in
      -- model_action_thresholds at the decided price, and a posted bet keeps
      -- the cuts it was written under (passesActionFilter), so no cut is
      -- re-applied here. The pre-game lock key, as
      -- tracking/publish_keys.lock_key_sql mints it. v_discord_published
      -- already drops a lock that a newer void notice released.
      AND EXISTS (
        SELECT 1 FROM public.v_discord_published pub
        WHERE pub.lock_key = p.game_id || ':' || p.model_id
                 || COALESCE(':' || p.player_id, '')
                 || COALESCE(':' || p.player_key, '')
                 || COALESCE(':' || p.prop_market, '')
      )
    ORDER BY g.commence_time::timestamptz NULLS LAST, p.created_at, p.pick_id
$view$;
  EXECUTE $c$COMMENT ON VIEW public.open_picks IS 'open_picks 28e0bb477645'$c$;
  REVOKE ALL ON public.open_picks FROM anon, authenticated;
  GRANT SELECT ON public.open_picks TO anon, authenticated;
END $mig$;
