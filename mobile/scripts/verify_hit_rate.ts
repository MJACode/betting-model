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
import {
  HIT_MODES,
  hitModeHeadline,
  hitModeLineLabel,
  rulerValue,
  rulerValueLabel,
  selectionFor,
  type HitMode,
} from '../src/lib/hitMode';

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
// over or under." Then, 2026-09-06: "I want to fix how over under is
// displayed" — the MODE now chooses the idiom and the ruler is drawn in it,
// so every mode shares one set of stops and At Least 1 and Over 0.5 are the
// same bet under two names. Everything downstream reads only the (line, side)
// this resolves to, so the translation is the whole feature and these are its
// cases.
{
  const cases: [number, HitMode, number, 'over' | 'under', string, string][] = [
    // stop, mode,      line, side,     headline,            ruler face
    [1, 'atLeast', 0.5, 'over',  '1+ Hits',          '1'],
    [1, 'over',    0.5, 'over',  'Over 0.5 Hits',    '0.5'],
    [1, 'under',   0.5, 'under', 'Under 0.5 Hits',   '0.5'],
    [2, 'atLeast', 1.5, 'over',  '2+ Hits',          '2'],
    [2, 'over',    1.5, 'over',  'Over 1.5 Hits',    '1.5'],
    [2, 'under',   1.5, 'under', 'Under 1.5 Hits',   '1.5'],
    [3, 'under',   2.5, 'under', 'Under 2.5 Hits',   '2.5'],
  ];
  for (const [n, mode, line, side, headline, face] of cases) {
    const sel = selectionFor(n, mode);
    check(`${mode} stop ${n} is line ${line} ${side}`,
      sel.line === line && sel.side === side, `${sel.line} ${sel.side}`);
    check(`${mode} stop ${n} reads "${headline}"`,
      hitModeHeadline(n, mode, 'Hits') === headline, hitModeHeadline(n, mode, 'Hits'));
    check(`${mode} stop ${n} shows "${face}" on the ruler`,
      rulerValueLabel(n, mode) === face, rulerValueLabel(n, mode));
  }

  // The competitor's board, and the bug that started this: Over's first stop
  // is the book's smallest line. It used to be 1.5, so "Over 0.5 Hits" — the
  // most-bet prop there is — could not be reached in Over mode at all.
  check('Over starts at the line the book starts at',
    rulerValue(1, 'over') === 0.5 && hitModeHeadline(1, 'over', 'Hits') === 'Over 0.5 Hits');

  // Every line is a HALF point, so no game ever lands on it: a counting stat
  // is a whole number, and a push would make "hit rate" a lie.
  for (const n of [1, 2, 5, 12]) {
    for (const mode of ['atLeast', 'over', 'under'] as HitMode[]) {
      const { line } = selectionFor(n, mode);
      check(`${mode} ${n} lands between whole numbers`, Math.abs(line % 1) === 0.5, `${line}`);
    }
  }

  // The modes OVERLAP, which is the point: a book sells "Over 0.5 Hits" and a
  // fan asks for "1+". They are one bet at one price, so switching the mode
  // must move the BET nowhere — only the words on it.
  for (const n of [1, 2, 7]) {
    const over = selectionFor(n, 'over');
    const atLeast = selectionFor(n, 'atLeast');
    check(`stop ${n}: At Least and Over are one bet, named twice`,
      over.line === atLeast.line && over.side === atLeast.side
        && hitModeHeadline(n, 'over', 'Hits') !== hitModeHeadline(n, 'atLeast', 'Hits'));
  }
  check('and Under is the other side of that same line',
    selectionFor(2, 'under').line === selectionFor(2, 'over').line
      && selectionFor(2, 'under').side === 'under');

  // The three modes against real per-game values.
  const games = [0, 1, 2, 3, 1, 0];
  const rate = (n: number, mode: HitMode) => {
    const { line, side } = selectionFor(n, mode);
    return computeHitRate(games, line, side).hits;
  };
  check('At Least 1 counts every game with a hit', rate(1, 'atLeast') === 4, `${rate(1, 'atLeast')}`);
  check('Over 0.5 counts the same games — it is the same bet', rate(1, 'over') === 4, `${rate(1, 'over')}`);
  check('Over 1.5 counts only multi-hit games', rate(2, 'over') === 2, `${rate(2, 'over')}`);
  check('Under 0.5 counts only the hitless games', rate(1, 'under') === 2, `${rate(1, 'under')}`);
  check('a stop\'s two sides partition the games',
    rate(1, 'over') + rate(1, 'under') === games.length);

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

  // ── the ruler is drawn in the mode's idiom (2026-09-06) ─────────────────
  // Over and Under ARE the book's line, so the second copy of it that used to
  // sit beside the headline would now be the same string twice. At Least
  // keeps it: its headline is "2+ Hits", and without this the number the book
  // posts is nowhere on screen (UX review, 2026-09-05).
  check('the book\'s own line is what Over and Under are called',
    hitModeLineLabel(1, 'atLeast') === 'Over 0.5'
      && hitModeLineLabel(1, 'over') === 'Over 0.5'
      && hitModeLineLabel(2, 'under') === 'Under 1.5',
    [1, 2].map((n) => hitModeLineLabel(n, 'over')).join());
  check('the screen shows it beside the headline in At Least only',
    /\{hitMode === 'atLeast' \? \(\s*\n\s*<Text style=\{styles\.headlineLine\}>\{hitModeLineLabel\(lineN, hitMode\)\}<\/Text>/
      .test(screen));
  check('and the ruler prints the stop in that same idiom',
    screen.includes('format={(n) => rulerValueLabel(n, hitMode)}')
      && screen.includes('const faceOf = format ?? String;')
      && screen.includes('{labeled ? faceOf(v) : \'\'}')
      && screen.includes('<Text style={styles.tickValueActive}>{faceOf(value)}</Text>'));
  check('VoiceOver reads the face, not the stop index',
    screen.includes('accessibilityValue={{ min, max, now: value, text: faceOf(value) }}'));

  // Two idioms, two homes, and neither is spoken in the other's sentence.
  // The betslip explainer quotes the board headline and the book's number in
  // ONE sentence, so it is the place they would clash.
  check('the fan idiom keeps the stat label plural, which singularising cannot',
    hitModeHeadline(2, 'atLeast', 'Hits') === '2+ Hits'
      && hitModeHeadline(2, 'atLeast', 'Total Bases') === '2+ Total Bases');
  check('each idiom has ONE home, so the places that speak it cannot disagree',
    read('src/lib/hitMode.ts').includes('export function thresholdLabel(')
      && read('src/lib/hitMode.ts').includes('export function bookLineLabel(')
      && screen.includes('return bookLineLabel(line, side);')
      && read('src/lib/lineLegs.ts').includes('bookLineLabel(quote.line, quote.side)')
      && !/`\$\{[^}]*- 0\.5\} or fewer`/.test(screen + read('src/lib/lineLegs.ts')));

  // A selected row must not change size in a three-row list built for
  // comparison, and the preview is the reason the row exists.
  check('the selected row reserves its border rather than adding one',
    /borderWidth: 1\.5,\s*\n\s*borderColor: 'transparent',/.test(sheet)
      && sheet.includes('rowActive: { borderColor: colors.bet }'));
  check('the preview cannot be the thing that truncates',
    /styles\.rowPreview[^\n]*\]\}>\s*\n\s*\{priced \? preview/.test(sheet)
      && !/rowPreview[^\n]*numberOfLines/.test(sheet));

  // The trigger is a pop-up button: label / value / hint, a menu glyph, and a
  // target that clears 44pt with its slop.
  // Asserted as a SHAPE, not as three literal strings: the label was
  // "Show bets that are" until the college prune left this control alive on
  // columns with no bet at all, and the wording is allowed to keep moving.
  // What must not move is that all three parts are present and the label does
  // not promise a wager.
  check('the trigger announces itself as a pop-up button',
    (() => {
      const label = /accessibilityLabel="([^"]+)"\s*\n\s*accessibilityValue=\{\{ text: hitModeLabel\(hitMode\) \}\}/
        .exec(screen)?.[1];
      return !!label && !/\bbets?\b/i.test(label)
        && screen.includes('accessibilityHint="Opens the At Least, Over, Under options"');
    })());
  check('it carries a menu glyph and a real hit target',
    screen.includes('name="chevron-expand"')
      && /onPress=\{\(\) => setModeOpen\(true\)\}\s*\n\s*hitSlop=/.test(screen));

  // The ruler is ONE adjustable element, not N unlabelled tick buttons —
  // and in Under mode its number deliberately differs from the headline's.
  check('the ruler is adjustable by VoiceOver',
    screen.includes('accessibilityRole="adjustable"')
      && screen.includes("accessibilityActions={[{ name: 'increment' }, { name: 'decrement' }]}"));
  check('its ticks are decoration', /accessibilityElementsHidden[\s\S]{0,120}styles\.tickCol/.test(screen));

  // Every mode resolves a stop to the same line now, so the ceiling is one
  // number and a mode change leaves the ruler where it stands.
  check('every mode runs over the same stops',
    screen.includes('max={maxLineN(stat)}')
      && !screen.includes("hitMode === 'under' ? 1 : 0"));

  // The JSDoc of the deleted lineFor() documented the OLD mapping.
  check('no stale mapping comment survives the deleted helper',
    !screen.includes('at most  N  →  value < N+0.5'));
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
