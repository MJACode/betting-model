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
  DayDetail: { date: string };
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
  MyBets: undefined;
  Performance: undefined;
  Models: undefined;
  Stats: undefined;
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
