/**
 * Standalone verification for the line ruler's stop math (src/lib/lineRuler.ts).
 * Run with:
 *
 *   npx tsx scripts/verify_line_ruler.ts
 *
 * Matt, 2026-09-19: *"When dragging the numbers it should always drag by 5.
 * Make this a change for all NFL and NCAAF player stats"* — narrowed the same
 * session to the YARDAGE stats, because a step of five on Pass TDs (a 1..10
 * ruler) leaves two reachable stops and no way to ask for "2+".
 *
 * What these guard, in the order they would actually break:
 *
 *  - the SCOPE. Five on NFL/NCAAF yardage and nowhere else — not on football
 *    TDs or receptions, where it would delete the board, and not on the
 *    lookalike in another sport (MLB Pitches, default 89.5) that a
 *    scale-derived rule would have swept up uninvited;
 *  - that NOTHING ELSE MOVED. Every other stat in the catalog resolves to the
 *    exact scale the pre-2026-09-19 arithmetic gave it, asserted against a
 *    copy of that arithmetic rather than against a remembered number;
 *  - that every number the board can hold is one the strip can scroll back
 *    to. A value off the grid — from a default, a mode switch, or a settled
 *    scroll — is a pill printing a line the ruler cannot return to, and it is
 *    the failure a step of 1 could not produce and so was never guarded;
 *  - that Under's extra stop is a STOP and not a unit. `+1` on a step-5 ruler
 *    puts the ceiling between ticks, where the strip cannot settle on it.
 */

import {
  YARDAGE_STEP,
  defaultLineN,
  maxLineN,
  rulerScaleFor,
  rulerStepFor,
  snapStop,
  stopAt,
  stopCount,
  stopIndexOf,
  type RulerScale,
} from '../src/lib/lineRuler';
import { STAT_CATALOG, defaultThresholdFor, type StatDef } from '../src/lib/statCatalog';
import { HIT_MODES, selectionFor } from '../src/lib/hitMode';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const find = (sport: StatDef['sport'], key: string): StatDef => {
  const d = STAT_CATALOG.find((s) => s.sport === sport && String(s.key) === key);
  if (!d) throw new Error(`no ${sport} ${key} in the catalog`);
  return d;
};

/** Every value a ruler can reach, in order. */
const stopsOf = (s: RulerScale) => Array.from({ length: stopCount(s) }, (_, i) => stopAt(i, s));

// ── 1. Scope: which stats drag by five ────────────────────────────────────
// Named one at a time rather than swept by a rule, because the whole point of
// the narrowing is that the scale of a stat does not decide this.

const FIVES: [StatDef['sport'], string][] = [
  ['NFL', 'passing_yards'], ['NFL', 'rushing_yards'], ['NFL', 'receiving_yards'],
  ['NCAAF', 'passing_yards'], ['NCAAF', 'rushing_yards'], ['NCAAF', 'receiving_yards'],
];
for (const [sport, key] of FIVES) {
  check(`${sport} ${key} drags by ${YARDAGE_STEP}`, rulerStepFor(find(sport, key)) === YARDAGE_STEP);
}

const ONES: [StatDef['sport'], string][] = [
  // The football stats a blanket five would have destroyed: their whole ruler
  // is 1..10, so five leaves the stops {5, 10} and no way to say "2+ TDs".
  ['NFL', 'passing_tds'], ['NFL', 'receptions'], ['NFL', 'targets'], ['NFL', 'def_sacks'],
  ['NCAAF', 'rushing_tds'], ['NCAAF', 'def_tackles'], ['NCAAF', 'carries'],
  // The volume stats, left at one deliberately: books price completions and
  // attempts by the single unit, so 20/21/22 is the question people ask.
  ['NFL', 'completions'], ['NFL', 'attempts'],
  // Another sport's yard-scale stat. A `defaultLine >= 40` rule would have
  // moved this without anyone asking; the scope is NFL and NCAAF.
  ['MLB', 'pitches'], ['NBA', 'points'], ['WNBA', 'minutes'],
];
for (const [sport, key] of ONES) {
  check(`${sport} ${key} still drags by 1`, rulerStepFor(find(sport, key)) === 1);
}
check('a missing stat does not crash the ruler', rulerStepFor(null) === 1);

// ── 2. Nothing else moved ─────────────────────────────────────────────────
// The pre-change arithmetic, copied verbatim off origin/master, so "unchanged"
// is asserted rather than remembered.
const legacyScale = (def: StatDef | null, under: boolean) => {
  const dflt = Math.max(1, Math.ceil(defaultThresholdFor(def)));
  return { min: 1, max: Math.max(10, dflt * 3) + (under ? 1 : 0), step: 1, dflt };
};
const untouched = STAT_CATALOG.filter((d) => rulerStepFor(d) === 1);
check(
  'every step-1 stat keeps the exact scale it had before',
  untouched.every((d) =>
    HIT_MODES.every(({ mode }) => {
      const now = rulerScaleFor(d, mode);
      const was = legacyScale(d, mode === 'under');
      return now.min === was.min && now.max === was.max && now.step === 1 &&
        defaultLineN(d) === was.dflt;
    }),
  ),
  `${untouched.length} stats × 3 modes`,
);
check(
  'and that is most of the catalog, not an empty sweep',
  untouched.length === STAT_CATALOG.length - FIVES.length,
  `${untouched.length} of ${STAT_CATALOG.length}`,
);

// ── 3. Every reachable number is on the grid ──────────────────────────────
// The failure a step of 1 could not produce: a value the pill can print and
// the strip can never scroll back to.
for (const def of STAT_CATALOG) {
  const step = rulerStepFor(def);
  if (step === 1) continue;
  for (const { mode } of HIT_MODES) {
    const s = rulerScaleFor(def, mode);
    const stops = stopsOf(s);
    check(
      `${def.sport} ${String(def.key)} (${mode}): every stop is ${step} apart`,
      stops.every((v, i) => i === 0 || v - (stops[i - 1] as number) === step),
    );
    check(
      `${def.sport} ${String(def.key)} (${mode}): the ceiling is a stop`,
      stops[stops.length - 1] === s.max && (s.max - s.min) % step === 0,
      `min ${s.min}, max ${s.max}`,
    );
    check(
      `${def.sport} ${String(def.key)} (${mode}): the board opens on a stop`,
      stops.includes(defaultLineN(def)),
      `default ${defaultLineN(def)}`,
    );
    check(
      `${def.sport} ${String(def.key)} (${mode}): no stop is below one step`,
      s.min === step && stops.every((v) => v >= step),
    );
  }
}

// ── 3b. The snap is exercised, not merely satisfied ───────────────────────
// Every shipped yardage default (224.5, 49.5, 44.5) already clears to a
// multiple of five, so §3's "opens on a stop" passes whether `defaultLineN`
// snaps or not — a guard dead code satisfies (CLAUDE.md §7). These run the
// snap on a default that is genuinely off the grid, which is one tuned
// `defaultLine` away from being the real catalog.
{
  const offGrid = { ...find('NCAAF', 'receiving_yards'), defaultLine: 42.5 } as StatDef;
  check(
    'an off-grid default is pulled onto the nearest stop',
    defaultLineN(offGrid) === 45,
    `44.5→45 ships today; 42.5 clears to 43, which snaps to ${defaultLineN(offGrid)}`,
  );
  const tiny = { ...find('NFL', 'rushing_yards'), defaultLine: 0.5 } as StatDef;
  check('a default below one step becomes one step, never zero', defaultLineN(tiny) === YARDAGE_STEP);
  check(
    'and the snapped default is on the scale it opens',
    stopsOf(rulerScaleFor(offGrid, 'atLeast')).includes(defaultLineN(offGrid)) &&
      stopsOf(rulerScaleFor(tiny, 'atLeast')).includes(defaultLineN(tiny)),
  );
}

// ── 4. A settled scroll lands on a stop, never between two ────────────────
// `settle` divides the scroll offset by the tick width and hands the result to
// stopAt, so a fractional offset — a flick that stops mid-tick, a fling past
// the end — has to resolve to a real stop.
{
  const s = rulerScaleFor(find('NFL', 'passing_yards'), 'atLeast');
  const offsets = [-4.2, -0.4, 0, 0.49, 0.5, 1.5, 7.3, 43.6, stopCount(s) - 1, 1e4];
  check(
    'a fractional or runaway scroll offset still settles on a stop',
    offsets.every((o) => {
      const v = stopAt(o, s);
      return v >= s.min && v <= s.max && (v - s.min) % s.step === 0;
    }),
  );
  check(
    'an index round-trips through its value',
    stopsOf(s).every((v, i) => stopIndexOf(v, s) === i),
  );
  check('garbage reads as the floor, not NaN', stopAt(Number.NaN, s) === s.min && stopIndexOf(Number.NaN, s) === 0);
}

// ── 5. Under's extra stop is a stop ───────────────────────────────────────
for (const def of STAT_CATALOG) {
  const plain = rulerScaleFor(def, 'atLeast');
  const under = rulerScaleFor(def, 'under');
  check(
    `${def.sport} ${String(def.key)}: Under adds exactly one stop`,
    stopCount(under) === stopCount(plain) + 1 && under.max === plain.max + plain.step,
  );
}
{
  // "n or fewer" has to reach the number At Least says as "n+" — the 2026-09-06
  // fix, which a step-5 ruler would otherwise re-break by one tick.
  const def = find('NFL', 'passing_yards');
  const plain = rulerScaleFor(def, 'atLeast');
  const under = rulerScaleFor(def, 'under');
  const topAtLeast = selectionFor(plain.max, 'atLeast').line; // 674.5, taken over
  const topUnder = selectionFor(under.max, 'under').line;     // 679.5, taken under
  check(
    'Under can still name the ceiling At Least expresses',
    topUnder > topAtLeast && under.max - plain.max === YARDAGE_STEP,
    `At Least tops out over ${topAtLeast}, Under under ${topUnder}`,
  );
}

// ── 6. Leaving Under does not strand the line off the scale ───────────────
{
  const def = find('NFL', 'passing_yards');
  const under = rulerScaleFor(def, 'under');
  const plain = rulerScaleFor(def, 'atLeast');
  check(
    'the Under-only ceiling snaps back onto the At Least ruler',
    snapStop(under.max, plain) === plain.max,
    `${under.max} → ${snapStop(under.max, plain)}`,
  );
  check(
    'a line carried over from another stat lands on a stop',
    [1, 3, 227, 236, 999].every((n) => {
      const v = snapStop(n, plain);
      return v >= plain.min && v <= plain.max && (v - plain.min) % plain.step === 0;
    }),
  );
  check('a value already on the grid is left alone', snapStop(235, plain) === 235);
  check('and one between stops takes the nearer', snapStop(237, plain) === 235 && snapStop(238, plain) === 240);
}

// ── 7. The complaint itself ───────────────────────────────────────────────
// The board Matt was looking at: NFL Pass Yards, opening on 225.
{
  const def = find('NFL', 'passing_yards');
  const s = rulerScaleFor(def, 'atLeast');
  check('the Pass Yards board still opens on 225', defaultLineN(def) === 225);
  check('225 → 250 is five notches, not twenty-five', stopIndexOf(250, s) - stopIndexOf(225, s) === 5);
  check(
    'the ruler still reaches a league leader',
    maxLineN(def) >= 600 && s.max === maxLineN(def),
    `ceiling ${s.max}`,
  );
  check(
    'the strip is a fifth as long as it was',
    stopCount(s) === Math.floor((maxLineN(def) - YARDAGE_STEP) / YARDAGE_STEP) + 1,
    `${stopCount(s)} stops`,
  );
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
