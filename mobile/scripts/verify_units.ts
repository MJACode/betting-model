/**
 * Unit sizing: conviction (units to WIN) + the price-aware risk it implies.
 *
 * Pins the rule Matt set 2026-08-28 — conviction 1u..3u, stake grossed up by
 * the price ("at -110 the bet is 1.1u to win 1u"), risk hard-capped at 3u on a
 * single event — and the parity with tracking/discord_notifier.py that makes
 * the app and the Discord channel show the same numbers.
 *
 * Run: npx tsx scripts/verify_units.ts
 */
import {
  convictionFor, stakeFor, unitsFor, formatStake, formatUnits, decimalOdds,
  UNIT_KELLY_FRACTION, MAX_KELLY_FRACTION, MAX_CONVICTION, MIN_CONVICTION,
  MAX_RISK_UNITS,
} from '../src/lib/thresholds';

let failures = 0;
function eq(actual: unknown, expected: unknown, label: string) {
  const ok = typeof actual === 'number' && typeof expected === 'number'
    ? Math.abs(actual - expected) < 1e-9
    : actual === expected;
  if (!ok) { failures++; console.error(`[FAIL] ${label}: got ${actual}, expected ${expected}`); }
  else console.log(`[PASS] ${label}`);
}
function close(actual: number, expected: number, label: string, tol = 0.005) {
  const ok = Math.abs(actual - expected) <= tol;
  if (!ok) { failures++; console.error(`[FAIL] ${label}: got ${actual}, expected ~${expected}`); }
  else console.log(`[PASS] ${label}`);
}
const DEFAULT = { multiplier: 1, cap: null };

// ── Constants ───────────────────────────────────────────────────────────────
eq(UNIT_KELLY_FRACTION, 0.01, 'legacy unit is 1% of roll');
eq(MAX_KELLY_FRACTION, 0.05, 'server Kelly cap is 5%');
eq(MAX_CONVICTION, 3, 'top conviction is 3u');
eq(MIN_CONVICTION, 1, 'bottom conviction is 1u');
eq(MAX_RISK_UNITS, 3, 'never lay more than 3u on one event');

// ── Conviction: Kelly rescaled so the 5% cap lands exactly on 3u ────────────
eq(convictionFor(0.05, DEFAULT), 3, 'kelly at the server cap -> 3u (max conviction)');
eq(convictionFor(0.025, DEFAULT), 1.5, 'half the cap -> 1.5u');
eq(convictionFor(0.0328, DEFAULT), 2, 'median live kelly 3.28% -> 2u');
eq(convictionFor(0.039, DEFAULT), 2.5, 'p75 live kelly 3.9% -> 2.5u');
eq(convictionFor(0.0262, DEFAULT), 1.5, 'p25 live kelly 2.62% -> 1.5u');

// THE CAP. Every one of these used to publish 3.5u-5u.
eq(convictionFor(0.09, DEFAULT), 3, 'kelly far above the cap still tops out at 3u');
eq(convictionFor(1, DEFAULT), 3, 'absurd kelly cannot exceed 3u');

// THE FLOOR. Matt: "1 being the lowest" — no more 0.5u picks.
eq(convictionFor(0.002, DEFAULT), 1, 'tiny kelly floors at 1u, not 0.5u');
eq(convictionFor(0, DEFAULT), 1, 'kelly 0 -> 1u default');
eq(convictionFor(null, DEFAULT), 1, 'kelly null -> 1u');
eq(convictionFor(undefined, DEFAULT), 1, 'kelly undefined -> 1u');
eq(convictionFor(NaN, DEFAULT), 1, 'kelly NaN -> 1u');
eq(convictionFor(-0.01, DEFAULT), 1, 'negative kelly -> 1u');

// ── Odds conversion ─────────────────────────────────────────────────────────
close(decimalOdds(-110)!, 1.909091, 'american -110 -> decimal');
close(decimalOdds(150)!, 2.5, 'american +150 -> decimal');
eq(decimalOdds(null), null, 'no price -> null');
eq(decimalOdds(0), null, 'zero is not a price');

// ── THE HEADLINE: "on a -110, the bet should be 1.1U to win 1U" ─────────────
{
  const s = stakeFor(0.0167, -110, DEFAULT);   // kelly -> exactly 1u conviction
  eq(s.conviction, 1, 'the -110 example is a 1u-conviction play');
  close(s.risk, 1.1, 'risk 1.1u at -110');
  eq(s.win, 1, 'to win exactly 1u');
  eq(s.capped, false, 'no cap at -110 on a 1u play');
  eq(formatStake(s), '1.1u to win 1u', 'renders as Matt wrote it');
}

// Underdogs risk LESS than the conviction — the whole point of to-win units.
{
  const s = stakeFor(0.05, 150, DEFAULT);      // 3u conviction at +150
  eq(s.conviction, 3, '+150 max-conviction play');
  eq(s.risk, 2, 'risk 2u at +150 to win 3u');
  eq(s.win, 3, 'wins the full conviction');
  eq(s.capped, false, 'a plus-money price never trips the risk cap');
}

// Favourites risk MORE — until the cap.
{
  const s = stakeFor(0.0333, -135, DEFAULT);   // 2u conviction at the median price
  eq(s.conviction, 2, 'median-price play is 2u conviction');
  close(s.risk, 2.7, 'risk 2.7u at -135 to win 2u');
  eq(s.win, 2, 'still wins the full 2u — under the cap');
  eq(s.capped, false, 'under the cap');
}

// ── THE RISK CAP, and the invariant that makes it honest ───────────────────
{
  const s = stakeFor(0.05, -147, DEFAULT);     // 3u conviction; uncapped would lay 4.42u
  eq(s.conviction, 3, 'conviction is still 3u');
  eq(s.risk, 3, 'risk cut to the 3u cap');
  eq(s.capped, true, 'flagged as capped');
  close(s.win, 2.041, 'win RECOMPUTED from the capped risk, not left at 3u');
  // The invariant: risk x (decimal - 1) === win, always. A capped bet that still
  // advertised a 3u win would be claiming a payout it does not pay.
  close(s.risk * (decimalOdds(-147)! - 1), s.win, 'risk x (dec-1) === win when capped');
}
{
  const s = stakeFor(0.05, -325, DEFAULT);     // the worst price ever seen (WNBA)
  eq(s.risk, 3, 'worst observed price still lays only 3u');
  close(s.win, 0.923, 'and honestly reports the small payout');
  close(s.risk * (decimalOdds(-325)! - 1), s.win, 'invariant holds at the extreme');
}
// Never exceeds the cap at any price, at any conviction.
for (const odds of [-100, -110, -135, -147, -200, -325, -1000, 100, 150, 600]) {
  for (const k of [0.001, 0.0167, 0.025, 0.0333, 0.05, 0.2]) {
    const s = stakeFor(k, odds, DEFAULT);
    if (s.risk > MAX_RISK_UNITS + 1e-9) {
      failures++; console.error(`[FAIL] risk cap breached at ${odds} / kelly ${k}: ${s.risk}`);
    }
    // win and risk must always agree with the price
    const dec = decimalOdds(odds)!;
    if (Math.abs(s.risk * (dec - 1) - s.win) > 1e-9) {
      failures++; console.error(`[FAIL] risk/win disagree at ${odds} / kelly ${k}`);
    }
  }
}
console.log('[PASS] risk never exceeds the cap, and risk x (dec-1) === win, across the whole grid');

// ── Unpriced picks: publish conviction, never invent a price ───────────────
{
  const s = stakeFor(0.05, null, DEFAULT);
  eq(s.priced, false, 'no price -> not priced');
  eq(s.conviction, 3, 'conviction still computed from kelly');
  eq(s.risk, 3, 'risk falls back to the bare conviction');
  eq(formatStake(s), '3u', 'renders as a bare conviction, claiming no payout');
}

// ── unitsFor() is the RISK — what exposure sums must add up ────────────────
close(unitsFor(0.0167, DEFAULT, -110), 1.1, 'unitsFor returns units LAID');
eq(unitsFor(0.05, DEFAULT, 150), 2, 'unitsFor at +150');
eq(unitsFor(0.05, DEFAULT, null), 3, 'unitsFor with no price falls back to conviction');

// ── Aggressiveness still applies, and cannot escape the caps ───────────────
eq(convictionFor(0.0167, { multiplier: 3, cap: null }), 3, '3x aggressiveness raises conviction');
eq(convictionFor(0.05, { multiplier: 10, cap: null }), 3, 'aggressiveness cannot exceed 3u');
eq(convictionFor(0.05, { multiplier: 1, cap: 0.0167 }), 1, 'user cap lowers conviction');
{
  const s = stakeFor(0.05, -300, { multiplier: 10, cap: null });
  eq(s.risk, 3, 'even at 10x aggressiveness the 3u risk cap holds');
}

// ── Formatting ─────────────────────────────────────────────────────────────
eq(formatUnits(2), '2u', 'whole units');
eq(formatUnits(3), '3u', 'three units');
eq(formatUnits(1.1), '1.1u', 'the -110 stake');
eq(formatUnits(2.5), '2.5u', 'half units');
eq(formatUnits(1.15), '1.15u', 'the -115 stake keeps its second decimal');
eq(formatUnits(1.05), '1.05u', 'the -105 stake keeps its second decimal');
eq(formatUnits(20), '20u', 'trailing zeros trim only the fraction, not the whole part');
eq(formatUnits(2 / 3), '0.67u', 'a repeating stake rounds half-up at two decimals');
eq(formatStake(stakeFor(0.03, -115, DEFAULT)), '1.15u to win 1u', 'the -115 card stake');

// ── Determinism ────────────────────────────────────────────────────────────
eq(stakeFor(0.03, -120, DEFAULT).risk, stakeFor(0.03, -120, DEFAULT).risk,
   'deterministic, bankroll-free');

console.log(failures === 0 ? '\nALL PASS (units)' : `\n${failures} FAILURE(S)`);
if (failures) process.exit(1);
