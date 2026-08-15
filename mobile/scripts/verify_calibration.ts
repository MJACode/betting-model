/**
 * Standalone verification for the calibration math (src/lib/calibration.ts).
 *
 *   npx tsx scripts/verify_calibration.ts
 *
 * Pins: null below minTotal; perfectly-calibrated data → ~0 gap; a model that
 * loses every "high confidence" pick → large gap; bins are quantile-sized; only
 * decided (WIN/LOSS) picks count.
 */

import { buildCalibration } from '../src/lib/calibration';
import type { Pick, PickResult } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function mkPick(prob: number, result: PickResult, id = 1): Pick {
  return {
    pick_id: id, game_id: 'g', model_id: 'mlb_moneyline', sport: 'MLB', game_date: '2026-06-25',
    game_time: '2026-06-25T23:10:00+00:00', pick_side: 'home', pick_label: 'x', model_probability: prob, dk_implied_prob: 0.5, edge: 0.1,
    dk_odds: -110, scored_line: null, kelly_fraction: 0.02, recommended_bet: 20, bankroll_at_pick: 1000,
    injury_flag: null, injury_detail: null, signal_type: 'BET', confidence_tier: 'HIGH', result,
    profit_flat: null, profit_kelly: null, settled_at: '2026-06-25', created_at: '2026-06-25',
    player_id: null, pitcher_throw_hand: null, public_bet_pct: null, public_money_pct: null,
    closing_dk_odds: null, closing_line: null, clv_pct: null, clv_captured_at: null,
    is_live: null, inning_at_pick: null, score_diff_at_pick: null, dk_bet_link: null,
  };
}

// 1. Below minTotal → null.
check('null below minTotal', buildCalibration([mkPick(0.7, 'WIN')], { minTotal: 15 }) === null);

// 2. Perfectly calibrated: at prob 0.6, exactly 60% win; at 0.8, exactly 80%.
const perfect: Pick[] = [];
for (let i = 0; i < 10; i++) perfect.push(mkPick(0.6, i < 6 ? 'WIN' : 'LOSS', i));
for (let i = 0; i < 10; i++) perfect.push(mkPick(0.8, i < 8 ? 'WIN' : 'LOSS', 100 + i));
const cPerfect = buildCalibration(perfect, { minTotal: 15, minPerBin: 8, maxBins: 2 })!;
check('perfect calibration → gap ≈ 0', cPerfect != null && cPerfect.gap < 0.02, `gap=${cPerfect?.gap.toFixed(3)}`);
check('two quantile bins', cPerfect.bins.length === 2, `bins=${cPerfect.bins.length}`);
check('bin actual rates 0.6 / 0.8', Math.abs(cPerfect.bins[0]!.actualRate - 0.6) < 1e-9 && Math.abs(cPerfect.bins[1]!.actualRate - 0.8) < 1e-9);

// 3. Badly miscalibrated: says 85%, wins only 30% → large gap.
const bad: Pick[] = [];
for (let i = 0; i < 20; i++) bad.push(mkPick(0.85, i < 6 ? 'WIN' : 'LOSS', i));
const cBad = buildCalibration(bad, { minTotal: 15 })!;
check('miscalibrated → large gap', cBad.gap > 0.4, `gap=${cBad.gap.toFixed(3)}`);

// 4. Only decided picks count (PUSH / NO_ACTION / null excluded).
const mixed: Pick[] = [];
for (let i = 0; i < 16; i++) mixed.push(mkPick(0.7, i < 11 ? 'WIN' : 'LOSS', i));
mixed.push(mkPick(0.7, 'PUSH', 99), mkPick(0.7, 'NO_ACTION', 98), mkPick(0.7, null, 97));
const cMixed = buildCalibration(mixed, { minTotal: 15 })!;
check('excludes non-decided picks', cMixed.n === 16, `n=${cMixed.n}`);

console.log(failures === 0 ? '\nAll calibration checks passed.' : `\n${failures} FAILED.`);
process.exit(failures === 0 ? 0 : 1);
