/**
 * Market mapping + line-movement math shared by the movement chip (PickCard)
 * and the Line Movement card (PickDetail).
 *
 * The model_id → odds market mapping mirrors the CASE in
 * models/scorer.py check_line_movement() and docs/mobile_picks_prompt.md.
 * The steam thresholds mirror check_line_movement():
 *   - price implied-prob shift ≥ 3pp against the pick  → CAUTION
 *   - total/spread line moved 0.5+ against the pick    → SKIP
 */

import { americanImplied, americanToDecimal, formatStampET } from './format';
import { isUnlockedPreview } from './thresholds';
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
  // NFL card models: DK line snapshots are mirrored into the odds table by
  // scripts/nfl_wind_publisher.py on every scheduled card run, so movement
  // tracking works. The pick's own price is best-book/soft-book (not DK), so
  // NFL movement is LINE-only — see isNflLineOnly / computeMovement.
  if (modelId === 'nfl_wind_totals') return 'totals';
  if (modelId === 'nfl_opener_spread') return 'spreads';
  if (modelId.startsWith('nfl_')) return null; // any future NFL model without snapshots
  if (modelId.includes('over_under')) return 'totals';
  if (modelId.includes('runline') || modelId.includes('puckline') || modelId.includes('spread')) {
    return 'spreads';
  }
  if (modelId.includes('prop')) return null; // props live in player_prop_odds
  // Live (in-play) models. `mlb_live_total_runs` has no 'over_under' in its id,
  // so without this it fell through to 'h2h' and its totals price could never
  // resolve. Live rows come from v_latest_inplay_odds_all_books, not the
  // pre-game views (which exclude snapshot_type='in_play' by design).
  if (modelId === 'mlb_live_total_runs') return 'totals';
  if (modelId === 'ncaaf_live_total') return 'totals';
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
 *
 * Two roles, mirroring config.py (2026-09-03):
 *   - LINE_SHOP_BOOKS   = every book we FETCH (config.LINE_SHOP_BOOKMAKERS).
 *   - BETTABLE_BOOKS    = the books a member can actually place at from the US
 *                         (config.BEST_LINE_BOOKMAKERS). Pinnacle takes no US
 *                         customers, Bovada is offshore, and ESPN BET was
 *                         removed by mike; they stay in the feed as reference
 *                         prices but are never offered as "where to bet".
 * The picker and the per-pick line chips read BETTABLE_BOOKS; the All-books
 * table on the detail screen reads everything.
 */
export const MODEL_BOOK = 'draftkings' as const;

export type BookKey =
  | 'draftkings'
  | 'fanduel'
  | 'betmgm'
  | 'williamhill_us'
  | 'espnbet'
  | 'fanatics'
  | 'bovada'
  | 'pinnacle'
  | 'betrivers'
  | 'hardrockbet'
  | 'ballybet'
  | 'betparx'
  | 'rebet';

export const LINE_SHOP_BOOKS: BookKey[] = [
  'draftkings',
  'fanduel',
  'betmgm',
  'williamhill_us',
  'espnbet',
  'fanatics',
  'bovada',
  'pinnacle',
  'betrivers',
  'hardrockbet',
  'ballybet',
  'betparx',
  'rebet',
];

/** Reference-only books — mirrors config.BEST_LINE_EXCLUDE_BOOKMAKERS. */
export const REFERENCE_ONLY_BOOKS: BookKey[] = ['pinnacle', 'bovada', 'espnbet'];

/** Books a member can be sent to — mirrors config.BEST_LINE_BOOKMAKERS. */
export const BETTABLE_BOOKS: BookKey[] = LINE_SHOP_BOOKS.filter(
  (b) => !REFERENCE_ONLY_BOOKS.includes(b),
);

export function isBettableBook(key: string): boolean {
  return (BETTABLE_BOOKS as string[]).includes(key);
}

const BOOK_LABELS: Record<string, string> = {
  draftkings: 'DK',
  fanduel: 'FD',
  betmgm: 'MGM',
  williamhill_us: 'CZR',
  caesars: 'CZR', // legacy/alternate key for the same book
  espnbet: 'ESPN',
  fanatics: 'FAN',
  bovada: 'BOV',
  pinnacle: 'PIN',
  betrivers: 'BR',
  hardrockbet: 'HRB',
  ballybet: 'BALLY',
  betparx: 'PARX',
  rebet: 'REBET',
};

const BOOK_NAMES: Record<string, string> = {
  draftkings: 'DraftKings',
  fanduel: 'FanDuel',
  betmgm: 'BetMGM',
  williamhill_us: 'Caesars',
  caesars: 'Caesars',
  espnbet: 'ESPN BET',
  fanatics: 'Fanatics',
  bovada: 'Bovada',
  pinnacle: 'Pinnacle',
  betrivers: 'BetRivers',
  hardrockbet: 'Hard Rock Bet',
  ballybet: 'Bally Bet',
  betparx: 'betPARX',
  rebet: 'ReBet',
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

/** Abbrev → book key, for reading the book back out of an NFL pick_label. */
const BOOK_KEY_BY_ABBREV: Record<string, string> = {
  DK: 'draftkings',
  FD: 'fanduel',
  MGM: 'betmgm',
  CZR: 'williamhill_us',
  ESPN: 'espnbet',
  FAN: 'fanatics',
  BR: 'betrivers',
  HRB: 'hardrockbet',
  BALLY: 'ballybet',
  PARX: 'betparx',
  REBET: 'rebet',
};

/**
 * Which book the price STORED on a pick came from.
 *
 * Everywhere except NFL that's DraftKings — the book the models score against.
 * The standalone nfl/ package (§28) line-shops by design and stores the best/soft
 * book's price in `dk_odds`, naming the book in pick_label:
 *   "NYJ @ MIA Under 43.5 (Wind 14 mph, FD) · 1.00u"
 *   "NYJ @ MIA — NYJ +5 (Opener -1.5 vs Pinnacle, MGM) · 1.00u"
 * Labeling that "DK" tells the user a price they cannot get at the book named.
 * An unrecognised abbrev is returned as-is rather than guessed at.
 */
export function storedQuoteBook(pick: Pick): string {
  if (!(pick.model_id ?? '').startsWith('nfl_')) return MODEL_BOOK;
  const m = /\(([^()]*?),\s*([A-Za-z]{2,5})\)/.exec(pick.pick_label ?? '');
  if (!m) return MODEL_BOOK;
  const abbrev = m[2].toUpperCase();
  return BOOK_KEY_BY_ABBREV[abbrev] ?? abbrev;
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
  const storedBook = storedQuoteBook(pick);
  const storedQuote = (): DisplayQuote | null => {
    const stored = numOrNull(pick.dk_odds);
    if (stored == null) return null;
    const isPreferred = storedBook === book;
    return {
      bookmaker: storedBook,
      price: stored,
      link: pick.dk_bet_link ?? null,
      line: numOrNull(pick.scored_line),
      isPreferred,
      isFallback: !isPreferred,
    };
  };

  // The book we model against: the STORED price is the number the pick's edge was
  // computed from, so it wins over any fresher snapshot (see the doc block above).
  if (book === MODEL_BOOK && storedBook === MODEL_BOOK) return storedQuote();

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

  return storedQuote();
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

// ── Betting lines: the per-pick chip row ────────────────────────────────────

/** One chip on a pick's "Betting lines" row. */
export interface LineQuote extends BookQuote {
  /** The price the pick was GIVEN at — `dk_odds` at the stored book (DK, or
   *  the NFL card's soft book). It is the bet of record (§1c), so it is always
   *  a chip, at the stored price rather than a fresher snapshot. */
  isRecord: boolean;
}

/**
 * Every book a member can actually bet this pick at, best payout first.
 *
 * Rules, each of which is a product decision rather than a convenience:
 *   - SAME LINE ONLY. Over 9.0 at -105 is not a better price on Over 8.5; it
 *     is a different bet, and the model probability was computed at the
 *     scored line (docs/best_line.md §5). A book whose line differs is left
 *     to the All-books table, which prints the line beside the price.
 *   - BETTABLE BOOKS ONLY. Pinnacle / Bovada / ESPN BET are reference prices
 *     (config.BEST_LINE_EXCLUDE_BOOKMAKERS); a chip is an invitation to bet.
 *   - THE RECORD CHIP IS ALWAYS PRESENT when the pick carries a price. It is
 *     the stored number, never re-priced, so a DK bettor sees the bet they
 *     were given even when DK's current snapshot has moved.
 *   - The scorer's own best-price stamp (`best_book` / `best_odds`) fills in
 *     when today's per-book rows don't carry that book — it is the same
 *     number the Discord post's "also … @ …" line quotes.
 *   - LIVE PICKS ARE DRAFTKINGS ONLY (Matt, 2026-09-03): the in-play model
 *     reads DK's line and the bet is placed there, so a live pick gets the
 *     record chip and nothing else.
 */
export function pickLineQuotes(pick: Pick, rows: BookPricedRow[]): LineQuote[] {
  const recordBook = storedQuoteBook(pick);
  const recordPrice = numOrNull(pick.dk_odds);
  const scoredLine = numOrNull(pick.scored_line);
  const record: Omit<LineQuote, 'isBest'> | null =
    recordPrice == null
      ? null
      : {
          bookmaker: recordBook,
          price: recordPrice,
          link: pick.dk_bet_link ?? null,
          line: scoredLine,
          isRecord: true,
        };

  if (pick.is_live === true) {
    return record ? [{ ...record, isBest: true }] : [];
  }

  const market = gameMarketForModel(pick.model_id) ?? propMarketForModel(pick.model_id);
  const marketHasLine = market != null && !market.startsWith('h2h');

  const byBook = new Map<string, Omit<LineQuote, 'isBest'>>();
  if (record) byBook.set(record.bookmaker, record);

  for (const r of rows) {
    if (byBook.has(r.bookmaker)) continue; // the record chip wins over a fresher row
    if (!isBettableBook(r.bookmaker)) continue;
    const price = priceForSide(r, pick.pick_side);
    if (price == null) continue;
    const line = lineFromSnapshot(r, market);
    if (marketHasLine && scoredLine != null && line !== scoredLine) continue;
    byBook.set(r.bookmaker, {
      bookmaker: r.bookmaker,
      price,
      link: linkForSide(r, pick.pick_side),
      line,
      isRecord: false,
    });
  }

  // The scorer's stamp: same-line by construction (_best_game_price /
  // _best_prop_price shop the scored line only), bettable by construction
  // (BEST_LINE_BOOKMAKERS), so it needs neither filter — just the dedupe.
  const stampBook = (pick.best_book ?? '').trim().toLowerCase();
  const stampPrice = numOrNull(pick.best_odds);
  if (stampBook && stampPrice != null && !byBook.has(stampBook) && isBettableBook(stampBook)) {
    byBook.set(stampBook, {
      bookmaker: stampBook,
      price: stampPrice,
      link: pick.best_bet_link ?? null,
      line: scoredLine,
      isRecord: false,
    });
  }

  const quotes = Array.from(byBook.values());
  if (quotes.length === 0) return [];
  const order = (b: string) => {
    const i = (LINE_SHOP_BOOKS as string[]).indexOf(b);
    return i < 0 ? LINE_SHOP_BOOKS.length : i;
  };
  quotes.sort((a, b) => {
    const d = americanToDecimal(b.price) - americanToDecimal(a.price);
    if (d !== 0) return d;
    if (a.isRecord !== b.isRecord) return a.isRecord ? -1 : 1;
    return order(a.bookmaker) - order(b.bookmaker);
  });
  const bestDecimal = americanToDecimal(quotes[0].price);
  return quotes.map((q) => ({ ...q, isBest: americanToDecimal(q.price) === bestDecimal }));
}

/**
 * Which chips fit on the card. The best-first order is kept; when there are
 * more than `max`, the record chip and the user's own book are guaranteed a
 * slot (dropping the weakest of the rest), and `hidden` says how many the
 * detail screen's All-books table still holds.
 */
export function selectLineChips(
  quotes: LineQuote[],
  preferredBook: string,
  max = 4,
): { shown: LineQuote[]; hidden: number } {
  if (quotes.length <= max) return { shown: quotes, hidden: 0 };
  const pinned = quotes.filter((q) => q.isRecord || q.bookmaker === preferredBook);
  const shown = quotes.slice(0, max);
  for (const p of pinned) {
    if (shown.includes(p)) continue;
    // Evict the lowest-ranked unpinned chip to make room.
    for (let i = shown.length - 1; i >= 0; i--) {
      if (!pinned.includes(shown[i])) {
        shown.splice(i, 1);
        break;
      }
    }
    shown.push(p);
  }
  shown.sort((a, b) => quotes.indexOf(a) - quotes.indexOf(b));
  return { shown, hidden: quotes.length - shown.length };
}

/**
 * A line as the PICK'S SIDE sees it. Spreads are stored home-relative
 * (`scored_line` / `spread_home` are always the HOME number), so an away pick
 * must be shown the negation — a pick labeled "NYJ +5" has scored_line -5, and
 * showing "-5" next to that label reads as a different bet.
 */
export function lineForSide(
  line: number | null,
  side: PickSide,
  market: string | null,
): number | null {
  if (line == null) return null;
  if (market != null && market.startsWith('spreads') && side === 'away') return -line;
  return line;
}

/** lineForSide, formatted the way the pick label writes it (spreads get a sign). */
export function formatSideLine(
  line: number | null,
  side: PickSide,
  market: string | null,
): string {
  const v = lineForSide(line, side, market);
  if (v == null) return '—';
  const isSpread = market != null && market.startsWith('spreads');
  return isSpread ? `${v > 0 ? '+' : ''}${v}` : `${v}`;
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
  /** Line-only comparison (NFL): the pick's stored price is the card's
   *  best-book/soft-book quote, not DraftKings', so a stored-vs-DK price delta
   *  would be cross-book noise, not movement — only the LINE is compared. */
  lineOnly: boolean;
}

/**
 * NFL picks are published from the standalone card scripts, which line-shop —
 * their stored price is NOT a DraftKings quote, so movement vs the DK
 * snapshots must ignore the price and compare lines only.
 */
export function isNflLineOnly(modelId: string): boolean {
  return modelId.startsWith('nfl_');
}

/**
 * Compare the price/line a pick was scored at vs the latest snapshot.
 * Returns null when nothing moved meaningfully (or there's nothing to compare).
 * Direction is the ENTRY frame ("re-check before betting"): a line move is
 * "against" when a bet placed now gets a worse number than the pick locked.
 */
export function computeMovement(
  pick: Pick,
  latest: PricedSnapshot,
  market: string | null,
  opts?: { lineOnly?: boolean },
): Movement | null {
  const lineOnly = opts?.lineOnly ?? false;
  const scoredPrice = numOrNull(pick.dk_odds);
  const currentPrice = priceForSide(latest, pick.pick_side);

  let priceShiftPp: number | null = null;
  if (!lineOnly && scoredPrice != null && currentPrice != null && scoredPrice !== currentPrice) {
    priceShiftPp = (americanImplied(currentPrice) - americanImplied(scoredPrice)) * 100;
  }

  const scoredLine = numOrNull(pick.scored_line);
  const currentLine = lineFromSnapshot(latest, market);
  let lineMovedAgainst = false;
  let lineMovedFor = false;
  if (market != null && !market.startsWith('h2h') && scoredLine != null && currentLine != null) {
    const delta = currentLine - scoredLine;
    if (market.startsWith('spreads')) {
      // scored_line is the HOME spread. The home side's entry worsens as the
      // home number shrinks (fewer points / laying more); the away side's as
      // it grows. Fixed ±1.5 runline/puckline never moves, so this only fires
      // for markets whose spread genuinely floats (NFL opener, NBA/WNBA).
      lineMovedAgainst =
        (pick.pick_side === 'home' && delta < -0.4) || (pick.pick_side === 'away' && delta > 0.4);
      lineMovedFor =
        (pick.pick_side === 'home' && delta > 0.4) || (pick.pick_side === 'away' && delta < -0.4);
    } else {
      // O/U markets (totals + player props). Mirror check_line_movement:
      // Under entry hurt by the line dropping, Over by rising.
      lineMovedAgainst =
        (pick.pick_side === 'under' && delta < -0.4) || (pick.pick_side === 'over' && delta > 0.4);
      lineMovedFor =
        (pick.pick_side === 'under' && delta > 0.4) || (pick.pick_side === 'over' && delta < -0.4);
    }
  }

  if (priceShiftPp == null && !lineMovedAgainst && !(lineOnly && lineMovedFor)) return null;

  let severity: MovementSeverity;
  if (lineMovedAgainst) {
    severity = 'skip';
  } else if (priceShiftPp != null && priceShiftPp >= 3) {
    severity = 'caution';
  } else if (priceShiftPp != null && priceShiftPp <= -1) {
    severity = 'good'; // moved ≥1pp in the bettor's favor
  } else if (lineOnly && lineMovedFor) {
    severity = 'good'; // line-only picks: a favorable 0.5+ line move is the signal
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
    lineOnly,
  };
}

/** Movement for a pick given the day's latest-odds rows (PickCard chip path). */
export function movementFromLatest(
  pick: Pick,
  latest: LatestDkOddsRow | null | undefined,
): Movement | null {
  if (!latest || pick.dk_odds == null) return null;
  return computeMovement(pick, latest, latest.market, {
    lineOnly: isNflLineOnly(pick.model_id),
  });
}

// ── NFL pick timing ─────────────────────────────────────────────────────────

export interface NflTiming {
  /** 'Locked' (opener — never re-priced) or 'Priced' (wind — re-priced each run). */
  verb: 'Locked' | 'Priced';
  /** Plain-language explanation for the detail screen. */
  note: string;
}

/**
 * NFL picks are published days ahead by scheduled card runs (§28) — the
 * when-was-this-priced context every other sport gets implicitly from same-day
 * scoring. Opener picks lock once and are never re-priced (the edge IS the
 * stale opening number); wind picks are delete+re-priced each card run, so
 * created_at is the LATEST pricing, not the first election.
 */
export function nflTimingInfo(pick: Pick): NflTiming | null {
  if (pick.model_id === 'nfl_opener_spread') {
    return {
      verb: 'Locked',
      note:
        'Locked at the opening number and never re-priced — the edge is the stale line the book ' +
        'was still hanging. The market has usually corrected by game day, so check the line ' +
        'movement below before betting at today’s number: the model only endorsed the locked one.',
    };
  }
  if (pick.model_id === 'nfl_wind_totals') {
    return {
      verb: 'Priced',
      note:
        'Re-priced at each scheduled card run through game morning; a game that stops qualifying ' +
        '(wind dropped, edge gone) is removed from the board. This number is from the latest run.',
    };
  }
  return null;
}

// ── When a pick posted ──────────────────────────────────────────────────────

export interface PickTiming {
  /** Drives presentation: the live lock is emphasized, the rest is context. */
  kind: 'live' | 'nfl' | 'posted';
  verb: 'Locked' | 'Priced' | 'Posted';
  /** Card chip text, e.g. "Posted 11:07 AM ET" / "Locked Tue 8/18 · 9:31 AM ET". */
  label: string;
  /** Plain-language explanation for the detail screen. */
  note: string;
}

/**
 * When this bet posted, and what that time means for the number beside it.
 *
 * created_at IS the post time for every locked pick, because a locked row is
 * never rewritten: game picks lock at the first scoring run of the day
 * (LOCK_GAME_PICKS_AT_FIRST_RUN), props at the first signal on a confirmed
 * lineup (LOCK_PROP_PICKS_AT_FIRST_SIGNAL), live bets at the first BET in the
 * lane (LOCK_LIVE_PICKS_AT_FIRST_SIGNAL), and NFL card picks are insert-once.
 *
 * Two classes are deliberately excluded, because for them created_at is the
 * latest re-score rather than a post time and stamping it would misreport when
 * the bet was given:
 *   - anything that is not a BET (AVOID, and the NCAAF "watching" NONE rows,
 *     which are delete+rescored every pass), and
 *   - unlocked look-ahead previews (future UFC/golf), which re-price until
 *     game day.
 */
export function pickTimingInfo(pick: Pick): PickTiming | null {
  if (!pick.created_at) return null;
  if (pick.signal_type !== 'BET') return null;
  if (isUnlockedPreview(pick)) return null;

  const stamp = formatStampET(pick.created_at);
  if (!stamp) return null;

  const nfl = nflTimingInfo(pick);
  if (nfl) {
    return { kind: 'nfl', verb: nfl.verb, label: `${nfl.verb} ${stamp}`, note: nfl.note };
  }

  if (pick.is_live) {
    const period =
      pick.inning_at_pick != null
        ? pick.sport === 'NCAAF'
          ? ` · Q${pick.inning_at_pick}`
          : ` · inning ${pick.inning_at_pick}`
        : '';
    return {
      kind: 'live',
      verb: 'Locked',
      label: `Locked ${stamp}${period} — bet of record`,
      note:
        'Locked the moment this crossed, and never re-priced — this is the line and price that ' +
        'were on offer then, not the current ones. In-play numbers move fast, so check the book ' +
        'before betting.',
    };
  }

  return {
    kind: 'posted',
    verb: 'Posted',
    label: `Posted ${stamp}`,
    note:
      pick.player_id != null
        ? 'Props lock at the first signal after the lineup is confirmed, and are never re-priced. ' +
          'This is when the bet posted, at the line and price shown.'
        : 'Game picks lock at the first scoring run of the day and are never re-priced. This is ' +
          'when the bet posted, at the line and price shown.',
  };
}

/**
 * Top model inputs, transcribed from the trainer feature-importance output
 * documented in docs/sports/{mlb,wnba}.md. Static by design: importances live
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
