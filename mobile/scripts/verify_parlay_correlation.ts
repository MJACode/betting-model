/**
 * Standalone verification for the Gaussian-copula parlay engine
 * (src/lib/parlayCorrelation.ts). No JS test runner is configured for the app,
 * so — like the original parlay math (CLAUDE.md sessions 43/48) — we assert the
 * pure functions here and run with tsx:
 *
 *   npx tsx scripts/verify_parlay_correlation.ts
 *
 * Pins: independence reproduces Π p exactly; a positive same-game pair lifts the
 * joint above the product; a negative pair drops it below; grading maps EV
 * correctly; PSD repair survives a non-PD matrix; results are deterministic.
 */

import {
  computeCorrelatedMetrics,
  correlatedJointProb,
  gradeForEv,
  PARLAY_CORRELATION_PRIORS,
  type RhoTable,
} from '../src/lib/parlayCorrelation';
import type { ParlayLeg } from '../src/lib/parlay';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}
function approx(a: number, b: number, tol = 1e-9): boolean {
  return Math.abs(a - b) <= tol;
}

const rho: RhoTable = PARLAY_CORRELATION_PRIORS;

/** Minimal ParlayLeg builder. `side`/`sport` feed the correlation taxonomy. */
function leg(
  pickId: number,
  modelId: string,
  gameId: string,
  modelProb: number,
  americanOdds: number,
  side: Pick['pick_side'] = 'over',
  sport = 'MLB',
): ParlayLeg {
  const decimalOdds = americanOdds > 0 ? 1 + americanOdds / 100 : 1 + 100 / Math.abs(americanOdds);
  const pick = { pick_side: side, sport } as unknown as Pick;
  return {
    pickId,
    gameId,
    modelId,
    isGameLine: false,
    isFavorite: americanOdds < 0,
    label: `${modelId} #${pickId}`,
    modelProb,
    decimalOdds,
    americanOdds,
    legEdge: 0,
    pick,
    game: null,
  };
}

const product = (legs: ParlayLeg[]) => legs.reduce((a, l) => a * l.modelProb, 1);

// 1. Independence: legs in different games → exact Π p, no MC.
{
  const legs = [
    leg(1, 'mlb_prop_batter_hits', 'G1', 0.6, -110),
    leg(2, 'mlb_prop_batter_hits', 'G2', 0.55, -110),
    leg(3, 'wnba_prop_player_points', 'G3', 0.62, -110, 'over', 'WNBA'),
  ];
  const { jointProb, hasCorrelation } = correlatedJointProb(legs, rho);
  check('Independent cross-game legs reproduce Π p exactly', approx(jointProb, product(legs)), `joint=${jointProb} prod=${product(legs)}`);
  check('Independent set flagged hasCorrelation=false', hasCorrelation === false);
}

// 2. Positive same-game pair: batter hits over + game total over → joint > product.
{
  const legs = [
    leg(10, 'mlb_prop_batter_hits', 'G9', 0.6, -110, 'over'),
    leg(11, 'mlb_over_under', 'G9', 0.55, -110, 'over'),
  ];
  const { jointProb, hasCorrelation } = correlatedJointProb(legs, rho);
  check('Positive same-game pair lifts joint above product', hasCorrelation && jointProb > product(legs) + 1e-4, `joint=${jointProb.toFixed(4)} prod=${product(legs).toFixed(4)}`);
}

// 3. Negative same-game pair: pitcher Ks over + opposing batter hits over → joint < product.
{
  const legs = [
    leg(20, 'mlb_prop_pitcher_k', 'G9', 0.6, -110, 'over'),
    leg(21, 'mlb_prop_batter_hits', 'G9', 0.55, -110, 'over'),
  ];
  const { jointProb, hasCorrelation } = correlatedJointProb(legs, rho);
  check('Negative same-game pair drops joint below product', hasCorrelation && jointProb < product(legs) - 1e-4, `joint=${jointProb.toFixed(4)} prod=${product(legs).toFixed(4)}`);
}

// 3b. Pitcher Ks over + game total UNDER → positive (suppression ↔ fewer runs).
{
  const legs = [
    leg(30, 'mlb_prop_pitcher_k', 'G9', 0.6, -110, 'over'),
    leg(31, 'mlb_over_under', 'G9', 0.55, -110, 'under'),
  ];
  const { jointProb } = correlatedJointProb(legs, rho);
  check('Ks-over + total-under is positively correlated', jointProb > product(legs) + 1e-4, `joint=${jointProb.toFixed(4)} prod=${product(legs).toFixed(4)}`);
}

// 4. Grade mapping.
{
  check('gradeForEv(-0.10) = bad', gradeForEv(-0.1) === 'bad');
  check('gradeForEv(0.0) = fair', gradeForEv(0.0) === 'fair');
  check('gradeForEv(0.05) = good', gradeForEv(0.05) === 'good');
  check('gradeForEv(0.12) = great', gradeForEv(0.12) === 'great');
  // A juiced negative-EV combo grades Bad and shows a positive DK hold.
  const juiced = [leg(40, 'mlb_moneyline', 'G1', 0.5, -200), leg(41, 'mlb_moneyline', 'G2', 0.5, -200)];
  const jm = computeCorrelatedMetrics(juiced, rho);
  check('Juiced -EV combo grades Bad', jm.grade === 'bad', `ev=${jm.ev.toFixed(3)}`);
  check('Juiced -EV combo shows positive DK hold', jm.dkHoldPct > 0, `hold=${(jm.dkHoldPct * 100).toFixed(1)}%`);
}

// 5. PSD repair: a high-magnitude same-game triple can produce a non-PD matrix;
//    the engine must still return a finite joint probability.
{
  const legs = [
    leg(50, 'mlb_prop_pitcher_k', 'G9', 0.6, -110, 'over'),
    leg(51, 'mlb_prop_pitcher_hits', 'G9', 0.55, -110, 'over'),
    leg(52, 'mlb_over_under', 'G9', 0.5, -110, 'over'),
  ];
  const { jointProb } = correlatedJointProb(legs, rho);
  check('Correlated triple returns a finite joint prob', Number.isFinite(jointProb) && jointProb > 0 && jointProb < 1, `joint=${jointProb.toFixed(4)}`);
}

// 6. Determinism: same slip twice → identical joint probability (seeded PRNG).
{
  const legs = [
    leg(60, 'mlb_prop_batter_hits', 'G9', 0.6, -110, 'over'),
    leg(61, 'mlb_over_under', 'G9', 0.55, -110, 'over'),
  ];
  const a = correlatedJointProb(legs, rho).jointProb;
  const b = correlatedJointProb(legs, rho).jointProb;
  check('Deterministic across runs', a === b, `a=${a} b=${b}`);
}

console.log(failures === 0 ? '\nALL CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
