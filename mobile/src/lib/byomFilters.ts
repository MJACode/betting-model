/**
 * Filter keys the BYOM RPCs grade. A mixed-case or unknown key is an
 * error. It is not dropped and it is not rewritten, so a save cannot
 * store a different filter than the one that was passed.
 */

export interface ByomFilters {
  side?: 'home' | 'away' | 'over' | 'under';
  role?: 'favorite' | 'underdog' | 'pickem';
  weeks?: number[];
  min_rest_days?: number;
  max_rest_days?: number;
  primetime?: boolean;
  markets?: string[];
  /** Over or under on a prop. The player's team stays on side. */
  prop_side?: 'over' | 'under';
  /** Player prop line at game start. Both ends, or neither. */
  min_line?: number;
  max_line?: number;
  /** DraftKings American price on the chosen side at game start. */
  min_price?: number;
  max_price?: number;
  /** Player's team spread at game start. Negative is the favorite. */
  min_team_spread?: number;
  max_team_spread?: number;
  /** Game total at game start. */
  min_game_total?: number;
  max_game_total?: number;
  /** Calendar month in America/New_York. 1 is January. */
  months?: number[];
  /** Kickoff weekday in America/New_York. 0 is Sunday. */
  weekdays?: number[];
  /** Kickoff hour bands in America/New_York: early, late, prime. */
  kick_slots?: ('early' | 'late' | 'prime')[];
  /** Opponent abbrev. The other team in the game. */
  opponents?: string[];
  /** One player, matched to the stored name. */
  player?: string;
}

const FILTER_KEYS: (keyof ByomFilters)[] = [
  'side',
  'role',
  'weeks',
  'min_rest_days',
  'max_rest_days',
  'primetime',
  'markets',
  'prop_side',
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
];

const FILTER_KEY_SET = new Set<string>(FILTER_KEYS);

export function byomFilters(input: ByomFilters | null | undefined): ByomFilters {
  if (input == null) return {};
  const src = input as Record<string, unknown>;
  for (const key of Object.keys(src)) {
    if (FILTER_KEY_SET.has(key)) continue;
    if (FILTER_KEY_SET.has(key.toLowerCase())) {
      throw new Error('filter keys must be lowercase');
    }
    throw new Error(`unknown filter key: ${key}`);
  }
  const out: ByomFilters = {};
  for (const key of FILTER_KEYS) {
    const value = src[key];
    if (value !== undefined) {
      Object.assign(out, { [key]: value });
    }
  }
  return out;
}

/** A stored row. One unknown key is dropped. A save still goes through byomFilters. */
export function readStoredFilters(value: unknown): ByomFilters {
  if (value == null || typeof value !== 'object' || Array.isArray(value)) return {};
  const src: Record<string, unknown> = { ...(value as Record<string, unknown>) };
  for (;;) {
    try {
      return byomFilters(src as ByomFilters);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : '';
      const match = /^unknown filter key: (.+)$/.exec(message);
      if (match == null || !Object.prototype.hasOwnProperty.call(src, match[1])) {
        throw err;
      }
      delete src[match[1]];
    }
  }
}
