/**
 * Standalone verification for the two-thumb range slider's math
 * (src/lib/rangeSlider.ts). Run with:
 *
 *   npx tsx scripts/verify_range_slider.ts
 *
 * The slider replaced the hit-rate band's two numeric fields (2026-09-12), so
 * these are the guards on what a finger can now produce: a value off the
 * scale, a thumb through its partner, a band that collapses and cannot be
 * reopened, or a touch read against the wrong origin.
 */

import {
  applyBound,
  grabTarget,
  resolveTie,
  snapTo,
  valueAtX,
  type Scale,
} from '../src/lib/rangeSlider';
import { HIT_RATE_MAX, HIT_RATE_MIN, HIT_RATE_PRESETS, HIT_RATE_STEP } from '../src/lib/statsBoard';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// The scale the Stats sheet actually ships, so these run on the real numbers.
const S: Scale = { min: HIT_RATE_MIN, max: HIT_RATE_MAX, step: HIT_RATE_STEP };

// ── 1. Snapping ──

check('snaps to the nearest stop', snapTo(62, S) === 60 && snapTo(63, S) === 65);
check('a stop is left alone', snapTo(60, S) === 60);
check('never leaves the scale', snapTo(-40, S) === 0 && snapTo(140, S) === 100);
check('garbage is the floor, not NaN', snapTo(Number.NaN, S) === 0);
check('every stop is a multiple of the step',
  Array.from({ length: 21 }, (_, i) => snapTo(i * 5, S)).every((v) => v % HIT_RATE_STEP === 0));

// ── 2. Touch → value ──
// A 300pt track whose left edge sits 40pt into the window.
const W = 300;
const X0 = 40;
const at = (pageX: number) => valueAtX(pageX, X0, W, S);

check('the left edge is the floor', at(X0) === 0);
check('the right edge is the ceiling', at(X0 + W) === 100);
check('the middle is the middle', at(X0 + W / 2) === 50);
check('a touch past either end is clamped, not extrapolated',
  at(X0 - 500) === 0 && at(X0 + W + 500) === 100);
// The origin is the TRACK's, not the window's: reading a touch against 0 when
// the track starts at 40 shifts every value on the scale.
check('the track origin is subtracted', at(X0 + 150) !== valueAtX(X0 + 150, 0, W, S));
check('a track with no width yet reads as the floor (no divide by zero)',
  valueAtX(X0 + 150, X0, 0, S) === 0 && Number.isFinite(valueAtX(X0, X0, 0, S)));

// ── 3. Bounds — the thumbs meet, they never cross ──

check('min moves freely below max', applyBound('low', 40, 20, 80).low === 40);
check('max moves freely above min', applyBound('high', 90, 20, 80).high === 90);
const crossed = applyBound('low', 95, 20, 80);
check('min dragged past max pins AT max', crossed.low === 80 && crossed.high === 80);
const crossedHigh = applyBound('high', 5, 20, 80);
check('max dragged below min pins AT min', crossedHigh.low === 20 && crossedHigh.high === 20);
check('moving one end never moves the other',
  applyBound('low', 30, 20, 80).high === 80 && applyBound('high', 70, 20, 80).low === 20);

// ── 4. The collapsed band is not a dead end ──

check('coincident thumbs defer the grab', grabTarget(60, 60, 60) === 'tie');
check('a deferred grab waits for a real movement', resolveTie(1) === null);
check('dragging right off a collapsed band takes the MAX thumb', resolveTie(12) === 'high');
check('dragging left off a collapsed band takes the MIN thumb', resolveTie(-12) === 'low');
// End to end: the band collapses at 60 and reopens upward on the next drag.
const collapsed = applyBound('low', 95, 60, 60);
const reopened = applyBound(resolveTie(20) ?? 'high', 80, collapsed.low, collapsed.high);
check('a collapsed band reopens', reopened.low === 60 && reopened.high === 80,
  JSON.stringify(reopened));

// ── 5. Grab picks the nearer thumb ──

check('a touch near the min takes the min', grabTarget(25, 20, 80) === 'low');
check('a touch near the max takes the max', grabTarget(75, 20, 80) === 'high');
check('a touch dead centre takes the min (the tie goes left, deterministically)',
  grabTarget(50, 20, 80) === 'low');
check('a touch outside the band takes the end it is outside of',
  grabTarget(5, 20, 80) === 'low' && grabTarget(99, 20, 80) === 'high');

// ── 6. Every preset chip is a position the finger can reach ──
// The chips set the band directly, so a preset off the stop grid would leave
// the slider unable to reproduce what the chip above it just set.
check('every preset round-trips through the slider',
  HIT_RATE_PRESETS.every((p) => snapTo(p, S) === p), HIT_RATE_PRESETS.join(', '));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
