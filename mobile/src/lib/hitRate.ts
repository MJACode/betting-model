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

/** The three colour bands the board ramps a hit rate through. */
export type HitRateBandName = 'high' | 'mid' | 'low';

/** Band boundaries. Display only — these price nothing and gate no bet. */
export const HIT_RATE_BANDS = { high: 0.6, mid: 0.4 } as const;

export function hitRateBandOf(pct: number): HitRateBandName {
  if (pct >= HIT_RATE_BANDS.high) return 'high';
  if (pct >= HIT_RATE_BANDS.mid) return 'mid';
  return 'low';
}

/**
 * Should the board colour hit rates at all, for THIS column?
 *
 * The ramp is absolute — good at 60%, mid at 40%, bad below — which reads as a
 * comparison between players only while the column actually spans bands. On a
 * rare-event column it does not: at "1+ Doubles" every hitter in the league
 * sits at 10-30%, so the whole column renders the bad end of the ramp beside a
 * +450 price that may well be the better side of that number, and one tap to
 * "No Doubles" turns the same column into a wall of green beside heavy chalk.
 * The colour stops distinguishing players and starts delivering a verdict on
 * the bet — which this board is not entitled to give, because no model prices
 * Doubles (UX review, 2026-09-05).
 *
 * Orthogonal to WHICH colours the ramp uses: session 234 repainted it onto the
 * accessible `colors.grade*` tokens, and a ramp that says the same thing about
 * every row says nothing about any of them at any contrast level.
 *
 * So: colour when it discriminates, and otherwise let the percentage and the
 * x/N sub-label carry it, as they already do. Both are always printed, so
 * colour is never the only carrier of meaning here.
 */
export function hitRateColorDiscriminates(pcts: number[]): boolean {
  if (pcts.length < 2) return false;
  const first = hitRateBandOf(pcts[0]);
  return pcts.some((p) => hitRateBandOf(p) !== first);
}
