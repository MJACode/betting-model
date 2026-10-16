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
 * The tie on the 3-way regulation market is latest_odds.draw_price. The view
 * does not return that column until the hand-applied migration
 * add_draw_price_to_latest_odds_view_2026_10_16.sql. Until a row actually
 * carries draw_price, the sheet hides the tie. Home and away 60-min prices
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
export const LINES_GAME_UNPRICED = 'No lines posted yet';
export const LINES_PAUSED_CHIP = 'Paused pick';
export const LINES_CELL_HINT = 'Opens every book’s price';
/** Unicode minus. formatAmerican and formatLineValue print an ASCII hyphen. */
export const LINES_MINUS = '\u2212';
export const LINES_FULL_GAME_NOTE = 'Includes overtime and shootouts.';
export const LINES_REGULATION_NOTE =
  'Pays only if that team leads after 60 minutes. Overtime counts as a loss. The tie price isn’t shown yet.';
export const LINES_REGULATION_NOTE_PRICED =
  'Pays only if that team leads after 60 minutes. Overtime counts as a loss.';

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

/** ASCII hyphen to U+2212, so a negative price is a minus and not a dash. */
export function linesMinus(text: string): string {
  return text.replace(/-/g, LINES_MINUS);
}

export function linesPriceText(price: number | null | undefined): string {
  if (price == null || !Number.isFinite(Number(price))) return LINES_NO_PRICE;
  return linesMinus(formatAmerican(Number(price)));
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
  draw_price?: number | string | null;
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
  /** Combined label. VoiceOver and the sheet use this. */
  label: string;
  /** Team, or the short total. The card clips this line, not the number. */
  name: string;
  /** Signed spread, drawn under the team on the card. Null for moneyline and total. */
  lineText: string | null;
  price: number | null;
  book: string | null;
}

export interface LinesSheetSide {
  key: LinesSideKey;
  label: string;
  price: number | null;
  link: string | null;
  /** This price is the best on its side. A row can win one side and lose the other. */
  isBestPrice: boolean;
}

export interface LinesSheetRow {
  bookmaker: string;
  sides: LinesSheetSide[];
  /** True only when this book wins every side. A split is not a best row. */
  isBest: boolean;
}

export interface LinesPickRef {
  game_id: string;
  model_id: string;
  signal_type: string;
  is_live: boolean | null;
  condition_status: string | null;
  pick_id?: number;
  pick_label?: string;
}

export interface LinesMarkPick {
  pickId: number;
  label: string;
}

export interface LinesMarks {
  chip: boolean;
  cells: ReadonlySet<LinesMarket>;
  picks: LinesMarkPick[];
  paused: LinesMarkPick[];
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

/** '2026-10-16' → 'Friday'. Noon UTC, so the calendar day does not shift. */
export function linesWeekday(date: string): string {
  const d = new Date(`${date}T12:00:00Z`);
  if (Number.isNaN(d.getTime())) return date;
  return new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', weekday: 'long' }).format(d);
}

export function linesPickChipLabel(n: number): string {
  return `${n} ${n === 1 ? 'pick' : 'picks'}`;
}

export function linesPausedChipLabel(n: number): string {
  return n === 1 ? LINES_PAUSED_CHIP : `${n} paused picks`;
}

/** 'Friday · 3 NHL games · 2 NBA games'. Sports with no games are left out. */
export function linesHeaderCount(date: string, games: readonly { sport: string }[]): string {
  const parts: string[] = [];
  for (const sport of ['NHL', 'NBA'] as const) {
    const n = games.filter((g) => g.sport === sport).length;
    if (n > 0) parts.push(`${n} ${sport} ${n === 1 ? 'game' : 'games'}`);
  }
  const other = games.length - parts.reduce((sum, part) => sum + Number(part.split(' ')[0]), 0);
  if (other > 0) parts.push(`${other} ${other === 1 ? 'game' : 'games'}`);
  return `${linesWeekday(date)} · ${parts.join(' · ')}`;
}

export function linesHeaderSubtitle(o: {
  loaded: boolean;
  error: boolean;
  date: string;
  games: readonly { sport: string }[];
  hasOdds: boolean;
  sport?: LinesSportFilter;
}): string {
  if (!o.loaded) return o.error ? 'Lines unavailable' : '—';
  if (o.games.length === 0) return linesEmptyGamesTitle(o.sport ?? 'all');
  if (!o.hasOdds) return LINES_EMPTY_LINES;
  return linesHeaderCount(o.date, o.games);
}

/**
 * The number the sheet is comparing, without the home-team sign.
 * 'Puck line 1.5 · the line most books post'.
 */
export function linesLineCaption(line: number | null, market: LinesMarket, sport: string): string | null {
  if (line == null || market === 'h2h') return null;
  const name = linesMarketLabel(sport, market);
  return `${name} ${String(Math.abs(line))} · the line most books post`;
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
function qualifyingBet(p: LinesPickRef): boolean {
  return p.signal_type === 'BET' && !p.is_live && p.condition_status !== 'DUPLICATE';
}

function markPick(p: LinesPickRef): LinesMarkPick | null {
  if (p.pick_id == null) return null;
  return { pickId: p.pick_id, label: p.pick_label?.trim() || 'Pick' };
}

/**
 * Active BETs mark the card and the market cell. Paused BETs are a separate
 * grey chip and never a navy dot — a paused number is not a pick to place.
 */
export function linesMarks(
  picks: readonly LinesPickRef[],
  paused: readonly LinesPickRef[] = [],
): Map<string, LinesMarks> {
  const out = new Map<string, { chip: boolean; cells: Set<LinesMarket>; picks: LinesMarkPick[]; paused: LinesMarkPick[] }>();
  const ensure = (gameId: string) => {
    const cur = out.get(gameId) ?? { chip: false, cells: new Set<LinesMarket>(), picks: [], paused: [] };
    out.set(gameId, cur);
    return cur;
  };
  for (const p of picks) {
    if (!qualifyingBet(p)) continue;
    const cur = ensure(p.game_id);
    cur.chip = true;
    const listed = markPick(p);
    if (listed) cur.picks.push(listed);
    const cell = linesCellForModel(p.model_id);
    if (cell) cur.cells.add(cell);
  }
  for (const p of paused) {
    if (!qualifyingBet(p)) continue;
    const cur = ensure(p.game_id);
    const listed = markPick(p);
    if (listed) cur.paused.push(listed);
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

function sideKeys(market: LinesMarket, mode: LinesMlMode, showTie: boolean): LinesSideKey[] {
  if (market === 'totals') return ['over', 'under'];
  if (market === 'h2h' && mode === 'reg' && showTie) return ['away', 'tie', 'home'];
  return ['away', 'home'];
}

function rowsIncludeTie(rows: readonly LinesOddsRow[]): boolean {
  return rows.some((r) => numOrNull(r.draw_price) != null);
}

function lineField(market: LinesMarket): 'spread_home' | 'total_line' | null {
  if (market === 'spreads') return 'spread_home';
  if (market === 'totals') return 'total_line';
  return null;
}

function sideName(key: LinesSideKey, teams: LinesTeams, line: number | null): string {
  if (key === 'tie') return 'Tie';
  if (key === 'over') return line == null ? 'Over' : `O ${line}`;
  if (key === 'under') return line == null ? 'Under' : `U ${line}`;
  return key === 'home' ? teams.home : teams.away;
}

function spreadLineText(key: LinesSideKey, line: number | null, market: LinesMarket): string | null {
  if (market !== 'spreads' || line == null || (key !== 'home' && key !== 'away')) return null;
  const n = key === 'home' ? line : -line;
  return linesMinus(formatLineValue(n, 'spreads'));
}

function sideLabel(key: LinesSideKey, teams: LinesTeams, line: number | null, market: LinesMarket): string {
  const name = sideName(key, teams, line);
  const signed = spreadLineText(key, line, market);
  return signed ? `${name} ${signed}` : name;
}

function priceOf(row: LinesOddsRow, key: LinesSideKey): number | null {
  if (key === 'home') return numOrNull(row.home_price);
  if (key === 'away') return numOrNull(row.away_price);
  if (key === 'over') return numOrNull(row.over_price);
  if (key === 'under') return numOrNull(row.under_price);
  if (key === 'tie') return numOrNull(row.draw_price);
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
  return sideKeys(market, mode, rowsIncludeTie(use)).map((key) => {
    let best: { book: string; price: number } | null = null;
    for (const r of use) {
      const price = priceOf(r, key);
      if (price == null) continue;
      if (betterPrice(price, r.bookmaker, best)) best = { book: r.bookmaker, price };
    }
    return {
      key,
      label: sideLabel(key, teams, line, market),
      name: sideName(key, teams, line),
      lineText: spreadLineText(key, line, market),
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
 * One row per bettable book at the modal line. A row is Best only when it
 * wins every side. Two books that tie on every side would both qualify;
 * the earlier LINE_SHOP_BOOKS rank is the one Best row. Green is per price
 * (`isBestPrice`), including a tied price, so a book that wins one side
 * does not paint the other side green. Each side keeps its own link.
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
  const keys = sideKeys(market, mode, rowsIncludeTie(use));
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
  const marked: LinesSheetRow[] = draft.map((row) => {
    const sides = row.sides.map((s) => ({
      ...s,
      isBestPrice: sideWins(s.price, bestDecimal.get(s.key)),
    }));
    const pricedSides = sides.filter((s) => bestDecimal.has(s.key));
    const isBest = pricedSides.length > 0 && pricedSides.every((s) => s.isBestPrice);
    return { bookmaker: row.bookmaker, sides, isBest };
  });
  const winners = marked.filter((r) => r.isBest);
  if (winners.length > 1) {
    const sole = winners.reduce((best, row) => {
      const byShop = bookOrder(row.bookmaker) - bookOrder(best.bookmaker);
      if (byShop !== 0) return byShop < 0 ? row : best;
      return row.bookmaker < best.bookmaker ? row : best;
    });
    for (const row of marked) row.isBest = row.bookmaker === sole.bookmaker;
  }
  marked.sort((a, b) => Number(b.isBest) - Number(a.isBest) || bookOrder(a.bookmaker) - bookOrder(b.bookmaker));
  return marked;
}

/** Reference-only books never reach the board. Pinned so a list edit is visible. */
export function linesBettableBooks(): readonly string[] {
  return BETTABLE_BOOKS;
}
