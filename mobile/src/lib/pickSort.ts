/**
 * Sort + search helpers for the pick lists (Picks and Signals screens).
 *
 * Both screens render `EnrichedPick` (Picks) and `EnrichedPick | DroppedSignal`
 * (Signals) — every item carries `.pick` and an optional joined `.game`, so the
 * generics below work for both without coupling to either screen.
 */

import { expectedValue } from '@/lib/format';
import type { ConfidenceTier } from '@/types';

export type SortKey = 'edge' | 'ev' | 'time' | 'conf';

export const SORT_OPTIONS: Array<{ key: SortKey; label: string }> = [
  { key: 'edge', label: 'Edge' },
  { key: 'ev', label: 'EV' },
  { key: 'time', label: 'Time' },
  { key: 'conf', label: 'Conf' },
];

const CONF_RANK: Record<string, number> = { HIGH: 3, MED: 2, LOW: 1 };

interface SortablePick {
  pick: {
    edge: number;
    model_probability: number;
    dk_odds: number | null;
    confidence_tier: ConfidenceTier;
  };
  game?: { commence_time?: string | null } | null;
}

/** Per-$1 EV; prob-only picks (null EV) sink to the bottom of an EV sort. */
function evOf(it: SortablePick): number {
  const ev = expectedValue(it.pick.model_probability, it.pick.dk_odds);
  return ev == null ? Number.NEGATIVE_INFINITY : ev;
}

/**
 * Returns a new, sorted array (does not mutate). Edge DESC is the shared default
 * across Picks and Signals; Time falls back to edge to break ties, and every
 * sort uses edge as the final tiebreaker so ordering is stable.
 */
export function sortPicks<T extends SortablePick>(items: T[], key: SortKey): T[] {
  const arr = [...items];
  switch (key) {
    case 'ev':
      arr.sort((a, b) => evOf(b) - evOf(a) || b.pick.edge - a.pick.edge);
      break;
    case 'time':
      arr.sort((a, b) => {
        const ta = a.game?.commence_time ?? '';
        const tb = b.game?.commence_time ?? '';
        if (ta !== tb) return ta.localeCompare(tb);
        return b.pick.edge - a.pick.edge;
      });
      break;
    case 'conf':
      arr.sort((a, b) => {
        const ca = CONF_RANK[a.pick.confidence_tier ?? ''] ?? 0;
        const cb = CONF_RANK[b.pick.confidence_tier ?? ''] ?? 0;
        if (ca !== cb) return cb - ca;
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
