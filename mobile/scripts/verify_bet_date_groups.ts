/**
 * Verify the Performance tab's bet-date grouping (lib/betDateGroups.ts).
 * Run by tests/test_mobile_performance_insights.py with node's type stripping.
 */
import {
  DEFAULT_OPEN_DATES,
  DEFAULT_VISIBLE_DATES,
  groupByDate,
  isDateOpen,
  summarizeDate,
  visibleDateGroups,
} from '../src/lib/betDateGroups';

let failures = 0;
function check(name: string, cond: boolean, detail?: unknown) {
  if (cond) console.log(`[PASS] ${name}`);
  else {
    failures++;
    console.log(`[FAIL] ${name}${detail !== undefined ? ` -> ${JSON.stringify(detail)}` : ''}`);
  }
}

type Row = { id: string; date: string; status: string; profit: number };
const rows: Row[] = [
  { id: 'a-open', date: '2026-11-21', status: 'open', profit: 0 },
  { id: 'b-open', date: '2026-11-22', status: 'open', profit: 0 },
  { id: 'c-won', date: '2026-11-21', status: 'won', profit: 91 },
  { id: 'd-lost', date: '2026-11-20', status: 'lost', profit: -110 },
  { id: 'e-push', date: '2026-11-21', status: 'push', profit: 0 },
];
const g = groupByDate(rows, (r) => r.date);
check('dates run newest first', g.map((x) => x.date).join(',') === '2026-11-22,2026-11-21,2026-11-20', g.map((x) => x.date));
check('a day keeps the order it was given', g[1].items.map((r) => r.id).join(',') === 'a-open,c-won,e-push', g[1].items);
check('every row lands in exactly one day', g.reduce((n, x) => n + x.items.length, 0) === rows.length);

const s = summarizeDate(g[1].items, (r) => r.status, (r) => r.profit);
check('a day sums won and lost only', s.net === 91 && s.wins === 1 && s.losses === 0, s);
check('a day counts its push and its open bet apart', s.pushes === 1 && s.open === 1 && s.settled === 2, s);
const v = summarizeDate([{ status: 'no_action' }, { status: 'won' }], (r) => r.status, () => 91);
check('no action counts in the day, not its record', v.other === 1 && v.wins === 1 && v.settled === 1, v);

check('the two newest days start open', isDateOpen('x', 0, {}) && isDateOpen('y', DEFAULT_OPEN_DATES - 1, {}));
check('older days start folded', !isDateOpen('z', DEFAULT_OPEN_DATES, {}));
check('a tap folds an open day', !isDateOpen('x', 0, { x: false }));
check('a tap opens a folded day', isDateOpen('z', 5, { z: true }));

const many = Array.from({ length: 10 }, (_, i) => ({ id: String(i), date: `2026-11-${String(10 + i).padStart(2, '0')}`, status: 'won', profit: 1 }));
const mg = groupByDate(many, (r) => r.date);
check('the list shows the newest seven days first', visibleDateGroups(mg, false).length === DEFAULT_VISIBLE_DATES && visibleDateGroups(mg, false)[0].date === '2026-11-19');
check('See all shows every day', visibleDateGroups(mg, true).length === 10);
const withOld = [...many, { id: 'old-open', date: '2026-10-01', status: 'open', profit: 0 }];
const og = groupByDate(withOld, (r) => r.date);
const hasOpen = (g: { items: { status: string }[] }) => g.items.some((r) => r.status === 'open');
const ov = visibleDateGroups(og, false, hasOpen);
check('an old day with an open bet shows before See all', ov.some((g) => g.date === '2026-10-01') && ov.length === DEFAULT_VISIBLE_DATES + 1, ov.map((g) => g.date));
check('a day with an open bet starts open, however old', isDateOpen('2026-10-01', 10, {}, true));
check('a tap still folds a day with an open bet', !isDateOpen('2026-10-01', 10, { '2026-10-01': false }, true));

if (failures > 0) {
  console.log(`\n${failures} failure(s)`);
  process.exit(1);
}
console.log('\nAll bet-date grouping checks passed');
