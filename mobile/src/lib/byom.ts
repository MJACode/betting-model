/**
 * Data layer for Build Your Own Model. Types, fetchers, and nothing else.
 *
 * byom_backtest reads the facts tables. The saved-model RPCs need a
 * signed-in session. This file does not turn sign-in on and it does not
 * render a screen. units_uncapped and units_capped are results of
 * DraftKings' own lock price: 1u-to-win, and the same result after a
 * 3-unit risk ceiling. There is no recommended stake.
 */

import { supabase } from './supabase';

export interface ByomFilters {
  side?: 'home' | 'away';
  role?: 'favorite' | 'underdog' | 'pickem';
  weeks?: number[];
  min_rest_days?: number;
  max_rest_days?: number;
  primetime?: boolean;
  markets?: string[];
}

export interface ByomBacktestRow {
  market: string;
  bets: number;
  wins: number;
  losses: number;
  pushes: number;
  ties: number;
  units_uncapped: number;
  units_capped: number;
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
  units_uncapped: number;
  units_capped: number;
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

const FILTER_KEYS: (keyof ByomFilters)[] = [
  'side',
  'role',
  'weeks',
  'min_rest_days',
  'max_rest_days',
  'primetime',
  'markets',
];

/** Keep the keys the RPC grades. Anything else is dropped. */
export function byomFilters(input: ByomFilters | null | undefined): ByomFilters {
  const src = input ?? {};
  const out: ByomFilters = {};
  for (const key of FILTER_KEYS) {
    const value = src[key];
    if (value !== undefined) {
      Object.assign(out, { [key]: value });
    }
  }
  return out;
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

export function parseBacktestRow(value: unknown): ByomBacktestRow {
  const row = asRecord(value) ?? {};
  return {
    market: text(row.market),
    bets: num(row.bets),
    wins: num(row.wins),
    losses: num(row.losses),
    pushes: num(row.pushes),
    ties: num(row.ties),
    units_uncapped: num(row.units_uncapped),
    units_capped: num(row.units_capped),
  };
}

function parseFilters(value: unknown): ByomFilters {
  const row = asRecord(value);
  if (row == null) return {};
  return byomFilters(row as ByomFilters);
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
    units_uncapped: num(row.units_uncapped),
    units_capped: num(row.units_capped),
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
 * The RPC returns both result columns. It does not suggest a stake.
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
