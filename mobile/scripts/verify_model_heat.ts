/**
 * The Picks filter's Model section: each model's record and its hot / cold
 * tag (Matt, 2026-11-18). Run with:
 *
 *   npx tsx scripts/verify_model_heat.ts
 *
 * The cases are the production numbers measured 2026-11-18 over 11-11..11-17
 * (v_public_track_record_model_daily), plus the edges of each threshold.
 */

import {
  HEAT_MIN_BETS,
  HEAT_MIN_UNITS,
  addDays,
  buildModelRecords,
  heatFor,
  heatWindow,
  modelRecordLine,
  modelRecordSpoken,
} from '../src/lib/modelHeat';

let failures = 0;
function check(name: string, ok: boolean, detail = '') {
  if (ok) console.log(`[PASS] ${name}`);
  else {
    failures++;
    console.log(`[FAIL] ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

// ── the window ──
check('addDays crosses a month', addDays('2026-12-01', -1) === '2026-11-30', addDays('2026-12-01', -1));
check('addDays crosses a year', addDays('2027-01-01', -7) === '2026-12-25', addDays('2027-01-01', -7));
const w = heatWindow('2026-11-18');
check(
  'the window is the 7 days ending yesterday',
  w.first === '2026-11-11' && w.last === '2026-11-17',
  `${w.first}..${w.last}`,
);

// ── the thresholds, at their edges ──
check('exactly +3u on exactly 8 bets is hot', heatFor(HEAT_MIN_BETS, HEAT_MIN_UNITS) === 'hot');
check('exactly −3u on exactly 8 bets is cold', heatFor(HEAT_MIN_BETS, -HEAT_MIN_UNITS) === 'cold');
check('+10u on 7 bets is no tag (too few bets)', heatFor(HEAT_MIN_BETS - 1, 10) === null);
check('+2.99u on 20 bets is no tag', heatFor(20, 2.99) === null);
check('−2.99u on 20 bets is no tag', heatFor(20, -2.99) === null);

// ── the production week, 2026-11-11..17 ──
const daily = [
  // NCAAB 1st-half totals: +10.32u on 19 — hot
  { game_date: '2026-11-12', model_id: 'ncaab_first_half_total', picks: 16, units: 9.42 },
  { game_date: '2026-11-17', model_id: 'ncaab_first_half_total', picks: 3, units: '0.90' },
  // NCAABW live halftime totals: −6.17u on 11 — cold
  { game_date: '2026-11-15', model_id: 'ncaabw_live_total_ht', picks: 9, units: -3.84 },
  { game_date: '2026-11-17', model_id: 'ncaabw_live_total_ht', picks: 2, units: -2.33 },
  // NHL Shots on Goal: +0.08u on 18 — no tag
  { game_date: '2026-11-14', model_id: 'nhl_prop_shots_on_goal', picks: 18, units: 0.08 },
  // Outside the window on both sides — ignored
  { game_date: '2026-11-10', model_id: 'nhl_moneyline', picks: 30, units: 20 },
  { game_date: '2026-11-18', model_id: 'nhl_moneyline', picks: 30, units: 20 },
];
const totals = [
  { model_id: 'ncaab_first_half_total', picks: 40, units: 12.5 },
  { model_id: 'ncaabw_live_total_ht', picks: 20, units: -4.04 },
  { model_id: 'nhl_prop_shots_on_goal', picks: 61, units: 4.2 },
  // A model scored under two sports has two total rows; they sum.
  { model_id: 'nhl_moneyline', picks: '10', units: '-1.5' },
  { model_id: 'nhl_moneyline', picks: 5, units: 0.5 },
];
const recs = buildModelRecords(totals, daily, '2026-11-18');
check('NCAAB 1st-half totals is hot', recs.ncaab_first_half_total.heat === 'hot');
check(
  'its window sums to the measured +10.32u on 19',
  recs.ncaab_first_half_total.windowBets === 19 &&
    Math.abs(recs.ncaab_first_half_total.windowUnits - 10.32) < 1e-9,
);
check('NCAABW live halftime totals is cold', recs.ncaabw_live_total_ht.heat === 'cold');
check('NHL Shots on Goal carries no tag', recs.nhl_prop_shots_on_goal.heat === null);
check(
  'days outside the window are ignored',
  recs.nhl_moneyline.windowBets === 0 && recs.nhl_moneyline.heat === null,
);
check(
  'total rows for one model are summed across sports',
  recs.nhl_moneyline.bets === 15 && Math.abs(recs.nhl_moneyline.units - -1) < 1e-9,
);

// ── the row text ──
check('record line, up', modelRecordLine(recs.nhl_prop_shots_on_goal) === '+4.2u · 61 bets', modelRecordLine(recs.nhl_prop_shots_on_goal));
check('record line, down (true minus)', modelRecordLine(recs.nhl_moneyline) === '−1.0u · 15 bets', modelRecordLine(recs.nhl_moneyline));
check('record line, no record', modelRecordLine(undefined) === 'No settled bets yet');
check(
  'record line, one bet is singular',
  modelRecordLine({ bets: 1, units: 0.91, windowBets: 1, windowUnits: 0.91, heat: null }) === '+0.9u · 1 bet',
);
check(
  'spoken form names the tag',
  modelRecordSpoken(recs.ncaabw_live_total_ht) === 'down 4.0 units over 20 bets, cold over the last 7 days',
  modelRecordSpoken(recs.ncaabw_live_total_ht),
);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
