/**
 * Cross-language parity: the TypeScript stake rule must match the Python one.
 *
 * The rule lives twice — tracking/discord_notifier.stake_for() drives the
 * Discord channels and the recap, src/lib/thresholds.stakeFor() drives the app.
 * Publishing in units only means anything if the two agree: a "2u to win" in
 * the channel and on the card have to be the same bet.
 *
 * tests/fixtures/unit_sizing_parity.json is the shared contract, generated from
 * the Python side (`python -m tests.test_unit_sizing_parity --write`) and
 * checked there too. If either implementation drifts, one of them fails.
 *
 * A row with a `stake_units` key is a pick that carries its own stake
 * (picks.stake_units, units to win). It goes in as the third argument, as the
 * Python side's stake_for(kelly, odds, stake_units) takes it. A row without
 * the key is called with two arguments, the way every pick was before.
 *
 * Run: npx tsx scripts/verify_units_parity.ts
 */
import * as fs from 'fs';
import * as path from 'path';
import { stakeFor, formatStake } from '../src/lib/thresholds';

const FIXTURE = path.resolve(__dirname, '../../tests/fixtures/unit_sizing_parity.json');

if (!fs.existsSync(FIXTURE)) {
  console.error(`[FAIL] parity fixture missing: ${FIXTURE}\n` +
    'Regenerate with `python -m tests.test_unit_sizing_parity --write`.');
  process.exit(1);
}

type Case = {
  kelly: number; odds: number | null; stake_units?: number | null;
  conviction: number; risk: number;
  win: number; capped: boolean; priced: boolean; fmt: string;
};
const cases: Case[] = JSON.parse(fs.readFileSync(FIXTURE, 'utf8')).cases;

let failures = 0;
for (const c of cases) {
  const own = 'stake_units' in c;
  const s = own ? stakeFor(c.kelly, c.odds, c.stake_units) : stakeFor(c.kelly, c.odds);
  const diffs: string[] = [];
  if (Math.abs(s.conviction - c.conviction) > 1e-9) diffs.push(`conviction ${s.conviction} != ${c.conviction}`);
  if (Math.abs(s.risk - c.risk) > 1e-6) diffs.push(`risk ${s.risk} != ${c.risk}`);
  if (Math.abs(s.win - c.win) > 1e-6) diffs.push(`win ${s.win} != ${c.win}`);
  if (s.capped !== c.capped) diffs.push(`capped ${s.capped} != ${c.capped}`);
  if (s.priced !== c.priced) diffs.push(`priced ${s.priced} != ${c.priced}`);
  if (formatStake(s) !== c.fmt) diffs.push(`fmt "${formatStake(s)}" != "${c.fmt}"`);
  if (diffs.length) {
    failures++;
    const units = own ? ` stake_units=${c.stake_units}` : '';
    console.error(`[FAIL] kelly=${c.kelly} odds=${c.odds}${units}: ${diffs.join('; ')}`);
  }
}

const withOwn = cases.filter((c) => 'stake_units' in c).length;
if (failures === 0) {
  console.log(`[PASS] ${cases.length} cases identical in Python and TypeScript ` +
    `(${withOwn} with the pick's own stake_units)`);
  console.log('\nALL PASS (units parity)');
} else {
  console.error(`\n${failures} PARITY FAILURE(S) — the app and the Discord ` +
    'channel would publish different stakes for the same bet.');
  process.exit(1);
}
