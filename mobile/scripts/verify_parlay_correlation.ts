/**
 * Standalone verification for the Gaussian-copula parlay engine
 * (src/lib/parlayCorrelation.ts). No JS test runner is configured for the app,
 * so — like the original parlay math (CLAUDE.md sessions 43/48) — we assert the
 * pure functions here and run with tsx:
 *
 *   npx tsx scripts/verify_parlay_correlation.ts
 *
 * Pins: independence reproduces Π p exactly; positive/negative same-game pairs
 * move the joint the right way; team resolution makes same-team stacking more
 * correlated than opposing (Phase 2); grading maps EV; PSD repair survives a
 * non-PD matrix; results are deterministic.
 */

import {
  computeCorrelatedMetrics,
  correlatedJointProb,
  gradeForEv,
  PARLAY_CORRELATION_PRIORS,
  type RhoTable,
  type TeamResolver,
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

/** Minimal ParlayLeg builder. `side`/`sport`/`playerId` feed the taxonomy. */
function leg(
  pickId: number,
  modelId: string,
  gameId: string,
  modelProb: number,
  americanOdds: number,
  side: Pick['pick_side'] = 'over',
  sport = 'MLB',
  playerId: string | null = null,
): ParlayLeg {
  const decimalOdds = americanOdds > 0 ? 1 + americanOdds / 100 : 1 + 100 / Math.abs(americanOdds);
  const pick = { pick_side: side, sport, player_id: playerId } as unknown as Pick;
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

// 3. Negative same-game pair: pitcher Ks over + OPPOSING batter hits over → joint < product.
{
  const teams: TeamResolver = (id) => (id === 'pPIT' ? 'AAA' : 'BBB'); // pitcher vs opposing bat
  const legs = [
    leg(20, 'mlb_prop_pitcher_k', 'G9', 0.6, -110, 'over', 'MLB', 'pPIT'),
    leg(21, 'mlb_prop_batter_hits', 'G9', 0.55, -110, 'over', 'MLB', 'bOPP'),
  ];
  const { jointProb, hasCorrelation } = correlatedJointProb(legs, rho, teams);
  check('Pitcher Ks over + opposing batter over drops joint below product', hasCorrelation && jointProb < product(legs) - 1e-4, `joint=${jointProb.toFixed(4)} prod=${product(legs).toFixed(4)}`);
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

// 4. Team resolution (Phase 2): same-team batter stack is MORE correlated than opposing.
{
  const sameTeam: TeamResolver = () => 'AAA';
  const oppTeam: TeamResolver = (id) => (id === 'b1' ? 'AAA' : 'BBB');
  const legsSame = [
    leg(40, 'mlb_prop_batter_hits', 'G9', 0.6, -110, 'over', 'MLB', 'b1'),
    leg(41, 'mlb_prop_batter_tb', 'G9', 0.55, -110, 'over', 'MLB', 'b2'),
  ];
  const legsOpp = [
    leg(42, 'mlb_prop_batter_hits', 'G9', 0.6, -110, 'over', 'MLB', 'b1'),
    leg(43, 'mlb_prop_batter_tb', 'G9', 0.55, -110, 'over', 'MLB', 'b2'),
  ];
  const jSame = correlatedJointProb(legsSame, rho, sameTeam).jointProb;
  const jOpp = correlatedJointProb(legsOpp, rho, oppTeam).jointProb;
  const prod = product(legsSame);
  check('Same-team stack joint > opposing stack joint > product', jSame > jOpp && jOpp > prod - 1e-3, `same=${jSame.toFixed(4)} opp=${jOpp.toFixed(4)} prod=${prod.toFixed(4)}`);
  // Team-unaware (no resolver) falls back to the 'na' bucket — still ≥ product.
  const jNa = correlatedJointProb(legsSame, rho).jointProb;
  check('Team-unaware falls back to na bucket (≥ product)', jNa > prod - 1e-3, `na=${jNa.toFixed(4)} prod=${prod.toFixed(4)}`);
}

// 5. Grade mapping + juiced negative-EV combo.
{
  check('gradeForEv(-0.10) = bad', gradeForEv(-0.1) === 'bad');
  check('gradeForEv(0.0) = fair', gradeForEv(0.0) === 'fair');
  check('gradeForEv(0.05) = good', gradeForEv(0.05) === 'good');
  check('gradeForEv(0.12) = great', gradeForEv(0.12) === 'great');
  const juiced = [leg(50, 'mlb_moneyline', 'G1', 0.5, -200), leg(51, 'mlb_moneyline', 'G2', 0.5, -200)];
  const jm = computeCorrelatedMetrics(juiced, rho);
  check('Juiced -EV combo grades Bad', jm.grade === 'bad', `ev=${jm.ev.toFixed(3)}`);
  check('Juiced -EV combo shows positive DK hold', jm.dkHoldPct > 0, `hold=${(jm.dkHoldPct * 100).toFixed(1)}%`);
}

// 6. PSD repair: a high-magnitude same-game triple must still return finite joint.
{
  const legs = [
    leg(60, 'mlb_prop_pitcher_k', 'G9', 0.6, -110, 'over'),
    leg(61, 'mlb_prop_pitcher_hits', 'G9', 0.55, -110, 'over'),
    leg(62, 'mlb_over_under', 'G9', 0.5, -110, 'over'),
  ];
  const { jointProb } = correlatedJointProb(legs, rho);
  check('Correlated triple returns a finite joint prob', Number.isFinite(jointProb) && jointProb > 0 && jointProb < 1, `joint=${jointProb.toFixed(4)}`);
}

// 7. Determinism: same slip twice → identical joint probability (seeded PRNG).
{
  const legs = [
    leg(70, 'mlb_prop_batter_hits', 'G9', 0.6, -110, 'over'),
    leg(71, 'mlb_over_under', 'G9', 0.55, -110, 'over'),
  ];
  const a = correlatedJointProb(legs, rho).jointProb;
  const b = correlatedJointProb(legs, rho).jointProb;
  check('Deterministic across runs', a === b, `a=${a} b=${b}`);
}

console.log(failures === 0 ? '\nALL CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
