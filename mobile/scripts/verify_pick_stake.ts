/**
 * A pick's own stake: picks.stake_units (units TO WIN, 1 to 3; NULL is the
 * usual 1u) and picks.stake_reason (why, in words).
 *
 * mike, 2026-11-06: an NCAAB bet that agrees with an earlier NCAAB bet on the
 * same game is staked at 2u to win (docs/sports/ncaab.md, "Agreement sizing").
 * The rule is tracking/discord_notifier.stake_for; the app's twin is
 * lib/thresholds.stakeFor, and verify_units_parity.ts pins the two equal over
 * the shared fixture. This script pins what the app SHOWS for such a pick:
 *
 *   - the pick card's stake at -110 is 2.2u to win 2u, in both card layouts,
 *     with the reason once, under the stake;
 *   - a pick with no stake_units shows exactly what it showed before;
 *   - the reasoning card, the board's exposure sum, the tracked tab's posted
 *     stake and the posted record all read the pick's stake_units;
 *   - a member's own stake, a custom model and a parlay leg stay where they
 *     were.
 *
 * Run: npx tsx scripts/verify_pick_stake.ts
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  formatStake,
  formatUnits,
  pickConviction,
  postedPickUnits,
  setServerThresholds,
  stakeFor,
  stakeReasonLine,
  unitsFor,
} from '../src/lib/thresholds';
import { signalsStakeLine } from '../src/lib/signalsCard';
import { customTrackedStake, postedTrackedStake } from '../src/lib/trackedStake';
import { computeBuiltInModelStats, computeCustomModelStats } from '../src/lib/customModelBacktest';
import type { CustomModel, Pick, PickSide, SettledPick } from '../src/types';

let failed = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failed++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}
const near = (a: number, b: number) => Math.abs(a - b) < 1e-9;
const read = (rel: string) => readFileSync(join(__dirname, '..', rel), 'utf-8');

const REASON = 'Two models agree: NCAAB Totals also bet Over 141.5';

function mkPick(over: Partial<Pick> = {}): Pick {
  return {
    pick_id: 7,
    game_id: 'NCAAB_2026-11-10_DUKE_UNC',
    model_id: 'ncaab_first_half_total',
    sport: 'NCAAB',
    game_date: '2026-11-10',
    pick_side: 'over' as PickSide,
    pick_label: 'Duke @ North Carolina 1H Over 68.5',
    model_probability: 0.58,
    dk_implied_prob: 0.524,
    edge: 0.056,
    dk_odds: -110,
    scored_line: 68.5,
    kelly_fraction: 0.02,
    signal_type: 'BET',
    result: null,
    is_live: false,
    decision_odds: -110,
    decision_edge: 0.056,
    decision_book: 'draftkings',
    line_book: null,
    ...over,
  } as Pick;
}

// The two strings the pick card prints for a stake: the signals layout's
// stake row and the board layout's caption cell (PickCard.tsx).
const signalsText = (p: Pick) => {
  const s = stakeFor(p.kelly_fraction, p.decision_odds, p.stake_units);
  return signalsStakeLine(formatUnits(s.risk), formatUnits(s.win));
};
const boardText = (p: Pick) => {
  const s = stakeFor(p.kelly_fraction, p.decision_odds, p.stake_units);
  return s.priced ? `${formatUnits(s.risk)} → ${formatUnits(s.win)}` : formatUnits(s.conviction);
};

// ── A 2u pick at -110 ───────────────────────────────────────────────────────
const two = mkPick({ stake_units: 2, stake_reason: REASON });
{
  const s = stakeFor(two.kelly_fraction, two.decision_odds, two.stake_units);
  check('a 2u pick at -110 is 2.2u to win 2u', formatStake(s) === '2.2u to win 2u', formatStake(s));
  check('the signals card prints Bet 2.2u · Win 2u', signalsText(two) === 'Bet 2.2u · Win 2u', signalsText(two));
  check('the board card prints 2.2u → 2u', boardText(two) === '2.2u → 2u', boardText(two));
  check('the card shows the reason', stakeReasonLine(s, two.stake_reason) === REASON,
    String(stakeReasonLine(s, two.stake_reason)));
}
// PostgREST can send a NUMERIC as a string. Python's float() reads one too.
{
  const s = stakeFor(0.02, -110, '2' as unknown as number);
  check('a string "2" is 2u, as Python float("2") is', formatStake(s) === '2.2u to win 2u', formatStake(s));
}
// The risk cap still binds, and the win is recomputed from the capped risk.
{
  const s = stakeFor(0.02, -200, 2);
  check('a 2u pick at -200 lays the 3u cap to win 1.5u', formatStake(s) === '3u to win 1.5u', formatStake(s));
}

// ── A pick without stake_units is unchanged ────────────────────────────────
for (const [name, p] of [
  ['no stake_units key', mkPick()],
  ['stake_units null', mkPick({ stake_units: null, stake_reason: null })],
  ['stake_units 1 with a reason', mkPick({ stake_units: 1, stake_reason: REASON })],
  ['stake_units 4 (outside 1..3)', mkPick({ stake_units: 4, stake_reason: REASON })],
  ['stake_units 0.5 (outside 1..3)', mkPick({ stake_units: 0.5, stake_reason: REASON })],
] as const) {
  const s = stakeFor(p.kelly_fraction, p.decision_odds, p.stake_units);
  const two = stakeFor(p.kelly_fraction, p.decision_odds);
  check(`${name}: the same stake as the two-argument call`,
    s.conviction === two.conviction && near(s.risk, two.risk) && near(s.win, two.win)
      && s.capped === two.capped && s.priced === two.priced);
  check(`${name}: 1.1u to win 1u`, formatStake(s) === '1.1u to win 1u', formatStake(s));
  check(`${name}: Bet 1.1u · Win 1u on the signals card`, signalsText(p) === 'Bet 1.1u · Win 1u', signalsText(p));
  check(`${name}: 1.1u → 1u on the board card`, boardText(p) === '1.1u → 1u', boardText(p));
  check(`${name}: no reason line`, stakeReasonLine(s, p.stake_reason) === null,
    String(stakeReasonLine(s, p.stake_reason)));
}
check('a 2u pick with a blank reason shows no reason line',
  stakeReasonLine(stakeFor(0.02, -110, 2), '   ') === null);
check('a 2u pick with no reason shows no reason line',
  stakeReasonLine(stakeFor(0.02, -110, 2), null) === null);
check('pickConviction: 2 is 2, null is the flat 1u, 4 is the flat 1u',
  pickConviction(0.02, 2) === 2 && pickConviction(0.02, null) === 1 && pickConviction(0.02, 4) === 1);
check('pickConviction: NaN and Infinity are the flat 1u',
  pickConviction(0.02, NaN) === 1 && pickConviction(0.02, Infinity) === 1);

// ── The posted record and the tracked tab read the pick's stake ────────────
{
  const win = postedPickUnits({ ...two, result: 'WIN' });
  const loss = postedPickUnits({ ...two, result: 'LOSS' });
  check('posted record: a 2u win at -110 is +2u', near(win.units, 2) && near(win.risked, 2.2),
    `${win.units} / ${win.risked}`);
  check('posted record: a 2u loss at -110 is -2.2u', near(loss.units, -2.2) && near(loss.risked, 2.2),
    `${loss.units} / ${loss.risked}`);
  const flat = postedPickUnits({ ...mkPick(), result: 'WIN' });
  check('posted record: a pick without stake_units still wins 1u', near(flat.units, 1) && near(flat.risked, 1.1),
    `${flat.units} / ${flat.risked}`);
}
{
  const t = postedTrackedStake(two);
  check('tracked tab, as posted: a 2u pick risks 2.2u to win 2u', near(t.risk, 220) && near(t.win, 200),
    `${t.risk} / ${t.win}`);
  const own = customTrackedStake(two, 50);
  check('tracked tab, my stakes: the member\'s own amount is not scaled by stake_units',
    near(own.risk, 50) && Math.abs(own.win - 50 / 1.1) < 1e-9, `${own.risk} / ${own.win}`);
}
check('exposure: unitsFor lays 2.2u on a 2u pick at -110', near(unitsFor(0.02, -110, 2), 2.2));
check('exposure: unitsFor two-argument call is unchanged', near(unitsFor(0.02, -110), 1.1));

// ── The surfaces pass the pick's stake_units (source) ──────────────────────
const card = read('src/components/PickCard.tsx');
check('PickCard sizes the stake with the pick\'s stake_units',
  /const stake = stakeFor\(pick\.kelly_fraction, myQuote \? myQuote\.price : decisionOdds\(pick\), pick\.stake_units\);/.test(card));
check('PickCard builds the reason only where a stake is shown',
  /const stakeReason = stakeCaption \? stakeReasonLine\(stake, pick\.stake_reason\) : null;/.test(card));
check('PickCard renders the reason once per layout (board and signals)',
  (card.match(/\{trueMinus\(stakeReason\)\}/g) ?? []).length === 2);
check('PickCard renders the reason as a glyph row in textSecondary, no new colour (UX review 2026-11-06)',
  (card.match(/<Text style=\{styles\.stakeReasonText\}>\{trueMinus\(stakeReason\)\}/g) ?? []).length === 2
    && (card.match(/name="layers-outline"/g) ?? []).length === 2
    && /stakeReasonText: \{[^}]*color: colors\.textSecondary,/.test(card)
    && !/stakeReasonText: \{[^}]*colors\.(bet|success|brand|warning)/.test(card));
check('PickCard speaks the reason with the stake, signals layout',
  /`Stake, \$\{signalsStakeSpeech\(signalsRiskUnits, signalsWinUnits\)\}\$\{stakeReason \? `\. \$\{stakeReason\}` : ''\}`/.test(card));
check('PickCard speaks the reason right after the stake, board layout',
  /stakeCaption \? `Stake \$\{unitsSpeech\(stakeCaption\)\}` : null,\r?\n\s*\/\/[^\n]*\r?\n\s*stakeReason,/.test(card));
const reasoning = read('src/components/ReasoningCard.tsx');
check('ReasoningCard sizes the stake with the pick\'s stake_units',
  /const stake = stakeFor\(pick\.kelly_fraction, odds, pick\.stake_units\);/.test(reasoning));
check('ReasoningCard explains the reason when the stake is above 1u',
  /stakeReasonLine\(stake, pick\.stake_reason\)/.test(reasoning));
check('ReasoningCard says a 2u pick is sized up from 1u, and keeps the 1u sentence for the rest',
  reasoning.includes('stake.conviction > FLAT_CONVICTION')
    && reasoning.includes('Sized up from the usual 1u. ${reasonSentence}')
    && reasoning.includes('Every BET is a 1u play'));
check('ReasoningCard names no second win amount under the 3u cap (UX review 2026-11-06)',
  /stake\.capped\s*\?\s*''\s*:\s*`A \$\{formatUnits\(stake\.conviction\)\} play means/.test(reasoning));
const home = read('src/screens/PicksHomeScreen.tsx');
check('PicksHomeScreen exposure sum passes the pick\'s stake_units',
  /unitsFor\(d\.pick\.kelly_fraction, decisionOdds\(d\.pick\), d\.pick\.stake_units\)/.test(home));
const tracked = read('src/lib/trackedStake.ts');
check('trackedStake posted stake passes the pick\'s stake_units',
  /stakeFor\(p\.kelly_fraction, decisionOdds\(p\), p\.stake_units\)/.test(tracked));
const thresholds = read('src/lib/thresholds.ts');
check('postedPickUnits passes the pick\'s stake_units',
  /stakeFor\(p\.kelly_fraction, decisionOdds\(p\), p\.stake_units\)/.test(thresholds));
const parlay = read('src/lib/parlay.ts');
check('a parlay leg stays on its kelly-derived stake (two arguments)',
  /return stakeFor\(metrics\.kellyFraction \* KELLY_MULTIPLIER, metrics\.americanOdds\);/.test(parlay));
const custom = read('src/hooks/useCustomModelStats.ts');
check('a custom model\'s server rows reach postedPickUnits without stake_units',
  custom.includes('postedPickUnits({ dk_odds: p.dk_odds, decision_odds: p.decision_odds, result: p.result })'));
check('a custom model\'s phone-graded rows are booked at the flat 1u',
  /\.map\(\(row\) => \(\{ \.\.\.row, stake_units: null \}\)\)\s*\.map\(\(p\) => \(\{[\s\S]*?units: postedPickUnits\(p\)\.units,/
    .test(custom.split('const localPicks')[1] ?? ''));

// ── Model pages: the official model books the stake, a custom model does not
setServerThresholds({});
{
  const settled = [{
    ...mkPick({ model_id: 'nba_total_luck', sport: 'NBA', stake_units: 2, stake_reason: REASON }),
    result: 'WIN', condition_status: null, profit_flat: 90.91,
  }] as unknown as SettledPick[];
  const official = computeBuiltInModelStats('nba_total_luck', settled);
  check('official model page (fallback behind the view): a 2u win books +2u on 2.2u risked',
    near(official.units, 2) && near(official.risked, 2.2), `${official.units} on ${official.risked}`);
  const model = {
    id: 'm', name: 'm', rules: [{ model_id: 'nba_total_luck', min_prob: 0, min_edge: -9 }],
    filters: {}, created_at: '', updated_at: '',
  } as unknown as CustomModel;
  const mine = computeCustomModelStats(model, settled);
  check('custom model: the same pick books the flat +1u on 1.1u risked',
    near(mine.units, 1) && near(mine.risked, 1.1), `${mine.units} on ${mine.risked}`);
}

// ── The selects carry the columns (picks only) ─────────────────────────────
const queries = read('src/lib/queries.ts');
// The select's column names: the string literals of the constant, joined,
// split on commas. Comments between the literals are not columns.
const columnsOf = (name: string): Set<string> => {
  const block = (queries.split(`const ${name} =`)[1].split(/';\r?\n/)[0] + "'")
    .replace(/\/\/[^\n]*/g, '');
  const text = (block.match(/'[^']*'/g) ?? []).map((s) => s.slice(1, -1)).join('');
  return new Set(text.split(',').map((c) => c.trim()).filter(Boolean));
};
const pickCols = columnsOf('PICK_COLUMNS');
check('PICK_COLUMNS selects stake_units and stake_reason',
  pickCols.has('stake_units') && pickCols.has('stake_reason') && pickCols.has('line_book'),
  [...pickCols].slice(-4).join(', '));
const settledCols = columnsOf('SETTLED_PICK_COLUMNS');
check('SETTLED_PICK_COLUMNS selects stake_units (model pages book the posted stake)',
  settledCols.has('stake_units') && settledCols.has('prop_market'), [...settledCols].slice(-3).join(', '));

console.log(failed === 0 ? '\nALL PASS (pick stake)' : `\n${failed} FAILURE(S)`);
if (failed) process.exit(1);
