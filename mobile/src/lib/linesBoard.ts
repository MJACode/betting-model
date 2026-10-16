/**
 * The Picks "Lines" board: one card per NHL or NBA game, priced at the best
 * bettable book (config.BEST_LINE_BOOKMAKERS / BETTABLE_BOOKS), never the
 * DraftKings-only view.
 *
 * A pick mark is a BET already written for that game. AVOID and NONE are
 * scored rows, not a pick on this board. A prop BET marks the card and no
 * cell — the cells are the three game markets. A regulation BET marks the
 * moneyline cell, because 60 min lives inside that sheet.
 *
 * The tie on the 3-way regulation market is stored as latest_odds.draw_price.
 * v_latest_odds_all_books does not return that column (measured 2026-10-16),
 * so the tie side is "—" and the sheet says so. Home and away 60-min prices
 * are the h2h_3way rows the view does return.
 */

import { americanToDecimal, formatAmerican } from '@/lib/format';
import {
  BETTABLE_BOOKS,
  LINE_SHOP_BOOKS,
  formatLineValue,
  gameMarketForModel,
  isBettableBook,
  numOrNull,
} from '@/lib/markets';

export const LINES_SPORTS = ['NHL', 'NBA'] as const;
export type LinesSport = (typeof LINES_SPORTS)[number];
export type LinesSportFilter = LinesSport | 'all';

export const LINES_SPORT_CHIPS: readonly { id: LinesSportFilter; label: string }[] = [
  { id: 'NHL', label: 'NHL' },
  { id: 'NBA', label: 'NBA' },
  { id: 'all', label: 'All' },
];

/** Markets the board reads. h2h_3way is the NHL 60-min price, not its own cell. */
export const LINES_ODDS_MARKETS = ['h2h', 'h2h_3way', 'spreads', 'totals'] as const;

export type LinesMarket = 'spreads' | 'h2h' | 'totals';
export type LinesMlMode = 'full' | 'reg';
export type LinesSideKey = 'away' | 'home' | 'over' | 'under' | 'tie';

export const LINES_NO_PRICE = '—';
export const LINES_EMPTY_GAMES = 'No games today';
export const LINES_EMPTY_GAMES_BODY = 'Today’s games show up here once they’re on the board.';
export const LINES_EMPTY_LINES = 'No lines yet';
export const LINES_EMPTY_LINES_BODY = 'Books haven’t posted a spread, moneyline or total for today’s games.';
export const LINES_ERROR_RETRY = 'Try again';
export const LINES_FULL_GAME_NOTE = 'Includes overtime and shootouts.';
export const LINES_REGULATION_NOTE =
  'Pays only if that team leads after 60 minutes. Overtime makes this a loss. The tie has its own price. That price isn’t in this list, so the tie shows as —.';

/** Stack the three markets once Dynamic Type reaches 2×. Below that they share a row. */
export function linesMarketsStack(fontScale: number): boolean {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  return scale >= 2;
}

export function linesMarketLabel(sport: string, market: LinesMarket): string {
  if (market === 'spreads') return sport === 'NHL' ? 'Puck line' : 'Spread';
  if (market === 'h2h') return 'Moneyline';
  return 'Total';
}

export function linesPriceText(price: number | null | undefined): string {
  if (price == null || !Number.isFinite(Number(price))) return LINES_NO_PRICE;
  return formatAmerican(Number(price));
}

export function linesOddsMarket(market: LinesMarket, mode: LinesMlMode): string {
  if (market === 'h2h' && mode === 'reg') return 'h2h_3way';
  return market;
}

/**
 * A snapshot taken after the game starts is not a pre-game price. The evening
 * refresh keeps writing `open` rows after first pitch (CLAUDE.md §6). A missing
 * clock fails open: blanking the card would hide a price we cannot date.
 */
export function pregameSnapshot(
  snapshotAt: string | null | undefined,
  commence: string | null | undefined,
): boolean {
  if (!commence || !snapshotAt) return true;
  const snap = Date.parse(snapshotAt);
  const start = Date.parse(commence);
  if (!Number.isFinite(snap) || !Number.isFinite(start)) return true;
  return snap <= start;
}

export interface LinesOddsRow {
  game_id: string;
  market: string;
  bookmaker: string;
  home_price?: number | string | null;
  away_price?: number | string | null;
  over_price?: number | string | null;
  under_price?: number | string | null;
  spread_home?: number | string | null;
  total_line?: number | string | null;
  home_link?: string | null;
  away_link?: string | null;
  over_link?: string | null;
  under_link?: string | null;
  snapshot_at?: string | null;
}

export interface LinesTeams {
  away: string;
  home: string;
}

export interface LinesSideQuote {
  key: LinesSideKey;
  label: string;
  price: number | null;
  book: string | null;
}

export interface LinesSheetSide {
  key: LinesSideKey;
  label: string;
  price: number | null;
  link: string | null;
}

export interface LinesSheetRow {
  bookmaker: string;
  sides: LinesSheetSide[];
  isBest: boolean;
  betLink: string | null;
  /** The side that betLink opens, price included. Null when the row has no link. */
  betSideLabel: string | null;
}

export interface LinesPickRef {
  game_id: string;
  model_id: string;
  signal_type: string;
  is_live: boolean | null;
  condition_status: string | null;
}

export interface LinesMarks {
  chip: boolean;
  cells: ReadonlySet<LinesMarket>;
}

const MARKETS_ON_CARD: readonly LinesMarket[] = ['spreads', 'h2h', 'totals'];

export function linesCardMarkets(): readonly LinesMarket[] {
  return MARKETS_ON_CARD;
}

export function filterLinesGames<T extends { sport: string }>(
  games: readonly T[],
  sport: LinesSportFilter,
): T[] {
  if (sport === 'all') return [...games];
  return games.filter((g) => g.sport === sport);
}

export function sortLinesGames<T extends { game_id: string; commence_time?: string | null }>(
  games: readonly T[],
): T[] {
  return [...games].sort((a, b) => {
    const ta = Date.parse(a.commence_time ?? '');
    const tb = Date.parse(b.commence_time ?? '');
    const aOk = Number.isFinite(ta);
    const bOk = Number.isFinite(tb);
    if (aOk && bOk && ta !== tb) return ta - tb;
    if (aOk !== bOk) return aOk ? -1 : 1;
    return a.game_id.localeCompare(b.game_id);
  });
}

export function linesHaveOdds(gameIds: readonly string[], odds: readonly { game_id: string }[]): boolean {
  const want = new Set(gameIds);
  return odds.some((r) => want.has(r.game_id));
}

/** All keeps the generic title. A sport chip that hid the other slate says which. */
export function linesEmptyGamesTitle(sport: LinesSportFilter): string {
  if (sport === 'NHL') return 'No NHL games today';
  if (sport === 'NBA') return 'No NBA games today';
  return LINES_EMPTY_GAMES;
}

/**
 * The generic sentence is for an empty slate. When the other sport is already
 * loaded, that sentence would say the games have not been posted.
 */
export function linesEmptyGamesBody(sport: LinesSportFilter, otherSportHasGames: boolean): string {
  if (!otherSportHasGames) return LINES_EMPTY_GAMES_BODY;
  if (sport === 'NHL') return 'NBA games are under NBA.';
  if (sport === 'NBA') return 'NHL games are under NHL.';
  return LINES_EMPTY_GAMES_BODY;
}

export function linesHeaderSubtitle(o: {
  loaded: boolean;
  error: boolean;
  date: string;
  games: number;
  hasOdds: boolean;
  sport?: LinesSportFilter;
}): string {
  if (!o.loaded) return o.error ? 'Lines unavailable' : '—';
  if (o.games === 0) return linesEmptyGamesTitle(o.sport ?? 'all');
  if (!o.hasOdds) return LINES_EMPTY_LINES;
  return `${o.date} · ${o.games} ${o.games === 1 ? 'game' : 'games'}`;
}

/** The number the sheet is comparing, when the market has one. */
export function linesLineCaption(line: number | null, market: LinesMarket): string | null {
  if (line == null || market === 'h2h') return null;
  const shown = market === 'spreads' ? formatLineValue(line, 'spreads') : String(line);
  return `Showing ${shown}, the number most books have.`;
}

/** Game-market cell a model marks, or null for a prop (chip only). */
export function linesCellForModel(modelId: string): LinesMarket | null {
  const market = gameMarketForModel(modelId);
  if (market === 'spreads') return 'spreads';
  if (market === 'totals') return 'totals';
  if (market === 'h2h' || market === 'h2h_3way') return 'h2h';
  return null;
}

/**
 * BET rows only. Live bets are a different price (the Live segment). A
 * DUPLICATE is the extra copy of one event (CLAUDE.md §1c) and is not a
 * second pick. VOID stays: the caller already dropped a void the channel
 * does not still show.
 */
export function linesMarks(picks: readonly LinesPickRef[]): Map<string, LinesMarks> {
  const out = new Map<string, { chip: boolean; cells: Set<LinesMarket> }>();
  for (const p of picks) {
    if (p.signal_type !== 'BET') continue;
    if (p.is_live) continue;
    if (p.condition_status === 'DUPLICATE') continue;
    const cur = out.get(p.game_id) ?? { chip: true, cells: new Set<LinesMarket>() };
    cur.chip = true;
    const cell = linesCellForModel(p.model_id);
    if (cell) cur.cells.add(cell);
    out.set(p.game_id, cur);
  }
  return out;
}

function bookOrder(book: string): number {
  const i = (LINE_SHOP_BOOKS as readonly string[]).indexOf(book);
  return i < 0 ? LINE_SHOP_BOOKS.length : i;
}

function numEq(a: number, b: number): boolean {
  return Math.abs(a - b) < 1e-9;
}

function sideKeys(market: LinesMarket, mode: LinesMlMode): LinesSideKey[] {
  if (market === 'totals') return ['over', 'under'];
  if (market === 'h2h' && mode === 'reg') return ['away', 'tie', 'home'];
  return ['away', 'home'];
}

function lineField(market: LinesMarket): 'spread_home' | 'total_line' | null {
  if (market === 'spreads') return 'spread_home';
  if (market === 'totals') return 'total_line';
  return null;
}

function sideLabel(key: LinesSideKey, teams: LinesTeams, line: number | null, market: LinesMarket): string {
  if (key === 'tie') return 'Tie';
  if (key === 'over') return line == null ? 'Over' : `O ${line}`;
  if (key === 'under') return line == null ? 'Under' : `U ${line}`;
  const team = key === 'home' ? teams.home : teams.away;
  if (market === 'spreads' && line != null) {
    const n = key === 'home' ? line : -line;
    return `${team} ${formatLineValue(n, 'spreads')}`;
  }
  return team;
}

function priceOf(row: LinesOddsRow, key: LinesSideKey): number | null {
  if (key === 'home') return numOrNull(row.home_price);
  if (key === 'away') return numOrNull(row.away_price);
  if (key === 'over') return numOrNull(row.over_price);
  if (key === 'under') return numOrNull(row.under_price);
  return null;
}

function linkOf(row: LinesOddsRow, key: LinesSideKey): string | null {
  if (key === 'home') return row.home_link ?? null;
  if (key === 'away') return row.away_link ?? null;
  if (key === 'over') return row.over_link ?? null;
  if (key === 'under') return row.under_link ?? null;
  return null;
}

/** The line the most bettable books post. Ties go to the earliest shop book. */
export function modalLine(rows: readonly LinesOddsRow[], market: LinesMarket): number | null {
  const field = lineField(market);
  if (!field) return null;
  const counts = new Map<number, number>();
  for (const r of rows) {
    if (!isBettableBook(r.bookmaker)) continue;
    const n = numOrNull(r[field]);
    if (n == null) continue;
    const key = [...counts.keys()].find((k) => numEq(k, n));
    if (key == null) counts.set(n, 1);
    else counts.set(key, (counts.get(key) ?? 0) + 1);
  }
  let best: number | null = null;
  let bestCount = -1;
  let bestRank = LINE_SHOP_BOOKS.length + 1;
  for (const [line, count] of counts) {
    let rank = LINE_SHOP_BOOKS.length;
    for (const r of rows) {
      if (!isBettableBook(r.bookmaker)) continue;
      const n = numOrNull(r[field]);
      if (n == null || !numEq(n, line)) continue;
      rank = Math.min(rank, bookOrder(r.bookmaker));
    }
    if (count > bestCount || (count === bestCount && rank < bestRank)) {
      best = line;
      bestCount = count;
      bestRank = rank;
    }
  }
  return best;
}

/** Bettable, pre-game, and — on a lined market — at the line most books post. */
export function linesRowsFor(
  rows: readonly LinesOddsRow[],
  gameId: string,
  market: LinesMarket,
  mode: LinesMlMode,
  commenceTime: string | null | undefined,
): LinesOddsRow[] {
  const want = linesOddsMarket(market, mode);
  const kept = rows.filter(
    (r) =>
      r.game_id === gameId &&
      r.market === want &&
      isBettableBook(r.bookmaker) &&
      pregameSnapshot(r.snapshot_at, commenceTime),
  );
  const line = modalLine(kept, market);
  const field = lineField(market);
  if (line == null || field == null) return kept;
  return kept.filter((r) => {
    const n = numOrNull(r[field]);
    return n != null && numEq(n, line);
  });
}

function betterPrice(
  price: number,
  book: string,
  best: { price: number; book: string } | null,
): boolean {
  if (best == null) return true;
  const p = americanToDecimal(price);
  const b = americanToDecimal(best.price);
  if (p > b + 1e-12) return true;
  if (Math.abs(p - b) <= 1e-12 && bookOrder(book) < bookOrder(best.book)) return true;
  return false;
}

/** Best bettable price on each side, at the modal line. Books may differ by side. */
export function linesSideQuotes(
  rows: readonly LinesOddsRow[],
  gameId: string,
  market: LinesMarket,
  teams: LinesTeams,
  commenceTime: string | null | undefined,
  mode: LinesMlMode = 'full',
): LinesSideQuote[] {
  const use = linesRowsFor(rows, gameId, market, mode, commenceTime);
  const line = modalLine(use, market);
  return sideKeys(market, mode).map((key) => {
    let best: { book: string; price: number } | null = null;
    for (const r of use) {
      const price = priceOf(r, key);
      if (price == null) continue;
      if (betterPrice(price, r.bookmaker, best)) best = { book: r.bookmaker, price };
    }
    return {
      key,
      label: sideLabel(key, teams, line, market),
      price: best?.price ?? null,
      book: best?.book ?? null,
    };
  });
}

function sideWins(price: number | null, bestDecimal: number | undefined): boolean {
  if (price == null || bestDecimal == null) return false;
  return Math.abs(americanToDecimal(price) - bestDecimal) <= 1e-12;
}

/**
 * One row per bettable book at the modal line. Exactly one row is the best
 * row: the book that holds the best price on the most sides, LINE_SHOP order
 * on a tie. A book with no price still gets a row so the sheet can print "—".
 */
export function linesSheetRows(
  rows: readonly LinesOddsRow[],
  gameId: string,
  market: LinesMarket,
  teams: LinesTeams,
  commenceTime: string | null | undefined,
  mode: LinesMlMode = 'full',
): LinesSheetRow[] {
  const use = linesRowsFor(rows, gameId, market, mode, commenceTime);
  const line = modalLine(use, market);
  const keys = sideKeys(market, mode);
  const byBook = new Map<string, LinesOddsRow>();
  for (const r of use) {
    if (!byBook.has(r.bookmaker)) byBook.set(r.bookmaker, r);
  }
  const draft = [...byBook.entries()].map(([bookmaker, r]) => ({
    bookmaker,
    sides: keys.map((key) => ({
      key,
      label: sideLabel(key, teams, line, market),
      price: priceOf(r, key),
      link: linkOf(r, key),
    })),
  }));
  const bestDecimal = new Map<LinesSideKey, number>();
  for (const row of draft) {
    for (const s of row.sides) {
      if (s.price == null) continue;
      const p = americanToDecimal(s.price);
      const cur = bestDecimal.get(s.key);
      if (cur == null || p > cur) bestDecimal.set(s.key, p);
    }
  }
  let topScore = 0;
  let topBook = '';
  for (const row of draft) {
    let score = 0;
    for (const s of row.sides) {
      if (sideWins(s.price, bestDecimal.get(s.key))) score += 1;
    }
    const better =
      score > topScore ||
      (score === topScore && score > 0 && (topBook === '' || bookOrder(row.bookmaker) < bookOrder(topBook)));
    if (better) {
      topScore = score;
      topBook = row.bookmaker;
    }
  }
  const marked: LinesSheetRow[] = draft.map((row) => {
    const isBest = topScore > 0 && row.bookmaker === topBook;
    const winning = row.sides.find((s) => s.link && sideWins(s.price, bestDecimal.get(s.key)));
    const any = row.sides.find((s) => s.link);
    const betSide = winning ?? any ?? null;
    const betSideLabel = betSide
      ? `${betSide.label}${betSide.price == null ? '' : ` ${linesPriceText(betSide.price)}`}`
      : null;
    return { ...row, isBest, betLink: betSide?.link ?? null, betSideLabel };
  });
  marked.sort((a, b) => Number(b.isBest) - Number(a.isBest) || bookOrder(a.bookmaker) - bookOrder(b.bookmaker));
  return marked;
}

/** Reference-only books never reach the board. Pinned so a list edit is visible. */
export function linesBettableBooks(): readonly string[] {
  return BETTABLE_BOOKS;
}
