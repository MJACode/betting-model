/**
 * Pure geometry and bound-keeping for the two-thumb RangeSlider.
 *
 * Split out of the component because this is where a slider actually goes
 * wrong — a thumb that crosses its partner, a touch near the end that reads
 * 101%, a collapsed band that can never be reopened — and none of that is
 * reachable from a headless test while it lives inside PanResponder callbacks.
 *
 * Verify with: npx tsx scripts/verify_range_slider.ts
 */

export interface Scale {
  min: number;
  max: number;
  /** Snap interval, in the scale's units. */
  step: number;
}

/** Nearest stop on the scale, clamped to its ends. */
export function snapTo(v: number, s: Scale): number {
  if (!Number.isFinite(v)) return s.min;
  const stepped = Math.round((v - s.min) / s.step) * s.step + s.min;
  return Math.min(s.max, Math.max(s.min, stepped));
}

/**
 * A touch's WINDOW x → a value on the scale.
 *
 * `originX` is the track's own left edge in window coordinates, not the
 * finger's offset inside whatever view it happens to be over: once a thumb
 * catches up with the finger, that view IS the thumb, and a location read off
 * a 44pt box would put the value somewhere near the middle of the scale
 * forever. A zero-width track (first frame, before layout) reads as `min`
 * rather than dividing by nothing.
 */
export function valueAtX(pageX: number, originX: number, width: number, s: Scale): number {
  if (!(width > 0)) return s.min;
  // No clamp here on purpose — `snapTo` is the one place the scale's ends are
  // enforced, so a drag that runs off the track lands on min or max by the
  // same rule as everything else. A second clamp would just be a second place
  // to get it wrong (and the mutation test proved it changed nothing).
  const frac = (pageX - originX) / width;
  return snapTo(s.min + frac * (s.max - s.min), s);
}

/**
 * Move one end of the band, keeping the pair ordered.
 *
 * The thumbs MEET but never cross: dragging min past max pins it at max, which
 * collapses the band to a single percent — a legitimate filter ("exactly
 * 60%"), and one the user can always reopen by dragging the other way.
 * Swapping the thumbs instead is the alternative, and it hands the finger to
 * the thumb it was not holding mid-drag.
 */
export function applyBound(
  which: 'low' | 'high',
  value: number,
  low: number,
  high: number,
): { low: number; high: number } {
  return which === 'low'
    ? { low: Math.min(value, high), high }
    : { low, high: Math.max(value, low) };
}

/**
 * Which thumb a touch at `v` should take.
 *
 * Coincident thumbs are indistinguishable by position — there is no nearer
 * one — so the choice is deferred ('tie') to the first move's direction.
 * Without that a collapsed band is a dead control: the grab would always land
 * on the same thumb and that thumb is already pinned against the other.
 */
export function grabTarget(v: number, low: number, high: number): 'low' | 'high' | 'tie' {
  if (low === high) return 'tie';
  return Math.abs(v - low) <= Math.abs(v - high) ? 'low' : 'high';
}

/** Resolve a deferred grab once the finger has moved far enough to mean it. */
export function resolveTie(dx: number, slop = 2): 'low' | 'high' | null {
  if (Math.abs(dx) < slop) return null;
  return dx > 0 ? 'high' : 'low';
}

/**
 * What a gesture on the track has turned out to be, once the finger has moved
 * far enough to say.
 *
 * The slider lives inside the filter sheet's ScrollView, and the first version
 * of it claimed every touch on contact AND committed a value on grant — so a
 * user who put a finger on the 44pt strip to flick the sheet did not merely
 * fail to scroll, they moved a thumb and re-filtered the board behind them
 * (UX review, 2026-09-12). Intent is read from the gesture instead: a
 * horizontal drag is the slider's, a vertical one belongs to the sheet, and
 * neither is decided until the finger has travelled past the slop.
 *
 * Two calibrations, both deliberate:
 *
 *  - A TIE goes to the sheet, not to the slider. iOS does not block the native
 *    scroll view under a JS responder (`RCTUIManager` discards
 *    `blockNativeResponder`; it is Android-only), so a ~45° flick can start the
 *    sheet scrolling AND move a thumb before the terminate lands. Dominance is
 *    a ratio for that reason, not a `>=`.
 *  - The slop that claims a DRAG is not the slop that classifies a finished
 *    TOUCH. 6pt is right for "the finger meant to drag"; judging a released
 *    tap by it throws away an ordinary sloppy tap — UIKit's own
 *    `allowableMovement` is 10pt — and on a sheet short enough not to scroll
 *    (`bounces={false}`) nothing else would have happened either. Callers pass
 *    the wider slop at release.
 */
export type GestureIntent = 'idle' | 'drag' | 'scroll';

/** How far a horizontal drag must dominate a vertical one to be the slider's. */
export const DRAG_DOMINANCE = 1.2;

export function readIntent(dx: number, dy: number, slop = 6): GestureIntent {
  if (Math.max(Math.abs(dx), Math.abs(dy)) < slop) return 'idle';
  return Math.abs(dx) > Math.abs(dy) * DRAG_DOMINANCE ? 'drag' : 'scroll';
}

/** Release-time slop — a tap is allowed to wobble further than a drag claim. */
export const TAP_SLOP = 10;

/**
 * Which thumb a TAP moves — the one case that cannot be deferred, because a
 * tap has no direction to defer to. Collapsed bands open toward the tap.
 */
export function tapTarget(v: number, low: number, high: number): 'low' | 'high' {
  if (low === high) return v >= low ? 'high' : 'low';
  return grabTarget(v, low, high) as 'low' | 'high';
}
