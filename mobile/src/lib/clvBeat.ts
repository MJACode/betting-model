/**
 * Headline same-book CLV beat rate.
 *
 * picks.clv_pct is percent, stored at 2 decimal places. A close that
 * equals the price taken is 0.00. Anything inside half a hundredth is
 * that zero: a push. Pushes stay in the average and stay out of the
 * beat rate. Beat rate = beats / (beats + losses).
 */

export const CLV_PCT_PUSH_EPS = 0.005;

export type ClvOutcome = 'beat' | 'loss' | 'push';

export function clvOutcome(pct: number | null | undefined): ClvOutcome | null {
  if (pct == null) return null;
  const v = typeof pct === 'number' ? pct : Number(pct);
  if (!Number.isFinite(v)) return null;
  if (Math.abs(v) < CLV_PCT_PUSH_EPS) return 'push';
  return v > 0 ? 'beat' : 'loss';
}

/** Beats + losses. A push is not in this count. */
export function clvDecisive(settled: number, pushes: number): number {
  return Math.max(0, settled - pushes);
}

/** Null when there is no beat and no loss, including an all-push set. */
export function clvBeatRate(beats: number, settled: number, pushes: number): number | null {
  const decisive = clvDecisive(settled, pushes);
  if (decisive <= 0) return null;
  return beats / decisive;
}

/**
 * The results-recap clause. Push count is omitted at zero.
 * An all-push set does not divide: `0 measured, N push`.
 */
export function formatClvBeatLine(beats: number, losses: number, pushes: number): string {
  const decisive = beats + losses;
  if (decisive <= 0 && pushes <= 0) return '';
  if (decisive <= 0) return `0 measured, ${pushes} push`;
  const pct = Math.round((beats / decisive) * 100);
  const core = `${pct}% beat close (${beats}/${decisive}`;
  return pushes > 0 ? `${core}, ${pushes} push)` : `${core})`;
}
