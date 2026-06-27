/**
 * Standalone verification for the Stats tab "Hit Rate" math
 * (computeHitRate / hitFlags / isHit in src/lib/hitRate.ts and
 * defaultThresholdFor in src/lib/statCatalog.ts). Run with:
 *
 *   npx tsx scripts/verify_hit_rate.ts
 *
 * Pins: over/under counting; null/NaN values skipped (don't inflate total);
 * total===0 → pct===0; hitFlags preserves order; defaultThresholdFor reads the
 * catalog; the ranking comparator puts 5/5 > 2/2 > 0/3.
 */

import { computeHitRate, hitFlags, isHit } from '../src/lib/hitRate';
import { STAT_CATALOG, defaultThresholdFor, type StatDef } from '../src/lib/statCatalog';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}
function approx(a: number, b: number, tol = 1e-9): boolean {
  return Math.abs(a - b) <= tol;
}

// ── computeHitRate, over ──
const r1 = computeHitRate([2, 0, 1, 3, 0], 0.5, 'over');
check('over: 3 of 5 cleared 0.5', r1.hits === 3 && r1.total === 5 && approx(r1.pct, 0.6), JSON.stringify(r1));

// ── computeHitRate, under ──
const r2 = computeHitRate([4, 6, 5], 5.5, 'under');
check('under: 2 of 3 below 5.5', r2.hits === 2 && r2.total === 3, JSON.stringify(r2));

// ── exactly on the line is NOT a hit (strict >) ──
const r3 = computeHitRate([1, 1, 1], 1, 'over');
check('over: value == line is a miss', r3.hits === 0 && r3.total === 3, JSON.stringify(r3));

// ── null/NaN skipped, do not inflate total ──
const r4 = computeHitRate([2, null, undefined, NaN, 0], 0.5, 'over');
check('null/NaN skipped from denominator', r4.hits === 1 && r4.total === 2, JSON.stringify(r4));

// ── empty / all-null → pct 0, total 0 ──
const r5 = computeHitRate([null, undefined], 0.5, 'over');
check('all-null → total 0, pct 0', r5.total === 0 && r5.pct === 0, JSON.stringify(r5));

// ── 10/10 example from the mockup ──
const r6 = computeHitRate([2, 1, 3, 1, 1, 2, 1, 1, 4, 1], 0.5, 'over');
check('10/10 hits ≥1', r6.hits === 10 && r6.total === 10 && approx(r6.pct, 1), JSON.stringify(r6));

// ── hitFlags order preserved + matches isHit ──
const vals = [2, 0, 1];
const flags = hitFlags(vals, 0.5, 'over');
check(
  'hitFlags preserves order',
  flags.length === 3 && flags[0] === true && flags[1] === false && flags[2] === true,
  JSON.stringify(flags),
);
check('isHit agrees with hitFlags', vals.every((v, i) => isHit(v, 0.5, 'over') === flags[i]));

// ── defaultThresholdFor reads the catalog ──
const hits = STAT_CATALOG.find((s: StatDef) => s.sport === 'MLB' && s.key === 'hits')!;
const pts = STAT_CATALOG.find((s: StatDef) => s.sport === 'NBA' && s.key === 'points')!;
check('default line: hits = 0.5', defaultThresholdFor(hits) === 0.5);
check('default line: NBA points = 14.5', defaultThresholdFor(pts) === 14.5);
check('default line: null → 0.5 fallback', defaultThresholdFor(null) === 0.5);
check(
  'every MLB/WNBA/NBA stat has a defaultLine',
  STAT_CATALOG.filter((s) => ['MLB', 'WNBA', 'NBA'].includes(s.sport)).every(
    (s) => typeof s.defaultLine === 'number',
  ),
);

// ── ranking comparator: pct desc, then total desc ──
const players = [
  { pct: 0, total: 3 },
  { pct: 1, total: 2 },
  { pct: 1, total: 5 },
];
const sorted = players.slice().sort((a, b) => b.pct - a.pct || b.total - a.total);
check(
  'sort: 5/5 > 2/2 > 0/3',
  sorted[0].total === 5 && sorted[1].total === 2 && sorted[2].pct === 0,
  JSON.stringify(sorted),
);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
