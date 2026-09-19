/**
 * The line ruler's STOPS — how far one notch of a drag moves the number.
 *
 * Matt, 2026-09-19, on an NFL Pass Yards board: *"When dragging the numbers it
 * should always drag by 5. Make this a change for all NFL and NCAAF player
 * stats."* The ruler had one stop per whole unit, so a passing-yards line
 * walked 225 → 226 → 227; the stop a user actually wants is the next number a
 * book hangs a line at, and on football yardage that is a multiple of five.
 *
 * WHICH STATS. Yardage only, and only in the two football leagues (his call,
 * same session, against the alternative of every NFL/NCAAF stat). A step of
 * five applied to Pass TDs — whose ruler runs 1..10 — would leave exactly two
 * reachable stops, 5 and 10, and no way to ask for "2+ TDs" at all. The same
 * shape of rule already exists one screen over: `lineStepFor` in
 * `lib/playerLog.ts` steps the player-detail line by 25 above 100 and 5 above
 * 40, "the increments books actually hang lines at".
 *
 * WHY THE STOPS ARE A SCALE AND NOT AN INDEX. `lineN` is the whole-number
 * threshold (`selectionFor` turns it into the half-point line every downstream
 * reader uses), and it stayed equal to the ruler's index only for as long as
 * every step was 1. It is the VALUE now, and the index is derived — which is
 * why the scroll offset, the tick list, the ends and the VoiceOver
 * increment all resolve through `stopIndexOf` / `stopAt` here rather than each
 * doing its own arithmetic. Two of them disagreeing is a thumb that lands on a
 * number the board cannot then be filtered to.
 *
 * Pure (no react-native import) so it can be verified headlessly:
 *   npx tsx scripts/verify_line_ruler.ts
 */

import { defaultThresholdFor, type StatDef } from '@/lib/statCatalog';
import type { HitMode } from '@/lib/hitMode';

/** One drag notch on a football yardage ruler. */
export const YARDAGE_STEP = 5;

/**
 * The yardage stats, by catalog key. Listed rather than inferred from
 * `defaultLine >= 40`, which would also be true of a future high-count
 * counting stat and would move its ruler without anyone deciding to.
 */
const YARDAGE_KEYS: ReadonlySet<string> = new Set([
  'passing_yards',
  'rushing_yards',
  'receiving_yards',
]);

/** How much one notch of the ruler moves the line, for a stat. */
export function rulerStepFor(def: StatDef | null): number {
  if (!def) return 1;
  if (def.sport !== 'NFL' && def.sport !== 'NCAAF') return 1;
  return YARDAGE_KEYS.has(String(def.key)) ? YARDAGE_STEP : 1;
}

/** A ruler's reachable numbers: `min`, `min + step`, … up to `max`. */
export interface RulerScale {
  min: number;
  max: number;
  step: number;
}

/**
 * Where the board opens for a stat, snapped onto that stat's own grid.
 *
 * Stat defaults are half-lines (224.5, 49.5) so the whole number is the first
 * one that clears them; on a step-5 ruler that whole number is then rounded to
 * the nearest stop, because a value off the grid is one the ruler can show
 * once and never return to.
 */
export function defaultLineN(def: StatDef | null): number {
  const step = rulerStepFor(def);
  const whole = Math.max(1, Math.ceil(defaultThresholdFor(def)));
  return Math.max(step, Math.round(whole / step) * step);
}

/** Upper bound of the ruler — generous enough to cover league leaders. */
export function maxLineN(def: StatDef | null): number {
  return Math.max(10, defaultLineN(def) * 3);
}

/**
 * The scale a stat's ruler runs on, in the active mode.
 *
 * The first stop is one step, not 1: stop 0 would be "at least none" — every
 * game — and "under -0.5", which no game can be and no book prices.
 *
 * Under needs ONE EXTRA STOP, because "Under n" names "n-1 or fewer": without
 * it "675 or fewer Pass Yards" is unsayable while "675+" is (UX review,
 * 2026-09-06). One extra STOP is one step, not one unit — a +1 here would put
 * the ceiling off the grid, where the strip cannot scroll to it.
 */
export function rulerScaleFor(def: StatDef | null, mode: HitMode): RulerScale {
  const step = rulerStepFor(def);
  const min = step;
  const ceiling = maxLineN(def) + (mode === 'under' ? step : 0);
  // Align down, so the last tick is a stop the strip can actually settle on.
  return { min, max: min + Math.max(0, Math.floor((ceiling - min) / step)) * step, step };
}

/** How many stops the ruler has. */
export function stopCount(s: RulerScale): number {
  return Math.max(1, Math.floor((s.max - s.min) / s.step) + 1);
}

/**
 * The value at a stop index, clamped to the scale's ends.
 *
 * A non-finite index reads as the floor rather than propagating: this is fed
 * the SCROLL OFFSET divided by the tick width, and a zero tick width on the
 * first frame would otherwise hand the board a NaN line — which no clamp
 * catches, because every comparison against NaN is false.
 */
export function stopAt(i: number, s: RulerScale): number {
  if (!Number.isFinite(i)) return s.min;
  const idx = Math.min(stopCount(s) - 1, Math.max(0, Math.round(i)));
  return s.min + idx * s.step;
}

/** The index of the stop nearest a value — what a scroll offset divides into. */
export function stopIndexOf(v: number, s: RulerScale): number {
  if (!Number.isFinite(v)) return 0;
  return Math.min(stopCount(s) - 1, Math.max(0, Math.round((v - s.min) / s.step)));
}

/**
 * The nearest reachable value. Every value that reaches state goes through
 * this — a stat switch, a mode switch, a restored default — so nothing can put
 * the ruler on a number it cannot scroll back to.
 */
export function snapStop(v: number, s: RulerScale): number {
  return stopAt(stopIndexOf(v, s), s);
}
