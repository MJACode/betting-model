/**
 * gameIsOver falls back to the pick's own start when the game row is missing.
 *
 * Run with:  npx tsx scripts/verify_game_is_over.ts
 *
 * Reviewer, #846: gameIsOver(null) read "not over" forever, so a VOID whose
 * game row never loaded kept Track and betslip on (openForActionNow). With no
 * row, or a row with no kickoff, the pick's own game_time and sport get the
 * blind window gameStatus would give the row (NFL 4h, MLB 6h, default 6h).
 */

import { gameIsOver } from '../src/lib/format';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const H = 3_600_000;
const ago = (h: number) => new Date(Date.now() - h * H).toISOString();

const pick = (sport: string, h: number | null) =>
  ({ sport, game_time: h == null ? null : ago(h) });

check('no row, no pick: not over (nothing to go on)', !gameIsOver(null, null));
check('no row, no game_time: not over', !gameIsOver(null, null, pick('NFL', null)));
check('no row, NFL started 5h ago: over (4h window)', gameIsOver(null, null, pick('NFL', 5)));
check('no row, NFL started 2h ago: not over yet', !gameIsOver(null, null, pick('NFL', 2)));
check('no row, MLB started 5h ago: not over yet (6h window)',
  !gameIsOver(null, null, pick('MLB', 5)));
check('no row, unknown sport 7h ago: over (6h default)', gameIsOver(null, null, pick('XFL', 7)));
check('no row, starts in 3h: not over', !gameIsOver(undefined, null, pick('NFL', -3)));
check('no row, unparseable game_time: not over',
  !gameIsOver(null, null, { sport: 'NFL', game_time: 'TBD' }));
check('no row, live snapshot says Final: over',
  gameIsOver(null, { abstract_game_state: 'Final' }, pick('NFL', 1)));
check('row without a kickoff falls back to the pick, keeping the row sport',
  gameIsOver({ sport: 'NFL' }, null, { sport: 'MLB', game_time: ago(5) }));
check('row with a kickoff ignores the pick (its own window rules)',
  !gameIsOver({ sport: 'NFL', commence_time: ago(1) }, null, pick('NFL', 30)));
check('a scored row is over regardless',
  gameIsOver({ commence_time: ago(1), home_score: 3, away_score: 2 }, null, pick('NFL', -5)));

if (failures) {
  console.error(`\n${failures} FAILED`);
  process.exit(1);
}
console.log('\nall gameIsOver checks passed');
