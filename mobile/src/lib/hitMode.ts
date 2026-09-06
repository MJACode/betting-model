/**
 * At Least / Over / Under — how the user says which bet the board is about.
 *
 * Matt, 2026-09-05, with a competitor's Leaders tab beside ours: "add this
 * feature where the user can say they want to show bets that are at least
 * which is how we have it today or if they want to say over or under."
 *
 * THE MODE CHOOSES THE IDIOM, AND THE RULER IS DRAWN IN IT. (Matt,
 * 2026-09-06, with the competitor's Over board beside ours: "I want to fix
 * how over under is displayed.") At Least is the fan's idiom and counts in
 * whole numbers — 1, 2, 3 — because "2+ Hits" is how a fan asks for it. Over
 * and Under are the BOOK's idiom and count in the book's own half-point
 * lines — 0.5, 1.5, 2.5 — because "Over 0.5 Hits" is what the sportsbook
 * posts. Same ruler position, same bet, two vocabularies:
 *
 *   ruler stop 1, At Least  ->  line 0.5 over   "1+ Hits"
 *   ruler stop 1, Over      ->  line 0.5 over   "Over 0.5 Hits"
 *   ruler stop 1, Under     ->  line 0.5 under  "Under 0.5 Hits"
 *
 * Before this, Over shifted the bet a whole number UP (ruler 1 meant Over
 * 1.5) so that it could not name the same bet twice. The cost was that the
 * user did the arithmetic: the ruler said 1, the headline said "2+", and
 * 1.5 — the only number their sportsbook shows — was the smallest text on
 * the row. Over 0.5 was unreachable in Over mode at all. Naming the same bet
 * two ways is the honest outcome, because the two idioms genuinely name the
 * same bet, and it is what the modes are FOR.
 *
 * Everything downstream — the hit-rate math (lib/hitRate.ts), the odds lookup
 * (statsOdds buildQuoteIndex), the betslip leg — reads only the (line, side)
 * this resolves to, never the mode. This module is the translation and the
 * vocabulary, nothing else.
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
 * The half-point line and side for a ruler stop.
 *
 * `n` is the ruler's STOP INDEX (1, 2, 3 …), not the number on its face — the
 * face is `rulerValue` below, which is the stop in the active mode's idiom.
 * Every mode resolves stop n to the same half-point line; only the side, and
 * the words, differ.
 *
 * Half points are what makes a counting stat unambiguous: no game ever lands
 * ON 0.5, so there is no push and every game is a hit or a miss.
 */
export function selectionFor(n: number, mode: HitMode): HitSelection {
  return { line: n - 0.5, side: mode === 'under' ? 'under' : 'over' };
}

/**
 * The number on the ruler's face at stop `n` — whole in At Least, the book's
 * half-point line in Over and Under.
 *
 * The ruler snaps on whole stops (an integer index is what a scroll offset
 * divides cleanly into), so the face is a rendering of the stop rather than
 * the state itself. Both the tick labels and the centre pill read this, so
 * they cannot drift apart.
 */
export function rulerValue(n: number, mode: HitMode): number {
  return mode === 'atLeast' ? n : n - 0.5;
}

/** The face as it is printed: "1" in At Least, "0.5" in Over / Under. */
export function rulerValueLabel(n: number, mode: HitMode): string {
  return String(rulerValue(n, mode));
}

/**
 * What the bet is called, under the ruler and on the betslip.
 *
 * In the active mode's own idiom, because the mode is the user's statement of
 * which vocabulary they read prices in. At Least says "2+ Hits"; Over says
 * "Over 1.5 Hits", which is the string their sportsbook prints beside the
 * price. Neither is translated into the other here — the picker sheet shows
 * all three at once, which is where the equivalence belongs.
 */
export function hitModeHeadline(n: number, mode: HitMode, statLabel: string): string {
  const label = statLabel.trim();
  if (mode === 'atLeast') return `${thresholdLabel(n - 0.5, 'over')} ${label}`.trim();
  return `${hitModeLineLabel(n, mode)} ${label}`.trim();
}

/** The book's own name for the bet at ruler stop `n` — "Over 0.5", "Under 1.5". */
export function hitModeLineLabel(n: number, mode: HitMode): string {
  const { line, side } = selectionFor(n, mode);
  return bookLineLabel(line, side);
}

/**
 * "Over 1.5" / "Under 1.5" — a half-point line named the way the sportsbook
 * posts it.
 *
 * ONE home for the book's idiom, because three places speak it: the Over /
 * Under headline, the caption on an odds pill whose book posts a different
 * number, and the add-to-betslip explainer that quotes both in one sentence.
 * The explainer reads "The board is on Over 0.5 Hits; FanDuel only posts Over
 * 1.5" — one sentence, one vocabulary. It said "… only posts 2+" until
 * 2026-09-06, which put the fan's idiom and the book's in the same breath.
 */
export function bookLineLabel(line: number, side: HitDirection): string {
  return `${side === 'under' ? 'Under' : 'Over'} ${line}`;
}

/**
 * "2+" / "1 or fewer" — the FAN's idiom for a whole-number threshold, given a
 * half-point line and a side.
 *
 * The other vocabulary, and the one At Least is named in. One home for the
 * same reason `bookLineLabel` has one.
 *
 * The stat label always stays PLURAL — "1 or fewer Hits", never "1 or fewer
 * Hit" — because no strip-the-s rule survives "3PM", "PRA", "RBI", "Total
 * Bases" or "Passes Defended".
 */
export function thresholdLabel(line: number, side: HitDirection): string {
  return side === 'under' ? `${line - 0.5} or fewer` : `${line + 0.5}+`;
}
