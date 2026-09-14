/**
 * Picks filter chrome + silent-sort / silent-empty guards.
 *
 * Run with:  npx tsx scripts/verify_pick_filter_ux.ts
 *
 * Designer filter UX audit (Matt greenlit 2026-09-14): idle chrome is search
 * + Filters only; Public is disabled when it would match Edge; search
 * participates in the badge / pills / Clear all; Minimums placeholders do not
 * look like defaults; leaving Today clears a Signal (and impossible Market)
 * the destination board cannot undo in-sheet.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { publicSortAvailable, publicSplitCount } from '../src/lib/pickSort';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, ok: boolean, detail = '') {
  if (ok) {
    console.log(`[PASS] ${name}`);
  } else {
    failures++;
    console.log(`[FAIL] ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

const pick = (over: { public_bet_pct?: number | null }) => ({
  pick: { public_bet_pct: over.public_bet_pct ?? null },
});

const noSplits = [pick({}), pick({})];
const withSplit = [...noSplits, pick({ public_bet_pct: 72 })];

check('zero splits → Public is not a real sort', !publicSortAvailable(noSplits));
check('zero splits → count is 0', publicSplitCount(noSplits) === 0);
check('one captured split → Public is offered', publicSortAvailable(withSplit));

const pf = read('src/components/filters/PickFilters.tsx');
const screen = read('src/screens/PicksHomeScreen.tsx');

check('idle bar has no quick-chip ScrollView', !/<FilterBar[\s\S]*?<ScrollView/.test(pf));
check('Sort lives in the sheet', /title="Sort"/.test(pf));
check('search is a removable pill', /key: 'search'/.test(pf));
check('search is in the Filters badge count', /searchActive \? 1 : 0/.test(pf));
check('Clear all also clears search', /onSearchChange\(''\)/.test(pf));
check('min fields use e.g. placeholders, not bare numbers',
  /placeholder="e\.g\. 65"/.test(pf) &&
    /placeholder="e\.g\. 10"/.test(pf) &&
    /placeholder="e\.g\. 2"/.test(pf) &&
    !/placeholder="65"/.test(pf) &&
    !/placeholder="10"/.test(pf));
check('Signals/Live Minimums name the action-filter overlap',
  /Optional extra floor/.test(pf));
check('Public is relabelled when it has no splits',
  /Public \(no splits\)/.test(pf));

check('leaving Today clears a narrowed Signal',
  /if \(view === 'today'\) return/.test(screen) &&
    /next\.signals = new Set\(ALL_SIGNALS\)/.test(screen));
check('and clears a Market the destination board cannot show',
  /marketImpossible/.test(screen) &&
    /next\.categories = new Set\(ALL_CATEGORIES\)/.test(screen));
check('an empty board caused by Games names the shared Stats cut',
  /emptiedByGames/.test(screen) &&
    /Games is shared with Stats/.test(screen));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
