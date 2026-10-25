/**
 * Pure BYOM record math. No network. Screens rank and preview from this.
 *
 * Units are the backtest's 1u-to-win profit. ROI needs the amount risked.
 * This file does not estimate a price, and it does not read a count of
 * bets the backtest left out.
 */

import { byomFilters, type ByomFilters } from './byomFilters';

/** Same bound as byom.constants.DK_HISTORY_START_SEASON. */
export const BYOM_NFL_FIRST_SEASON = 2020;

export const BYOM_UNITS_COPY =
  'u = units. Each bet is 1u to win at the DraftKings price at game start (or the closest DraftKings price). A push returns the stake. Win/loss only, no line locks.';

export type ByomSeasonScope = 'all' | 'current';

export type ByomGameMarket = 'h2h' | 'spreads' | 'totals';

export interface ByomDraft {
  market: ByomGameMarket;
  side: 'home' | 'away' | null;
  role: 'favorite' | 'underdog' | 'pickem' | null;
  /** null is any game. true is primetime only. false is the other kickoffs. */
  primetime: boolean | null;
}

export interface ByomCountedRow {
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  ties: number;
  /** Null when the row did not carry units. Zero is a real zero. */
  units: number | null;
  /** Null when the row did not carry the amount risked. ROI stays unset. */
  risked: number | null;
}

export interface ByomRecord {
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  ties: number;
  units: number | null;
  risked: number | null;
}

const GAME_MARKETS = new Set<string>(['h2h', 'spreads', 'totals']);

const MARKET_LABEL: Record<ByomGameMarket, string> = {
  h2h: 'Moneyline',
  spreads: 'Spread',
  totals: 'Over/Under',
};

export function currentNflSeason(now: Date = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: 'numeric',
  }).formatToParts(now);
  const year = Number(parts.find((p) => p.type === 'year')?.value);
  const month = Number(parts.find((p) => p.type === 'month')?.value);
  if (!Number.isFinite(year) || !Number.isFinite(month)) {
    throw new Error('NFL season clock');
  }
  return month >= 9 ? year : year - 1;
}

/** 2020 through the current NFL season, inclusive. */
export function nflSeasonList(now: Date = new Date()): number[] {
  const end = currentNflSeason(now);
  const seasons: number[] = [];
  for (let year = BYOM_NFL_FIRST_SEASON; year <= end; year += 1) seasons.push(year);
  return seasons;
}

export function isWholeSeason(filters: ByomFilters | null | undefined): boolean {
  return Object.keys(byomFilters(filters)).length === 0;
}

/** Game markets only. An empty market list is every market, including props. */
export function showsUnits(filters: ByomFilters | null | undefined): boolean {
  const markets = byomFilters(filters).markets;
  if (markets == null || markets.length === 0) return false;
  return markets.every((market) => GAME_MARKETS.has(market));
}

export function gameMarket(filters: ByomFilters | null | undefined): ByomGameMarket | null {
  const markets = byomFilters(filters).markets;
  if (markets?.length !== 1) return null;
  const market = markets[0];
  if (market === 'h2h' || market === 'spreads' || market === 'totals') return market;
  return null;
}

export function marketLabel(filters: ByomFilters | null | undefined): string {
  const markets = byomFilters(filters).markets;
  if (markets == null || markets.length === 0) return '—';
  const parts: string[] = [];
  let props = false;
  for (const market of markets) {
    if (market === 'h2h' || market === 'spreads' || market === 'totals') {
      parts.push(MARKET_LABEL[market]);
    } else {
      props = true;
    }
  }
  if (props) parts.push('Props');
  return parts.length > 0 ? parts.join(' · ') : '—';
}

export function recordFromRows(rows: readonly ByomCountedRow[]): ByomRecord {
  let bets = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let ties = 0;
  let units = 0;
  let unitsKnown = true;
  let risked = 0;
  let riskedKnown = true;
  for (const row of rows) {
    bets += row.bets;
    wins += row.wins;
    losses += row.losses;
    pushes += row.pushes;
    ties += row.ties;
    if (row.units == null || !Number.isFinite(row.units)) unitsKnown = false;
    else units += row.units;
    if (row.risked == null || !Number.isFinite(row.risked)) riskedKnown = false;
    else risked += row.risked;
  }
  return {
    bets,
    wins,
    losses,
    pushes,
    ties,
    units: unitsKnown ? units : null,
    risked: riskedKnown ? risked : null,
  };
}

/** Wins over wins and losses. Pushes and ties are not decided. */
export function byomWinRate(record: ByomRecord): number | null {
  const decided = record.wins + record.losses;
  if (decided <= 0) return null;
  return record.wins / decided;
}

/** Profit over the amount risked. Null when the stake was not returned. */
export function byomRoi(record: ByomRecord): number | null {
  if (record.units == null || record.risked == null || !(record.risked > 0)) return null;
  return record.units / record.risked;
}

/** W–L–P. Ties sit in the third count with pushes; both return the stake. */
export function formatByomRecord(record: ByomRecord): string {
  return `${record.wins}\u2013${record.losses}\u2013${record.pushes + record.ties}`;
}

export function filtersForDraft(draft: ByomDraft, base: ByomFilters = {}): ByomFilters {
  const next: ByomFilters = { ...base, markets: [draft.market] };
  if (draft.market === 'totals') {
    delete next.side;
    delete next.role;
  } else if (draft.side) {
    next.side = draft.side;
  } else {
    delete next.side;
  }
  if (draft.market !== 'totals') {
    if (draft.role) next.role = draft.role;
    else delete next.role;
  }
  if (draft.primetime == null) delete next.primetime;
  else next.primetime = draft.primetime;
  return byomFilters(next);
}

export function draftFromFilters(filters: ByomFilters | null | undefined): ByomDraft | null {
  const market = gameMarket(filters);
  if (market == null) return null;
  const parsed = byomFilters(filters);
  return {
    market,
    side: market === 'totals' ? null : (parsed.side ?? null),
    role: market === 'totals' ? null : (parsed.role ?? null),
    primetime: parsed.primetime ?? null,
  };
}

/**
 * Another saved model with this name, after trim. The save matches the
 * stored name exactly, so a different case is a different name. The model
 * being edited is not a collision with itself.
 */
export function otherModelWithName<T extends { model_id: string; name: string }>(
  models: readonly T[],
  name: string,
  exceptId?: string,
): T | null {
  const trimmed = name.trim();
  for (const model of models) {
    if (model.name === trimmed && model.model_id !== exceptId) return model;
  }
  return null;
}

export function suggestedName(draft: ByomDraft): string {
  if (draft.market === 'totals') {
    return draft.primetime === true ? 'Primetime over/under' : 'Over/under';
  }
  const bits: string[] = [];
  if (draft.primetime === true) bits.push('Primetime');
  if (draft.side === 'home') bits.push('Home');
  else if (draft.side === 'away') bits.push('Away');
  if (draft.role === 'favorite') bits.push('Favorites');
  else if (draft.role === 'underdog') bits.push('Underdogs');
  else if (draft.role === 'pickem') bits.push('Pick’ems');
  if (bits.length === 0) return MARKET_LABEL[draft.market];
  const [first, ...rest] = bits;
  return [first, ...rest.map((word) => word.toLowerCase())].join(' ');
}

export interface Rankable {
  id: string;
  name: string;
  bets: number;
  units: number | null;
  showsUnits: boolean;
}

function byName(a: Rankable, b: Rankable): number {
  const name = a.name.localeCompare(b.name);
  if (name !== 0) return name;
  return a.id.localeCompare(b.id);
}

/**
 * Models with a real unit total rank first, highest units first.
 * A model whose units are hidden (props, or units missing) ranks after those.
 * Zero included bets are unranked and sort last.
 */
export function rankByUnits<T extends Rankable>(items: readonly T[]): Array<T & { rank: number | null }> {
  const withBets: T[] = [];
  const without: T[] = [];
  for (const item of items) {
    if (item.bets > 0) withBets.push(item);
    else without.push(item);
  }
  const real = (item: T) => item.showsUnits && item.units != null && Number.isFinite(item.units);
  withBets.sort((a, b) => {
    const ar = real(a);
    const br = real(b);
    if (ar !== br) return ar ? -1 : 1;
    if (ar && br && a.units !== b.units) return (b.units as number) - (a.units as number);
    if (!ar && a.bets !== b.bets) return b.bets - a.bets;
    return byName(a, b);
  });
  without.sort(byName);
  return [
    ...withBets.map((item, index) => ({ ...item, rank: index + 1 })),
    ...without.map((item) => ({ ...item, rank: null })),
  ];
}
