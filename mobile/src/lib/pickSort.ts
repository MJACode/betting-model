/**
 * Sort + search helpers for the pick lists (Today, Signals, Movement views).
 *
 * Every item carries `.pick` and an optional joined `.game`, so the generics
 * below work across all three views without coupling to any one of them.
 */

import { sharpScore } from '@/lib/sharpScore';
import type { Pick } from '@/types';

export type SortKey = 'edge' | 'sharp' | 'time' | 'public';

export const SORT_OPTIONS: Array<{ key: SortKey; label: string }> = [
  { key: 'edge', label: 'Edge' },
  { key: 'sharp', label: 'Sharp' },
  { key: 'time', label: 'Time' },
  { key: 'public', label: 'Public' },
];

interface SortablePick {
  pick: Pick;
  game?: { commence_time?: string | null } | null;
}

/** Sharp Score; non-BET picks (null) sink below any scored BET (0..100). */
function sharpOf(it: SortablePick): number {
  return sharpScore(it.pick)?.score ?? -1;
}

/**
 * Share of public tickets on THIS pick's side; −1 when no split was captured so
 * those rows sink below every pick that has one. Splits are Action Network
 * consensus on full-game markets only — props, F5 and golf store NULL — so on a
 * prop-heavy board this sort degrades to plain edge order rather than shuffling
 * rows by a number the card cannot show.
 */
function publicOf(it: SortablePick): number {
  const v = it.pick.public_bet_pct;
  const n = typeof v === 'string' ? Number(v) : v;
  return n != null && Number.isFinite(n) ? n : -1;
}

/**
 * Returns a new, sorted array (does not mutate). Edge DESC is the shared default
 * across Picks and Signals; Time falls back to edge to break ties, and every
 * sort uses edge as the final tiebreaker so ordering is stable. Public orders
 * by the crowd's share of tickets on each pick's own side, heaviest first, so
 * the top of the board is where the public money actually is.
 */
export function sortPicks<T extends SortablePick>(items: T[], key: SortKey): T[] {
  const arr = [...items];
  switch (key) {
    case 'sharp':
      arr.sort((a, b) => sharpOf(b) - sharpOf(a) || b.pick.edge - a.pick.edge);
      break;
    case 'time':
      arr.sort((a, b) => {
        const ta = a.game?.commence_time ?? '';
        const tb = b.game?.commence_time ?? '';
        if (ta !== tb) return ta.localeCompare(tb);
        return b.pick.edge - a.pick.edge;
      });
      break;
    case 'public':
      arr.sort((a, b) => {
        const pa = publicOf(a);
        const pb = publicOf(b);
        if (pa !== pb) return pb - pa;
        return b.pick.edge - a.pick.edge;
      });
      break;
    case 'edge':
    default:
      arr.sort((a, b) => b.pick.edge - a.pick.edge);
      break;
  }
  return arr;
}

interface SearchablePick {
  pick: { pick_label: string };
  game?: { home_team?: string | null; away_team?: string | null } | null;
}

/**
 * Client-side filter by pick label or either team name. Data is already loaded,
 * so this adds no query. Empty/whitespace query returns the input unchanged.
 */
export function searchPicks<T extends SearchablePick>(items: T[], query: string): T[] {
  const q = query.trim().toLowerCase();
  if (!q) return items;
  return items.filter((it) => {
    const label = it.pick.pick_label?.toLowerCase() ?? '';
    const home = it.game?.home_team?.toLowerCase() ?? '';
    const away = it.game?.away_team?.toLowerCase() ?? '';
    return label.includes(q) || home.includes(q) || away.includes(q);
  });
}
