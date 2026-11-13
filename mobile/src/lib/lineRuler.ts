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

/**
 * The stop count the ruler chooses its PITCH from — always At Least's, never
 * the live mode's.
 *
 * Under carries one extra stop, and the pitch is branched on a count, so a
 * stat sitting on the branch's boundary changed appearance on one tap of the
 * direction pill: NFL Rush Yards is 30 stops in At Least and 31 in Under, and
 * that tipped it from 30pt ticks labelled every 5 yards to 12pt ticks labelled
 * every 25 — the same drag worth 3.8x as much, on a control whose whole
 * documented promise is that a mode change renames the bet without moving it
 * (UX review, 2026-09-19). Unreachable while every yardage board was 135+
 * stops; a step of five put three of them on the boundary.
 */
export function baseStopCount(def: StatDef | null): number {
  return stopCount(rulerScaleFor(def, 'atLeast'));
}

/** How many stops the ruler has. */
export function stopCount(s: RulerScale): number {
  return Math.max(1, Math.floor((s.max - s.min) / s.step) + 1);
}

/**
 * The last stop VoiceOver will step to.
 *
 * `scale.max` can sit off the grid (a ceiling that is not a multiple of the
 * step). The strip and the adjustable both stop at this stop. A typed clamp
 * has to use it too, or a number between here and `max` is one a decrement
 * is then refused.
 */
export function rulerHi(s: RulerScale): number {
  return stopAt(stopCount(s) - 1, s);
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

/**
 * A parsed typed line, clamped onto the ruler's `[lo, hi]`.
 *
 * `parseTypedLine` accepts four digits, so "999" is a line. The strip can
 * only scroll to the last stop (`stopIndexOf` clamps the offset), but the
 * VALUE stayed 999. VoiceOver then steps with `stepLineFrom`, which from 999
 * on a step-5 ruler lands on 995, and the ruler's `next <= hi` refuses it —
 * the number is pinned and cannot be stepped down. Clamping the typed value
 * onto the scale leaves the ceiling as a stop VoiceOver can leave.
 *
 * Junk (`null`, non-finite) stays null so the field can still refuse it.
 */
export function clampTypedLine(n: number | null, lo: number, hi: number): number | null {
  if (n == null || !Number.isFinite(n)) return null;
  const floor = Math.min(lo, hi);
  const ceil = Math.max(lo, hi);
  return Math.min(ceil, Math.max(floor, n));
}

/**
 * The text the type-a-line field shows once a typed number has been clamped.
 *
 * `applied` is the number the board will use. When the digits in the field
 * are a different number, the field has to paint `face(applied)` in that
 * same update — otherwise the reader is still looking at 999 while 150 is
 * what was applied. An in-range value, and junk, return null so the field
 * closes without being rewritten.
 */
export function clampedFieldText(
  draft: string,
  applied: number | null,
  face: (n: number) => string,
): string | null {
  if (applied == null || !Number.isFinite(applied)) return null;
  const raw = draft.trim().replace(/\+$/, '');
  const shown = face(applied);
  // Already the applied face — including Over/Under, where "1.5" is stop 2.
  // Returning the same glyphs would setState a no-op and leave the field open.
  if (raw === shown) return null;
  return shown;
}

/** The number the centre is holding, and whether the next settle belongs to
 *  a programmatic scroll rather than a finger. */
export interface RulerHold {
  value: number;
  skipNextSettle: boolean;
}

/**
 * A tap, a VoiceOver step, or a typed commit. Reports `value` itself and
 * arms a one-shot skip of the settle the animated `scrollTo` is about to
 * fire (`onMomentumScrollEnd` on iOS, and on some Android).
 *
 * An off-grid typed line scrolls to the NEAREST stop. Without the skip,
 * settle reads that stop and overwrites the typed number — 47 on Rec Yards
 * (step 5) becomes 45.
 */
export function programmaticPick(value: number): RulerHold {
  return { value, skipNextSettle: true };
}

/** A finger drag started. The pending skip must not swallow this drag's settle. */
export function clearSettleSkip(hold: RulerHold): RulerHold {
  if (!hold.skipNextSettle) return hold;
  return { value: hold.value, skipNextSettle: false };
}

/**
 * `onMomentumScrollEnd` / `onScrollEndDrag`. `offsetStops` is
 * `contentOffset.x / tickW`. The one-shot skip keeps the held value and
 * clears itself; the next settle applies.
 */
export function settleHold(hold: RulerHold, offsetStops: number, scale: RulerScale): RulerHold {
  if (hold.skipNextSettle) return { value: hold.value, skipNextSettle: false };
  return { value: stopAt(offsetStops, scale), skipNextSettle: false };
}

/** The threshold bubble's tap box. 64 wide so a three-digit face and the
 *  pencil fit; 44 tall, the HIG floor. */
export const THRESHOLD_BUBBLE_W = 64;
export const THRESHOLD_BUBBLE_H = 44;

/** A quick tap. Past this the finger is dragging the strip, and the tap fails
 *  so the scroll keeps the gesture. */
export const THRESHOLD_TAP_MAX_DIST = 12;
export const THRESHOLD_TAP_MAX_MS = 250;

export interface BubbleBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** What a typed line does on Done, Return, or blur.
 *
 * `parsed` is the mode's own reading of the draft (`parseTypedLine`), NOT
 * pre-clamped — clamping here is what tells a too-high line from a legal one.
 * Empty restores the value editing started at and says nothing. Anything that
 * does not parse restores that value and says the range. A number outside the
 * ruler is pulled to that end and says so. An in-range number is kept as
 * typed, including one the strip can only park near. */
export interface ThresholdCommit {
  apply: number | null;
  notice: string | null;
}

export function commitTypedThreshold(
  draft: string,
  parsed: number | null,
  lo: number,
  hi: number,
  face: (n: number) => string,
): ThresholdCommit {
  if (draft.trim() === '') return { apply: null, notice: null };
  const floor = Math.min(lo, hi);
  const ceil = Math.max(lo, hi);
  const loText = face(floor);
  const hiText = face(ceil);
  if (parsed == null || !Number.isFinite(parsed)) {
    return { apply: null, notice: `Enter ${loText} to ${hiText}` };
  }
  if (parsed > ceil) return { apply: ceil, notice: `Max is ${hiText}, set to ${hiText}` };
  if (parsed < floor) return { apply: floor, notice: `Min is ${loText}, set to ${loText}` };
  return { apply: parsed, notice: null };
}

/**
 * Where the strip parks while a draft is being typed.
 *
 * A keystroke that parses moves the strip to that number, clamped into the
 * ruler so 999 does not scroll into empty space. The clamp is only the
 * scroll; the field keeps the digits, and Done decides the value. Empty and
 * unparseable drafts return null. The screen scrolls an empty field back to
 * the value the edit opened on, and leaves the strip where it is for a
 * half-typed decimal such as "22.".
 */
export function previewTypedLine(
  draft: string,
  parsed: number | null,
  lo: number,
  hi: number,
): number | null {
  if (draft.trim() === '') return null;
  if (parsed == null || !Number.isFinite(parsed)) return null;
  const floor = Math.min(lo, hi);
  const ceil = Math.max(lo, hi);
  return Math.min(ceil, Math.max(floor, parsed));
}

/** Finger target for the compact marker. The strip itself stays short. */
export const MARKER_HIT_H = 44;

/**
 * How far a 44pt marker target hangs past the short strip, each side.
 * Zero once the strip is already at least 44pt (the typing field).
 */
export function markerHitOverhang(visualH: number, hitH = MARKER_HIT_H): number {
  if (!Number.isFinite(visualH) || visualH <= 0) return 0;
  const target = Number.isFinite(hitH) && hitH > 0 ? hitH : MARKER_HIT_H;
  return Math.max(0, (target - visualH) / 2);
}

/**
 * Marker layout measured inside the visual strip, shifted into the gesture
 * view. The strip sits `overhang` below that view's top; the wings occupy
 * the overhang and are only as wide as the pill.
 */
export function markerBoxInGesture(box: BubbleBox, overhang: number): BubbleBox {
  const shift = Number.isFinite(overhang) ? overhang : 0;
  return { x: box.x, y: box.y + shift, width: box.width, height: box.height };
}

export function pointInBubble(x: number, y: number, box: BubbleBox): boolean {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return false;
  // The compact marker draws at 22pt inside a 28pt strip. The finger target
  // is at least 44pt tall, grown equally above and below the drawn pill.
  // Width stays the pill's, so a tap on a neighbouring tick still moves the line.
  const height = Math.max(box.height, MARKER_HIT_H);
  const top = box.y - (height - box.height) / 2;
  return x >= box.x && x <= box.x + box.width && y >= top && y <= top + height;
}

/** VoiceOver name for the bubble. The stat label is the unit ("Pass Yards").
 *  The gesture lives in THRESHOLD_TYPE_HINT, not in this name: VoiceOver
 *  reads a hint after the name, and a name that already says "double tap"
 *  says it twice. */
export function thresholdBubbleLabel(face: string, statLabel: string): string {
  const unit = statLabel.trim();
  const value = unit.length > 0 ? `${face} ${unit}` : face;
  return `Threshold ${value}`;
}

/** How the bubble is activated. A hint, not part of the name. */
export const THRESHOLD_TYPE_HINT = 'double tap to type a value';

/** Width of the editing field.
 *
 * A web TextInput with no width uses the browser's default (about 20
 * characters: 222pt, and 424pt once the font doubles). That box covered the
 * strip and the direction control. The field is the bubble's width, grown
 * with the text the same way the strip grows, and capped at 2× so it stays
 * a bubble. */
export function thresholdFieldWidth(fontScale: number): number {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  return Math.round(THRESHOLD_BUBBLE_W * Math.min(scale, 2));
}

/**
 * The line control scrolls when 2x text or a landscape window would push it
 * off the page. Portrait at the default size does not.
 */
export function thresholdControlsScroll(fontScale: number, width: number, height: number): boolean {
  if (!Number.isFinite(fontScale) || !Number.isFinite(width) || !Number.isFinite(height)) return false;
  if (fontScale >= 2) return true;
  return width > height;
}

/** How tall the strip is so a 44pt bubble, grown with text, is not clipped. */
export function rulerChromeHeight(fontScale: number): number {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  const bubble = Math.max(THRESHOLD_BUBBLE_H, Math.round(THRESHOLD_BUBBLE_H * Math.min(scale, 2)));
  return Math.max(72, 26 + bubble);
}

/**
 * Resting height of the Stats ruler.
 *
 * Matt, 2026-10-28: the 28pt "Compact B" strip "looks too small and I cannot
 * tell what I'm dragging to". It is now three bands: the selected number on a
 * marker bubble (RULER_MARK_H), a pointer from that bubble onto the ticks,
 * and the tick row with its numbers printed under it (RULER_TICKS_H), so the
 * values passing under the pointer are readable while dragging. Taller than
 * the 44pt tap target, so the marker needs no overhang wings at rest. The
 * marker scales with text up to 1.6x; 2x text scrolls the control
 * (`thresholdControlsScroll`).
 */
export const RULER_MARK_H = 30;
/** Tick marks plus the number row printed under them. */
export const RULER_TICKS_H = 32;

/** Marker bubble height at a text scale (capped at 1.6x). */
export function rulerMarkHeight(fontScale: number): number {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  return Math.round(RULER_MARK_H * Math.min(Math.max(scale, 1), 1.6));
}

export function compactRulerHeight(fontScale: number): number {
  return rulerMarkHeight(fontScale) + RULER_TICKS_H;
}

/**
 * The stop sitting under the centre pointer at a scroll offset — what the
 * bubble shows WHILE the strip is moving, before it settles. Clamped to the
 * strip's ends so an overscroll bounce never names a stop that does not
 * exist.
 */
export function stopUnderOffset(offsetX: number, tickW: number, s: RulerScale): number {
  if (!Number.isFinite(offsetX) || !(tickW > 0)) return s.min;
  const last = stopCount(s) - 1;
  const i = Math.min(Math.max(Math.round(offsetX / tickW), 0), Math.max(last, 0));
  return stopAt(i, s);
}
