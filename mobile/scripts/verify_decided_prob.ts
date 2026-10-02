/**
 * Standalone verification for decidedNumbers / passesActionFilter on the
 * numbers the scorer DECIDED on (config.decided_cut_sql). Run with:
 *
 *   npx tsx scripts/verify_decided_prob.ts
 *
 * Pins: a BET whose raw probability is under its model's cut and whose
 * calibrated one is over it (pick 3094775, NYR (Regulation) +180) is a Signal;
 * a row with no calibrated number is cut raw, as before; a raw-deciding model
 * (DECIDES_ON_RAW_MODELS) is cut raw even when it carries a calibrated number.
 */

import {
  DECIDES_ON_RAW_MODELS,
  decidedNumbers,
  decidesOnCalibrated,
  passesActionFilter,
  type ActionFilterable,
} from '../src/lib/thresholds';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (cond) console.log(`ok   ${name}`);
  else { failures++; console.log(`FAIL ${name} ${detail}`); }
}

const nyr: ActionFilterable = {
  model_id: 'nhl_moneyline_regulation',
  model_probability: 0.3801,
  model_probability_cal: 0.443,
  edge: -0.0045,
  decision_edge: 0.023,
  decision_odds: 180,
  decision_implied_prob: 0.3571,
  dk_implied_prob: 0.3846,
  dk_odds: 160,
  signal_type: 'BET',
  condition_status: null,
};

const d = decidedNumbers(nyr);
check('decided prob is the calibrated one', Math.abs(d.prob - 0.443) < 1e-9, String(d.prob));
check('decided edge is cal - deciding implied', Math.abs(d.edge - (0.443 - 0.3571)) < 1e-9, String(d.edge));
check('raw-under / calibrated-over BET is a Signal', passesActionFilter(nyr));

const rawOnly = { ...nyr, model_probability_cal: null };
check('no calibrated number: raw cut, still fails', !passesActionFilter(rawOnly));
check('no calibrated number: raw numbers', decidedNumbers(rawOnly).prob === 0.3801
  && decidedNumbers(rawOnly).edge === 0.023);
const rawPass = { ...rawOnly, model_probability: 0.4638, decision_edge: 0.0864 };
check('no calibrated number: a raw pass still passes', passesActionFilter(rawPass));

const noPrice = { ...nyr, decision_implied_prob: null, dk_implied_prob: null as unknown as number };
check('no price: edge falls back to the stored one', decidedNumbers(noPrice).edge === 0.023);

check('nhl moneyline decides calibrated', decidesOnCalibrated('nhl_moneyline'));
for (const m of DECIDES_ON_RAW_MODELS) {
  check(`${m} decides raw`, !decidesOnCalibrated(m));
}
const rule = { ...nyr, model_id: 'nfl_wind_totals' };
check('raw decider: calibrated number ignored', decidedNumbers(rule).prob === 0.3801);

if (failures) { console.log(`\n${failures} failure(s)`); process.exit(1); }
console.log('\nall checks passed');
