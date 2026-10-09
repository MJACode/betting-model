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
const teams = readFileSync(join(ROOT, 'src/components/TeamsBoard.tsx'), 'utf-8');

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

check('the Players slate refetches when the ET date changes and on pull-to-refresh',
  /const slateKey = slateReadKey\(sport, etDay\)/.test(stats) &&
    /const etDay = etDate\(new Date\(now\)\)/.test(stats) &&
    /\[slateKey, etDay, sport, slateReload\]/.test(stats) &&
    /setSlateReload\(\(n\) => n \+ 1\)/.test(stats) &&
    /onRefresh=\{refreshBoard\}/.test(stats));
check('a line-only row does not navigate, and says why',
  /canOpenPlayerDetail\(p\.player_id\)/.test(stats) &&
    /No logged games, so this row does not open/.test(stats) &&
    !/LineOnlyRow[\s\S]{0,900}openPlayer\(/.test(stats));

const teamsReset = teams.slice(
  teams.indexOf('// Reset to the sport\'s default stat'),
  teams.indexOf('}, [sport]);') + 12,
);
check('a sport change clears the Teams slate before the next read lands',
  /setSlate\(\{ date: '', isToday: false, games: \[\] \}\)/.test(teamsReset) &&
    /setSlateFor\(null\)/.test(teamsReset) &&
    /setSlateOnly\(false\)/.test(teamsReset));
check('the Teams chip is disabled while the slate is still checking',
  /disabled=\{slateChipDisabled\(slateChecking, hasSlate\)\}/.test(teams));
check('the Teams slate refetches when the ET date changes and on pull-to-refresh',
  /const slateKey = slateReadKey\(sport, etDay\)/.test(teams) &&
    /const etDay = etDate\(new Date\(now\)\)/.test(teams) &&
    /\[slateKey, etDay, sport, slateReload\]/.test(teams) &&
    /setSlateReload\(\(n\) => n \+ 1\)/.test(teams) &&
    /onRefresh=\{refresh\}/.test(teams));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
