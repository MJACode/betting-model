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

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import {
  YARDAGE_STEP,
  clampTypedLine,
  clampedFieldText,
  clearSettleSkip,
  commitTypedThreshold,
  defaultLineN,
  maxLineN,
  pointInBubble,
  previewTypedLine,
  programmaticPick,
  compactRulerHeight,
  rulerMarkHeight,
  stopUnderOffset,
  RULER_MARK_H,
  RULER_TICKS_H,
  MARKER_HIT_H,
  markerBoxInGesture,
  markerHitOverhang,
  rulerChromeHeight,
  rulerHi,
  rulerScaleFor,
  rulerStepFor,
  settleHold,
  snapStop,
  stopAt,
  stopCount,
  stopIndexOf,
  THRESHOLD_TYPE_HINT,
  thresholdBubbleLabel,
  thresholdControlsScroll,
  thresholdFieldWidth,
  type RulerScale,
} from '../src/lib/lineRuler';
import { hitModeLineLabel } from '../src/lib/hitMode';
import { parseTypedLine, stepLineFrom } from '../src/lib/playerLog';
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
  // Targets left the catalog 2026-10-06. Naming it here aborted the script
  // before any later check ran.
  ['NFL', 'passing_tds'], ['NFL', 'receptions'], ['NFL', 'def_sacks'],
  ['NCAAF', 'rush_rec_tds'], ['NCAAF', 'def_tackles'], ['NCAAF', 'carries'],
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

// ── 8. A typed off-grid line must not snap when the scroll settles ────────
// Typing 47 on Rec Yards (step 5) calls onChange(47) and scrolls to the
// nearest stop. iOS (and some Android) then fire onMomentumScrollEnd, and
// settle reads that stop. Measured: stopIndexOf(47) settles on 45.
{
  const def = find('NFL', 'receiving_yards');
  const scale = rulerScaleFor(def, 'atLeast');
  const typed = parseTypedLine('47', 'atLeast');
  check('Rec Yards "47" parses as 47', typed === 47);
  const offset = stopIndexOf(typed ?? 0, scale);
  const nearest = stopAt(offset, scale);
  check(
    'typing 47 on Rec Yards snaps to 45 when that settle is not skipped',
    nearest === 45 && nearest !== typed,
    `nearest ${nearest}`,
  );
  const kept = settleHold(programmaticPick(typed ?? 0), offset, scale);
  check(
    'a programmatic pick of 47 skips that settle and stays 47',
    kept.value === 47 && kept.skipNextSettle === false,
    `value ${kept.value}, skip ${kept.skipNextSettle}`,
  );
  // The flag is one shot, and a finger drag clears it before the drag settles.
  const armed = programmaticPick(47);
  const dragged = clearSettleSkip(armed);
  const afterDrag = settleHold(dragged, stopIndexOf(50, scale), scale);
  check(
    'a user drag clears the skip and the settle lands on the dragged stop',
    dragged.skipNextSettle === false && afterDrag.value === 50,
  );
  const hi = scale.max;
  const clamped = clampTypedLine(parseTypedLine('999'), scale.min, hi);
  check('typed 999 clamps to the Rec Yards ceiling', clamped === hi, `got ${clamped}, hi ${hi}`);
  const down = stepLineFrom(clamped ?? 0, -1, scale.step);
  check(
    'VoiceOver can step down from a clamped ceiling',
    down >= scale.min && down <= hi && down < (clamped ?? 0),
    `down ${down}`,
  );
  const unclampedDown = stepLineFrom(999, -1, scale.step);
  check(
    'an unclamped 999 steps to a number the ruler refuses',
    unclampedDown > hi,
    `step ${unclampedDown}, hi ${hi}`,
  );
  check('typed 0 clamps up to the floor', clampTypedLine(parseTypedLine('0'), scale.min, hi) === scale.min);
  check('junk stays refused', clampTypedLine(parseTypedLine('abc'), scale.min, hi) === null);
  check(
    'a clamped 999 paints 150 in the text field',
    clampedFieldText('999', hi, String) === String(hi),
    `got ${clampedFieldText('999', hi, String)}`,
  );
  check(
    'an in-range typed line does not rewrite the field',
    clampedFieldText('47', 47, String) === null,
  );
  check(
    'a typed 0 paints the floor in the field',
    clampedFieldText('0', scale.min, String) === String(scale.min),
  );
  check(
    'the field uses the face, so a half-point mode shows the half point',
    clampedFieldText('999', hi, (n) => String(n - 0.5)) === String(hi - 0.5),
  );
  check(
    'an in-range Over face is already applied, so the field closes',
    clampedFieldText('1.5', 2, (n) => String(n - 0.5)) === null,
  );
  check('junk does not rewrite the field', clampedFieldText('abc', null, String) === null);
}

{
  const screen = readFileSync(join(import.meta.dirname, '../src/screens/StatsScreen.tsx'), 'utf-8');
  check(
    'the ruler arms the skip on a programmatic pick and clears it when a drag starts',
    screen.includes('programmaticPick(v)') &&
      screen.includes('settleHold(') &&
      screen.includes('clearSettleSkip(') &&
      screen.includes('onScrollBeginDrag='),
  );
  const offGrid: RulerScale = { min: 5, max: 152, step: 5 };
  const last = rulerHi(offGrid);
  check(
    'an off-grid max leaves the last stop below scale.max',
    last === 150 && last < offGrid.max,
    `hi ${last}, max ${offGrid.max}`,
  );
  check(
    'typed 999 clamps to that last stop, not the off-grid max',
    clampTypedLine(parseTypedLine('999'), offGrid.min, last) === last &&
      clampTypedLine(parseTypedLine('999'), offGrid.min, offGrid.max) === offGrid.max,
  );
  check(
    'a typed line is clamped to the VoiceOver ceiling, not scale.max',
    /commitTypedThreshold\(draft, typed, min, hi, faceOf\)/.test(screen) &&
      /const hi = rulerHi\(scale\)/.test(screen) &&
      !/clampTypedLine\(/.test(screen) &&
      !/rulerScale\.max/.test(screen) &&
      !screen.includes('Below one stop is refused'),
  );
  check(
    // The 2026-10-09 review removed a SEPARATE pencil button. Matt,
    // 2026-10-28, wanted the tap-to-edit visible, so the pencil is back as a
    // glyph INSIDE the marker — still one target, not a second button.
    'the marker is the field, and the pencil is inside it, not a separate button',
    !screen.includes('typeLineBtn') &&
      /styles\.thresholdMark,[\s\S]{0,1400}name="pencil"/.test(screen) &&
      screen.includes('styles.thresholdBubble') &&
      screen.includes('styles.thresholdMark') &&
      screen.includes('borderColor: colors.tint') &&
      screen.includes('minWidth: THRESHOLD_BUBBLE_W') &&
      screen.includes('minHeight: THRESHOLD_BUBBLE_H') &&
      screen.includes('TapGestureHandler') &&
      screen.includes('maxDist={THRESHOLD_TAP_MAX_DIST}') &&
      screen.includes('pointerEvents="none"'),
  );
  check(
    'the bubble button is a sibling of the adjustable, and Type a line stays',
    screen.includes('accessibilityRole="adjustable"') &&
      screen.includes("label: 'Type a line'") &&
      screen.includes('thresholdBubbleLabel(faceOf(value), statLabel)') &&
      screen.includes('accessibilityHint={THRESHOLD_TYPE_HINT}') &&
      screen.includes("name: 'activate'") &&
      screen.includes("actionName === 'activate'") &&
      screen.includes('onAccessibilityTap={openDraft}') &&
      screen.includes('accessibilityLabel="Cancel"') &&
      screen.includes('accessibilityLabel="Done"'),
  );
  check(
    'a typed correction is navy text with an info icon',
    screen.includes('name="information-circle-outline"') &&
      screen.includes('styles.lineNoticeText') &&
      /lineNoticeText: \{[^}]*color: colors\.tint/.test(screen) &&
      !/lineNoticeText: \{[^}]*colors\.avoid/.test(screen),
  );
  check(
    'the field opens on the current face, and the strip follows keystrokes',
    screen.includes('setDraft(faceOf(value))') &&
      !screen.includes('setDraft(\'\')') &&
      screen.includes('previewTypedLine(') &&
      screen.includes('selectTextOnFocus'),
  );
  const doneBar = screen.slice(
    screen.indexOf('function ThresholdDoneBar'),
    screen.indexOf('function LineRuler'),
  );
  check(
    'Cancel and Done are 44pt targets, the notice uses a spacing token, and a tap dims the bubble',
    (doneBar.match(/hitSlop=\{\{ top: 8, bottom: 8, left: 8, right: 8 \}\}/g) ?? []).length === 2 &&
      /doneBtn: \{[^}]*minWidth: 44/.test(screen) &&
      /lineNotice: \{[^}]*gap: spacing\.xs/.test(screen) &&
      screen.includes('bubblePressed && styles.pressed') &&
      screen.includes('setBubblePressed(false)'),
  );
  check(
    'the editing field is the bubble width, grown with the text',
    screen.includes('width: thresholdFieldWidth(fontScale)') &&
      screen.includes('maxWidth: thresholdFieldWidth(fontScale)') &&
      /thresholdInput: \{[^}]*width: THRESHOLD_BUBBLE_W/.test(screen) &&
      /thresholdInput: \{[^}]*alignSelf: 'center'/.test(screen) &&
      /thresholdInput: \{[^}]*flexGrow: 0/.test(screen),
  );
  const rulerFn = screen.slice(screen.indexOf('function LineRuler'), screen.indexOf('function StatSegmentRow'));
  check(
    'Android and web draw Cancel and Done across the row, not inside the ruler column',
    screen.includes('styles.lineStack') &&
      screen.includes("Platform.OS !== 'ios' && lineEditBar") &&
      /doneBar: \{[^}]*alignSelf: 'stretch'/.test(screen) &&
      rulerFn.includes('InputAccessoryView') &&
      !rulerFn.includes("Platform.OS !== 'ios'"),
  );
  const tapHandler = screen.slice(screen.indexOf('const onBubbleTap'), screen.indexOf('const draftSelection'));
  const guard = screen.slice(screen.indexOf('const releaseTickGuard'), screen.indexOf('const scrollToValue'));
  check(
    'a bubble tap holds the tick guard until the next frame',
    guard.includes('requestAnimationFrame') &&
      guard.indexOf('suppressTick.current = false') > guard.indexOf('requestAnimationFrame') &&
      tapHandler.includes('releaseTickGuard()') &&
      tapHandler.includes('suppressTick.current = inside') &&
      !tapHandler.includes('suppressTick.current = false'),
  );
  const cancelBody = screen.slice(screen.indexOf('const cancelDraft = () => {'), screen.indexOf('const commitRef'));
  check(
    'Cancel puts the strip back and does not move the board',
    cancelBody.includes('scrollToValue(openedValue.current)') && !cancelBody.includes('onChange('),
  );
  check(
    'the field commits on blur, and the clamp is announced once',
    screen.includes('onBlur={commitDraft}') &&
      screen.includes("addEventListener('mousedown', keepFocus)") &&
      screen.includes('event.preventDefault()') &&
      screen.includes('ref={cancelHost}') &&
      !screen.includes('cancelPending') &&
      screen.includes("outcome.notice && Platform.OS !== 'android'") &&
      screen.includes("accessibilityLiveRegion={Platform.OS === 'android' ? 'polite' : undefined}"),
  );
  const accessory = screen.slice(screen.indexOf('<InputAccessoryView'), screen.indexOf('</InputAccessoryView>'));
  check(
    'the iOS Done bar does not dismiss the keyboard a second time',
    accessory.includes('onDone={commitDraft}') && !accessory.includes('Keyboard.dismiss()'),
  );
  check(
    '2x text or landscape scrolls the line control',
    screen.includes('thresholdControlsScroll(windowFontScale, windowWidth, windowHeight)') &&
      screen.includes('automaticallyAdjustKeyboardInsets') &&
      screen.includes('function ThresholdChromeScroll'),
  );
}

// ── 9. Tap-to-type on the threshold bubble ────────────────────────────────
{
  const pass = find('NFL', 'passing_yards');
  const scale = rulerScaleFor(pass, 'atLeast');
  const hi = rulerHi(scale);
  const face = String;
  check('Pass Yards runs 5 to 675', scale.min === 5 && hi === 675, `min ${scale.min} hi ${hi}`);
  const typed225 = parseTypedLine('225', 'atLeast');
  check('typed 225 in At Least is stop 225', typed225 === 225);
  check(
    'and that stop is still Over 224.5',
    hitModeLineLabel(typed225 ?? 0, 'atLeast') === 'Over 224.5',
  );
  check('a whole number in Over is the next half-point stop', parseTypedLine('50', 'over') === 51);
  check('a whole number in Under is that same next half-point stop', parseTypedLine('50', 'under') === 51);
  const overMax = commitTypedThreshold('999', parseTypedLine('999', 'atLeast'), scale.min, hi, face);
  check(
    'over max clamps and says the ceiling',
    overMax.apply === hi && overMax.notice === 'Max is 675, set to 675',
    `${overMax.apply} ${overMax.notice}`,
  );
  const underMin = commitTypedThreshold('1', parseTypedLine('1', 'atLeast'), scale.min, hi, face);
  check(
    'under min clamps and says the floor',
    underMin.apply === scale.min && underMin.notice === 'Min is 5, set to 5',
    `${underMin.apply} ${underMin.notice}`,
  );
  const junk = commitTypedThreshold('abc', parseTypedLine('abc', 'atLeast'), scale.min, hi, face);
  check(
    'non-numeric restores and names the range',
    junk.apply === null && junk.notice === 'Enter 5 to 675',
    `${junk.apply} ${junk.notice}`,
  );
  const empty = commitTypedThreshold('  ', null, scale.min, hi, face);
  check('empty restores silently', empty.apply === null && empty.notice === null);
  const off = commitTypedThreshold('47', parseTypedLine('47', 'atLeast'), scale.min, hi, face);
  check('an off-grid 47 is kept as typed', off.apply === 47 && off.notice === null);
  check('the strip would park that 47 on 45', snapStop(47, scale) === 45);
  const live = previewTypedLine('47', 47, scale.min, hi);
  check('a keystroke of 47 previews 47, not the parked tick', live === 47);
  check('a keystroke of 999 previews the ceiling', previewTypedLine('999', 999, scale.min, hi) === hi);
  check('a half-typed decimal does not move the strip', previewTypedLine('22.', null, scale.min, hi) === null);
  check('an empty keystroke does not move the strip', previewTypedLine('', null, scale.min, hi) === null);
  const box = { x: 40, y: 20, width: 64, height: 44 };
  check('a point inside the bubble hits', pointInBubble(50, 30, box));
  check('a point outside the bubble misses', !pointInBubble(10, 30, box));
  // Compact marker is 22pt. The finger target grows to 44pt tall, centered
  // on the drawn pill. Width stays the pill's.
  const short = { x: 40, y: 20, width: 22, height: 22 };
  check('a 22pt marker still hits 11pt above its top', pointInBubble(50, 10, short));
  check('a 22pt marker misses a point beside it', !pointInBubble(10, 30, short));
  check('a 22pt marker misses a point 23pt above its top', !pointInBubble(50, 20 - 23, short));
  check(
    'the bubble name is the face and the stat',
    thresholdBubbleLabel('225', 'Pass Yards') === 'Threshold 225 Pass Yards',
  );
  check(
    'the gesture is the hint, not the name',
    THRESHOLD_TYPE_HINT === 'double tap to type a value' &&
      !thresholdBubbleLabel('225', 'Pass Yards').includes('double tap'),
  );
  check('the field is 64pt at 1x and 128pt at 2x', thresholdFieldWidth(1) === 64 && thresholdFieldWidth(2) === 128);
  check('the field stops growing past 2x', thresholdFieldWidth(3) === 128 && thresholdFieldWidth(0) === 64);
  check('2x text scrolls the line control', thresholdControlsScroll(2, 390, 844));
  check('landscape scrolls the line control', thresholdControlsScroll(1, 844, 390));
  check('portrait at 1x does not', !thresholdControlsScroll(1, 390, 844));
  check('the bubble has room to grow at 2x', rulerChromeHeight(2) > rulerChromeHeight(1));
  // Matt, 2026-10-28: the 28pt strip was "too small". Bubble + pointer +
  // numbered tick row, still shorter than the open typing field.
  check(
    'the resting ruler is the bubble plus a numbered tick row',
    compactRulerHeight(1) === RULER_MARK_H + RULER_TICKS_H &&
      compactRulerHeight(1) === 62 &&
      compactRulerHeight(1) < rulerChromeHeight(1) &&
      rulerMarkHeight(1) === 30 &&
      rulerMarkHeight(2) === 48 &&
      compactRulerHeight(1.3) > compactRulerHeight(1),
  );
  // Live number while dragging: the stop under the pointer at an offset.
  const dragScale: RulerScale = { min: 1, max: 30, step: 1 };
  const yards: RulerScale = { min: 5, max: 300, step: 5 };
  check(
    'the bubble names the stop under the pointer mid-drag',
    stopUnderOffset(0, 26, dragScale) === 1 &&
      stopUnderOffset(26 * 14, 26, dragScale) === 15 &&
      stopUnderOffset(26 * 14 + 12, 26, dragScale) === 15 &&
      stopUnderOffset(26 * 14 + 14, 26, dragScale) === 16 &&
      stopUnderOffset(18 * 44, 18, yards) === 225,
  );
  check(
    'an overscroll bounce never names a stop past either end',
    stopUnderOffset(-80, 26, dragScale) === 1 &&
      stopUnderOffset(26 * 500, 26, dragScale) === rulerHi(dragScale) &&
      stopUnderOffset(Number.NaN, 26, dragScale) === 1,
  );
  const liveScreen = readFileSync(join(import.meta.dirname, '../src/screens/StatsScreen.tsx'), 'utf-8');
  check(
    'the screen previews only a finger drag, and numbers the major ticks',
    liveScreen.includes('onScroll={onLiveScroll}') &&
      liveScreen.includes('if (!fingerRef.current) return;') &&
      liveScreen.includes('fingerRef.current = true;') &&
      liveScreen.includes('faceOf(preview ?? value)') &&
      liveScreen.includes('styles.tickNumber'),
  );
  // The 44pt box used to exist only inside pointInBubble. The gesture view
  // was the 28pt strip, so a tap in that grown box never arrived. The wings
  // are the band past the strip, and they are only as wide as the pill.
  // The overhang math still holds for any strip shorter than 44pt; the
  // resting ruler is now taller than that, so it hangs no wings at all.
  const shortStrip = 28;
  check(
    'a strip shorter than 44pt hangs wings up to 44pt; the resting ruler needs none',
    MARKER_HIT_H === 44 &&
      markerHitOverhang(shortStrip) === 8 &&
      shortStrip + 2 * markerHitOverhang(shortStrip) === MARKER_HIT_H &&
      markerHitOverhang(35) === 4.5 &&
      markerHitOverhang(compactRulerHeight(1)) === 0 &&
      markerHitOverhang(rulerChromeHeight(1)) === 0,
  );
  const shifted = markerBoxInGesture({ x: 40, y: 3, width: 22, height: 22 }, markerHitOverhang(shortStrip));
  check('a tap in the top wing hits the marker', pointInBubble(51, 1, shifted));
  check('a tap in the bottom wing hits the marker', pointInBubble(51, 43, shifted));
  check('a neighbouring tick misses the marker', !pointInBubble(39, 20, shifted));
  check('a point beside the wing misses', !pointInBubble(39, 1, shifted));
  const screen = readFileSync(join(import.meta.dirname, '../src/screens/StatsScreen.tsx'), 'utf-8');
  check(
    'the screen hangs that 44pt box off the short strip, wings only as wide as the marker',
    screen.includes('fieldOpen ? 0 : markerHitOverhang(visualH)') &&
      screen.includes('height: hitH') &&
      screen.includes('width: bubbleFrame.width') &&
      screen.includes('left: bubbleFrame.x') &&
      screen.includes('markerBoxInGesture') &&
      screen.includes('pointerEvents="box-none"'),
  );
  check(
    'the bottom wing does not pull the next row up, and a drag on the wing does not open the field',
    !screen.includes('marginBottom: -rulerChrome.overhang') &&
      screen.includes('THRESHOLD_TAP_MAX_DIST * THRESHOLD_TAP_MAX_DIST') &&
      screen.includes('onResponderRelease={onWingRelease}') &&
      screen.includes('left: bubbleFrame.x') &&
      screen.includes('width: bubbleFrame.width') &&
      screen.includes('draft != null || editingRef.current'),
  );
  check(
    'Filters is a word again, and Teams or an empty board mounts the book line',
    screen.includes('styles.filterBtnText}>Filters</Text>') &&
      screen.includes('showHeaderBookLine') &&
      (screen.match(/<SportsbookIndicator\b/g) ?? []).length >= 3,
  );
}

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
