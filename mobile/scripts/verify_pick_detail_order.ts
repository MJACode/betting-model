/**
 * Pick Detail order is football-only. MLB and NHL (and every other sport)
 * keep master's order: timing context, then the bet and Track, then the rest.
 * NFL and NCAAF put the bet and Track first.
 *
 *   npx tsx scripts/verify_pick_detail_order.ts
 */
import { readFileSync } from 'fs';
import { join } from 'path';
import { pickDetailBlockOrder } from '../src/lib/pickDetailOrder';

const ROOT = join(import.meta.dirname, '..');

let fail = 0;
function check(name: string, cond: boolean, extra?: unknown) {
  if (!cond) {
    fail++;
    console.error(`FAIL: ${name}`, extra ?? '');
  } else {
    console.log(`PASS: ${name}`);
  }
}
function eq(name: string, got: unknown, want: unknown) {
  check(`${name} (got ${JSON.stringify(got)})`, got === want);
}

const MASTER = 'timing,bet,after';
const FOOTBALL = 'bet,timing,after';
for (const sport of ['MLB', 'NHL', 'NBA', 'WNBA', 'UFC', 'GOLF', null, undefined, '']) {
  eq(`${sport ?? 'empty'} keeps master's order`, pickDetailBlockOrder(sport).join(','), MASTER);
}
eq('NFL puts the bet first', pickDetailBlockOrder('NFL').join(','), FOOTBALL);
eq('NCAAF puts the bet first', pickDetailBlockOrder('NCAAF').join(','), FOOTBALL);

const src = readFileSync(join(ROOT, 'src/screens/PickDetailScreen.tsx'), 'utf8');
check('the screen orders blocks from the pick’s sport', /pickDetailBlockOrder\(pick\.sport\)/.test(src));

function block(name: string, next: string): string {
  const start = src.indexOf(`const ${name} = (`);
  const end = src.indexOf(`const ${next} = (`);
  return start >= 0 && end > start ? src.slice(start, end) : '';
}
const timing = block('timingBlock', 'betBlock');
const bet = block('betBlock', 'afterBlock');
const afterStart = src.indexOf('const afterBlock = (');
const afterEnd = src.indexOf('\n  return (', afterStart);
const after = afterStart >= 0 && afterEnd > afterStart ? src.slice(afterStart, afterEnd) : '';

function order(chunk: string, markers: string[], label: string) {
  let at = -1;
  for (const m of markers) {
    const i = chunk.indexOf(m);
    check(`${label} contains ${m}`, i >= 0);
    check(`${label}: ${m} follows the previous card`, i > at);
    at = i;
  }
}

order(timing, ['<PickTimingCard', '<SharpScoreCard', 'Why no edge number?', '<LineMovementCard'], 'timing');
check('timing block has no bet row', !timing.includes('<BookLinesRow') && !timing.includes('Track this bet'));
order(bet, ['<BookLinesRow', 'cta.startedLine && openHere', '<AllBooksCard', 'Add to your betslip', 'Track this bet'], 'bet');
check('bet block has no timing card', !bet.includes('<PickTimingCard'));
order(after, ['<PublicBettingCard', '<ClvCard', 'Injury', 'Weather', '<OffenseDefenseCard', '<PropContextCard'], 'after');
check('reasoning stays above the ordered blocks',
  src.indexOf('<ReasoningCard') < src.indexOf('pickDetailBlockOrder(pick.sport)'));

console.log(fail === 0 ? '\nALL PASS' : `\n${fail} FAILED`);
process.exit(fail === 0 ? 0 : 1);
