/**
 * At Least / Over / Under — how the user says which bet the board is about.
 *
 * Matt, 2026-09-05, with a competitor's Leaders tab beside ours: "add this
 * feature where the user can say they want to show bets that are at least
 * which is how we have it today or if they want to say over or under."
 *
 * The ruler picks a WHOLE NUMBER; the mode says which side of it. Every
 * combination resolves to the same thing the rest of the app already speaks —
 * a half-point line and a side — so the hit-rate math (lib/hitRate.ts), the
 * odds lookup (statsOdds buildQuoteIndex) and the betslip leg all take it
 * unchanged. This module is only the translation.
 *
 *   ruler 1, At Least  ->  >= 1  ->  line 0.5 over   "1+ Hits"
 *   ruler 1, Over      ->  >  1  ->  line 1.5 over   "2+ Hits"
 *   ruler 1, Under     ->  <  1  ->  line 0.5 under  "No Hits"
 *
 * THESE MODES OVERLAP, AND THAT IS DELIBERATE. Because a counting stat is a
 * whole number, "Over 1" IS "At Least 2" — the same bet at the same price, and
 * the headline says so rather than pretending otherwise. The mode exists
 * because bettors and books use both idioms: a book sells "Over 1.5 Hits" and
 * a fan asks for "2+ hits". Naming the bet the same way whichever route the
 * user took is what keeps the board honest.
 *
 * Pure (no react-native import) so the verify script can run it under tsx.
 */

import type { HitDirection } from '@/lib/hitRate';

export type HitMode = 'atLeast' | 'over' | 'under';

/** The bet a (ruler, mode) pair names: a half-point line and a side. */
export interface HitSelection {
  line: number;
  side: HitDirection;
}

/** In menu order, which is also the order of how often they are wanted. */
export const HIT_MODES: readonly { mode: HitMode; label: string }[] = [
  { mode: 'atLeast', label: 'At Least' },
  { mode: 'over', label: 'Over' },
  { mode: 'under', label: 'Under' },
];

export function hitModeLabel(mode: HitMode): string {
  return HIT_MODES.find((m) => m.mode === mode)?.label ?? 'At Least';
}

/**
 * The half-point line and side for a whole-number ruler position.
 *
 * Half points are what makes a counting stat unambiguous: no game ever lands
 * ON 0.5, so there is no push and every game is a hit or a miss.
 */
export function selectionFor(n: number, mode: HitMode): HitSelection {
  if (mode === 'over') return { line: n + 0.5, side: 'over' };
  if (mode === 'under') return { line: n - 0.5, side: 'under' };
  return { line: n - 0.5, side: 'over' };
}

/**
 * What the bet is called, under the ruler and on the betslip.
 *
 * Always in the app's existing idiom — "N+" or "At most N" — never in the
 * mode's own words, because the price beside it belongs to the BET and a user
 * comparing our board to their sportsbook needs the two to agree. "Over 1"
 * therefore reads "2+ Hits", which is what it is.
 */
export function hitModeHeadline(n: number, mode: HitMode, statLabel: string): string {
  const label = statLabel.trim();
  if (mode === 'over') return `${n + 1}+ ${label}`.trim();
  if (mode === 'under') {
    // "At most 0 Hits" is nobody's phrasing for it.
    return n <= 1 ? `No ${label}`.trim() : `At most ${n - 1} ${label}`.trim();
  }
  return `${n}+ ${label}`.trim();
}
