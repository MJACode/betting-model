/**
 * Pure hit-rate math for the Stats tab "Hit Rate" mode.
 *
 * A "hit" = a game where the player's stat cleared the line (over) or stayed
 * under it (under). Games with a null/NaN value (DNP, missing) are skipped and
 * do NOT count toward the denominator, so "X/N" reflects games actually played.
 *
 * Verify with: npx tsx scripts/verify_hit_rate.ts
 */

export type HitDirection = 'over' | 'under';

export interface HitRate {
  hits: number;
  total: number;
  pct: number; // 0..1
}

/** A single game's value clears the line, given the direction. */
export function isHit(
  value: number | null | undefined,
  line: number,
  direction: HitDirection = 'over',
): boolean {
  if (value == null || Number.isNaN(value)) return false;
  return direction === 'over' ? value > line : value < line;
}

/** Count games over/under the line; null/NaN values are skipped (not counted). */
export function computeHitRate(
  values: Array<number | null | undefined>,
  line: number,
  direction: HitDirection = 'over',
): HitRate {
  let hits = 0;
  let total = 0;
  for (const v of values) {
    if (v == null || Number.isNaN(v)) continue; // skip — don't inflate total
    total++;
    if (direction === 'over' ? v > line : v < line) hits++;
  }
  return { hits, total, pct: total ? hits / total : 0 };
}

/** Per-game hit/miss flags (order preserved) for the dot strip. */
export function hitFlags(
  values: Array<number | null | undefined>,
  line: number,
  direction: HitDirection = 'over',
): boolean[] {
  return values.map((v) => isHit(v, line, direction));
}
