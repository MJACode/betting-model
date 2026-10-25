/**
 * Data layer for Build Your Own Model. Types, fetchers, and nothing else.
 *
 * byom_backtest reads the facts tables. The saved-model RPCs need a
 * signed-in session. This file does not turn sign-in on and it does not
 * render a screen. A result is a win, a loss, a push, or a tie. Units
 * are 1u to win at the stored DraftKings price. There is no recommended
 * stake. A count of bets the function left out is not parsed.
 *
 * LINE_BASIS is the label stored on each fact row. The backtest RPC
 * returns season totals, not that label per game. A screen shows this
 * string with the result.
 */

import { byomFilters, readStoredFilters, type ByomFilters } from './byomFilters';
import { nflSeasonList, type ByomSeasonScope } from './byomRecord';
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
export async function fetchByomBacktest(
  season: number | null,
  filters?: ByomFilters,
): Promise<ByomBacktestRow[]> {
  const { data, error } = await supabase.rpc('byom_backtest', {
    p_season: season,
    p_filters: byomFilters(filters),
  });
  if (error) throw error;
  return asRows(data).map(parseBacktestRow);
}

async function pool<T, R>(
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
): Promise<ByomBacktestRow[]> {
  const parsed = byomFilters(filters);
  if (scope === 'current') return fetchByomBacktest(null, parsed);
  const seasons = nflSeasonList(now);
  const groups = await pool(seasons, 4, (season) => fetchByomBacktest(season, parsed));
  return groups.flat();
}

/** Store the server's byom_backtest result. Requires a signed-in session. */
export async function saveByomModel(
  name: string,
  filters?: ByomFilters,
  season: number | null = null,
): Promise<ByomBacktestRow & { model_id: string; season: number }> {
  const { data, error } = await supabase.rpc('byom_save_model', {
    p_name: name,
    p_filters: byomFilters(filters),
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

export async function deleteByomModel(modelId: string): Promise<void> {
  const { error } = await supabase.rpc('byom_delete_model', {
    p_model_id: modelId,
  });
  if (error) throw error;
}
