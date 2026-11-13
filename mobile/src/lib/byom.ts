/**
 * Data layer for Build Your Own Model. Types, fetchers, and nothing else.
 *
 * byom_backtest reads the facts tables. The saved-model RPCs need a
 * signed-in session. This file does not turn sign-in on and it does not
 * render a screen. A result is a win, a loss, a push, or a tie. Units
 * are the main models' staking: 1u to win, risk capped at 3u. There is
 * no recommended stake. A count of bets the function left out is not
 * parsed.
 *
 * Two timings (Matt, 2026-11-04). `official` is the first DraftKings
 * quote where the bet fit the model's rules: the line and price it
 * became a pick at. `close` is the last DraftKings quote before kickoff.
 * byom_record returns both, byom_bets lists one. NFL and NBA both have
 * official rows (Matt, 2026-11-04).
 *
 * LINE_BASIS is the label stored on each fact row. The backtest RPC
 * returns season totals, not that label per game. A screen shows this
 * string with the result.
 */

import { byomFilters, readStoredFilters, type ByomFilters } from './byomFilters';
import {
  assertByomSide,
  seasonListFor,
  headlineFromCounts,
  type ByomSeasonScope,
  type ByomSport,
} from './byomRecord';
import { supabase } from './supabase';

export { byomFilters, type ByomFilters };

/** The line on a fact row: the last DraftKings snapshot at or before kickoff. */
export const LINE_BASIS = 'DraftKings line at game start';

export interface ByomBacktestRow {
  market: string;
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  ties: number;
  /** Null when this response had no units column. Zero is a real zero. */
  units: number | null;
  /** Null when this response had no amount risked. ROI is not estimated. */
  risked: number | null;
}

export interface ByomSnapshot {
  snapshot_id: string;
  saved_at: string;
  season: number;
  filters: ByomFilters;
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  ties: number;
  summary: ByomBacktestRow[];
}

export interface ByomModel {
  model_id: string;
  name: string;
  sport: string;
  filters: ByomFilters;
  created_at: string;
  updated_at: string;
  snapshots: ByomSnapshot[];
}

function num(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return 0;
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value == null || typeof value !== 'object' || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function asRows(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((row): row is Record<string, unknown> => asRecord(row) != null);
}

function optionalNum(row: Record<string, unknown>, key: string): number | null {
  if (!Object.prototype.hasOwnProperty.call(row, key)) return null;
  const value = row[key];
  if (value == null || value === '') return null;
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) return parsed;
  }
  return null;
}

export function parseBacktestRow(value: unknown): ByomBacktestRow {
  const row = asRecord(value) ?? {};
  return {
    market: text(row.market),
    bets: num(row.bets),
    wins: num(row.wins),
    losses: num(row.losses),
    pushes: num(row.pushes),
    ties: num(row.ties),
    units: optionalNum(row, 'units'),
    risked: optionalNum(row, 'risked'),
  };
}

function parseFilters(value: unknown): ByomFilters {
  // A stored row can carry a key this build does not grade. Drop that key
  // and keep the rest, so one unknown key does not drop the whole list.
  // byomFilters still rejects the same key on save.
  return readStoredFilters(value);
}

function parseSnapshot(value: unknown): ByomSnapshot {
  const row = asRecord(value) ?? {};
  const summary = Array.isArray(row.summary) ? row.summary.map(parseBacktestRow) : [];
  return {
    snapshot_id: text(row.snapshot_id),
    saved_at: text(row.saved_at),
    season: num(row.season),
    filters: parseFilters(row.filters),
    bets: num(row.bets),
    wins: num(row.wins),
    losses: num(row.losses),
    pushes: num(row.pushes),
    ties: num(row.ties),
    summary,
  };
}

export function parseByomModel(value: unknown): ByomModel {
  const row = asRecord(value) ?? {};
  const snapshots = Array.isArray(row.snapshots) ? row.snapshots.map(parseSnapshot) : [];
  return {
    model_id: text(row.model_id),
    name: text(row.name),
    sport: text(row.sport) || 'NFL',
    filters: parseFilters(row.filters),
    created_at: text(row.created_at),
    updated_at: text(row.updated_at),
    snapshots,
  };
}

/**
 * One season of facts. `season` null is the current NFL season.
 * The RPC returns win, loss, push, and tie counts, plus units when the
 * deployed function has that column. It does not suggest a stake.
 * The line label is LINE_BASIS.
 */
function rpcFilters(
  filters: ByomFilters | undefined,
  sport: ByomSport,
): ByomFilters & { sport?: ByomSport } {
  const checked = byomFilters(filters);
  // NFL omits sport. Production byom_backtest rejects an unknown key
  // until byom_nba_props_2026_10_29.sql is applied, and a missing
  // sport there is NFL. Sending it on every NFL call would break the
  // live builder before that file is applied.
  if (sport !== 'NFL') return { ...checked, sport };
  return checked;
}

export interface ByomPlayerSearch {
  names: string[];
  /** The name RPC is not on this database yet. */
  missing: boolean;
}

/**
 * Distinct player names on byom_prop_facts. Two characters minimum.
 * A database without byom_player_names returns missing, not a throw.
 */
export async function searchByomPlayerNames(
  sport: ByomSport,
  query: string,
): Promise<ByomPlayerSearch> {
  const q = query.trim().replace(/[%_\\]/g, '');
  if (q.length < 2) return { names: [], missing: false };
  const { data, error } = await supabase.rpc('byom_player_names', {
    p_sport: sport,
    p_query: q,
  });
  if (error) {
    const code = typeof error.code === 'string' ? error.code : '';
    const message = typeof error.message === 'string' ? error.message : '';
    if (code === 'PGRST202' || /could not find the function/i.test(message)) {
      return { names: [], missing: true };
    }
    throw error;
  }
  const names: string[] = [];
  const seen = new Set<string>();
  for (const row of asRows(data)) {
    const name = text(row.player_name);
    if (name === '' || seen.has(name)) continue;
    seen.add(name);
    names.push(name);
  }
  return { names, missing: false };
}

export async function fetchByomBacktest(
  season: number | null,
  filters?: ByomFilters,
  sport: ByomSport = 'NFL',
): Promise<ByomBacktestRow[]> {
  const { data, error } = await supabase.rpc('byom_backtest', {
    p_season: season,
    p_filters: rpcFilters(filters, sport),
  });
  if (error) throw error;
  return asRows(data).map(parseBacktestRow);
}

export type ByomTiming = 'official' | 'close';

export interface ByomTimedRows {
  /** The timing the screen leads with: official, or the close when official is empty. */
  headline: ByomTiming;
  official: ByomBacktestRow[];
  close: ByomBacktestRow[];
  /** One entry per season read. Season is null for the current-season read. */
  seasons: { season: number | null; official: ByomBacktestRow[]; close: ByomBacktestRow[] }[];
}

function isMissingFunction(error: { code?: unknown; message?: unknown }): boolean {
  const code = typeof error.code === 'string' ? error.code : '';
  const message = typeof error.message === 'string' ? error.message : '';
  return code === 'PGRST202' || /could not find the function/i.test(message);
}

/** True once byom_record answered "no such function" in this process. */
let recordMissing = false;

/**
 * One season, both timings. A database without byom_record (the
 * migration has not landed yet) falls back to byom_backtest, which is
 * the close only, so an over-the-air build never shows an error for it.
 */
export async function fetchByomRecord(
  season: number | null,
  filters?: ByomFilters,
  sport: ByomSport = 'NFL',
): Promise<{ official: ByomBacktestRow[]; close: ByomBacktestRow[] }> {
  if (!recordMissing) {
    const { data, error } = await supabase.rpc('byom_record', {
      p_season: season,
      p_filters: rpcFilters(filters, sport),
    });
    if (!error) {
      const official: ByomBacktestRow[] = [];
      const close: ByomBacktestRow[] = [];
      for (const row of asRows(data)) {
        (text(row.timing) === 'official' ? official : close).push(parseBacktestRow(row));
      }
      return { official, close };
    }
    if (!isMissingFunction(error)) throw error;
    recordMissing = true;
  }
  return { official: [], close: await fetchByomBacktest(season, filters, sport) };
}

/**
 * byom_bets ships in the same migration as byom_record. Until the server
 * has it, no screen offers the bet list (UX review, 2026-11-04).
 */
export function byomBetsAvailable(): boolean {
  return !recordMissing;
}

/**
 * Official leads once the server has it, on NFL and NBA alike (Matt,
 * 2026-11-04: "do the same as what I said for nfl"). `sport` stays in
 * the signature so a later sport can opt in or out.
 */
export function headlineTiming(_sport: ByomSport): ByomTiming {
  return recordMissing ? 'close' : 'official';
}

function countedBets(rows: readonly ByomBacktestRow[]): number {
  return rows.reduce((sum, row) => sum + (Number.isFinite(row.bets) ? row.bets : 0), 0);
}

/**
 * The card's headline. It leads with the official record once the server
 * has it. An empty official record beside a closing record (the rebuild
 * has not finished, or the season has no official rows) leads with the
 * close, so the card is not stuck at 0-0.
 */
export function headlineFor(
  sport: ByomSport,
  official: readonly ByomBacktestRow[],
  close: readonly ByomBacktestRow[],
): ByomTiming {
  return headlineFromCounts(headlineTiming(sport), countedBets(official), countedBets(close));
}

/** `fetchByomScopedBacktest`'s seasons, both timings. */
export async function fetchByomScopedRecord(
  scope: ByomSeasonScope,
  filters?: ByomFilters,
  now: Date = new Date(),
  sport: ByomSport = 'NFL',
): Promise<ByomTimedRows> {
  const parsed = byomFilters(filters);
  const seasons: (number | null)[] = scope === 'current'
    ? [null]
    : seasonListFor(sport, now);
  const groups = await pool(seasons, 4, (season) => fetchByomRecord(season, parsed, sport));
  const official = groups.flatMap((group) => group.official);
  const close = groups.flatMap((group) => group.close);
  return {
    headline: headlineFor(sport, official, close),
    official,
    close,
    seasons: groups.map((group, index) => ({
      season: seasons[index] ?? null,
      official: group.official,
      close: group.close,
    })),
  };
}

/** One counted bet. `label` is built by the server from the stored fields. */
export interface ByomBet {
  key: string;
  commence_time: string;
  market: string;
  leg_side: string;
  label: string;
  home_team: string;
  away_team: string;
  player_name: string | null;
  price: number | null;
  result: 'win' | 'loss' | 'push' | 'tie' | '';
  units: number | null;
  /** When the bet became official. Null on a closing-line row. */
  locked_at: string | null;
}

export interface ByomBetList {
  bets: ByomBet[];
  /** Every counted bet, including ones past a season's 500-row page. */
  total: number;
  /** Seasons whose count passed the 500-row page. Each shows its newest 500. */
  cappedSeasons: number;
}

export function parseByomBet(value: unknown): ByomBet {
  const row = asRecord(value) ?? {};
  const result = text(row.result);
  return {
    key: [text(row.canonical_key), text(row.market), text(row.player_name ?? ''),
      text(row.leg_side)].join('|'),
    commence_time: text(row.commence_time),
    market: text(row.market),
    leg_side: text(row.leg_side),
    label: text(row.label),
    home_team: text(row.home_team),
    away_team: text(row.away_team),
    player_name: text(row.player_name) || null,
    price: optionalNum(row, 'price'),
    result: result === 'win' || result === 'loss' || result === 'push' || result === 'tie'
      ? result : '',
    units: optionalNum(row, 'units'),
    locked_at: text(row.locked_at) || null,
  };
}

/** The bets one timing counts, newest first. One call per season in scope. */
export async function fetchByomScopedBets(
  scope: ByomSeasonScope,
  filters: ByomFilters,
  timing: ByomTiming,
  now: Date = new Date(),
  sport: ByomSport = 'NFL',
): Promise<ByomBetList> {
  const parsed = byomFilters(filters);
  const seasons: (number | null)[] = scope === 'current'
    ? [null]
    : seasonListFor(sport, now).slice().reverse();
  const pages = await pool(seasons, 4, async (season) => {
    const { data, error } = await supabase.rpc('byom_bets', {
      p_season: season,
      p_filters: rpcFilters(parsed, sport),
      p_timing: timing,
    });
    if (error) throw error;
    const rows = asRows(data);
    const total = rows.length ? num(rows[0].total_bets) : 0;
    return { bets: rows.map(parseByomBet), total, capped: total > rows.length };
  });
  const bets = pages.flatMap((page) => page.bets);
  bets.sort((a, b) => (a.commence_time < b.commence_time ? 1 : a.commence_time > b.commence_time ? -1 : 0));
  return {
    bets,
    total: pages.reduce((sum, page) => sum + page.total, 0),
    cappedSeasons: pages.filter((page) => page.capped).length,
  };
}

/** Run `fn` over `items` with at most `limit` calls in flight. */
export async function pool<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T) => Promise<R>,
): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let next = 0;
  const workers = Math.min(Math.max(limit, 0), items.length);
  await Promise.all(Array.from({ length: workers }, async () => {
    for (;;) {
      const index = next;
      next += 1;
      if (index >= items.length) return;
      out[index] = await fn(items[index]);
    }
  }));
  return out;
}

/**
 * `current` is one call with season null (the server's NFL season).
 * `all` is one call per season from 2020 through the current season
 * on this device's America/New_York clock, summed by the caller.
 */
export async function fetchByomScopedBacktest(
  scope: ByomSeasonScope,
  filters?: ByomFilters,
  now: Date = new Date(),
  sport: ByomSport = 'NFL',
): Promise<ByomBacktestRow[]> {
  const parsed = byomFilters(filters);
  if (scope === 'current') return fetchByomBacktest(null, parsed, sport);
  const seasons = seasonListFor(sport, now);
  const groups = await pool(seasons, 4, (season) => fetchByomBacktest(season, parsed, sport));
  return groups.flat();
}

/** Store the server's byom_backtest result. Requires a signed-in session. */
export async function saveByomModel(
  name: string,
  filters?: ByomFilters,
  season: number | null = null,
  sport: ByomSport = 'NFL',
): Promise<ByomBacktestRow & { model_id: string; season: number }> {
  const checked = byomFilters(filters);
  assertByomSide(checked);
  const { data, error } = await supabase.rpc('byom_save_model', {
    p_name: name,
    p_filters: rpcFilters(filters, sport),
    p_season: season,
  });
  if (error) throw error;
  const row = asRows(data)[0] ?? {};
  const parsed = parseBacktestRow(row);
  return {
    ...parsed,
    market: '',
    model_id: text(row.model_id),
    season: num(row.season),
  };
}

export async function fetchByomModels(): Promise<ByomModel[]> {
  const { data, error } = await supabase.rpc('byom_list_models');
  if (error) throw error;
  return asRows(data).map(parseByomModel);
}

/** True once this process has seen one NBA byom_game_facts row. */
let nbaGameFactsKnown = false;

export function nbaGameFactsAreKnown(): boolean {
  return nbaGameFactsKnown;
}

/**
 * Whether NBA game facts exist. An empty table is 'missing'. A hit stays
 * 'ready' for the rest of this process. A failed read throws.
 */
export async function fetchNbaGameFactsReady(): Promise<'ready' | 'missing'> {
  if (nbaGameFactsKnown) return 'ready';
  const { data, error } = await supabase
    .from('byom_game_facts')
    .select('canonical_key')
    .eq('sport', 'NBA')
    .limit(1);
  if (error) throw error;
  if (!Array.isArray(data) || data.length === 0) return 'missing';
  nbaGameFactsKnown = true;
  return 'ready';
}

export async function deleteByomModel(modelId: string): Promise<void> {
  const { error } = await supabase.rpc('byom_delete_model', {
    p_model_id: modelId,
  });
  if (error) throw error;
}
