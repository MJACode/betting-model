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
    // "N or fewer", the exact mirror of "N+" ("N or more"), and it keeps the
    // stat label PLURAL. Singularising was the obvious alternative and does
    // not survive this label set — "3PM", "PRA", "RBI", "Total Bases",
    // "Passes Defended" — so the sentence bends instead of the noun
    // (UX review, 2026-09-05). "0 or fewer" is nobody's phrasing, hence "No".
    return n <= 1 ? `No ${label}`.trim() : `${thresholdLabel(n - 0.5, 'under')} ${label}`.trim();
  }
  return `${n}+ ${label}`.trim();
}

/**
 * The book's own name for the same bet — "Over 1.5", "Under 1.5".
 *
 * The headline speaks the fan's idiom ("2+ Hits") because the price beside it
 * and the betslip explainer are both written that way. But with the ruler on
 * 1 and the headline on "2+", the number that connects them — 1.5 — appeared
 * nowhere, and a mode whose effect you have to derive reads as a mode that
 * did nothing (UX review, 2026-09-05). This is that number, shown beside the
 * headline, not instead of it.
 */
export function hitModeLineLabel(n: number, mode: HitMode): string {
  const { line, side } = selectionFor(n, mode);
  return `${side === 'under' ? 'Under' : 'Over'} ${line}`;
}

/**
 * "2+" / "1 or fewer" — the board's own way of naming a whole-number
 * threshold, given a half-point line and a side.
 *
 * ONE home for the idiom, because three places speak it: this module's
 * headline, the Stats pill's off-line caption, and the add-to-betslip
 * explainer that quotes both in a single sentence. They disagreed the moment
 * one of them changed (UX review, 2026-09-05), so they share this instead.
 *
 * The stat label always stays PLURAL — "1 or fewer Hits", never "1 or fewer
 * Hit" — because no strip-the-s rule survives "3PM", "PRA", "RBI", "Total
 * Bases" or "Passes Defended".
 */
export function thresholdLabel(line: number, side: HitDirection): string {
  return side === 'under' ? `${line - 0.5} or fewer` : `${line + 0.5}+`;
}
