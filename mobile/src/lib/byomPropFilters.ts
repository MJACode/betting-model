/**
 * Phase A prop filters. The builder keeps one market. These keys narrow
 * that market. Staking stays 1u to win at the stored DraftKings price.
 *
 * Short week is rest_days <= 6 (the team-stats board). Off a bye is
 * rest_days >= 12 (the NFL feature cut). A first game has no rest and
 * matches neither. Prime time on a new prop model is kickoff at 7pm ET
 * or later. A saved model that still has primetime true keeps that flag
 * until the time control is changed.
 */

import type { ByomFilters } from './byomFilters';

const MINUS = '\u2212';

export type ByomKickSlot = 'early' | 'late' | 'prime';
export type ByomPriceBand = 'plus' | 'mid' | 'heavy' | 'custom';
export type ByomSportId = 'NFL' | 'NBA' | 'NHL';
export type ByomLineMove = 'toward' | 'against' | 'none';
export type ByomPrevResult = 'won' | 'lost';
export type ByomPrevAts = 'covered' | 'not_covered';
export type ByomPrevTotal = 'over' | 'under';

export interface ByomBand {
  min: number;
  max: number;
}

export interface LineScale {
  step: number;
  min: number;
  max: number;
  unit: string;
  openFrom: number;
  openTo: number;
}

export interface ByomPropFilterState {
  lineBand: ByomBand | null;
  priceBand: ByomPriceBand | null;
  priceCustom: ByomBand | null;
  months: number[];
  weekdays: number[];
  kickSlots: ByomKickSlot[];
  opponents: string[];
  player: string | null;
  shortWeek: boolean;
  offBye: boolean;
  /** Trend filters (Matt, 2026-11-05). Null is Any. */
  lineMove: ByomLineMove | null;
  prevResult: ByomPrevResult | null;
  prevAts: ByomPrevAts | null;
  prevTotal: ByomPrevTotal | null;
  division: boolean | null;
}

export const EMPTY_PROP_FILTERS: ByomPropFilterState = {
  lineBand: null,
  priceBand: null,
  priceCustom: null,
  months: [],
  weekdays: [],
  kickSlots: [],
  opponents: [],
  player: null,
  shortWeek: false,
  offBye: false,
  lineMove: null,
  prevResult: null,
  prevAts: null,
  prevTotal: null,
  division: null,
};

export interface FilterSummary {
  detail: string;
  pills: string[];
}

const ANY: FilterSummary = { detail: 'Any', pills: ['Any'] };

/** Example defaults from the Phase A boards. Not a measured line distribution. */
const LINE_SCALES: Record<string, LineScale> = {
  player_pass_yds: { step: 5, min: 150.5, max: 349.5, unit: 'yds', openFrom: 200.5, openTo: 274.5 },
  player_rush_yds: { step: 5, min: 10.5, max: 149.5, unit: 'yds', openFrom: 40.5, openTo: 89.5 },
  player_reception_yds: { step: 5, min: 10.5, max: 149.5, unit: 'yds', openFrom: 30.5, openTo: 79.5 },
  player_rush_reception_yds: { step: 5, min: 20.5, max: 199.5, unit: 'yds', openFrom: 40.5, openTo: 99.5 },
  player_receptions: { step: 1, min: 1.5, max: 10.5, unit: 'rec', openFrom: 3.5, openTo: 5.5 },
  player_pass_attempts: { step: 1, min: 20.5, max: 49.5, unit: 'att', openFrom: 27.5, openTo: 35.5 },
  player_pass_completions: { step: 1, min: 15.5, max: 39.5, unit: 'cmp', openFrom: 20.5, openTo: 28.5 },
  player_pass_tds: { step: 0.5, min: 0.5, max: 3.5, unit: 'TD', openFrom: 0.5, openTo: 1.5 },
  player_rush_attempts: { step: 0.5, min: 4.5, max: 24.5, unit: 'att', openFrom: 8.5, openTo: 16.5 },
  player_tackles_assists: { step: 0.5, min: 2.5, max: 14.5, unit: 'tkl', openFrom: 4.5, openTo: 8.5 },
  player_sacks: { step: 0.5, min: 0.5, max: 2.5, unit: 'sacks', openFrom: 0.5, openTo: 1.5 },
  player_points: { step: 0.5, min: 8.5, max: 40.5, unit: 'pts', openFrom: 15.5, openTo: 25.5 },
  player_rebounds: { step: 0.5, min: 1.5, max: 18.5, unit: 'reb', openFrom: 4.5, openTo: 10.5 },
  player_assists: { step: 0.5, min: 1.5, max: 15.5, unit: 'ast', openFrom: 3.5, openTo: 8.5 },
  player_threes: { step: 0.5, min: 0.5, max: 8.5, unit: '3s', openFrom: 1.5, openTo: 3.5 },
  player_points_rebounds_assists: { step: 0.5, min: 15.5, max: 55.5, unit: 'pts', openFrom: 25.5, openTo: 40.5 },
  player_points_rebounds: { step: 0.5, min: 12.5, max: 45.5, unit: 'pts', openFrom: 20.5, openTo: 32.5 },
  player_points_assists: { step: 0.5, min: 12.5, max: 45.5, unit: 'pts', openFrom: 20.5, openTo: 32.5 },
  player_rebounds_assists: { step: 0.5, min: 6.5, max: 25.5, unit: '', openFrom: 10.5, openTo: 16.5 },
  player_blocks: { step: 0.5, min: 0.5, max: 5.5, unit: 'blk', openFrom: 0.5, openTo: 1.5 },
  player_steals: { step: 0.5, min: 0.5, max: 4.5, unit: 'stl', openFrom: 0.5, openTo: 1.5 },
  player_blocks_steals: { step: 0.5, min: 0.5, max: 6.5, unit: '', openFrom: 1.5, openTo: 3.5 },
  player_turnovers: { step: 0.5, min: 0.5, max: 6.5, unit: 'to', openFrom: 1.5, openTo: 3.5 },
};

export function lineScale(market: string | null | undefined): LineScale | null {
  if (market == null) return null;
  return LINE_SCALES[market] ?? null;
}

export function openBand(scale: LineScale): ByomBand {
  return { min: scale.openFrom, max: scale.openTo };
}

const PRICE_STEP = 5;
const PRICE_MIN = -500;
const PRICE_MAX = 500;

export function openPriceBand(): ByomBand {
  return { min: -150, max: -110 };
}

export function formatLineNumber(value: number): string {
  const rounded = Math.round(value * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

export function formatAmericanBand(price: number): string {
  const rounded = Math.round(price);
  if (rounded > 0) return `+${rounded}`;
  if (rounded < 0) return `${MINUS}${Math.abs(rounded)}`;
  return '0';
}

function roundToStep(value: number, step: number): number {
  const units = Math.round(value / step);
  return Math.round(units * step * 1000) / 1000;
}

export function moveBand(band: ByomBand, edge: 'min' | 'max', dir: 1 | -1, scale: LineScale): ByomBand {
  const next = roundToStep(band[edge] + dir * scale.step, scale.step);
  if (next < scale.min || next > scale.max) return band;
  if (edge === 'min' && next > band.max) return band;
  if (edge === 'max' && next < band.min) return band;
  return { ...band, [edge]: next };
}

export function stepAmerican(price: number, dir: 1 | -1): number {
  let next = price + dir * PRICE_STEP;
  if (next > -100 && next < 100) next = dir > 0 ? 100 : -100;
  if (next < PRICE_MIN) return PRICE_MIN;
  if (next > PRICE_MAX) return PRICE_MAX;
  return next;
}

export function movePrice(band: ByomBand, edge: 'min' | 'max', dir: 1 | -1): ByomBand {
  const next = stepAmerican(band[edge], dir);
  if (next === band[edge]) return band;
  if (edge === 'min' && next > band.max) return band;
  if (edge === 'max' && next < band.min) return band;
  return { ...band, [edge]: next };
}

export function canMoveBand(band: ByomBand, edge: 'min' | 'max', dir: 1 | -1, scale: LineScale): boolean {
  const moved = moveBand(band, edge, dir, scale);
  return moved.min !== band.min || moved.max !== band.max;
}

export function canMovePrice(band: ByomBand, edge: 'min' | 'max', dir: 1 | -1): boolean {
  const moved = movePrice(band, edge, dir);
  return moved.min !== band.min || moved.max !== band.max;
}

export const NFL_MONTHS: readonly { value: number; label: string }[] = [
  { value: 9, label: 'Sep' },
  { value: 10, label: 'Oct' },
  { value: 11, label: 'Nov' },
  { value: 12, label: 'Dec' },
  { value: 1, label: 'Jan' },
];

export const NBA_MONTHS: readonly { value: number; label: string }[] = [
  { value: 10, label: 'Oct' },
  { value: 11, label: 'Nov' },
  { value: 12, label: 'Dec' },
  { value: 1, label: 'Jan' },
  { value: 2, label: 'Feb' },
  { value: 3, label: 'Mar' },
  { value: 4, label: 'Apr' },
  { value: 5, label: 'May' },
  { value: 6, label: 'Jun' },
];

export const NFL_DAYS: readonly { value: number; label: string }[] = [
  { value: 4, label: 'Thu' },
  { value: 0, label: 'Sun' },
  { value: 1, label: 'Mon' },
  { value: 6, label: 'Sat' },
];

export const NBA_DAYS: readonly { value: number; label: string }[] = [
  { value: 0, label: 'Sun' },
  { value: 1, label: 'Mon' },
  { value: 2, label: 'Tue' },
  { value: 3, label: 'Wed' },
  { value: 4, label: 'Thu' },
  { value: 5, label: 'Fri' },
  { value: 6, label: 'Sat' },
];

export const KICK_SLOTS: readonly { value: ByomKickSlot; label: string; pill: string }[] = [
  { value: 'early', label: 'Early (1 PM)', pill: 'Early' },
  { value: 'late', label: 'Late (4 PM)', pill: 'Late' },
  { value: 'prime', label: 'Primetime (night)', pill: 'Primetime' },
];

export function monthsFor(sport: ByomSportId) {
  return sport === 'NFL' ? NFL_MONTHS : NBA_MONTHS;
}

export function daysFor(sport: ByomSportId) {
  return sport === 'NFL' ? NFL_DAYS : NBA_DAYS;
}

export function shownKickSlots(
  slots: readonly ByomKickSlot[],
  primetime: boolean | null,
): ByomKickSlot[] {
  if (primetime === true && !slots.includes('prime')) return [...slots, 'prime'];
  return [...slots];
}

export function primeOn(slots: readonly ByomKickSlot[], primetime: boolean | null): boolean {
  return shownKickSlots(slots, primetime).includes('prime');
}

export function withPrime(
  slots: readonly ByomKickSlot[],
  primetime: boolean | null,
  on: boolean,
): { kickSlots: ByomKickSlot[]; primetime: null } {
  const base = shownKickSlots(slots, primetime).filter((slot) => slot !== 'prime');
  return {
    kickSlots: on ? [...base, 'prime'] : base,
    primetime: null,
  };
}

export function withKickSlots(slots: readonly ByomKickSlot[]): { kickSlots: ByomKickSlot[]; primetime: null } {
  return { kickSlots: [...slots], primetime: null };
}

/** Empty means Any. Choosing every option collapses back to Any. */
export function toggleMember<T>(selected: readonly T[], value: T, all: readonly T[]): T[] {
  if (selected.length === 0) return [value];
  if (selected.includes(value)) return selected.filter((item) => item !== value);
  const next = [...selected, value];
  if (all.every((item) => next.includes(item))) return [];
  return next;
}

/** A prop keeps its rest chips (they sit on step 2); a game bet's are in the sheet. */
export function resetSheetFilters(state: ByomPropFilterState, prop = true): ByomPropFilterState {
  return {
    ...EMPTY_PROP_FILTERS,
    shortWeek: prop ? state.shortWeek : false,
    offBye: prop ? state.offBye : false,
    kickSlots: state.kickSlots.includes('prime') ? ['prime'] : [],
  };
}

export const PRICE_CHOICES: readonly { value: ByomPriceBand | 'any'; label: string }[] = [
  { value: 'any', label: 'Any' },
  { value: 'plus', label: 'Plus money (+100 or more)' },
  { value: 'mid', label: `${MINUS}100 to ${MINUS}130` },
  { value: 'heavy', label: `Heavy juice (${MINUS}131 or more)` },
  { value: 'custom', label: 'Custom' },
];

function labelsInOrder(
  selected: readonly number[],
  options: readonly { value: number; label: string }[],
): string[] {
  return options.filter((option) => selected.includes(option.value)).map((option) => option.label);
}

function joinShort(labels: readonly string[]): string {
  if (labels.length === 2) return `${labels[0]}\u2013${labels[1]}`;
  return labels.join(', ');
}

export function oddsSummary(state: ByomPropFilterState): FilterSummary {
  const bits: { detail: string; pill: string }[] = [];
  if (state.lineBand) {
    const text = `Line ${formatLineNumber(state.lineBand.min)}\u2013${formatLineNumber(state.lineBand.max)}`;
    bits.push({ detail: text, pill: text });
  }
  if (state.priceBand === 'plus') bits.push({ detail: 'Plus money', pill: '+100 or more' });
  else if (state.priceBand === 'mid') {
    const text = `${MINUS}100 to ${MINUS}130`;
    bits.push({ detail: text, pill: text });
  } else if (state.priceBand === 'heavy') {
    bits.push({ detail: 'Heavy juice', pill: `${MINUS}131 or more` });
  } else if (state.priceBand === 'custom' && state.priceCustom) {
    const text = `${formatAmericanBand(state.priceCustom.min)} to ${formatAmericanBand(state.priceCustom.max)}`;
    bits.push({ detail: text, pill: text });
  }
  if (bits.length === 0) return ANY;
  return { detail: bits.map((bit) => bit.detail).join(' · '), pills: bits.map((bit) => bit.pill) };
}

export function timeSummary(
  state: ByomPropFilterState,
  sport: ByomSportId,
  slots: readonly ByomKickSlot[],
): FilterSummary {
  const bits: { detail: string; pills: string[] }[] = [];
  const months = labelsInOrder(state.months, monthsFor(sport));
  if (months.length > 0) bits.push({ detail: joinShort(months), pills: months });
  const days = labelsInOrder(state.weekdays, daysFor(sport));
  if (days.length > 0) bits.push({ detail: joinShort(days), pills: days });
  if (sport === 'NFL' && slots.length > 0) {
    const labels = KICK_SLOTS.filter((slot) => slots.includes(slot.value)).map((slot) => slot.pill);
    if (labels.length > 0) bits.push({ detail: joinShort(labels), pills: labels });
  }
  if (bits.length === 0) return ANY;
  return {
    detail: bits.map((bit) => bit.detail).join(' · '),
    pills: bits.flatMap((bit) => bit.pills),
  };
}

export function matchupSummary(
  side: 'home' | 'away' | 'over' | 'under' | null,
  state: ByomPropFilterState,
): FilterSummary {
  const bits: { detail: string; pill: string }[] = [];
  if (side === 'home' || side === 'away') {
    const label = side === 'home' ? 'Home' : 'Away';
    bits.push({ detail: label, pill: label });
  }
  if (state.opponents.length > 0) {
    const abbrevs = [...state.opponents].sort();
    bits.push({
      detail: abbrevs.length === 1 ? `vs ${abbrevs[0]}` : `${abbrevs.length} opponents`,
      pill: `vs ${abbrevs.join(', ')}`,
    });
  }
  if (state.player) bits.push({ detail: state.player, pill: state.player });
  if (bits.length === 0) return ANY;
  return { detail: bits.map((bit) => bit.detail).join(' · '), pills: bits.map((bit) => bit.pill) };
}

export const LINE_MOVE_CHOICES: readonly { value: ByomLineMove; label: string }[] = [
  { value: 'toward', label: 'Moved toward this side' },
  { value: 'against', label: 'Moved away from this side' },
  { value: 'none', label: 'Didn\u2019t move' },
];
export const PREV_RESULT_CHOICES: readonly { value: ByomPrevResult; label: string }[] = [
  { value: 'won', label: 'Off a win' },
  { value: 'lost', label: 'Off a loss' },
];
export const PREV_ATS_CHOICES: readonly { value: ByomPrevAts; label: string }[] = [
  { value: 'covered', label: 'Covered' },
  { value: 'not_covered', label: 'Didn\u2019t cover' },
];
export const PREV_TOTAL_CHOICES: readonly { value: ByomPrevTotal; label: string }[] = [
  { value: 'over', label: 'Both went over' },
  { value: 'under', label: 'Both went under' },
];

const MOVE_PILL: Record<ByomLineMove, string> = {
  toward: 'Line moved toward',
  against: 'Line moved against',
  none: 'Line didn\u2019t move',
};

export function trendsSummary(state: ByomPropFilterState): FilterSummary {
  const bits: string[] = [];
  if (state.lineMove) bits.push(MOVE_PILL[state.lineMove]);
  if (state.prevResult) bits.push(state.prevResult === 'won' ? 'Off a win' : 'Off a loss');
  if (state.prevAts) bits.push(state.prevAts === 'covered' ? 'Covered last game' : 'Didn\u2019t cover last game');
  if (state.prevTotal) bits.push(state.prevTotal === 'over' ? 'Last games over' : 'Last games under');
  if (state.division === true) bits.push('Division game');
  else if (state.division === false) bits.push('Not a division game');
  if (bits.length === 0) return ANY;
  return { detail: bits.join(' \u00b7 '), pills: bits };
}

export function propFilterSummary(
  filters: ByomFilters,
  sport: ByomSportId,
  market: string | null,
): string | null {
  const state = propStateFromFilters(filters);
  const slots = shownKickSlots(state.kickSlots, filters.primetime ?? null);
  // A game bet's side is already in its market line, so it is not repeated.
  const game = market === 'h2h' || market === 'spreads' || market === 'totals';
  const parts = [
    oddsSummary(state).detail,
    timeSummary(state, sport, slots).detail,
    matchupSummary(game ? null : filters.side ?? null, state).detail,
    trendsSummary(state).detail,
  ].filter((detail) => detail !== 'Any');
  // Rest chips are NFL's; NBA and NHL rest is in the market line.
  if (sport === 'NFL' && state.shortWeek) parts.push('Short week');
  if (sport === 'NFL' && state.offBye) parts.push('Off a bye');
  if (market == null && parts.length === 0) return null;
  if (parts.length === 0) return null;
  return parts.join(' · ');
}

function num(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

function numList(value: unknown): number[] {
  if (!Array.isArray(value)) return [];
  const out: number[] = [];
  for (const item of value) {
    const parsed = num(item);
    if (parsed != null) out.push(parsed);
  }
  return out;
}

function textList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  const out: string[] = [];
  for (const item of value) {
    if (typeof item !== 'string') continue;
    const trimmed = item.trim();
    if (trimmed !== '') out.push(trimmed);
  }
  return out;
}

export function propStateFromFilters(filters: ByomFilters): ByomPropFilterState {
  const minLine = num(filters.min_line);
  const maxLine = num(filters.max_line);
  const minPrice = num(filters.min_price);
  const maxPrice = num(filters.max_price);
  let priceBand: ByomPriceBand | null = null;
  let priceCustom: ByomBand | null = null;
  if (minPrice === 101 && maxPrice == null) priceBand = 'plus';
  else if (minPrice === 100 && maxPrice == null) priceBand = 'plus';
  else if (minPrice === -130 && maxPrice === -100) priceBand = 'mid';
  else if (minPrice == null && maxPrice === -131) priceBand = 'heavy';
  else if (minPrice != null || maxPrice != null) {
    priceBand = 'custom';
    priceCustom = {
      min: minPrice ?? openPriceBand().min,
      max: maxPrice ?? openPriceBand().max,
    };
  }
  const slots = textList(filters.kick_slots).filter(
    (slot): slot is ByomKickSlot => slot === 'early' || slot === 'late' || slot === 'prime',
  );
  const player = typeof filters.player === 'string' ? filters.player.trim() : '';
  return {
    lineBand: minLine != null && maxLine != null ? { min: minLine, max: maxLine } : null,
    priceBand,
    priceCustom,
    months: numList(filters.months),
    weekdays: numList(filters.weekdays),
    kickSlots: slots,
    opponents: textList(filters.opponents).map((abbrev) => abbrev.toUpperCase()),
    player: player === '' ? null : player,
    shortWeek: filters.max_rest_days === 6,
    offBye: filters.min_rest_days != null && filters.min_rest_days >= 12,
    lineMove: filters.line_move === 'toward' || filters.line_move === 'against' || filters.line_move === 'none'
      ? filters.line_move : null,
    prevResult: filters.prev_result === 'won' || filters.prev_result === 'lost' ? filters.prev_result : null,
    prevAts: filters.prev_ats === 'covered' || filters.prev_ats === 'not_covered' ? filters.prev_ats : null,
    prevTotal: filters.prev_total === 'over' || filters.prev_total === 'under' ? filters.prev_total : null,
    division: typeof filters.division_game === 'boolean' ? filters.division_game : null,
  };
}

// The team spread and game total keys stay listed so clearPhaseA removes
// any stored on a prop. No prop writes them (Matt, 2026-11-04).
const PHASE_A_KEYS: (keyof ByomFilters)[] = [
  'min_line',
  'max_line',
  'min_price',
  'max_price',
  'min_team_spread',
  'max_team_spread',
  'min_game_total',
  'max_game_total',
  'months',
  'weekdays',
  'kick_slots',
  'opponents',
  'player',
  'line_move',
  'prev_result',
  'prev_ats',
  'prev_total',
  'division_game',
];

function clearPhaseA(next: ByomFilters): void {
  for (const key of PHASE_A_KEYS) delete next[key];
}

function putBand(next: ByomFilters, minKey: keyof ByomFilters, maxKey: keyof ByomFilters, band: ByomBand | null): void {
  if (band == null) {
    delete next[minKey];
    delete next[maxKey];
    return;
  }
  Object.assign(next, { [minKey]: band.min, [maxKey]: band.max });
}

/**
 * Writes the sheet's keys. A game bet takes price, time, opponent and
 * trends, never a player line or a player (Matt, 2026-11-05). NBA and NHL
 * do not write kickoff slots; their rest chips are filtersForDraft's. NFL
 * owns rest days here, for the short-week and bye chips.
 */
export function applyPropFilterKeys(
  next: ByomFilters,
  state: ByomPropFilterState,
  opts: {
    prop: boolean;
    sport: ByomSportId;
    yesOnly: boolean;
    marketCount: number;
    primetime: boolean | null;
  },
): ByomFilters {
  clearPhaseA(next);
  const oneMarket = opts.prop && opts.marketCount === 1 && !opts.yesOnly;
  if (oneMarket) putBand(next, 'min_line', 'max_line', state.lineBand);
  if (state.priceBand === 'plus') next.min_price = 100;
  else if (state.priceBand === 'mid') {
    next.min_price = -130;
    next.max_price = -100;
  } else if (state.priceBand === 'heavy') next.max_price = -131;
  else if (state.priceBand === 'custom') putBand(next, 'min_price', 'max_price', state.priceCustom);
  // No team spread or game total on a prop (Matt, 2026-11-04): those are
  // team bets. clearPhaseA above already removed any stored ones.
  if (state.months.length > 0) next.months = [...state.months];
  if (state.weekdays.length > 0) next.weekdays = [...state.weekdays];
  if (state.opponents.length > 0) next.opponents = [...state.opponents];
  if (opts.prop && state.player) next.player = state.player;
  if (state.lineMove) next.line_move = state.lineMove;
  if (state.prevResult) next.prev_result = state.prevResult;
  if (state.prevAts) next.prev_ats = state.prevAts;
  if (state.prevTotal) next.prev_total = state.prevTotal;
  if (state.division != null) next.division_game = state.division;
  if (opts.sport === 'NFL') {
    if (state.kickSlots.length > 0) {
      next.kick_slots = [...state.kickSlots];
      delete next.primetime;
    } else if (opts.primetime == null) {
      delete next.primetime;
    } else {
      next.primetime = opts.primetime;
    }
    if (state.shortWeek) {
      delete next.min_rest_days;
      next.max_rest_days = 6;
    } else if (state.offBye) {
      next.min_rest_days = 12;
      delete next.max_rest_days;
    } else {
      delete next.min_rest_days;
      delete next.max_rest_days;
    }
  }
  return next;
}

export function lineStepNote(scale: LineScale): string {
  const unit = scale.unit === '' ? '' : ` ${scale.unit}`;
  const step = Number.isInteger(scale.step) ? String(scale.step) : formatLineNumber(scale.step);
  return `Steps of ${step}${unit} · range ${formatLineNumber(scale.min)}\u2013${formatLineNumber(scale.max)}`;
}
