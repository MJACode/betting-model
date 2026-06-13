export type SignalType = 'BET' | 'AVOID' | 'NONE';
export type ConfidenceTier = 'HIGH' | 'MED' | 'LOW' | null;
export type PickSide = 'home' | 'away' | 'over' | 'under' | 'draw';
export type PickResult = 'WIN' | 'LOSS' | 'PUSH' | 'NO_ACTION' | null;
export type PlayerType = 'pitcher' | 'batter';

export interface Pick {
  pick_id: number;
  game_id: string;
  model_id: string;
  sport: string;
  game_date: string;
  pick_side: PickSide;
  pick_label: string;
  model_probability: number;
  dk_implied_prob: number;
  edge: number;
  dk_odds: number | null;
  scored_line: number | null;
  kelly_fraction: number;
  recommended_bet: number;
  bankroll_at_pick: number;
  injury_flag: string | null;
  injury_detail: string | null;
  signal_type: SignalType;
  confidence_tier: ConfidenceTier;
  result: PickResult;
  profit_flat: number | null;
  profit_kelly: number | null;
  settled_at: string | null;
  created_at: string;
  player_id: string | null;
  pitcher_throw_hand: string | null;
  // Public betting splits (Action Network). NULL on F5/prop picks and any
  // full-game pick where splits weren't available at score time.
  public_bet_pct: number | null;
  public_money_pct: number | null;
  // Closing line value (CLV) — captured at settlement from the last pre-game DK
  // snapshot on the pick side. NULL until settled / for prop picks.
  closing_dk_odds: number | null;
  closing_line: number | null;
  clv_pct: number | null; // closing_implied_prob - bet_implied_prob, in pp (positive = beat the close)
  clv_captured_at: string | null;
  // Live (in-play) betting — Phase 1 scaffolding. NULL on all pre-game picks.
  is_live: boolean | null;
  inning_at_pick: number | null;
  score_diff_at_pick: number | null;
  // DraftKings betslip deep link for the pick side (The Odds API). NULL when DK
  // didn't supply a link for that market (prob-only picks, unsupported markets).
  dk_bet_link: string | null;
}

export interface LiveGameState {
  game_id: string;
  snapshot_at: string;
  inning: number | null;
  inning_half: 'top' | 'bottom' | null;
  outs: number | null;
  bases_state: string | null;          // '000' .. '111'
  home_score: number | null;
  away_score: number | null;
  abstract_game_state: 'Preview' | 'Live' | 'Final' | null;
}

export interface GameRow {
  game_id: string;
  sport: string;
  season: number;
  game_date: string;
  home_team: string;
  away_team: string;
  home_score: number | null;
  away_score: number | null;
  home_score_f5: number | null;
  away_score_f5: number | null;
  commence_time: string;
  home_win: number | null;
  home_win_reg: number | null;
  went_to_ot: number;
}

export interface GameWeather {
  game_id: string;
  game_date: string;
  home_team: string;
  venue: string | null;
  temp_f: number | null;
  wind_mph: number | null;
  wind_dir_deg: number | null;
  wind_out_component: number | null;
  precip_mm: number | null;
  is_dome_game: number | null;
}

export interface PlayerGameLogRow {
  player_id: string;
  player_name: string;
  team: string;
  player_type: PlayerType;
  game_id: string;
  game_date: string;
  season: number;
  innings_pitched: number | null;
  p_strikeouts: number | null;
  p_walks: number | null;
  p_hits_allowed: number | null;
  p_earned_runs: number | null;
  p_home_runs: number | null;
  at_bats: number | null;
  hits: number | null;
  doubles: number | null;
  triples: number | null;
  home_runs: number | null;
  rbi: number | null;
  runs: number | null;
  walks: number | null;
  strikeouts: number | null;
  stolen_bases: number | null;
  total_bases: number | null;
  batting_order: number | null;
}

export interface EnrichedPick {
  pick: Pick;
  game: GameRow | null;
  weather: GameWeather | null;
  /** Latest DK snapshot for this pick's market (v_latest_dk_odds). Used for the
   * line-movement chip. Null for prop/prob-only picks or when no odds today. */
  latestOdds?: LatestDkOddsRow | null;
}

/** One row from v_latest_dk_odds — the freshest DK snapshot per game+market. */
export interface LatestDkOddsRow {
  game_id: string;
  game_date: string;
  market: string;
  home_price: number | null;
  away_price: number | null;
  spread_home: number | null;
  total_line: number | null;
  over_price: number | null;
  under_price: number | null;
  snapshot_at: string;
}

/** One snapshot from the odds table (game markets, DK only). */
export interface OddsSnapshotRow {
  market: string;
  snapshot_at: string;
  home_price: number | null;
  away_price: number | null;
  spread_home: number | null;
  total_line: number | null;
  over_price: number | null;
  under_price: number | null;
}

/** One snapshot from player_prop_odds for a player+market. */
export interface PropOddsSnapshotRow {
  snapshot_at: string;
  line: number | null;
  over_price: number | null;
  under_price: number | null;
}

/** Season-level Statcast metrics (player_savant_stats). */
export interface SavantStatsRow {
  player_id: string;
  player_type: PlayerType;
  season: number;
  // pitcher
  k_pct: number | null;
  whiff_pct: number | null;
  csw_pct: number | null;
  xera: number | null;
  avg_velocity: number | null;
  gb_pct: number | null;
  // batter
  barrel_pct: number | null;
  hard_hit_pct: number | null;
  xba: number | null;
  xslg: number | null;
  launch_angle: number | null;
  sprint_speed: number | null;
}

export interface UmpireRow {
  umpire_name: string;
  k_per_game: number | null;
  k_plus_minus: number | null;
}

export interface LineupSlotRow {
  batting_order: number | null;
  position: string | null;
  hand: string | null;
  is_confirmed: boolean | null;
}

export interface ModelRegistryRow {
  model_id: string;
  version: string;
  trained_on: string;
  holdout_season: number | null;
  holdout_accuracy: number | null;
  holdout_roi: number | null;
  holdout_picks: number | null;
  calibration_score: number | null;
}

/** Fighter profile (UFC tale of the tape). */
export interface FighterRow {
  fighter_id: string;
  name: string;
  height_in: number | null;
  reach_in: number | null;
  stance: string | null;
  dob: string | null;
}

/** One fight from ufc_fight_log (per-fighter perspective). */
export interface FightLogRow {
  game_id: string;
  game_date: string;
  result: string | null; // 'win' | 'loss' | 'draw' | 'nc'
  method: string | null; // 'decision' | 'ko_tko' | 'submission' | 'dq' | 'other'
  end_round: number | null;
}

export interface TeamGameStat {
  game_id: string;
  game_date: string;
  is_home: boolean;
  won: boolean | null;
  runs_for: number | null;
  runs_against: number | null;
  opponent: string;
}

export interface TrendBuckets {
  l3: TrendValue;
  l5: TrendValue;
  l10: TrendValue;
  l20: TrendValue;
  season: TrendValue;
}

export interface TrendValue {
  avg: number | null;
  winPct: number | null;
  games: number;
}

export type RootStackParamList = {
  Tabs: undefined;
  PickDetail: { pickId: number };
  ModelEdit: { modelId?: string };
  ModelDetail: { modelId: string };
  BuiltInModelDetail: { modelId: string };
  PlayerStats: { playerId: string; playerName: string; playerType: PlayerType };
  Explainer: undefined;
  ConnectSportsbook: undefined;
};

export type TabParamList = {
  Picks: undefined;
  Signals: undefined;
  Parlay: undefined;
  Live: undefined;
  Performance: undefined;
  Models: undefined;
  // fromParlay: user came from the Parlay tab's "Build your own" mode to find a
  // leg — adding a player returns them to the Parlay tab automatically.
  Stats: { fromParlay?: boolean } | undefined;
  Settings: undefined;
};

export interface CustomModelRule {
  model_id: string;
  min_prob: number;
  min_edge: number;
}

export interface CustomModel {
  id: string;
  name: string;
  rules: CustomModelRule[];
  created_at: string;
  updated_at: string;
}

/**
 * One row from v_player_season_totals_mlb or v_player_season_totals_wnba —
 * season totals per player. All stat columns optional since MLB and WNBA
 * expose different sets (and MLB splits batter vs pitcher columns).
 */
export interface SeasonTotalsRow {
  player_id: string;
  player_name: string;
  team: string | null;
  season: number;
  games_played: number;
  player_type?: PlayerType; // MLB only
  // MLB batting
  at_bats?: number;
  hits?: number;
  doubles?: number;
  triples?: number;
  home_runs?: number;
  total_bases?: number;
  rbi?: number;
  runs?: number;
  walks?: number;
  strikeouts?: number;
  stolen_bases?: number;
  // MLB pitching
  p_strikeouts?: number;
  p_walks?: number;
  p_hits_allowed?: number;
  p_earned_runs?: number;
  p_home_runs?: number;
  innings_pitched?: number;
  pitches?: number;
  // WNBA
  points?: number;
  rebounds?: number;
  assists?: number;
  threes?: number;
  steals?: number;
  blocks?: number;
  turnovers?: number;
  minutes?: number;
  pra?: number;
  // UFC (fighter leaderboard — games_played = fights; team = weight class)
  wins?: number;
  ko_wins?: number;
  sub_wins?: number;
  sig_strikes?: number;
  takedowns?: number;
  knockdowns?: number;
  sub_attempts?: number;
}
