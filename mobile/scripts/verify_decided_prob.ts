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
 * And the two publish-time guards (config.publishable_cut_sql): a decided-only
 * pick waits until its game is within DECIDED_ONLY_PUBLISH_WITHIN_HOURS, and a
 * deciding price more than PUBLISH_MAX_PRICE_GAP from DraftKings' is refused
 * (3101240 FLA ML, BetMGM +154 vs DK -125). Both pre-game only.
 */

import {
  DECIDES_ON_RAW_MODELS,
  decidedNumbers,
  decidesOnCalibrated,
  decisionSource,
  passesActionFilter,
  publishGuardsPass,
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
  // Starts in 3 hours: inside the decided-only window.
  game_time: new Date(Date.now() + 3 * 3600_000).toISOString(),
  game_date: null,
  is_live: false,
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

// ── the publish-time guards ─────────────────────────────────────────────────
const far = { ...nyr, game_time: new Date(Date.now() + 72 * 3600_000).toISOString() };
check('decided-only pick 72h out waits', !passesActionFilter(far));
check('a raw pass 72h out still shows', passesActionFilter({ ...far, model_probability_cal: null,
  model_probability: 0.4638, decision_edge: 0.0864 }));
const cut = { min_prob: 0.40, min_edge: 0.05, prob_only: false };
const now = Date.parse('2026-10-02T20:05:00Z');
check('window: 6:40 PM ET start is open at 4:05 PM ET',
  publishGuardsPass({ ...nyr, game_time: '2026-10-02T22:40:00+00:00' }, cut, now));
check('window: 10/3 7:10 PM ET start is closed at 4:05 PM ET',
  !publishGuardsPass({ ...nyr, game_time: '2026-10-03T23:10:00+00:00' }, cut, now));
const fla: ActionFilterable = {
  model_id: 'nhl_moneyline', model_probability: 0.4998, model_probability_cal: 0.5644,
  edge: -0.0558, decision_edge: 0.1061, decision_odds: 154, decision_implied_prob: 0.3937,
  dk_implied_prob: 0.5556, dk_odds: -125, signal_type: 'BET', condition_status: null,
  game_time: new Date(Date.now() + 3 * 3600_000).toISOString(), is_live: false,
};
check('3101240: 16pp price gap is refused', !passesActionFilter(fla));
check('a 7.56pp best-price gap passes', passesActionFilter({ ...fla, decision_implied_prob: 0.48 }));
check('no DK price (0.0): the gap guard passes',
  publishGuardsPass({ ...fla, dk_implied_prob: 0 }, { min_prob: 0.55, min_edge: 0.05, prob_only: false }));
const live = { ...fla, model_id: 'ncaaf_live_win_prob', is_live: true,
  game_time: new Date(Date.now() + 96 * 3600_000).toISOString() };
check('live rows skip both guards', publishGuardsPass(live, cut));

// ── who decides on what ─────────────────────────────────────────────────────
check('ncaaf_live decides calibrated at DK', decisionSource('ncaaf_live_win_prob') === 'calibrated_at_dk');
const ncaaf = { ...nyr, model_id: 'ncaaf_live_win_prob', model_probability_cal: 0.47,
  decision_implied_prob: 0.33, dk_implied_prob: 0.40 };
check('ncaaf_live edge is cal - DK implied', Math.abs(decidedNumbers(ncaaf).edge - 0.07) < 1e-9,
  String(decidedNumbers(ncaaf).edge));
const zero = { ...nyr, decision_implied_prob: null, dk_implied_prob: 0 };
check('implied 0.0 is a missing price', decidedNumbers(zero).edge === 0.023);

if (failures) { console.log(`\n${failures} failure(s)`); process.exit(1); }
console.log('\nall checks passed');
