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
 * Every measured bet closed at the price taken: none beat it, none trailed it.
 * It read `0 measured, N push` until 2026-11-20, which said nothing had been
 * measured. Same words as the Discord recap (tracking/discord_notifier.all_matched_text).
 */
export function allMatchedText(pushes: number, opts: { sentence?: boolean } = {}): string {
  if (pushes === 1) return '1 matched the close';
  return `${opts.sentence ? 'All' : 'all'} ${pushes} matched the close`;
}

/**
 * The results-recap clause. Push count is omitted at zero.
 * An all-push set does not divide: `all N matched the close`.
 */
export function formatClvBeatLine(beats: number, losses: number, pushes: number): string {
  const decisive = beats + losses;
  if (decisive <= 0 && pushes <= 0) return '';
  if (decisive <= 0) return allMatchedText(pushes);
  const pct = Math.round((beats / decisive) * 100);
  const core = `${pct}% beat close (${beats}/${decisive}`;
  return pushes > 0 ? `${core}, ${pushes} push)` : `${core})`;
}
