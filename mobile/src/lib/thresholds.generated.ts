/**
 * GENERATED FILE — do not edit by hand.
 * Source of truth: config.py (ACTION_THRESHOLDS, PAUSED_MODELS,
 * PROB_ONLY_MODELS, RETIRED_MODELS, KELLY_*).
 * Regenerate: python -m scripts.generate_mobile_thresholds
 * Check (CI):  python -m scripts.generate_mobile_thresholds --check
 * Last generated: 2026-09-15
 */

export interface ModelThreshold {
  min_prob: number;
  min_edge: number;
  min_odds: number | null;
}

export const ACTION_THRESHOLDS: Record<string, ModelThreshold> = {
  mlb_f5_moneyline: { min_prob: 0.58, min_edge: 0.02, min_odds: -200 },
  mlb_f5_over_under: { min_prob: 0.65, min_edge: 0.15, min_odds: -200 },
  mlb_f5_runline: { min_prob: 0.65, min_edge: 0.15, min_odds: -200 },
  mlb_live_total_runs: { min_prob: 0.72, min_edge: 0.14, min_odds: -200 },
  mlb_moneyline: { min_prob: 0.72, min_edge: 0.11, min_odds: -200 },
  mlb_over_under: { min_prob: 0.5, min_edge: 0.04, min_odds: -200 },
  mlb_prop_batter_hits: { min_prob: 0.78, min_edge: 0.17, min_odds: -140 },
  mlb_prop_batter_runs: { min_prob: 0.62, min_edge: 0.1, min_odds: -140 },
  mlb_prop_batter_sb: { min_prob: 0.18, min_edge: 0.1, min_odds: -140 },
  mlb_prop_batter_tb: { min_prob: 0.83, min_edge: 0.17, min_odds: -140 },
  mlb_prop_batter_walks: { min_prob: 0.45, min_edge: 0.14, min_odds: -140 },
  mlb_prop_pitcher_er: { min_prob: 0.61, min_edge: 0.08, min_odds: -140 },
  mlb_prop_pitcher_hits: { min_prob: 0.54, min_edge: 0.08, min_odds: -140 },
  mlb_prop_pitcher_k: { min_prob: 0.58, min_edge: 0.08, min_odds: -140 },
  mlb_prop_pitcher_outs: { min_prob: 0.5, min_edge: 0.12, min_odds: -140 },
  mlb_prop_pitcher_walks: { min_prob: 0.6, min_edge: 0.08, min_odds: -140 },
  mlb_runline: { min_prob: 0.68, min_edge: 0.11, min_odds: -200 },
  mlb_spread_market: { min_prob: 0, min_edge: 0.018, min_odds: -200 },
  nba_moneyline: { min_prob: 0.66, min_edge: 0.12, min_odds: -200 },
  nba_over_under: { min_prob: 0.66, min_edge: 0.12, min_odds: -200 },
  nba_prop_player_assists: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_prop_player_blocks: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_prop_player_dd: { min_prob: 0.55, min_edge: 0, min_odds: -200 },
  nba_prop_player_points: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_prop_player_pra: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_prop_player_rebounds: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_prop_player_steals: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_prop_player_threes: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_prop_player_turnovers: { min_prob: 0.6, min_edge: 0.08, min_odds: -200 },
  nba_spread: { min_prob: 0.66, min_edge: 0.12, min_odds: -200 },
  ncaaf_live_total: { min_prob: 0.73, min_edge: 0.12, min_odds: -200 },
  ncaaf_live_win_prob: { min_prob: 0.65, min_edge: 0.1, min_odds: -200 },
  ncaaf_moneyline: { min_prob: 0.62, min_edge: 0.08, min_odds: -250 },
  ncaaf_over_under: { min_prob: 0.65, min_edge: 0, min_odds: -200 },
  ncaaf_spread: { min_prob: 0.55, min_edge: 0, min_odds: -200 },
  ncaaf_spread_premium: { min_prob: 0.58, min_edge: 0, min_odds: -200 },
  nfl_live_prop: { min_prob: 0, min_edge: 0, min_odds: -140 },
  nfl_opener_spread: { min_prob: 0.55, min_edge: 0, min_odds: -200 },
  nfl_prop_anytime_td: { min_prob: 0.37, min_edge: 0.16, min_odds: -200 },
  nfl_prop_market: { min_prob: 0, min_edge: 0.05, min_odds: -200 },
  nfl_prop_pass_attempts: { min_prob: 0.73, min_edge: 0.19, min_odds: -200 },
  nfl_prop_pass_completions: { min_prob: 0.68, min_edge: 0.16, min_odds: -200 },
  nfl_prop_pass_tds: { min_prob: 0.78, min_edge: 0.17, min_odds: -200 },
  nfl_prop_pass_yards: { min_prob: 0.68, min_edge: 0.15, min_odds: -200 },
  nfl_prop_rec_yards: { min_prob: 0.69, min_edge: 0.16, min_odds: -200 },
  nfl_prop_receptions: { min_prob: 0.63, min_edge: 0.16, min_odds: -200 },
  nfl_prop_rush_attempts: { min_prob: 0.76, min_edge: 0.2, min_odds: -200 },
  nfl_prop_rush_rec_yards: { min_prob: 0.68, min_edge: 0.15, min_odds: -200 },
  nfl_prop_rush_yards: { min_prob: 0.71, min_edge: 0.19, min_odds: -200 },
  nfl_prop_sacks: { min_prob: 0.7, min_edge: 0.15, min_odds: -200 },
  nfl_prop_tackles_assists: { min_prob: 0.7, min_edge: 0.15, min_odds: -200 },
  nfl_wind_totals: { min_prob: 0.52, min_edge: 0.03, min_odds: -200 },
  nhl_moneyline: { min_prob: 0.55, min_edge: 0.05, min_odds: -200 },
  nhl_moneyline_regulation: { min_prob: 0.4, min_edge: 0.05, min_odds: -200 },
  nhl_over_under: { min_prob: 0.55, min_edge: 0.05, min_odds: -200 },
  nhl_puckline: { min_prob: 0.55, min_edge: 0.05, min_odds: -200 },
  ufc_method_of_victory: { min_prob: 0.65, min_edge: 0, min_odds: -200 },
  ufc_moneyline: { min_prob: 0.65, min_edge: 0.08, min_odds: -200 },
  ufc_total_rounds: { min_prob: 0.62, min_edge: 0.08, min_odds: -200 },
  wnba_moneyline: { min_prob: 0.5, min_edge: 0.06, min_odds: -200 },
  wnba_over_under: { min_prob: 0.6, min_edge: 0.06, min_odds: -200 },
  wnba_prop_market: { min_prob: 0, min_edge: 0.05, min_odds: -140 },
  wnba_prop_player_assists: { min_prob: 0.5, min_edge: 0.1, min_odds: -140 },
  wnba_prop_player_points: { min_prob: 0.58, min_edge: 0.17, min_odds: -140 },
  wnba_prop_player_pra: { min_prob: 0.68, min_edge: 0.16, min_odds: -140 },
  wnba_prop_player_rebounds: { min_prob: 0.62, min_edge: 0, min_odds: -140 },
  wnba_prop_player_threes: { min_prob: 0.706, min_edge: 0.026, min_odds: -140 },
  wnba_spread: { min_prob: 0.6, min_edge: 0.1, min_odds: -200 },
};

export const PROB_ONLY_MODELS = new Set<string>([
  'nba_prop_player_dd',
  'ufc_method_of_victory',
]);

export const RETIRED_PROB_ONLY_MODELS = new Set<string>([
  'mlb_prop_batter_hr',
]);

export const PAUSED_MODELS = new Set<string>([
  'mlb_f5_over_under',
  'mlb_f5_runline',
  'mlb_over_under',
  'mlb_prop_batter_hits',
  'mlb_prop_batter_sb',
  'mlb_prop_batter_tb',
  'mlb_prop_pitcher_er',
  'mlb_prop_pitcher_walks',
  'mlb_runline',
  'ncaaf_moneyline',
  'nfl_prop_anytime_td',
  'nfl_prop_pass_attempts',
  'nfl_prop_pass_completions',
  'nfl_prop_pass_tds',
  'nfl_prop_pass_yards',
  'nfl_prop_rec_yards',
  'nfl_prop_receptions',
  'nfl_prop_rush_attempts',
  'nfl_prop_rush_rec_yards',
  'nfl_prop_rush_yards',
  'nfl_prop_sacks',
  'ufc_total_rounds',
  'wnba_over_under',
  'wnba_prop_player_points',
  'wnba_prop_player_threes',
  'wnba_spread',
]);

export const RETIRED_MODELS = new Set<string>([
  'golf_make_cut',
  'golf_matchup',
  'golf_outright',
  'golf_top10',
  'golf_top20',
  'mlb_live_runline',
  'mlb_live_win_prob',
  'mlb_prop_batter_hr',
  'mlb_prop_batter_rbi',
]);

export const KELLY_MULTIPLIER = 0.1;
export const MAX_KELLY_FRACTION = 0.05;
