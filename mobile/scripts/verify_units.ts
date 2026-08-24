/**
 * Units sizing — must stay in lockstep with units_for() in
 * tracking/discord_notifier.py. At the default 1.00x aggressiveness the app and
 * the Discord channel show the SAME stake for the same pick; if these two ever
 * disagree, a user reading both sees two different numbers for one bet.
 */
import { unitsFor, formatUnits, UNIT_KELLY_FRACTION } from '../src/lib/thresholds';

let failed = 0;
const eq = (got: unknown, want: unknown, what: string) => {
  if (got !== want) { console.error(`FAIL ${what}: got ${got}, want ${want}`); failed++; }
};

const DEFAULT = { multiplier: 1, cap: null };

// 1 unit == 1% of roll.
eq(UNIT_KELLY_FRACTION, 0.01, 'unit is 1% of roll');

// The exact table asserted on the Python side, from today's real picks.
eq(unitsFor(0.02192, DEFAULT), 2, 'kelly 2.19% -> 2u (TEX ML F5)');
eq(unitsFor(0.03045, DEFAULT), 3, 'kelly 3.05% -> 3u (Genao)');
eq(unitsFor(0.03270, DEFAULT), 3.5, 'kelly 3.27% -> 3.5u (DeLauter)');
eq(unitsFor(0.05, DEFAULT), 5, 'kelly at the 5% server cap -> 5u');

// Prob-only picks carry kelly 0 — they publish 1u, never 0u.
eq(unitsFor(0, DEFAULT), 1, 'kelly 0 -> the 1u default');
eq(unitsFor(null, DEFAULT), 1, 'kelly null -> 1u');
eq(unitsFor(undefined, DEFAULT), 1, 'kelly undefined -> 1u');
eq(unitsFor(NaN, DEFAULT), 1, 'kelly NaN -> 1u');
eq(unitsFor(-0.01, DEFAULT), 1, 'negative kelly -> 1u');

// A real but tiny kelly floors rather than rounding away to nothing.
eq(unitsFor(0.002, DEFAULT), 0.5, 'kelly 0.2% floors at 0.5u');

// Rounding is to the nearest half unit.
eq(unitsFor(0.0124, DEFAULT), 1, '1.24% rounds down to 1u');
eq(unitsFor(0.0126, DEFAULT), 1.5, '1.26% rounds up to 1.5u');

// The user's aggressiveness setting scales units; default 1.00x matches Discord.
eq(unitsFor(0.02, { multiplier: 2, cap: null }), 4, '2x aggressiveness doubles units');
eq(unitsFor(0.02, { multiplier: 1, cap: 0.01 }), 1, 'user cap clamps units');

// Formatting drops the trailing zero.
eq(formatUnits(2), '2u', 'whole units');
eq(formatUnits(3.5), '3.5u', 'half units');
eq(formatUnits(0.5), '0.5u', 'half unit');
eq(formatUnits(1), '1u', 'one unit');

// Nothing here may depend on bankroll — that is the entire point.
eq(unitsFor(0.03, DEFAULT), unitsFor(0.03, DEFAULT), 'deterministic, bankroll-free');

console.log(failed === 0 ? 'ALL PASS (units)' : `${failed} check(s) FAILED.`);
process.exit(failed === 0 ? 0 : 1);
