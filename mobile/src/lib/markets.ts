/**
 * Market mapping + line-movement math shared by the movement chip (PickCard)
 * and the Line Movement card (PickDetail).
 *
 * The model_id → odds market mapping mirrors the CASE in
 * models/scorer.py check_line_movement() and CLAUDE.md Section 16.
 * The steam thresholds mirror check_line_movement():
 *   - price implied-prob shift ≥ 3pp against the pick  → CAUTION
 *   - total/spread line moved 0.5+ against the pick    → SKIP
 */

import { americanImplied, americanToDecimal } from './format';
import type { BookPricedRow, LatestDkOddsRow, OddsByBookRow, Pick, PickSide } from '@/types';

/** Odds-table market for a game-level model. Null = prob-only (no priced market). */
export function gameMarketForModel(modelId: string): string | null {
  if (modelId.includes('f5_over_under')) return 'totals_1st_5_innings';
  if (modelId.includes('f5_runline')) return 'spreads_1st_5_innings';
  if (modelId.includes('f5_moneyline')) return 'h2h_1st_5_innings';
  if (modelId === 'ufc_method_of_victory') return null; // prob-only, never priced
  if (modelId === 'ufc_total_rounds') return 'totals';
  if (modelId === 'nhl_moneyline_regulation') return 'h2h_3way';
  if (modelId.startsWith('golf_')) return null; // golf odds live in golf_odds, not the odds table
  if (modelId === 'nfl_wind_totals') return null; // priced in the standalone nfl/ package, never in the odds table
  if (modelId.includes('over_under')) return 'totals';
  if (modelId.includes('runline') || modelId.includes('puckline') || modelId.includes('spread')) {
    return 'spreads';
  }
  if (modelId.includes('prop')) return null; // props live in player_prop_odds
  return 'h2h';
}

/** player_prop_odds market for a prop model. Mirrors scorer prop configs. */
const PROP_MARKET_BY_MODEL: Record<string, string> = {
  mlb_prop_pitcher_k: 'pitcher_strikeouts',
  mlb_prop_pitcher_hits: 'pitcher_hits_allowed',
  mlb_prop_pitcher_er: 'pitcher_earned_runs',
  mlb_prop_pitcher_outs: 'pitcher_outs',
  mlb_prop_pitcher_walks: 'pitcher_walks',
  mlb_prop_batter_hits: 'batter_hits',
  mlb_prop_batter_tb: 'batter_total_bases',
  mlb_prop_batter_hr: 'batter_home_runs',
  mlb_prop_batter_rbi: 'batter_rbis',
  mlb_prop_batter_runs: 'batter_runs_scored',
  mlb_prop_batter_sb: 'batter_stolen_bases',
  mlb_prop_batter_walks: 'batter_walks',
  wnba_prop_player_points: 'player_points',
  wnba_prop_player_rebounds: 'player_rebounds',
  wnba_prop_player_assists: 'player_assists',
  wnba_prop_player_threes: 'player_threes',
  wnba_prop_player_pra: 'player_points_rebounds_assists',
  nba_prop_player_points: 'player_points',
  nba_prop_player_rebounds: 'player_rebounds',
  nba_prop_player_assists: 'player_assists',
  nba_prop_player_threes: 'player_threes',
  nba_prop_player_pra: 'player_points_rebounds_assists',
  nba_prop_player_blocks: 'player_blocks',
  nba_prop_player_steals: 'player_steals',
  nba_prop_player_turnovers: 'player_turnovers',
  nba_prop_player_dd: 'player_double_double',
};

export function propMarketForModel(modelId: string): string | null {
  return PROP_MARKET_BY_MODEL[modelId] ?? null;
}

/**
 * Player name for a prop pick, parsed from its label. Prop odds are keyed by
 * player_name (not player_id), so this is how a prop pick is matched to its
 * lines. Label format is set by scorer._make_prop_pick:
 *   "Blake Snell Over 5.5 Ks" / "Aaron Judge Over 0.5 HR"
 * Returns null for game-level picks or an unrecognized label.
 */
export function playerNameFromPickLabel(label: string): string | null {
  const m = label.match(/^([A-Za-z .'\-]+?)\s+(?:Over|Under)\s/);
  return m ? m[1] : null;
}

// ── Parlay correlation: market class ──────────────────────────────────────────

/**
 * Coarse market class for parlay correlation modeling (see parlayCorrelation.ts).
 * Groups every model into the handful of buckets whose pairwise correlation we
 * price. 'other' (UFC / golf, and anything offense-neutral) is treated as
 * independent — it never contributes a non-zero coefficient.
 */
export type MarketClass =
  | 'game_ml'
  | 'game_total'
  | 'game_spread'
  | 'off_prop'
  | 'pitching_prop'
  | 'other';

export function marketClassForModel(modelId: string): MarketClass {
  // UFC / golf have no same-game offensive structure we model — treat as independent.
  if (modelId.startsWith('ufc_') || modelId.startsWith('golf_')) return 'other';
  if (modelId.startsWith('mlb_prop_pitcher_')) return 'pitching_prop';
  if (modelId.includes('prop')) return 'off_prop'; // batter / player scoring props
  if (modelId.includes('over_under') || modelId.includes('total_runs')) return 'game_total';
  if (modelId.includes('runline') || modelId.includes('puckline') || modelId.includes('spread')) {
    return 'game_spread';
  }
  if (modelId.includes('moneyline') || modelId.includes('win_prob')) return 'game_ml';
  return 'other';
}

/** Numeric coercion — PostgREST can serialize NUMERIC columns as strings. */
export function numOrNull(v: number | string | null | undefined): number | null {
  if (v == null) return null;
  const n = typeof v === 'string' ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

export interface PricedSnapshot {
  home_price?: number | string | null;
  away_price?: number | string | null;
  over_price?: number | string | null;
  under_price?: number | string | null;
  spread_home?: number | string | null;
  total_line?: number | string | null;
  line?: number | string | null; // player_prop_odds
}

/** American price for the pick's side from an odds snapshot. */
export function priceForSide(snap: PricedSnapshot, side: PickSide): number | null {
  switch (side) {
    case 'home':
      return numOrNull(snap.home_price);
    case 'away':
      return numOrNull(snap.away_price);
    case 'over':
      return numOrNull(snap.over_price);
    case 'under':
      return numOrNull(snap.under_price);
    default:
      return null;
  }
}

/** Betslip deep link for the pick's side from an odds snapshot, if present. */
export function linkForSide(
  snap: { home_link?: string | null; away_link?: string | null; over_link?: string | null; under_link?: string | null },
  side: PickSide,
): string | null {
  switch (side) {
    case 'home':
      return snap.home_link ?? null;
    case 'away':
      return snap.away_link ?? null;
    case 'over':
      return snap.over_link ?? null;
    case 'under':
      return snap.under_link ?? null;
    default:
      return null;
  }
}

// ── Line shopping ───────────────────────────────────────────────────────────

/**
 * The books we ingest lines for, in display order. Keys are The Odds API's
 * bookmaker keys and MUST match config.LINE_SHOP_BOOKMAKERS on the backend.
 *
 * Caesars is `williamhill_us` on The Odds API — not `caesars`. Both are mapped
 * so a key change on their side degrades to the right label instead of "WILL".
 *
 * DraftKings is first and special: it is the book the MODELS score against.
 * Every other book here is display-only.
 */
export const MODEL_BOOK = 'draftkings' as const;

export type BookKey = 'draftkings' | 'fanduel' | 'betmgm' | 'williamhill_us' | 'espnbet';

export const LINE_SHOP_BOOKS: BookKey[] = [
  'draftkings',
  'fanduel',
  'betmgm',
  'williamhill_us',
  'espnbet',
];

const BOOK_LABELS: Record<string, string> = {
  draftkings: 'DK',
  fanduel: 'FD',
  betmgm: 'MGM',
  williamhill_us: 'CZR',
  caesars: 'CZR', // legacy/alternate key for the same book
  espnbet: 'ESPN',
};

const BOOK_NAMES: Record<string, string> = {
  draftkings: 'DraftKings',
  fanduel: 'FanDuel',
  betmgm: 'BetMGM',
  williamhill_us: 'Caesars',
  caesars: 'Caesars',
  espnbet: 'ESPN BET',
};

export function bookLabel(key: string): string {
  return BOOK_LABELS[key] ?? key.slice(0, 4).toUpperCase();
}

/** Full book name for settings / detail rows. */
export function bookName(key: string): string {
  return BOOK_NAMES[key] ?? key;
}

/** "Bet on FanDuel" / "Bet on DraftKings" — the hand-off button's label. */
export function betOnBookLabel(key: string): string {
  return `Bet on ${bookName(key)}`;
}

export interface BookPrice {
  bookmaker: string;
  price: number;
  link: string | null;
}

/**
 * Best (highest-payout) price for a side across books. For American odds, a
 * larger decimal payout is strictly better for the bettor. Returns null if no
 * book prices the side.
 */
export function bestPriceForSide(rows: BookPricedRow[], side: PickSide): BookPrice | null {
  let best: BookPrice | null = null;
  for (const r of rows) {
    const price = priceForSide(r, side);
    if (price == null) continue;
    if (best == null || americanToDecimal(price) > americanToDecimal(best.price)) {
      best = { bookmaker: r.bookmaker, price, link: linkForSide(r, side) };
    }
  }
  return best;
}

/**
 * Line-shopping suggestion for a pick: the best non-DraftKings price for the
 * pick side that STRICTLY beats DraftKings. Returns null when DK is already best
 * (or the only book), so the chip only appears when there's genuine value to add.
 */
export function lineShopForPick(pick: Pick, rows: BookPricedRow[]): BookPrice | null {
  if (rows.length === 0) return null;
  const dk = rows.find((r) => r.bookmaker === 'draftkings');
  const dkPrice = dk ? priceForSide(dk, pick.pick_side) : numOrNull(pick.dk_odds);
  const best = bestPriceForSide(rows, pick.pick_side);
  if (!best || best.bookmaker === 'draftkings') return null;
  if (dkPrice != null && americanToDecimal(best.price) <= americanToDecimal(dkPrice)) return null;
  return best;
}

/**
 * The price for the pick's side at ONE specific book — what the user sees when
 * they've told us which sportsbook they bet at. Returns null when that book
 * didn't price the side (coverage is uneven; the UI must render "—", not guess).
 */
export function priceForBook(
  rows: BookPricedRow[],
  side: PickSide,
  book: string,
): BookPrice | null {
  const row = rows.find((r) => r.bookmaker === book);
  if (!row) return null;
  const price = priceForSide(row, side);
  if (price == null) return null;
  return { bookmaker: book, price, link: linkForSide(row, side) };
}

/** The price/line/link we actually put in front of the user for a pick. */
export interface DisplayQuote extends BookPrice {
  /** Total/spread/prop line at this book. Two books can hang the same price off
   *  different numbers, so the UI shows this whenever it differs from the line
   *  the model scored. */
  line: number | null;
  /** True when this is the book the user chose in Settings. */
  isPreferred: boolean;
  /** True when the chosen book didn't price this side and we fell back to the
   *  modeled DraftKings number. The UI must say so — a FanDuel bettor seeing a
   *  DK price unlabeled would take it as FanDuel's. */
  isFallback: boolean;
}

/**
 * The quote to display for a pick at the user's sportsbook.
 *
 * Resolution order:
 *   1. the chosen book's latest price for this side (what they'll actually get),
 *   2. the DraftKings price the scorer stored on the pick — flagged as a
 *      fallback so a FanDuel bettor never reads DK's number as their own.
 *
 * For a DraftKings user this is always the STORED price, never a fresher
 * snapshot: it's the number the pick's edge was computed from, so showing a
 * moved price beside an unmoved edge would misrepresent the bet. Drift is
 * surfaced separately by the movement chip and the Line Movement card.
 *
 * Coverage is genuinely uneven — DraftKings prices ~17 prop markets, FanDuel
 * ~9 — so the fallback is the common case, not an edge case.
 */
export function displayQuoteForPick(
  pick: Pick,
  rows: BookPricedRow[],
  book: string,
): DisplayQuote | null {
  const dkQuote = (isPreferred: boolean): DisplayQuote | null => {
    const stored = numOrNull(pick.dk_odds);
    if (stored == null) return null;
    return {
      bookmaker: MODEL_BOOK,
      price: stored,
      link: pick.dk_bet_link ?? null,
      line: numOrNull(pick.scored_line),
      isPreferred,
      isFallback: !isPreferred,
    };
  };

  if (book === MODEL_BOOK) return dkQuote(true);

  const market = gameMarketForModel(pick.model_id) ?? propMarketForModel(pick.model_id);
  const row = rows.find((r) => r.bookmaker === book);
  const price = row ? priceForSide(row, pick.pick_side) : null;
  if (row && price != null) {
    return {
      bookmaker: book,
      price,
      link: linkForSide(row, pick.pick_side),
      line: lineFromSnapshot(row, market),
      isPreferred: true,
      isFallback: false,
    };
  }

  return dkQuote(false);
}

/** A book's price for a side, plus the line it's attached to. */
export interface BookQuote extends BookPrice {
  /** Total/spread/prop line at this book — two books can hang the same price
   *  off different numbers, so the UI shows this next to the price. */
  line: number | null;
  /** True for the best available payout on this side. */
  isBest: boolean;
}

/**
 * Every book that prices this side, best payout first — the "All books" table.
 *
 * `market` is used only to pull the right line column; pass the pick's market
 * (game or prop) or null to omit lines.
 */
export function allBookPrices(
  rows: BookPricedRow[],
  side: PickSide,
  market: string | null = null,
): BookQuote[] {
  const quotes: Omit<BookQuote, 'isBest'>[] = [];
  for (const r of rows) {
    const price = priceForSide(r, side);
    if (price == null) continue;
    quotes.push({
      bookmaker: r.bookmaker,
      price,
      link: linkForSide(r, side),
      line: lineFromSnapshot(r, market),
    });
  }
  if (quotes.length === 0) return [];

  quotes.sort((a, b) => americanToDecimal(b.price) - americanToDecimal(a.price));
  // Ties all get the badge — several books are genuinely tied at e.g. -110.
  const bestDecimal = americanToDecimal(quotes[0].price);
  return quotes.map((q) => ({
    ...q,
    isBest: americanToDecimal(q.price) === bestDecimal,
  }));
}

/** Line value (total or spread) from a snapshot, if the market carries one. */
export function lineFromSnapshot(snap: PricedSnapshot, market: string | null): number | null {
  if (market == null) return null;
  if (market.startsWith('totals')) return numOrNull(snap.total_line);
  if (market.startsWith('spreads')) return numOrNull(snap.spread_home);
  return numOrNull(snap.line); // prop markets
}

export type MovementSeverity = 'good' | 'caution' | 'skip';

export interface Movement {
  severity: MovementSeverity;
  /** Implied-prob shift in pp; positive = moved against the bettor. */
  priceShiftPp: number | null;
  scoredPrice: number | null;
  currentPrice: number | null;
  scoredLine: number | null;
  currentLine: number | null;
  lineMovedAgainst: boolean;
}

/**
 * Compare the price/line a pick was scored at vs the latest snapshot.
 * Returns null when nothing moved meaningfully (or there's nothing to compare).
 */
export function computeMovement(
  pick: Pick,
  latest: PricedSnapshot,
  market: string | null,
): Movement | null {
  const scoredPrice = numOrNull(pick.dk_odds);
  const currentPrice = priceForSide(latest, pick.pick_side);

  let priceShiftPp: number | null = null;
  if (scoredPrice != null && currentPrice != null && scoredPrice !== currentPrice) {
    priceShiftPp = (americanImplied(currentPrice) - americanImplied(scoredPrice)) * 100;
  }

  const scoredLine = numOrNull(pick.scored_line);
  const currentLine = lineFromSnapshot(latest, market);
  let lineMovedAgainst = false;
  // Over/Under markets: totals and player props both carry an O/U line.
  const isOverUnderMarket =
    market != null && !market.startsWith('h2h') && !market.startsWith('spreads');
  if (isOverUnderMarket && scoredLine != null && currentLine != null) {
    const delta = currentLine - scoredLine;
    // Mirror check_line_movement: Under hurt by line dropping, Over by rising.
    lineMovedAgainst =
      (pick.pick_side === 'under' && delta < -0.4) || (pick.pick_side === 'over' && delta > 0.4);
  }

  if (priceShiftPp == null && !lineMovedAgainst) return null;

  let severity: MovementSeverity;
  if (lineMovedAgainst) {
    severity = 'skip';
  } else if (priceShiftPp != null && priceShiftPp >= 3) {
    severity = 'caution';
  } else if (priceShiftPp != null && priceShiftPp <= -1) {
    severity = 'good'; // moved ≥1pp in the bettor's favor
  } else {
    return null; // sub-threshold noise either way — no chip
  }

  return {
    severity,
    priceShiftPp,
    scoredPrice,
    currentPrice,
    scoredLine,
    currentLine,
    lineMovedAgainst,
  };
}

/** Movement for a pick given the day's latest-odds rows (PickCard chip path). */
export function movementFromLatest(
  pick: Pick,
  latest: LatestDkOddsRow | null | undefined,
): Movement | null {
  if (!latest || pick.dk_odds == null) return null;
  return computeMovement(pick, latest, latest.market);
}

/**
 * Top model inputs, transcribed from the trainer feature-importance output
 * documented in CLAUDE.md Section 11/18/19. Static by design: importances live
 * inside the .pkl artifacts, not the DB — re-sync this map after retrains.
 */
export const MODEL_TOP_FEATURES: Record<string, string[]> = {
  mlb_moneyline: ['d_starter_era_last3', 'd_starter_era', 'd_bullpen_era', 'd_woba', 'd_team_era'],
  mlb_over_under: ['home_starter_era', 'away_starter_era', 'total_line', 'is_dome_game', 'temp_f'],
  mlb_runline: ['d_starter_era', 'd_starter_era_last3', 'd_bullpen_era', 'd_team_whip', 'd_woba'],
  mlb_f5_moneyline: ['d_starter_era', 'd_starter_era_last3', 'd_iso', 'd_woba'],
  mlb_prop_pitcher_k: ['season_k_avg', 'k_last10_avg', 'k_last5_avg', 'savant_k_pct', 'k_last3_avg'],
  mlb_prop_pitcher_hits: ['season_hits_avg'],
  mlb_prop_pitcher_er: ['opp_team_woba'],
  mlb_prop_pitcher_outs: ['season_outs_avg'],
  mlb_prop_pitcher_walks: ['walks_last10_avg'],
  mlb_prop_batter_hits: ['batting_order', 'season_hit_avg', 'hits_last10_avg', 'opp_team_era', 'savant_xba'],
  mlb_prop_batter_tb: ['batting_order', 'season_tb_avg', 'savant_xslg', 'opp_team_era', 'savant_hard_hit_pct'],
  mlb_prop_batter_hr: ['season_hr_avg', 'hr_last20_avg', 'savant_xslg', 'savant_barrel_pct', 'savant_hard_hit_pct'],
  mlb_prop_batter_rbi: ['savant_xslg', 'batting_order', 'opp_team_era', 'season_rbi_avg'],
  mlb_prop_batter_runs: ['batting_order', 'season_runs_avg', 'opp_team_era', 'savant_woba', 'savant_sprint_speed'],
  mlb_prop_batter_sb: ['season_sb_avg', 'savant_sprint_speed', 'sb_last20_avg', 'batting_order'],
  mlb_prop_batter_walks: ['season_walks_avg', 'batting_order', 'savant_batter_bb_pct', 'walks_last10_avg'],
  wnba_moneyline: ['d_point_differential', 'd_net_rating', 'd_off_rating'],
  wnba_prop_player_points: ['season_points_avg', 'points_last10_avg', 'points_last5_avg'],
};

/** Humanized labels for feature names shown in the model card. */
const FEATURE_LABELS: Record<string, string> = {
  d_starter_era: 'Starter ERA diff',
  d_starter_era_last3: 'Starter ERA diff (last 3)',
  d_bullpen_era: 'Bullpen ERA diff',
  d_team_era: 'Team ERA diff',
  d_team_whip: 'Team WHIP diff',
  d_woba: 'wOBA diff',
  d_iso: 'ISO diff',
  home_starter_era: 'Home starter ERA',
  away_starter_era: 'Away starter ERA',
  total_line: 'Market total line',
  is_dome_game: 'Dome game',
  temp_f: 'Temperature',
  batting_order: 'Batting order',
  opp_team_era: 'Opponent team ERA',
  opp_team_woba: 'Opponent team wOBA',
  season_k_avg: 'Season K avg',
  k_last10_avg: 'Ks last 10',
  k_last5_avg: 'Ks last 5',
  k_last3_avg: 'Ks last 3',
  savant_k_pct: 'Statcast K%',
  season_hits_avg: 'Season hits avg',
  season_outs_avg: 'Season outs avg',
  walks_last10_avg: 'Walks last 10',
  season_hit_avg: 'Season hit avg',
  hits_last10_avg: 'Hits last 10',
  savant_xba: 'Statcast xBA',
  season_tb_avg: 'Season TB avg',
  savant_xslg: 'Statcast xSLG',
  savant_hard_hit_pct: 'Hard-hit %',
  season_hr_avg: 'Season HR avg',
  hr_last20_avg: 'HRs last 20',
  savant_barrel_pct: 'Barrel %',
  season_rbi_avg: 'Season RBI avg',
  season_runs_avg: 'Season runs avg',
  savant_woba: 'Statcast wOBA',
  savant_sprint_speed: 'Sprint speed',
  season_sb_avg: 'Season SB avg',
  sb_last20_avg: 'SBs last 20',
  season_walks_avg: 'Season walks avg',
  savant_batter_bb_pct: 'Walk rate',
  d_point_differential: 'Point diff',
  d_net_rating: 'Net rating diff',
  d_off_rating: 'Off rating diff',
  season_points_avg: 'Season points avg',
  points_last10_avg: 'Points last 10',
  points_last5_avg: 'Points last 5',
};

export function featureLabel(feature: string): string {
  return FEATURE_LABELS[feature] ?? feature.replace(/_/g, ' ');
}
