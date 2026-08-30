/**
 * Human-friendly labels and descriptions for each model_id.
 * Mirrors the models registry in docs/history/build_state.md.
 */

export interface ModelMeta {
  shortLabel: string;
  longLabel: string;
  type: 'game' | 'pitcher_prop' | 'batter_prop' | 'player_prop';
  statKey: keyof PlayerStats | null;
  statLabel: string;
}

export interface PlayerStats {
  p_strikeouts: number;
  p_hits_allowed: number;
  p_earned_runs: number;
  outs: number;
  p_walks: number;
  hits: number;
  total_bases: number;
  home_runs: number;
  rbi: number;
  runs: number;
  stolen_bases: number;
  walks: number;
}

export const MODEL_META: Record<string, ModelMeta> = {
  mlb_moneyline: {
    shortLabel: 'ML',
    longLabel: 'Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_over_under: {
    shortLabel: 'O/U',
    longLabel: 'Total Runs',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_runline: {
    shortLabel: 'RL',
    longLabel: 'Runline (±1.5)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_f5_moneyline: {
    shortLabel: 'F5 ML',
    longLabel: 'First 5 Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // mlb_live_win_prob + mlb_live_runline are RETIRED (2026-08-30, see
  // thresholds.RETIRED_MODELS). Their labels stay so the picks they already made
  // still render with a name wherever history is shown.
  mlb_live_win_prob: {
    shortLabel: 'LIVE ML',
    longLabel: 'Live Win Probability',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_live_total_runs: {
    shortLabel: 'LIVE O/U',
    longLabel: 'Live Total Runs',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_live_runline: {
    shortLabel: 'LIVE RL',
    longLabel: 'Live Runline (−1.5)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  mlb_prop_pitcher_k: {
    shortLabel: 'P K',
    longLabel: 'Pitcher Strikeouts',
    type: 'pitcher_prop',
    statKey: 'p_strikeouts',
    statLabel: 'Ks',
  },
  mlb_prop_pitcher_hits: {
    shortLabel: 'P H',
    longLabel: 'Pitcher Hits Allowed',
    type: 'pitcher_prop',
    statKey: 'p_hits_allowed',
    statLabel: 'Hits Allowed',
  },
  mlb_prop_pitcher_er: {
    shortLabel: 'P ER',
    longLabel: 'Pitcher Earned Runs',
    type: 'pitcher_prop',
    statKey: 'p_earned_runs',
    statLabel: 'ER',
  },
  mlb_prop_pitcher_outs: {
    shortLabel: 'P Outs',
    longLabel: 'Pitcher Outs',
    type: 'pitcher_prop',
    statKey: 'outs',
    statLabel: 'Outs',
  },
  mlb_prop_pitcher_walks: {
    shortLabel: 'P BB',
    longLabel: 'Pitcher Walks',
    type: 'pitcher_prop',
    statKey: 'p_walks',
    statLabel: 'Walks',
  },
  mlb_prop_batter_hits: {
    shortLabel: 'B H',
    longLabel: 'Batter Hits',
    type: 'batter_prop',
    statKey: 'hits',
    statLabel: 'Hits',
  },
  mlb_prop_batter_tb: {
    shortLabel: 'B TB',
    longLabel: 'Batter Total Bases',
    type: 'batter_prop',
    statKey: 'total_bases',
    statLabel: 'TB',
  },
  mlb_prop_batter_hr: {
    shortLabel: 'B HR',
    longLabel: 'Batter Home Runs',
    type: 'batter_prop',
    statKey: 'home_runs',
    statLabel: 'HR',
  },
  mlb_prop_batter_rbi: {
    shortLabel: 'B RBI',
    longLabel: 'Batter RBIs',
    type: 'batter_prop',
    statKey: 'rbi',
    statLabel: 'RBI',
  },
  mlb_prop_batter_runs: {
    shortLabel: 'B R',
    longLabel: 'Batter Runs Scored',
    type: 'batter_prop',
    statKey: 'runs',
    statLabel: 'Runs',
  },
  mlb_prop_batter_sb: {
    shortLabel: 'B SB',
    longLabel: 'Batter Stolen Bases',
    type: 'batter_prop',
    statKey: 'stolen_bases',
    statLabel: 'SB',
  },
  mlb_prop_batter_walks: {
    shortLabel: 'B BB',
    longLabel: 'Batter Walks',
    type: 'batter_prop',
    statKey: 'walks',
    statLabel: 'Walks',
  },

  // ── WNBA ──────────────────────────────────────────────────────────────────
  wnba_moneyline: {
    shortLabel: 'ML',
    longLabel: 'Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  wnba_over_under: {
    shortLabel: 'O/U',
    longLabel: 'Total Points',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  wnba_spread: {
    shortLabel: 'Spread',
    longLabel: 'Point Spread',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  wnba_prop_player_points: {
    shortLabel: 'PTS',
    longLabel: 'Player Points',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pts',
  },
  wnba_prop_player_rebounds: {
    shortLabel: 'REB',
    longLabel: 'Player Rebounds',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Reb',
  },
  wnba_prop_player_assists: {
    shortLabel: 'AST',
    longLabel: 'Player Assists',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Ast',
  },
  wnba_prop_player_threes: {
    shortLabel: '3PM',
    longLabel: 'Player Made Threes',
    type: 'player_prop',
    statKey: null,
    statLabel: '3PM',
  },
  wnba_prop_player_pra: {
    shortLabel: 'PRA',
    longLabel: 'Pts + Reb + Ast',
    type: 'player_prop',
    statKey: null,
    statLabel: 'PRA',
  },

  // ── NBA ───────────────────────────────────────────────────────────────────
  nba_moneyline: {
    shortLabel: 'ML',
    longLabel: 'Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nba_over_under: {
    shortLabel: 'O/U',
    longLabel: 'Total Points',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nba_spread: {
    shortLabel: 'Spread',
    longLabel: 'Point Spread',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nba_prop_player_points: {
    shortLabel: 'PTS',
    longLabel: 'Player Points',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Pts',
  },
  nba_prop_player_rebounds: {
    shortLabel: 'REB',
    longLabel: 'Player Rebounds',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Reb',
  },
  nba_prop_player_assists: {
    shortLabel: 'AST',
    longLabel: 'Player Assists',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Ast',
  },
  nba_prop_player_threes: {
    shortLabel: '3PM',
    longLabel: 'Player Made Threes',
    type: 'player_prop',
    statKey: null,
    statLabel: '3PM',
  },
  nba_prop_player_pra: {
    shortLabel: 'PRA',
    longLabel: 'Pts + Reb + Ast',
    type: 'player_prop',
    statKey: null,
    statLabel: 'PRA',
  },
  nba_prop_player_blocks: {
    shortLabel: 'BLK',
    longLabel: 'Player Blocks',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Blk',
  },
  nba_prop_player_steals: {
    shortLabel: 'STL',
    longLabel: 'Player Steals',
    type: 'player_prop',
    statKey: null,
    statLabel: 'Stl',
  },
  nba_prop_player_turnovers: {
    shortLabel: 'TO',
    longLabel: 'Player Turnovers',
    type: 'player_prop',
    statKey: null,
    statLabel: 'TO',
  },
  nba_prop_player_dd: {
    shortLabel: 'DD',
    longLabel: 'Double-Double',
    type: 'player_prop',
    statKey: null,
    statLabel: 'DD',
  },

  // ── UFC ───────────────────────────────────────────────────────────────────
  ufc_moneyline: {
    shortLabel: 'ML',
    longLabel: 'Fight Winner',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ufc_total_rounds: {
    shortLabel: 'Rounds',
    longLabel: 'Total Rounds O/U',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ufc_method_of_victory: {
    shortLabel: 'Method',
    longLabel: 'Method of Victory',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_moneyline: {
    shortLabel: 'ML',
    longLabel: 'Moneyline (incl. OT/SO)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_moneyline_regulation: {
    shortLabel: 'Reg 3-Way',
    longLabel: 'Regulation Result (Home / Draw / Away)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_over_under: {
    shortLabel: 'O/U',
    longLabel: 'Total Goals',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nhl_puckline: {
    shortLabel: 'PL',
    longLabel: 'Puck Line (±1.5)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },

  // ── NFL ───────────────────────────────────────────────────────────────────
  // The standalone wind-totals card (§28) — under-only, published into picks
  // by scripts/nfl_wind_publisher.py after each scheduled live card run.
  // NCAAF (FBS). ncaaf_spread is a MARGIN-REGRESSION model, not a classifier:
  // it predicts the game's margin from fundamentals and bets when that
  // disagrees with the closing spread by >= 5.5 points. Moneyline and totals
  // are paused (their classifiers held out at AUC ~0.49 — coin flips).
  ncaaf_spread: {
    shortLabel: 'Spread',
    longLabel: 'Spread (Opener)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // Same opener rule, DISJOINT high-conviction band: the two books' openers
  // disagree by 2.5+ points instead of 1.0-2.5. Fewer picks, higher rate. A
  // game fires exactly ONE of the two tiers -- the scorer's band ceiling makes
  // them mutually exclusive, so these never double-stake the same side.
  ncaaf_spread_premium: {
    shortLabel: 'Spread+',
    longLabel: 'Spread (Opener, High Conviction)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // NCAAF live (in-play) lanes — picks appear on the Live tab only.
  ncaaf_live_win_prob: {
    shortLabel: 'LIVE ML',
    longLabel: 'Live Win Probability',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaaf_live_total: {
    shortLabel: 'LIVE O/U',
    longLabel: 'Live Total',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaaf_moneyline: {
    shortLabel: 'ML',
    longLabel: 'Moneyline',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  ncaaf_over_under: {
    shortLabel: 'O/U',
    longLabel: 'Total Points',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  nfl_wind_totals: {
    shortLabel: 'Wind U',
    longLabel: 'Wind Totals (Under)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // The opener-spread rule: bet the side Pinnacle favours at a soft book's
  // stale number, locked ~2-7 days before kickoff (insert-once — never
  // re-priced; the edge is the staleness).
  nfl_opener_spread: {
    shortLabel: 'Opener',
    longLabel: 'Opener Spread (vs Pinnacle)',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  // The market-relative player-prop rule: de-vig Pinnacle, bet the retail
  // outlier. ONE id across every market it trades — the validated number is
  // pooled, and the market itself is on picks.prop_market, so per-market
  // breakdowns are a query rather than eight entries here.
  nfl_prop_market: {
    shortLabel: 'Prop Mkt',
    longLabel: 'NFL Props (market-relative)',
    type: 'player_prop',
    statKey: null,
    statLabel: '',
  },

  // ── GOLF ──────────────────────────────────────────────────────────────────
  // Per-player markets rendered as single bets (player name in pick_label).
  golf_outright: {
    shortLabel: 'Win',
    longLabel: 'Outright Winner',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_top10: {
    shortLabel: 'T10',
    longLabel: 'Top 10 Finish',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_top20: {
    shortLabel: 'T20',
    longLabel: 'Top 20 Finish',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_make_cut: {
    shortLabel: 'Cut',
    longLabel: 'Make the Cut',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
  golf_matchup: {
    shortLabel: 'H2H',
    longLabel: 'Tournament Matchup',
    type: 'game',
    statKey: null,
    statLabel: '',
  },
};

export function modelShort(modelId: string): string {
  if (modelId === 'custom') return 'Custom'; // user-entered parlay leg (CUSTOM_MODEL_ID)
  return MODEL_META[modelId]?.shortLabel ?? modelId;
}

export function modelLong(modelId: string): string {
  return MODEL_META[modelId]?.longLabel ?? modelId;
}

export function isPropModel(modelId: string): boolean {
  const m = MODEL_META[modelId];
  return m?.type === 'pitcher_prop' || m?.type === 'batter_prop' || m?.type === 'player_prop';
}

// ---------------------------------------------------------------------------
// Bet-type catalog — what the custom-model builder offers
// ---------------------------------------------------------------------------

export type BetTypeSport = 'MLB' | 'WNBA' | 'NBA' | 'NFL' | 'NCAAF' | 'UFC' | 'NHL' | 'GOLF';

/** Which sport a model_id belongs to, from its prefix. */
export function sportOfModel(modelId: string): BetTypeSport {
  if (modelId.startsWith('wnba')) return 'WNBA';
  if (modelId.startsWith('nba')) return 'NBA';
  if (modelId.startsWith('ncaaf')) return 'NCAAF';
  if (modelId.startsWith('nfl')) return 'NFL';
  if (modelId.startsWith('ufc')) return 'UFC';
  if (modelId.startsWith('nhl')) return 'NHL';
  if (modelId.startsWith('golf')) return 'GOLF';
  return 'MLB';
}

export interface BetTypeOption {
  /** The underlying model_id — one model prices each market. */
  id: string;
  /** The market name the user sees (never a model id). */
  label: string;
  sport: BetTypeSport;
  type: ModelMeta['type'];
}

const BET_TYPE_SPORT_ORDER: BetTypeSport[] = [
  'MLB',
  'WNBA',
  'NBA',
  'NFL',
  'NCAAF',
  'UFC',
  'NHL',
  'GOLF',
];

/**
 * Every market a custom model can be built on, grouped by sport. Users pick a
 * BET TYPE (moneyline, a specific prop, …), not one of our in-house models —
 * the model_id is only the plumbing underneath. Live (in-play) markets are
 * excluded: live picks are delete-and-rescored every pass and never graded
 * into the backtest universe, so a rule on them could match nothing.
 */
export const BET_TYPE_GROUPS: Array<{ sport: BetTypeSport; options: BetTypeOption[] }> =
  BET_TYPE_SPORT_ORDER.map((sport) => ({
    sport,
    options: Object.entries(MODEL_META)
      .filter(([id]) => !id.includes('_live_') && sportOfModel(id) === sport)
      .map(([id, meta]) => ({ id, label: meta.longLabel, sport, type: meta.type })),
  })).filter((g) => g.options.length > 0);

/** "MLB · Moneyline" — how a bet-type rule is titled everywhere it renders. */
export function betTypeLabel(modelId: string): string {
  return `${sportOfModel(modelId)} · ${modelLong(modelId)}`;
}
