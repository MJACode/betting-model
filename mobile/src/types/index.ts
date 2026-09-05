import type { NavigatorScreenParams } from '@react-navigation/native';
import type { PlayerLogSport } from '@/lib/playerLog';

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
  /** Scheduled first pitch / tip-off (ISO, UTC). Stamped by the scorer; ~100%
   *  populated. Powers the custom-model time-of-day filter with no games join. */
  game_time: string | null;
  pick_side: PickSide;
  pick_label: string;
  model_probability: number;
  /** What that probability has actually been WORTH, mapped from the model's own
   *  graded record (models/probability_calibration.py). Null where no map
   *  applies — either the model is well calibrated, has too few graded picks,
   *  or its gap was not stable enough to map honestly. DISPLAY ONLY: `edge`,
   *  the signal and every threshold still run on model_probability. */
  model_probability_cal?: number | null;
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
  // snapshot on the pick side. NULL until the game has started and settled.
  closing_dk_odds: number | null;
  closing_line: number | null;
  // Price CLV, in pp: closing_implied_prob - bet_implied_prob (positive = beat
  // the close). SAME-LINE ONLY — NULL when the number moved, because two prices
  // on different numbers are two different bets, not a comparison.
  clv_pct: number | null;
  // Line CLV, in points: how far the number moved toward our side between the
  // signal and the close (positive = we beat the close on the number). This is
  // the measure that survives a moved line. NULL for moneyline, which has none.
  line_clv_pts: number | null;
  // The one verdict, from whichever of the two applies: line_clv_pts > 0 where
  // the number moved, clv_pct > 0 where it held.
  clv_beat_close: boolean | null;
  clv_captured_at: string | null;
  // Live (in-play) betting — Phase 1 scaffolding. NULL on all pre-game picks.
  is_live: boolean | null;
  inning_at_pick: number | null;
  score_diff_at_pick: number | null;
  // DraftKings betslip deep link for the pick side (The Odds API). NULL when DK
  // didn't supply a link for that market (prob-only picks, unsupported markets).
  dk_bet_link: string | null;
  // Best price we found across every book the odds feed carries, and where.
  // DISPLAY + BET only: `edge`, the BET/AVOID call, the Kelly stake and the
  // settled P&L all still measure against DraftKings, so the pick set stays
  // identical to the calibrated thresholds. `best_edge` shows the true EV of
  // the bet actually placed. NULL on picks scored before 2026-08-28, on
  // prob-only markets, and anywhere the feed carries a single book (golf).
  best_book: string | null;
  best_odds: number | null;
  best_implied_prob: number | null;
  best_edge: number | null;
  best_bet_link: string | null;
}

/**
 * The subset of a settled pick the model screens actually read — custom-model
 * matching + filters, the built-in action filter, calibration, CLV, and the
 * pick rows rendered on model detail.
 *
 * Deliberately narrower than `Pick`: this set is fetched for every settled pick
 * since paper start and cached on device, so the columns we don't need are
 * payload and AsyncStorage budget we don't spend. Widen it only alongside a
 * bump of the cache key in settledPickCache.ts.
 */
export type SettledPickKey =
  | 'pick_id'
  | 'game_id'
  | 'model_id'
  | 'sport'
  | 'game_date'
  | 'game_time'
  | 'pick_side'
  | 'pick_label'
  | 'model_probability'
  | 'edge'
  | 'dk_odds'
  | 'scored_line'
  | 'signal_type'
  | 'confidence_tier'
  | 'result'
  | 'profit_flat'
  | 'player_id'
  | 'public_bet_pct'
  | 'injury_flag'
  | 'clv_pct';

// A mapped type rather than Pick<Pick, …> because the `Pick` interface above
// shadows TypeScript's built-in Pick<> utility inside this module. It stays
// derived from Pick, and adding a column to Pick does NOT silently join this
// set — which is the point, since the SELECT is hand-listed to match.
export type SettledPick = { [K in SettledPickKey]: Pick[K] };

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
   * line-movement chip. Null for prop/prop-only picks or when no odds today. */
  latestOdds?: LatestDkOddsRow | null;
  /** Best non-DK price for the pick side that beats DK (line shopping). Null when
   * DK is already the best price, or no other book prices the side. */
  bestOdds?: { bookmaker: string; price: number; link: string | null } | null;
  /** Every book's latest price for this pick's side — game markets from
   * v_latest_odds_all_books, props from v_latest_prop_odds_all_books. Powers the
   * betting-lines chips and the All books table. Empty when nothing is priced.
   * DISPLAY ONLY: the model's edge always comes from the DraftKings price. */
  bookRows?: BookPricedRow[];
}

/** One row from v_latest_odds_all_books — latest snapshot per game+market+book. */
export interface OddsByBookRow {
  game_id: string;
  game_date: string;
  market: string;
  bookmaker: string;
  home_price: number | null;
  away_price: number | null;
  over_price: number | null;
  under_price: number | null;
  spread_home: number | null;
  total_line: number | null;
  home_link: string | null;
  away_link: string | null;
  over_link: string | null;
  under_link: string | null;
  snapshot_at: string;
}

/** One row from v_latest_prop_odds_all_books — latest prop line per
 *  game+market+player+book. Props became multi-book in the same session that
 *  took game markets to the US top 5. */
export interface PropOddsByBookRow {
  game_id: string;
  game_date: string;
  market: string;
  player_name: string;
  team: string | null;
  bookmaker: string;
  line: number | null;
  over_price: number | null;
  under_price: number | null;
  over_link: string | null;
  under_link: string | null;
  snapshot_at: string;
}

/**
 * Anything the book-price helpers can read: a per-book priced snapshot, game
 * market or prop. Both OddsByBookRow and PropOddsByBookRow satisfy it, so
 * priceForBook / allBookPrices work over either without branching.
 */
export type BookPricedRow = {
  bookmaker: string;
  home_price?: number | string | null;
  away_price?: number | string | null;
  over_price?: number | string | null;
  under_price?: number | string | null;
  spread_home?: number | string | null;
  total_line?: number | string | null;
  line?: number | string | null;
  home_link?: string | null;
  away_link?: string | null;
  over_link?: string | null;
  under_link?: string | null;
};

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

/**
 * One row from v_live_game_state_latest — the freshest in-play snapshot per
 * game, written every ~15s by the live poller. MLB only today (that's the only
 * sport the poller covers); other sports simply have no row.
 */
export interface LiveGameStateRow {
  game_id: string;
  game_date: string;
  snapshot_at: string;
  inning: number | null;
  /** 'top' | 'bottom' as written by the poller. */
  inning_half: string | null;
  outs: number | null;
  /** '000'..'111' — first/second/third base occupancy. */
  bases_state: string | null;
  home_score: number | null;
  away_score: number | null;
  /** 'Preview' | 'Live' | 'Final' straight from the MLB feed. */
  abstract_game_state: string | null;
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
  Tabs: NavigatorScreenParams<TabParamList> | undefined;
  PickDetail: { pickId: number };
  ModelEdit: { modelId?: string };
  ModelDetail: { modelId: string };
  BuiltInModelDetail: { modelId: string };
  // playerType is MLB-only (it picks batter vs pitcher chips); every other
  // sport's chips come from the sport alone.
  PlayerStats: {
    playerId: string;
    playerName: string;
    sport: PlayerLogSport;
    playerType?: PlayerType;
    // The user came from the Betslip screen to find a leg. Adding one here
    // bounces them straight back, the same round-trip the Stats tab ran before
    // its line pills became sportsbook links (2026-09-04).
    fromParlay?: boolean;
    /**
     * Tonight's matchup in full — "vs LAA · S. Gray 5.90 ERA (R)" — and the
     * letter the board graded it.
     *
     * Carried as params rather than refetched here: the Stats board already
     * holds both, and this screen would otherwise pull the whole matchup view
     * to print one line. Passed from the board ONLY, so a player opened from
     * anywhere else simply shows no matchup line.
     *
     * They exist because the MATCHUP column became a bare grade on 2026-09-05
     * and the FACT behind it had nowhere else to go — Matt's own alternative
     * on 2026-09-04 was "have it be in the player data when you click on a
     * record". Without this the ERA left the product for every sighted user.
     */
    matchupText?: string;
    matchupGrade?: string;
  };
  Explainer: undefined;
  ConnectSportsbook: undefined;
  // TrackRecord is a tab now, but it's kept here too so the existing
  // navigate('TrackRecord') callers (typed against RootStackParamList) still
  // resolve — at runtime React Navigation finds the tab.
  TrackRecord: undefined;
  // Live (in-play) is a bottom tab now, but kept here so navigate('Live')
  // callers typed against RootStackParamList still resolve (React Navigation
  // finds the tab at runtime).
  Live: undefined;
  OpeningComparison: undefined;
  // The betslip. A pushed screen rather than a tab: it's empty most of the
  // time, and the persistent betslip bar (components/BetslipBar) is what
  // advertises it — from every page — once the slip has something in it.
  Betslip: undefined;
  SavedParlays: undefined;
  // Sign-in. Registered so the screen typechecks and is one flag away from
  // reachable, but nothing navigates here while AUTH_ENABLED is false.
  SignIn: undefined;
  // Paywall. Same posture — unreachable while BILLING_ENABLED is false.
  Paywall: undefined;
  // Settings moved off the tab bar — now opened via the top-right gear.
  Settings: undefined;
  // In-app feedback: the composer + your past conversations, and one thread.
  Feedback: undefined;
  FeedbackThread: { threadId: number };
};

/** One row from v_opening_vs_live — game-level settled record per track. */
export interface OpeningVsLiveRow {
  track: 'opening' | 'live';
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  profit_flat: number;
  staked_flat: number;
  clv_settled: number;
  clv_beat: number;
  avg_clv_pct: number | null;
}

/** One row from v_opening_signal_slices — opening track sliced by line move / public side. */
export interface OpeningSliceRow {
  slice_kind: 'line_move' | 'public';
  slice_value: string;
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  profit_flat: number;
  staked_flat: number;
  avg_clv_pct: number | null;
}

/**
 * One row from v_public_track_record — every settled BET pick that meets the
 * CURRENT action criteria, since the live date (2026-09-01), aggregated
 * per (sport, model_id). Nothing cherry-picked; losing models included.
 */
export interface TrackRecordRow {
  sport: string;
  model_id: string;
  picks: number;          // settled W/L/P
  wins: number;
  losses: number;
  pushes: number;
  profit_flat: number;    // sum of profit_flat on $100 flat stakes
  staked_flat: number;    // 100 * picks
  clv_settled: number;    // settled picks with a captured CLV
  clv_beat: number;       // of those, how many beat the close (clv_pct > 0)
  avg_clv_pct: number | null;
  first_date: string;
  last_date: string;
}

/** One row from v_public_track_record_daily — daily settled totals (equity curve). */
export interface TrackRecordDailyRow {
  game_date: string;
  sport: string;
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  profit_flat: number;
  staked_flat: number;
}

/** One row from parlay_track_record — the daily canonical cross-game parlay. */
export interface ParlayTrackRow {
  parlay_key: string;
  sport: string;
  game_date: string;
  n_legs: number;
  leg_labels: string; // JSON array string of leg pick labels
  leg_keys: string; // JSON array string of leg lock_keys (game_id:model_id[:player_id])
  combined_american: number;
  model_prob: number;
  dk_implied_prob: number;
  edge: number;
  result: 'WIN' | 'LOSS' | 'PUSH' | null;
  profit_flat: number | null;
  settled_at: string | null;
}

export type TabParamList = {
  // Merged Picks home (Today | Signals | Movement) replaces the old Picks +
  // Signals tabs. Live (in-play) is promoted to its own tab; Settings moved off
  // the tab bar to a top-right gear.
  Picks: undefined;
  Live: undefined;
  TrackRecord: undefined;
  Performance: undefined;
  Models: undefined;
  // fromParlay: user came from the Betslip screen's "Your slip" mode to find a
  // leg — adding a player returns them to the Betslip screen automatically.
  Stats: { fromParlay?: boolean } | undefined;
};

export interface CustomModelRule {
  /**
   * The bet type this rule matches. Exactly one model prices each market, so
   * the market IS the model_id under the hood — the builder shows it as a bet
   * type ("Moneyline", "Batter Hits"), never as a pickable in-house model.
   */
  model_id: string;
  /**
   * Minimum model probability (0.6 = 60%). Absent/null = no floor ("Any").
   * The builder starts every field blank rather than seeding the in-house cut,
   * so a saved number is always one the user chose. Models saved before
   * 2026-08-30 always carry both floors.
   */
  min_prob?: number | null;
  /** Minimum edge over the DK implied probability. Absent/null = no floor. */
  min_edge?: number | null;
  /**
   * Minimum EV per $1 staked at the DK price (0.05 = +5% EV). Absent/null =
   * no floor. A pick with no DK price can't compute EV, so a floor excludes it.
   */
  min_ev?: number | null;
}

/** ET time-of-day bucket a game falls in (see timeSlotOf in customModelFilters). */
export type TimeSlot = 'day' | 'early' | 'prime' | 'late';
/** Which way the DK price leans: minus money vs plus money. */
export type PriceSide = 'fav' | 'dog';
/** Game market (ML/total/spread) vs a player prop. */
export type BetKind = 'game' | 'prop';
/** Weekend = Saturday/Sunday in ET (the date the pipeline stamps as game_date). */
export type DayType = 'weekday' | 'weekend';

/**
 * Model-level filters, applied to every pick that already passed one of the
 * model's rules. Every field is optional and an absent/empty one means "no
 * constraint", so a model saved before filters existed behaves exactly as it
 * did. See customModelFilters.ts for the matcher and the UI catalog.
 */
export interface CustomModelFilters {
  /**
   * LEGACY — removed from the builder 2026-08-22 and IGNORED by the matcher.
   * Kept only so older saved models still parse; sanitizeFilters strips it
   * before anything (client matcher or server RPC) evaluates a model.
   */
  signals?: SignalType[];
  /** LEGACY — the bet-type rules now pick specific markets, so this chip group
   *  left the builder. Still honored on models saved before 2026-08-22. */
  betKinds?: BetKind[];
  sides?: PickSide[];
  price?: PriceSide[];
  timeSlots?: TimeSlot[];
  dayTypes?: DayType[];
  tiers?: Exclude<ConfidenceTier, null>[];
  /** American price floor/ceiling, e.g. minOdds -140 skips anything juicier. */
  minOdds?: number;
  maxOdds?: number;
  /** Betting-line range (total, spread, or prop line the pick was priced at).
   *  Moneyline picks carry no line, so setting either bound drops them. */
  minLine?: number;
  maxLine?: number;
  /** Public backing on the pick side, 0-100. Only full-game markets carry splits. */
  maxPublicBetPct?: number;
  minPublicBetPct?: number;
  excludeInjuries?: boolean;
}

export interface CustomModel {
  id: string;
  name: string;
  rules: CustomModelRule[];
  /** Absent on models created before the filter builder shipped. */
  filters?: CustomModelFilters;
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
  // NFL (nfl_player_game_log via v_player_season_totals_nfl; yards arrive as
  // NUMERIC strings from Supabase — statValue treats non-numbers as 0, so the
  // leaderboard coerces below)
  pos?: string | null;
  completions?: number;
  attempts?: number;
  passing_yards?: number | string;
  passing_tds?: number;
  interceptions?: number;
  carries?: number;
  rushing_yards?: number | string;
  rushing_tds?: number;
  receptions?: number;
  targets?: number;
  receiving_yards?: number | string;
  receiving_tds?: number;
  rush_rec_tds?: number;
  def_sacks?: number | string;
  def_interceptions?: number;
  // NCAAF (ncaaf_player_game_log via v_player_season_totals_ncaaf) reuses the
  // football keys above and adds the defensive counts college box scores carry.
  // Tackles/TFL are NUMERIC (shared tackles are charged in halves).
  def_tackles?: number | string;
  def_solo?: number | string;
  def_tfl?: number | string;
  def_pd?: number;
}

/**
 * One row per team side of tonight's games, from v_mlb_tonight_matchups /
 * v_wnba_tonight_matchups. Powers the Stats tab "Tonight" filter + the
 * opponent-strength line on leaderboard rows (batters see the opposing
 * probable starter; pitchers see the opposing lineup; WNBA sees opponent
 * defense). Numeric columns arrive as strings from Supabase — coerce.
 */
export interface TonightMatchupRow {
  game_id: string;
  game_date: string;
  commence_time: string | null;
  team: string;
  opponent: string;
  is_home: number;
  // MLB — opposing probable starter (null when DK hasn't listed him / no stats)
  opp_starter_name?: string | null;
  opp_starter_id?: string | null;
  opp_starter_hand?: string | null;
  opp_starter_era?: number | string | null;
  opp_starter_era_last3?: number | string | null;
  opp_starter_k9?: number | string | null;
  opp_starter_whip?: number | string | null;
  // MLB — opposing team offense (for pitcher rows)
  opp_team_k_pct?: number | string | null;
  opp_team_woba?: number | string | null;
  opp_team_era?: number | string | null;
  // WNBA — opposing team defense
  opp_def_rating?: number | string | null;
  opp_pace?: number | string | null;
  opp_points_allowed_pg?: number | string | null;
}

/**
 * One raw per-game row from the player_recent_games_* RPCs — a player's last N
 * games (newest-first via `rn`). Backs the Stats tab "Hit Rate" mode, which
 * computes "X of N games over the line" + the per-game dot strip client-side.
 * The index signature lets statValue(row, def) read any stat column by key.
 */
export interface RecentGameRow {
  player_id: string;
  player_name: string;
  team: string | null;
  player_type?: PlayerType; // MLB only
  game_id: string;
  game_date: string;
  season: number;
  rn: number;
  [key: string]: number | string | null | undefined; // sport's stat columns
}

/** A player's hit-rate over a window (last N or the whole season) for the
 * selected stat + line. In last-N mode `games` carries the raw rows; in Season
 * mode the rate comes from player_season_stat_values_* and `games` is empty. */
export interface HitRatePlayer {
  player_id: string;
  player_name: string;
  team: string | null;
  player_type?: PlayerType;
  games: RecentGameRow[]; // newest-first, length ≤ N ([] in Season mode)
  values: number[]; // per-game stat values, newest-first (dot strip source)
  hits: number;
  total: number;
  pct: number;
  avg: number;
}

/**
 * One row from the player_season_stat_values_* RPCs — a player's full-season
 * per-game values for ONE stat, as an ordered array (newest game first, nulls
 * excluded server-side). Backs the Hit Rate mode's Season window: ~1 compact
 * row per player instead of the 35K+ raw game rows a season would take.
 */
export interface SeasonStatValuesRow {
  player_id: string;
  player_name: string;
  team: string | null;
  player_type?: PlayerType; // MLB only
  games: number;
  values: number[];
}

/**
 * One team's row on the Stats tab's Teams board — efficiency metrics merged
 * with derived betting records. Backed by the team_stats_board(sport, season)
 * RPC; every metric column is optional because the set varies by sport (a
 * baseball row has no offensive rating, a hockey row has no wRC+).
 */
export interface TeamStatsRow {
  team: string;
  conference: string | null; // NCAAF only
  games_played: number;
  wins: number;
  losses: number;
  win_pct: number | null;
  points_for_pg: number | null;
  points_against_pg: number | null;
  point_diff_pg: number | null;
  // Betting records (derived from finals + the pre-game line)
  ats_w: number;
  ats_l: number;
  ats_p: number;
  ats_pct: number | null;
  ou_o: number;
  ou_u: number;
  ou_p: number;
  over_pct: number | null;
  home_w: number;
  home_l: number;
  away_w: number;
  away_l: number;
  ats_home_pct: number | null;
  ats_away_pct: number | null;
  fav_ats_pct: number | null;
  dog_ats_pct: number | null;
  rest_adv_games: number;
  rest_adv_ats_pct: number | null;
  short_rest_games: number;
  short_rest_ats_pct: number | null;
  // Efficiency — MLB
  wrc_plus?: number | null;
  ops?: number | null;
  team_era?: number | null;
  bullpen_era?: number | null;
  team_whip?: number | null;
  // Efficiency — basketball
  off_rating?: number | null;
  def_rating?: number | null;
  net_rating?: number | null;
  pace?: number | null;
  efg_pct?: number | null;
  tov_pct?: number | null;
  // Efficiency — NHL
  corsi_for_pct?: number | null;
  pp_pct?: number | null;
  pk_pct?: number | null;
  // Efficiency — NCAAF
  sp_overall?: number | null;
  epa_off?: number | null;
  epa_def?: number | null;
  success_off?: number | null;
  success_def?: number | null;
  explosiveness_off?: number | null;
  havoc_rate?: number | null;
  // Efficiency — NFL
  yards_per_play?: number | null;
  pass_yards_pg?: number | null;
  rush_yards_pg?: number | null;
}

/**
 * One recent-news note about one player, from `player_news`. `analysis` is the
 * fantasy-note ANALYSIS paragraph — null for providers (ESPN) that carry none,
 * and the sheet simply omits the block.
 */
export interface PlayerNewsRow {
  news_id: number;
  sport: string;
  player_id: string | null;
  player_name: string;
  team: string | null;
  source: string;
  published_at: string;
  headline: string;
  body: string | null;
  analysis: string | null;
  url: string | null;
}
