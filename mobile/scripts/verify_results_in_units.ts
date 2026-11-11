/**
 * Every result in the app is in units, never dollars (mike, 2026-11-03:
 * "everything must be units"; CLAUDE.md §4). One unit is one flat bet.
 *
 * Amounts are stored per 100 (a −110 win at 1u risked is 90.91), and so are
 * the Performance tab's stakes, so a screen divides by 100 and prints "u".
 * Tracked picks book the posted stake by default (verify_units_one_basis).
 * The 2026-11-02 UX review found the model page's history rows printing
 * "+$90.91"; these pin the formatter that replaced it, its tone, the betslip
 * bar's 1u payout, and the one record-price statement every model shares.
 *
 *   npx tsx scripts/verify_results_in_units.ts
 */
import {
  FLAT_UNIT,
  FLAT_UNIT_TONE_SCALE,
  flatToUnits,
  formatFlatStake,
  formatFlatUnits,
  MINUS,
} from '../src/lib/format';
import { pnlTone } from '../src/lib/tone';
import { unitsSpeech } from '../src/lib/a11y';
import { formatUnits } from '../src/lib/thresholds';
import { BETSLIP_BAR_STAKE, betslipSummary } from '../src/lib/parlay';
import { recordNoteFor, recordNoteShortFor } from '../src/lib/myBooks';
import { computeTrackedResults } from '../src/lib/trackedPerformance';
import { customTrackedStake, trackedStakeFor } from '../src/lib/trackedStake';
import { settledProfit } from '../src/hooks/useManualBets';
import type { Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  const status = cond ? 'PASS' : 'FAIL';
  if (!cond) failures++;
  console.log(`[${status}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// ── The formatter ────────────────────────────────────────────────────────
check('100 stored is 1 unit', FLAT_UNIT === 100 && flatToUnits(100) === 1);
check('a −110 win (90.91 stored) prints +0.91u', formatFlatUnits(90.91) === '+0.91u', formatFlatUnits(90.91));
check('a loss (−100 stored) prints −1.00u', formatFlatUnits(-100) === `${MINUS}1.00u`, formatFlatUnits(-100));
check('a season total (+321.4 stored) prints +3.21u', formatFlatUnits(321.4) === '+3.21u', formatFlatUnits(321.4));
check('a push that rounds to zero is unsigned', formatFlatUnits(0.3) === '0.00u', formatFlatUnits(0.3));
check('missing is a dash, never 0', formatFlatUnits(null) === '—' && formatFlatUnits(undefined) === '—');
check('PostgREST NUMERIC strings still format', formatFlatUnits('-45' as unknown as number) === `${MINUS}0.45u`,
  formatFlatUnits('-45' as unknown as number));
for (const v of [90.91, -100, 321.4, 0.3, -0.4, 12345.678, -0.5]) {
  check(`no dollar sign in ${v}`, !formatFlatUnits(v).includes('$') && formatFlatUnits(v).endsWith('u'), formatFlatUnits(v));
}

// ── Its tone follows the number as printed ───────────────────────────────
check('+0.91u is green', pnlTone(90.91, 2, FLAT_UNIT_TONE_SCALE) === 'betInk');
check('−1.00u is red', pnlTone(-100, 2, FLAT_UNIT_TONE_SCALE) === 'avoidInk');
check('a +0.4 stored result prints 0.00u and is grey, not green',
  formatFlatUnits(0.4) === '0.00u' && pnlTone(0.4, 2, FLAT_UNIT_TONE_SCALE) === 'textSecondary');

// ── Stakes ───────────────────────────────────────────────────────────────
check('the default stake (100 stored) is 1u', formatFlatStake(100) === '1u', formatFlatStake(100));
check('a half stake is 0.5u', formatFlatStake(50) === '0.5u', formatFlatStake(50));
check('a 1.15u stake keeps two decimals', formatFlatStake(115) === '1.15u', formatFlatStake(115));

// ── Spoken as units ──────────────────────────────────────────────────────
check('VoiceOver: "+0.91u" is "+0.91 units"', unitsSpeech('+0.91u') === '+0.91 units', unitsSpeech('+0.91u'));
check('VoiceOver: "1u stake" is "1 unit stake", not "1 units"', unitsSpeech('1u stake') === '1 unit stake', unitsSpeech('1u stake'));
check('VoiceOver: a percent passes through', unitsSpeech('+12.5%') === '+12.5%');
check('formatFlatStake and formatUnits share one rounding', formatFlatStake(115) === formatUnits(1.15) && formatFlatStake(12.5) === formatUnits(0.125));

// ── Tracked picks: units at the default stake, as posted ─────────────────
const win = { pick_id: 1, game_date: '2026-11-01', result: 'WIN', profit_flat: 90.91, dk_odds: -110 } as unknown as Pick;
const loss = { pick_id: 2, game_date: '2026-11-01', result: 'LOSS', profit_flat: -100, dk_odds: -110 } as unknown as Pick;
const t = computeTrackedResults([1, 2], [win, loss], trackedStakeFor('posted', {}));
check('a tracked −110 win and loss as posted net −0.10u (+1.00u − 1.10u, the Record tab\'s units)',
  formatFlatUnits(t.summary.net) === `${MINUS}0.10u`, formatFlatUnits(t.summary.net));
const half = computeTrackedResults([1], [win], (p) => customTrackedStake(p, 0.5 * FLAT_UNIT));
check('a tracked win at a 0.5u custom stake is +0.45u',
  formatFlatUnits(half.summary.net) === '+0.45u', formatFlatUnits(half.summary.net));

// ── A logged bet: typed in units, stored at the same scale ───────────────
const loggedStake = 2 * FLAT_UNIT; // the modal stores what was typed × FLAT_UNIT
check('a logged 2u win at +150 is +3.00u',
  formatFlatUnits(settledProfit(loggedStake, 150, 'won')) === '+3.00u',
  formatFlatUnits(settledProfit(loggedStake, 150, 'won')));
check('a logged 2u loss is −2.00u',
  formatFlatUnits(settledProfit(loggedStake, -110, 'lost')) === `${MINUS}2.00u`);

// ── The betslip bar: 1u pays, in units ───────────────────────────────────
check('the bar stake is 1 unit', BETSLIP_BAR_STAKE === 1);
const leg = { decimalOdds: 1 + 100 / 110 } as unknown as Parameters<typeof betslipSummary>[0][number];
const one = betslipSummary([leg], 1);
check('1u at −110 pays 1.91u (stake included)',
  one.payoutPerUnit != null && Math.abs(one.payoutPerUnit - (1 + 100 / 110)) < 1e-9,
  String(one.payoutPerUnit));
check('no price, no payout', betslipSummary([], 2).payoutPerUnit === null);

// ── The record is kept at the price the pick was decided at, every model ──
const NOTE = 'Model records and stats use the price the model found, not your book’s.';
for (const m of ['ncaab_moneyline_own_spread', 'ncaab_spread_market', 'mlb_moneyline', 'nba_total_luck']) {
  check(`${m}: the record note never claims the best price`,
    recordNoteFor(m) === NOTE && recordNoteShortFor(m) === 'record kept at that price'
      && !recordNoteFor(m).includes('best price') && !recordNoteShortFor(m).includes('best price'),
    `${recordNoteFor(m)} | ${recordNoteShortFor(m)}`);
}

console.log(failures === 0 ? '\nAll checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);
