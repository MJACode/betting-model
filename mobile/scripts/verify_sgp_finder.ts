/**
 * Standalone verification for the same-game parlay finder (src/lib/sgpFinder.ts).
 * No JS test runner is configured for the app, so — like the parlay math — we
 * assert the pure function here and run with tsx:
 *
 *   npx tsx scripts/verify_sgp_finder.ts
 *
 * Pins: a correlation-only +EV same-game combo is surfaced (independent EV < 0 <
 * correlated EV); cross-game legs never form an SGP; the ≤1-game-line rule holds;
 * per-game + global caps are respected; −EV-only slates return none_positive;
 * results are deterministic.
 */

import { findSameGameParlays } from '../src/lib/sgpFinder';
import { computeParlayMetrics, type ParlayLeg } from '../src/lib/parlay';
import { PARLAY_CORRELATION_PRIORS, type RhoTable } from '../src/lib/parlayCorrelation';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const rho: RhoTable = PARLAY_CORRELATION_PRIORS;

function leg(
  pickId: number,
  modelId: string,
  gameId: string,
  modelProb: number,
  americanOdds: number,
  side: Pick['pick_side'] = 'over',
  isGameLine = false,
  sport = 'MLB',
  playerId: string | null = null,
): ParlayLeg {
  const decimalOdds = americanOdds > 0 ? 1 + americanOdds / 100 : 1 + 100 / Math.abs(americanOdds);
  const pick = { pick_side: side, sport, player_id: playerId } as unknown as Pick;
  return {
    pickId,
    slipKey: `${gameId}|${modelId}|${playerId ?? ''}`,
    gameId,
    modelId,
    isGameLine,
    isFavorite: americanOdds < 0,
    label: `${modelId} #${pickId}`,
    modelProb,
    decimalOdds,
    americanOdds,
    legEdge: 0,
    bestBook: null,
    bookPrices: [],
    pick,
    game: null,
  };
}

// 1. Correlation-only +EV: an off-prop over + game-total over (ρ>0) priced so the
//    naïve product is −EV but the joint is +EV. The finder must surface it.
{
  const legs = [
    leg(1, 'mlb_prop_batter_hits', 'G1', 0.6, 65, 'over'),
    leg(2, 'mlb_over_under', 'G1', 0.6, 65, 'over', true),
  ];
  const indepEv = computeParlayMetrics(legs).ev;
  const res = findSameGameParlays(legs, rho);
  const top = res.candidates[0];
  check('Surfaces a correlation-only +EV same-game combo', !!top && top.metrics.ev > 0, `indepEv=${indepEv.toFixed(4)} corrEv=${top ? top.metrics.ev.toFixed(4) : 'n/a'}`);
  check('That combo is −EV under the naïve independent model', indepEv < 0, `indepEv=${indepEv.toFixed(4)}`);
  check('Surfaced combo is flagged correlated', !!top && top.metrics.hasCorrelation === true);
  check('gamesConsidered counts the one eligible game', res.gamesConsidered === 1, `got ${res.gamesConsidered}`);
}

// 2. Cross-game legs never form a same-game parlay.
{
  const legs = [
    leg(10, 'mlb_prop_batter_hits', 'A', 0.62, 120, 'over'),
    leg(11, 'mlb_prop_batter_tb', 'B', 0.62, 120, 'over'),
  ];
  const res = findSameGameParlays(legs, rho);
  check('Different-game legs yield no SGP', res.candidates.length === 0 && res.reason === 'no_eligible', `n=${res.candidates.length} reason=${res.reason}`);
}

// 3. ≤1 game-line per game: ML + RL in one game is the only pair → no valid combo.
{
  const legs = [
    leg(20, 'mlb_moneyline', 'G2', 0.7, -130, 'home', true),
    leg(21, 'mlb_runline', 'G2', 0.6, 110, 'home', true),
  ];
  const res = findSameGameParlays(legs, rho);
  check('Two game-lines in one game produce no valid combo', res.candidates.length === 0, `n=${res.candidates.length}`);
}

// 4. Per-game + global caps. One game with 5 correlated +EV legs → many combos,
//    but at most perGameLimit surface.
{
  const legs = [
    leg(30, 'mlb_prop_batter_hits', 'G3', 0.62, 60, 'over'),
    leg(31, 'mlb_prop_batter_tb', 'G3', 0.62, 60, 'over'),
    leg(32, 'mlb_prop_batter_rbi', 'G3', 0.6, 70, 'over'),
    leg(33, 'mlb_prop_batter_runs', 'G3', 0.6, 70, 'over'),
    leg(34, 'mlb_over_under', 'G3', 0.6, 60, 'over', true),
  ];
  const res = findSameGameParlays(legs, rho, { perGameLimit: 2, maxResults: 8 });
  check('Per-game limit caps surfaced combos for one game', res.candidates.length <= 2, `n=${res.candidates.length}`);
  check('All surfaced combos belong to that game', res.candidates.every((c) => c.gameId === 'G3'));
  check('Surfaced combos are all +EV', res.candidates.every((c) => c.metrics.ev > 0));
}

// 5. −EV only: heavy juice so even the correlated joint can't clear → none_positive.
{
  const legs = [
    leg(40, 'mlb_prop_batter_hits', 'G4', 0.5, -300, 'over'),
    leg(41, 'mlb_over_under', 'G4', 0.5, -300, 'over', true),
  ];
  const res = findSameGameParlays(legs, rho);
  check('All −EV slate returns none_positive', res.candidates.length === 0 && res.reason === 'none_positive', `n=${res.candidates.length} reason=${res.reason}`);
}

// 6. Determinism: identical inputs → identical EV (seeded MC).
{
  const legs = [
    leg(50, 'mlb_prop_batter_hits', 'G5', 0.6, 65, 'over'),
    leg(51, 'mlb_over_under', 'G5', 0.6, 65, 'over', true),
  ];
  const a = findSameGameParlays(legs, rho).candidates[0]?.metrics.ev;
  const b = findSameGameParlays(legs, rho).candidates[0]?.metrics.ev;
  check('Finder is deterministic across runs', a != null && a === b, `a=${a} b=${b}`);
}

// 7. Global maxResults cap across many games.
{
  const legs: ParlayLeg[] = [];
  for (let g = 0; g < 6; g++) {
    legs.push(leg(100 + g * 2, 'mlb_prop_batter_hits', `M${g}`, 0.62, 60, 'over'));
    legs.push(leg(101 + g * 2, 'mlb_over_under', `M${g}`, 0.6, 60, 'over', true));
  }
  const res = findSameGameParlays(legs, rho, { maxResults: 3 });
  check('Global maxResults cap respected', res.candidates.length <= 3, `n=${res.candidates.length}`);
}

console.log(failures === 0 ? '\nAll SGP finder checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);
