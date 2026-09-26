/**
 * The DATE filter on the Picks board.
 *
 * Run with:  npx tsx scripts/verify_date_filter.ts
 *
 * Matt, 2026-09-26, from the NCAAF board: *"Add a Filter by date because games
 * could be on different days."* The first three cards on that board were a game
 * in play, a 6:30 PM kickoff and a look-ahead pick for Sat 11/28.
 *
 * What this pins, each a way the filter can be quietly wrong:
 *
 *   1. EMPTY MEANS EVERY DATE — the default hides nothing (it is a viewer's
 *      filter, never a publishing horizon).
 *   2. THE CHIPS ONLY OFFER DAYS THE BOARD HOLDS, earliest first, with counts.
 *   3. AN IMPOSSIBLE SELECTION WIDENS, IT DOES NOT EMPTY — a day picked on Today
 *      that Signals lacks must not blank Signals behind chips showing nothing.
 *   4. THE SCREEN ACTUALLY APPLIES IT, shows it in the bar, and clears it with
 *      Clear all.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  dateFilterSummary,
  dateLabel,
  dateOptionsFor,
  datesAreNarrowed,
  effectiveDateSelection,
  isDateSelected,
} from '../src/lib/dateFilter';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const TODAY = '2026-09-26';
// The screenshot's board: live game filed under today, tonight, and 11/28.
const boardDates = ['2026-11-28', TODAY, TODAY, '2026-09-27', null, TODAY];
const opts = dateOptionsFor(boardDates, TODAY);

// 1. Empty = everything.
check('empty selection keeps every date', isDateSelected('2026-11-28', new Set()));
check('empty selection keeps a pick with no date', isDateSelected(null, new Set()));
check('empty selection is not narrowed', !datesAreNarrowed(new Set(), opts));
check('empty selection summarises as All dates', dateFilterSummary(new Set(), opts) === 'All dates');

// 2. Options.
check(
  'options are the distinct dates, earliest first',
  opts.map((o) => o.date).join(',') === `${TODAY},2026-09-27,2026-11-28`,
  opts.map((o) => o.date).join(','),
);
check('counts per date', opts.map((o) => o.count).join(',') === '3,1,1', opts.map((o) => o.count).join(','));
check('today labelled Today', dateLabel(TODAY, TODAY) === 'Today');
check('tomorrow labelled Tomorrow', dateLabel('2026-09-27', TODAY) === 'Tomorrow');
check('yesterday labelled Yesterday (a late game past midnight)', dateLabel('2026-09-25', TODAY) === 'Yesterday');
check('a far day names weekday + date', dateLabel('2026-11-28', TODAY) === 'Sat Nov 28', dateLabel('2026-11-28', TODAY));
check('tomorrow across a month end', dateLabel('2026-10-01', '2026-09-30') === 'Tomorrow');

// Narrowing.
const sat = new Set(['2026-11-28']);
check('a selected date keeps its picks', isDateSelected('2026-11-28', sat));
check('an unselected date is cut', !isDateSelected(TODAY, sat));
check('a dateless pick is cut while narrowed', !isDateSelected(null, sat));
check('one day is narrowed', datesAreNarrowed(sat, opts));
check('one day summarises by its label', dateFilterSummary(sat, opts) === 'Sat Nov 28');
check('two days summarise as a count', dateFilterSummary(new Set([TODAY, '2026-11-28']), opts) === '2 dates');
const every = new Set(opts.map((o) => o.date));
check('selecting every day is not narrowing', !datesAreNarrowed(every, opts));

// 3. Impossible selection widens.
const signalsOpts = dateOptionsFor([TODAY, TODAY], TODAY);
const resolved = effectiveDateSelection(sat, signalsOpts);
check('a day absent from this board falls back to every date', resolved.size === 0);
check('a partly present selection is kept as-is', effectiveDateSelection(new Set([TODAY, '2026-11-28']), signalsOpts).size === 2);
check('a possible selection keeps identity (no render loop)', effectiveDateSelection(sat, opts) === sat);
const empty = new Set<string>();
check('empty selection keeps identity (no render loop)', effectiveDateSelection(empty, opts) === empty);

// 4. Wiring.
const screen = read('src/screens/PicksHomeScreen.tsx');
const filters = read('src/components/filters/PickFilters.tsx');
check(
  'the board filters on the pick\'s game_date',
  /isDateSelected\(d\.pick\.game_date, selectedDates\)/.test(screen),
);
check('the filtered list is built from the date-cut items', /applyFilter\(datedItems, displayFilter\)/.test(screen));
check('the screen hands the date cut to the filter bar', /onToggleDate=\{toggleDate\}/.test(screen));
check('the date selection resets on sport change', /setPickedDates\(new Set\(\)\);\s*\}, \[sport\]\)/.test(screen));
check('the sheet renders a Date section', /title="Date"/.test(filters));
check('a narrowed date shows as a removable pill', /key: 'dates'/.test(filters));
check('Clear all clears the dates', /onClearDates\?\.\(\);/.test(filters));
check('a narrowed date counts on the Filters badge', /\(datesNarrowed \? 1 : 0\)/.test(filters));

console.log(failures === 0 ? '\nAll date-filter checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);
