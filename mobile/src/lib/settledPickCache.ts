/**
 * On-device cache of settled picks since the record start (2026-04-14).
 *
 * The model screens backtest custom models against every settled pick, which is
 * ~3.2k rows and grows ~29/day. Re-downloading all of it on every Models tab
 * open is wasteful and only gets worse, so we keep it locally and refetch just
 * a trailing window.
 *
 * The window is what makes this correct rather than merely fast: picks do NOT
 * settle on their game date. Game picks settle over a trailing 14 days and
 * props/UFC/golf the same, so a row for a date we already cached can gain (or
 * change) its result days later. We therefore re-fetch REFRESH_WINDOW_DAYS of
 * history every time and treat the server as authoritative for that window —
 * dropping cached rows inside it rather than merging, so a deleted or re-graded
 * pick can't linger.
 */

import AsyncStorage from '@react-native-async-storage/async-storage';
import { addDays } from './format';
import type { SettledPick } from '@/types';

// Bump when SETTLED_PICK_COLUMNS / SettledPickKey changes — cached rows written
// by an older build would be missing the new column.
const KEY = 'settledPicks.v2'; // v2: + scored_line (line-value filter, 2026-08-22)

/**
 * How much history to re-fetch each load. Comfortably wider than the 14-day
 * settle windows in paper_tracker so late-settling picks are always picked up.
 */
export const REFRESH_WINDOW_DAYS = 21;

interface CacheEnvelope {
  rows: SettledPick[];
  cachedAt: string;
}

export async function readSettledCache(): Promise<SettledPick[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as CacheEnvelope;
    return Array.isArray(parsed?.rows) ? parsed.rows : [];
  } catch {
    return [];
  }
}

export async function writeSettledCache(rows: SettledPick[]): Promise<void> {
  try {
    const envelope: CacheEnvelope = { rows, cachedAt: new Date().toISOString() };
    await AsyncStorage.setItem(KEY, JSON.stringify(envelope));
  } catch {
    // A cache write failure is not worth surfacing — the next load just costs
    // a full fetch.
  }
}

export async function clearSettledCache(): Promise<void> {
  try {
    await AsyncStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

/** Newest game_date present in the cache, or null when it's empty. */
export function latestCachedDate(rows: SettledPick[]): string | null {
  let max: string | null = null;
  for (const r of rows) {
    if (!r.game_date) continue;
    if (max == null || r.game_date > max) max = r.game_date;
  }
  return max;
}

/**
 * The date to refetch from: REFRESH_WINDOW_DAYS before the newest cached row,
 * floored at paperStart. Returns paperStart when there's nothing cached.
 */
export function refreshFrom(rows: SettledPick[], paperStart: string): string {
  const latest = latestCachedDate(rows);
  if (latest == null) return paperStart;
  const from = addDays(latest, -REFRESH_WINDOW_DAYS);
  return from < paperStart ? paperStart : from;
}

/**
 * Cached history before `from`, plus everything the server returned from `from`
 * onward. The server is authoritative inside the window, so rows that were
 * deleted or re-graded there are replaced rather than merged.
 */
export function mergeSettled(
  cached: SettledPick[],
  fresh: SettledPick[],
  from: string,
): SettledPick[] {
  const kept = cached.filter((r) => r.game_date < from);
  const out = [...kept, ...fresh];
  out.sort((a, b) => (a.game_date < b.game_date ? 1 : a.game_date > b.game_date ? -1 : 0));
  return out;
}
