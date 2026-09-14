/**
 * Stats filter sheet — sport-change reset, Availability copy, UFC Search order.
 *
 * Run with:  npx tsx scripts/verify_stats_filter_ux.ts
 *
 * Designer filter UX audit (Matt greenlit 2026-09-14): the sport-change
 * comment claimed it cleared filters and the effect did not; Availability
 * did not say that Playing today is the slate and Games is fixtures;
 * UFC's Games empty note said "search above" while Search sat below.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
const stats = readFileSync(join(ROOT, 'src/screens/StatsScreen.tsx'), 'utf-8');

let failures = 0;
function check(name: string, ok: boolean, detail = '') {
  if (ok) {
    console.log(`[PASS] ${name}`);
  } else {
    failures++;
    console.log(`[FAIL] ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

const sportReset = stats.slice(
  stats.indexOf('// Reset to the sport\'s default stat'),
  stats.indexOf('}, [sport]);') + 20,
);

check('sport-change comment still says it clears filters',
  /clear filters whenever the sport changes/.test(sportReset));
check('sport-change resets minGrade', /setMinGrade\(null\)/.test(sportReset));
check('sport-change resets includeUngraded', /setIncludeUngraded\(true\)/.test(sportReset));
check('sport-change resets the hit band',
  /setHitLow\(HIT_RATE_MIN\)/.test(sportReset) && /setHitHigh\(HIT_RATE_MAX\)/.test(sportReset));
check('sport-change resets basis', /setBasis\('perGame'\)/.test(sportReset));

check('Availability names slate vs fixtures',
  /This slate is the day.s card/.test(stats) && /Games above is specific fixtures/.test(stats));
check('the Games-wins note tells the user how to undo',
  /Clear Games to use Playing today/.test(stats));

check('UFC empty note does not say search above',
  !/filter by fighter with the search above/.test(stats));
check('UFC empty note points at Search without a false direction',
  /use Search to filter by fighter/.test(stats));
check('Search is rendered first when Games is empty',
  /gamesEmpty \? searchFilterSection : null/.test(stats) &&
    /gamesEmpty \? null : searchFilterSection/.test(stats));
check('Search does not hop during the slate read',
  /sport === 'UFC' \|\| \(!slateChecking && pickableGames\.length === 0\)/.test(stats));
check('Games stays open when there are no fixtures',
  /summary=\{gamesEmpty \? undefined : gameFilterSummary/.test(stats));
check('Games emptyNote does not claim a dead week while checking',
  /slateChecking\s*\?\s*'Checking the schedule…'/.test(stats));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
