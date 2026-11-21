/**
 * The TRACKED filter on the Picks board (All / Not tracked / Tracked).
 *
 * Run with:  npx tsx scripts/verify_tracked_filter.ts
 *
 * Matt, 2026-11-21: "Add a filter here to show bets that have not been
 * placed so we should go off of the track indicator." What this pins:
 *
 *   1. The cut follows the tracked state exactly; All passes everything.
 *   2. The chips carry counts that add up (Not tracked + Tracked = All).
 *   3. The screen cuts with the card's own isTracked, defaults to All, and the
 *      sheet shows it as a pill and clears it with Clear all.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { passesTrackedCut, trackedCutOptionsFor } from '../src/lib/trackedFilter';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// 1. The cut.
check('All passes tracked and untracked', passesTrackedCut('all', true) && passesTrackedCut('all', false));
check('Not tracked keeps only untracked', passesTrackedCut('untracked', false) && !passesTrackedCut('untracked', true));
check('Tracked keeps only tracked', passesTrackedCut('tracked', true) && !passesTrackedCut('tracked', false));

// 2. Counts.
const opts = trackedCutOptionsFor([true, false, false, true, false]);
const n = (c: string) => opts.find((o) => o.cut === c)?.count;
check('three chips, All first', opts.map((o) => o.cut).join(',') === 'all,untracked,tracked');
check('counts: 5 / 3 / 2', n('all') === 5 && n('untracked') === 3 && n('tracked') === 2, JSON.stringify(opts));
check('labels', opts.map((o) => o.label).join('|') === 'All|Not tracked|Tracked');
check('nothing tracked: Not tracked = All', (() => {
  const o = trackedCutOptionsFor([false, false]);
  return o[0].count === 2 && o[1].count === 2 && o[2].count === 0;
})());

// 3. Wiring.
const screen = read('src/screens/PicksHomeScreen.tsx');
const sheet = read('src/components/filters/PickFilters.tsx');
check('screen defaults to All', screen.includes("useState<TrackedCut>('all')"));
check('screen cuts with the card\'s isTracked',
  screen.includes('passesTrackedCut(trackedCut, tracked.isTracked(d.pick))'));
check('screen passes the cut to the sheet',
  screen.includes('trackedCut={trackedCut}') && screen.includes('onTrackedCutChange={setTrackedCut}'));
check('sheet renders a Tracked section', sheet.includes('title="Tracked"'));
check('sheet shows a pill while narrowed', sheet.includes("key: 'tracked'"));
check('Clear all resets Tracked', /const clearAll = \(\) => \{[^}]*onTrackedCutChange\?\.\('all'\)/s.test(sheet));
check('Tracked empty state only when Tracked alone emptied the board',
  screen.includes('if (hasAny && emptiedByTracked)')
  && screen.includes("trackedCut !== 'all' && filtered.length === 0 && trackedPool.length > 0"));
check('chip counts come from every other cut, search included',
  screen.includes('trackedCutOptionsFor(trackedPool.map('));
check('an emptied board offers Show all', screen.includes('onShowAllTracked={() => setTrackedCut(\'all\')}'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
