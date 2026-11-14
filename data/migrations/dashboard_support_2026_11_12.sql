-- Two things the ops dashboard reads (mike, 2026-11-12: "change the front end
-- names of the models to something more friendly ... allow savable layouts,
-- like the different sections are tiles that can be moved").
--
-- WHAT IT BUILDS
--   model_display_names   every model's name as the mobile app shows it:
--       model_id, name (MODEL_META longLabel), short_name (shortLabel),
--       sport, in_play. The VALUES list is written by
--       `python -m scripts.model_display_names` from mobile/src/lib/
--       modelMeta.ts; tests/test_dashboard_support.py fails while the two
--       disagree. Do not edit the list by hand.
--   dashboard_layouts     a person's saved arrangement of the dashboard's
--       tiles, one row per (owner, tab, name). owner is the signed-in
--       person's email, set by the dashboard's server code, never by the
--       page. layout is the tile list as the page wrote it.
--
-- Neither touches a pick, a cut, the record or the app. anon and
-- authenticated get nothing on either: the dashboard reads and writes as
-- the database owner through its own resource.
--
-- One DO block: data/view_migrations.py runs each file as one statement, on
-- every pass. It returns on a catalog read once the view carries this file's
-- marker (the hash of this file with the marker blanked), so an edit here,
-- such as a new model's name, is applied on the next pass.

DO $mig$
BEGIN
  IF to_regclass('public.model_display_names') IS NOT NULL
     AND COALESCE(obj_description(to_regclass('public.model_display_names'), 'pg_class'), '')
         = 'dashboard_support 039f0e55d8dc'
     AND to_regclass('public.dashboard_layouts') IS NOT NULL
     AND NOT has_table_privilege('anon', 'public.dashboard_layouts', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.dashboard_layouts', 'SELECT')
     AND NOT has_table_privilege('anon', 'public.model_display_names', 'SELECT')
     AND NOT has_table_privilege('authenticated', 'public.model_display_names', 'SELECT')
  THEN
    RETURN;
  END IF;

  -- 1. saved layouts
  CREATE TABLE IF NOT EXISTS public.dashboard_layouts (
    owner       TEXT NOT NULL,
    tab         TEXT NOT NULL,
    name        TEXT NOT NULL,
    layout      JSONB NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (owner, tab, name),
    CONSTRAINT dashboard_layouts_owner CHECK (btrim(owner) <> ''),
    CONSTRAINT dashboard_layouts_tab CHECK (tab IN ('models', 'volume', 'ops', 'picks')),
    CONSTRAINT dashboard_layouts_name CHECK (btrim(name) <> '' AND length(name) <= 60),
    CONSTRAINT dashboard_layouts_shape CHECK (jsonb_typeof(layout) IN ('array', 'object'))
  );
  ALTER TABLE public.dashboard_layouts ENABLE ROW LEVEL SECURITY;
  REVOKE ALL ON public.dashboard_layouts FROM anon, authenticated;

  -- 2. the app's names
  EXECUTE $view$
    CREATE OR REPLACE VIEW public.model_display_names
    WITH (security_invoker = on) AS
    SELECT n.model_id,
           n.name,
           n.short_name,
           upper(split_part(n.model_id, '_', 1)) AS sport,
           (n.model_id LIKE '%\_live\_%') AS in_play
      FROM (VALUES
        -- names:begin
        ('euroleague_live_spread_ht', 'EuroLeague Halftime Spread', 'LIVE Spread'),
        ('golf_make_cut', 'Golf Make Cut', 'Cut'),
        ('golf_matchup', 'Golf Matchups', 'H2H'),
        ('golf_outright', 'Golf Outright', 'Win'),
        ('golf_top10', 'Golf Top 10', 'T10'),
        ('golf_top20', 'Golf Top 20', 'T20'),
        ('mlb_f5_moneyline', 'MLB First 5 Moneyline', 'F5 ML'),
        ('mlb_f5_over_under', 'MLB First 5 Totals', 'F5 O/U'),
        ('mlb_f5_runline', 'MLB First 5 Spreads', 'F5 Spread'),
        ('mlb_live_runline', 'MLB Live Spreads', 'LIVE Spread'),
        ('mlb_live_total_runs', 'MLB Live Totals', 'LIVE O/U'),
        ('mlb_live_win_prob', 'MLB Live Moneyline', 'LIVE ML'),
        ('mlb_moneyline', 'MLB Moneyline', 'ML'),
        ('mlb_over_under', 'MLB Totals', 'O/U'),
        ('mlb_prop_batter_hits', 'MLB Hits', 'B H'),
        ('mlb_prop_batter_hr', 'MLB Home Runs', 'B HR'),
        ('mlb_prop_batter_rbi', 'MLB RBIs', 'B RBI'),
        ('mlb_prop_batter_runs', 'MLB Runs Scored', 'B R'),
        ('mlb_prop_batter_sb', 'MLB Stolen Bases', 'B SB'),
        ('mlb_prop_batter_tb', 'MLB Total Bases', 'B TB'),
        ('mlb_prop_batter_walks', 'MLB Batter Walks', 'B BB'),
        ('mlb_prop_pitcher_er', 'MLB Earned Runs', 'P ER'),
        ('mlb_prop_pitcher_hits', 'MLB Hits Allowed', 'P H'),
        ('mlb_prop_pitcher_k', 'MLB Pitcher Strikeouts', 'P K'),
        ('mlb_prop_pitcher_outs', 'MLB Pitcher Outs', 'P Outs'),
        ('mlb_prop_pitcher_walks', 'MLB Pitcher Walks', 'P BB'),
        ('mlb_runline', 'MLB Spreads', 'Spread'),
        ('mlb_spread_market', 'MLB Spreads', 'Spread'),
        ('mlb_total_market', 'MLB Totals', 'O/U'),
        ('mlb_total_public_fade', 'MLB Totals Fade', 'Fade'),
        ('nba_first_half_total_luck', 'NBA First Half Totals', '1H O/U'),
        ('nba_live_spread_q12', 'NBA Early Live Spreads', 'Early Spread'),
        ('nba_moneyline', 'NBA Moneyline', 'ML'),
        ('nba_over_under', 'NBA Totals', 'O/U'),
        ('nba_prop_market', 'NBA Props', 'Props'),
        ('nba_prop_player_assists', 'NBA Assists', 'AST'),
        ('nba_prop_player_blocks', 'NBA Blocks', 'BLK'),
        ('nba_prop_player_dd', 'NBA Double-Double', 'DD'),
        ('nba_prop_player_points', 'NBA Points', 'PTS'),
        ('nba_prop_player_pra', 'NBA Pts + Reb + Ast', 'PRA'),
        ('nba_prop_player_rebounds', 'NBA Rebounds', 'REB'),
        ('nba_prop_player_steals', 'NBA Steals', 'STL'),
        ('nba_prop_player_threes', 'NBA Threes', '3PM'),
        ('nba_prop_player_turnovers', 'NBA Turnovers', 'TO'),
        ('nba_prop_projection', 'NBA Projected Props', 'Projected'),
        ('nba_q1_trend', 'NBA First Quarter Spreads', '1Q Spread'),
        ('nba_q1_trend_ml', 'NBA First Quarter Moneyline', '1Q ML'),
        ('nba_spread', 'NBA Spreads', 'Spread'),
        ('nba_team_total_luck', 'NBA Team Totals', 'TT'),
        ('nba_total_luck', 'NBA Totals', 'O/U'),
        ('ncaab_first_half_spread', 'NCAAB First Half Spreads', '1H Spread'),
        ('ncaab_first_half_total', 'NCAAB First Half Totals', '1H O/U'),
        ('ncaab_live_spread_h1', 'NCAAB Early Live Spreads', 'Early Spread'),
        ('ncaab_live_spread_h2', 'NCAAB Late Live Spreads', 'Late Spread'),
        ('ncaab_live_total_h2', 'NCAAB Late Live Totals', 'Late O/U'),
        ('ncaab_moneyline_first_post', 'NCAAB Opening Moneyline', 'Open ML'),
        ('ncaab_moneyline_own_spread', 'NCAAB Moneyline', 'ML'),
        ('ncaab_spread_market', 'NCAAB Spreads', 'Spread'),
        ('ncaab_total_blend', 'NCAAB Totals', 'O/U'),
        ('ncaabw_live_total_ht', 'NCAABW Live Totals', 'LIVE O/U'),
        ('ncaabw_total_blend', 'NCAABW Totals', 'O/U'),
        ('ncaaf_live_total', 'NCAAF Live Totals', 'LIVE O/U'),
        ('ncaaf_live_win_prob', 'NCAAF Live Moneyline', 'LIVE ML'),
        ('ncaaf_moneyline', 'NCAAF Moneyline', 'ML'),
        ('ncaaf_moneyline_market', 'NCAAF Moneyline', 'ML'),
        ('ncaaf_over_under', 'NCAAF Totals', 'O/U'),
        ('ncaaf_spread', 'NCAAF Spreads', 'Spread'),
        ('ncaaf_spread_premium', 'NCAAF Premium Spreads', 'Premium'),
        ('nfl_live_leader_ml', 'NFL Live Moneyline', 'LIVE ML'),
        ('nfl_live_prop', 'NFL Live Rush Attempts', 'LIVE Carries'),
        ('nfl_opener_spread', 'NFL Spreads', 'Spread'),
        ('nfl_prop_anytime_td', 'NFL Anytime TD', 'Anytime TD'),
        ('nfl_prop_market', 'NFL Props', 'Props'),
        ('nfl_prop_pass_attempts', 'NFL Pass Attempts', 'Pass Att'),
        ('nfl_prop_pass_completions', 'NFL Pass Completions', 'Pass Comp'),
        ('nfl_prop_pass_tds', 'NFL Passing Touchdowns', 'Pass TD'),
        ('nfl_prop_pass_yards', 'NFL Passing Yards', 'Pass Yds'),
        ('nfl_prop_rec_yards', 'NFL Receiving Yards', 'Rec Yds'),
        ('nfl_prop_receptions', 'NFL Receptions', 'Recs'),
        ('nfl_prop_rush_attempts', 'NFL Rush Attempts', 'Rush Att'),
        ('nfl_prop_rush_rec_yards', 'NFL Rush + Receiving Yards', 'Ru+Re Yds'),
        ('nfl_prop_rush_yards', 'NFL Rushing Yards', 'Rush Yds'),
        ('nfl_prop_sacks', 'NFL Sacks', 'Sacks'),
        ('nfl_prop_tackles_assists', 'NFL Tackles + Assists', 'Tkl+Ast'),
        ('nfl_wind_totals', 'NFL Totals', 'O/U'),
        ('nhl_moneyline', 'NHL Moneyline', 'ML'),
        ('nhl_moneyline_regulation', 'NHL 3-Way Moneyline', '3-Way'),
        ('nhl_over_under', 'NHL Totals', 'O/U'),
        ('nhl_prop_assists', 'NHL Assists', 'AST'),
        ('nhl_prop_blocked_shots', 'NHL Blocked Shots', 'BLK'),
        ('nhl_prop_saves', 'NHL Saves', 'SV'),
        ('nhl_prop_shots_on_goal', 'NHL Shots on Goal', 'SOG'),
        ('nhl_puckline', 'NHL Spreads', 'Spread'),
        ('ufc_method_of_victory', 'UFC Method of Victory', 'Method'),
        ('ufc_moneyline', 'UFC Moneyline', 'ML'),
        ('ufc_total_rounds', 'UFC Totals', 'O/U'),
        ('wnba_moneyline', 'WNBA Moneyline', 'ML'),
        ('wnba_over_under', 'WNBA Totals', 'O/U'),
        ('wnba_prop_market', 'WNBA Props', 'Props'),
        ('wnba_prop_player_assists', 'WNBA Assists', 'AST'),
        ('wnba_prop_player_points', 'WNBA Points', 'PTS'),
        ('wnba_prop_player_pra', 'WNBA Pts + Reb + Ast', 'PRA'),
        ('wnba_prop_player_rebounds', 'WNBA Rebounds', 'REB'),
        ('wnba_prop_player_threes', 'WNBA Threes', '3PM'),
        ('wnba_spread', 'WNBA Spreads', 'Spread')
        -- names:end
      ) AS n(model_id, name, short_name)
  $view$;
  EXECUTE $c$COMMENT ON VIEW public.model_display_names IS 'dashboard_support 039f0e55d8dc'$c$;
  REVOKE ALL ON public.model_display_names FROM anon, authenticated;
END $mig$;
