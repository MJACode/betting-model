/**
 * Picks filter chrome + silent-sort / silent-empty guards.
 *
 * Run with:  npx tsx scripts/verify_pick_filter_ux.ts
 *
 * Designer locks (Matt greenlit 2026-09-14): idle chrome is search + Filters;
 * Public hides when under 20% of on-screen rows have a split; search is in the badge / pills /
 * Clear all; leaving Today resets Signal; any segment change resets an
 * impossible Market; Games-empty copy names the board and offers Clear games.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  ALL_CATEGORIES,
  freshFilter,
  presentCategoriesFor,
  resetImpossibleMarket,
  selectedCategories,
} from '../src/lib/pickFilterState';
import { PUBLIC_SORT_MIN_SHARE, publicSortAvailable, publicSplitCount } from '../src/lib/pickSort';

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
check('zero splits → Public is hidden', !publicSortAvailable(noSplits));
check('zero splits → count is 0', publicSplitCount(noSplits) === 0);
check('the lock is 20%', PUBLIC_SORT_MIN_SHARE === 0.2);

const ten = Array.from({ length: 10 }, () => pick({}));
ten[0] = pick({ public_bet_pct: 72 });
check('1 of 10 splits (10%) → Public is hidden', !publicSortAvailable(ten));
ten[1] = pick({ public_bet_pct: 40 });
check('2 of 10 splits (20%) → Public is offered', publicSortAvailable(ten));

const playerOnly = { ...freshFilter(), categories: new Set(['player_prop'] as const) };
const gameBoard = presentCategoriesFor(['ncaaf_spread', 'ncaaf_moneyline']);
const nflBoard = presentCategoriesFor(['nfl_wind_totals', 'nfl_prop_receptions']);
check('Player-only on an all-game board is impossible',
  selectedCategories(playerOnly, gameBoard).length === 0);
check('and resets to all present',
  resetImpossibleMarket(playerOnly, gameBoard).categories.size === ALL_CATEGORIES.length);
check('Player-only on an NFL board is a real cut and is kept',
  resetImpossibleMarket(playerOnly, nflBoard) === playerOnly);

const pf = read('src/components/filters/PickFilters.tsx');
const screen = read('src/screens/PicksHomeScreen.tsx');
const empty = read('src/components/EmptyState.tsx');

check('idle bar has no quick-chip ScrollView', !/<FilterBar[\s\S]*?<ScrollView/.test(pf));
check('Sort lives in the sheet', /title="Sort"/.test(pf));
check('Public chip is hidden, not disabled-on-bar',
  /o\.key !== 'public' \|\| publicSortAvailable/.test(pf) && !/Public \(no splits\)/.test(pf));
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
check('Market section still hides when it cannot cut', /\{marketCutBites \? \(/.test(pf));

check('leaving Today resets Signal to all three',
  /leaveToday/.test(screen) && /next\.signals = new Set\(ALL_SIGNALS\)/.test(screen));
check('any segment change resets an impossible Market',
  /resetImpossibleMarket/.test(screen));
check('Public share is measured on on-screen rows',
  /publicSortAvailable\(filtered\)/.test(screen));
check('Games-empty copy names the board',
  /No picks for \$\{gameSummary\} on \$\{boardLabel\(view\)\}/.test(screen));
check('and offers Clear games',
  /actionLabel="Clear games"/.test(screen) && /actionLabel\?:/.test(empty));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
