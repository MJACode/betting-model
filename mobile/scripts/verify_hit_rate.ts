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

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { computeHitRate, hitFlags, isHit } from '../src/lib/hitRate';
import { HIT_MODES, hitModeHeadline, selectionFor, type HitMode } from '../src/lib/hitMode';

const read = (p: string) => readFileSync(join(import.meta.dirname, '..', p), 'utf-8');
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

// ── At Least / Over / Under (lib/hitMode.ts, 2026-09-05) ───────────────────
//
// Matt, with a competitor's Leaders tab: "add this feature where the user can
// say they want to show bets that are at least ... or if they want to say
// over or under." The ruler picks a WHOLE number; the mode says which side.
// Everything downstream reads only the (line, side) this resolves to, so the
// translation is the whole feature and these are its cases.
{
  const cases: [number, HitMode, number, 'over' | 'under', string][] = [
    // ruler, mode,      line, side,     headline
    [1, 'atLeast', 0.5, 'over', '1+ Hits'],
    [1, 'over',    1.5, 'over', '2+ Hits'],
    [1, 'under',   0.5, 'under', 'No Hits'],
    [2, 'atLeast', 1.5, 'over', '2+ Hits'],
    [2, 'over',    2.5, 'over', '3+ Hits'],
    [2, 'under',   1.5, 'under', 'At most 1 Hits'],
    [3, 'under',   2.5, 'under', 'At most 2 Hits'],
  ];
  for (const [n, mode, line, side, headline] of cases) {
    const sel = selectionFor(n, mode);
    check(`${mode} ${n} is line ${line} ${side}`,
      sel.line === line && sel.side === side, `${sel.line} ${sel.side}`);
    check(`${mode} ${n} reads "${headline}"`,
      hitModeHeadline(n, mode, 'Hits') === headline, hitModeHeadline(n, mode, 'Hits'));
  }

  // Every line is a HALF point, so no game ever lands on it: a counting stat
  // is a whole number, and a push would make "hit rate" a lie.
  for (const n of [1, 2, 5, 12]) {
    for (const mode of ['atLeast', 'over', 'under'] as HitMode[]) {
      const { line } = selectionFor(n, mode);
      check(`${mode} ${n} lands between whole numbers`, Math.abs(line % 1) === 0.5, `${line}`);
    }
  }

  // The modes OVERLAP on a whole-number stat, which is the point: a book sells
  // "Over 1.5 Hits" and a fan asks for "2+". Both must name the same bet at
  // the same price, or the board is telling two stories.
  const overN = selectionFor(1, 'over');
  const atLeastNext = selectionFor(2, 'atLeast');
  check('Over N is exactly At Least N+1 — same line, same side',
    overN.line === atLeastNext.line && overN.side === atLeastNext.side);
  check('and both are called the same thing',
    hitModeHeadline(1, 'over', 'Hits') === hitModeHeadline(2, 'atLeast', 'Hits'));

  // The three modes against real per-game values.
  const games = [0, 1, 2, 3, 1, 0];
  const rate = (n: number, mode: HitMode) => {
    const { line, side } = selectionFor(n, mode);
    return computeHitRate(games, line, side).hits;
  };
  check('At Least 1 counts every game with a hit', rate(1, 'atLeast') === 4, `${rate(1, 'atLeast')}`);
  check('Over 1 counts only multi-hit games', rate(1, 'over') === 2, `${rate(1, 'over')}`);
  check('Under 1 counts only the hitless games', rate(1, 'under') === 2, `${rate(1, 'under')}`);
  check('the three modes at one ruler partition the games',
    rate(1, 'atLeast') + rate(1, 'under') === games.length);

  // The control opens a real menu. It used to be a two-way toggle wearing a
  // chevron-down, which promised one and gave a flip.
  const screen = read('src/screens/StatsScreen.tsx');
  check('the mode control opens the picker rather than toggling',
    screen.includes('onPress={() => setModeOpen(true)}') && !screen.includes("setDirection"));
  check('the board reads the resolved line and side, never the mode',
    screen.includes('selectionFor(lineN, hitMode)')
      && screen.includes('computeHitRate(values, line, side)')
      && !/side: hitMode/.test(screen));
  const sheet = read('src/components/HitModeSheet.tsx');
  check('every mode is offered', HIT_MODES.length === 3 && sheet.includes('HIT_MODES.map'));
  check('each row previews the bet it would make, since the modes overlap',
    sheet.includes('hitModeHeadline(lineN, m.mode, statLabel)'));
  check('the rows are radios to VoiceOver', sheet.includes('accessibilityRole="radio"'));
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
