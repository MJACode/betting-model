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
