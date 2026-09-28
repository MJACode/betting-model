/**
 * Tap targets and VoiceOver — usability audit PR 4 (H9, M5, M7, M8, M9, M10,
 * M18, M19, M22, M25, M26, L13, and the ~50 unlabelled Pressables).
 *
 *   npx tsx scripts/verify_a11y.ts
 *   node --experimental-strip-types scripts/verify_a11y.ts   (what CI's pytest runs)
 *
 * Only node: imports, plus a dynamic import of the pure src/lib/a11y.ts, so it
 * runs the same under tsx and plain node.
 *
 * Static rules, over every .tsx under src/ plus App.tsx:
 *   1. Every <Pressable> has accessibilityRole AND accessibilityLabel.
 *   2. Every <Pressable> is 44pt tall or has hitSlop: a style (inline or a
 *      styles.X it references) with height/minHeight >= 44, padding or
 *      paddingVertical >= 12, or absoluteFill (a full-screen backdrop).
 *      Where BOTH an explicit height and a numeric hitSlop are known, their
 *      sum must reach 44 — having a hitSlop prop is not enough on its own.
 *   3. A Pressable with accessible={false} is not a VoiceOver element and is
 *      exempt from 1-2, but only as a tap-swallowing sheet (onPress={() => {}})
 *      or with a comment just above it saying why (VoiceOver).
 *   4. A Pressable hidden from VoiceOver (accessibilityElementsHidden +
 *      importantForAccessibility="no-hide-descendants") is exempt from 1 only.
 *   5. Every <TextInput> and <Switch> has accessibilityLabel.
 *   6. M7: every vertical ScrollView / FlatList / SectionList that the betslip
 *      bar can float over — not inside a <Modal>, not horizontal, not on a
 *      route in App.tsx's NO_BETSLIP_BAR_ROUTES — ends with BetslipBarSpacer
 *      (last ScrollView child, or the FlatList's ListFooterComponent).
 * Plus pins for the tab semantics (H9/M8), the audited slop numbers, and the
 * spoken labels (M5/M8/M22/M19/M25), and behavioural checks of lib/a11y.ts.
 *
 * ALLOWLIST: entries only where the rule can't be met without a visible
 * layout change or where a label would make VoiceOver worse; each says why.
 */

import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
let passes = 0;
function check(name: string, ok: boolean, detail?: unknown) {
  if (ok) {
    passes++;
    console.log(`  ✓ ${name}`);
  } else {
    failures++;
    console.log(`  ✗ FAIL ${name}${detail === undefined ? '' : ` — ${typeof detail === 'string' ? detail : JSON.stringify(detail)}`}`);
  }
}

/** file:line-of-<Pressable> → reason. Keyed by a stable snippet, not a line number. */
const ALLOWLIST: { file: string; snippet: RegExp; rule: 'label' | 'size'; reason: string }[] = [
  {
    file: 'src/screens/SettingsScreen.tsx',
    snippet: /style=\{\(\{ pressed \}\) => \[styles\.linkCard/,
    rule: 'label',
    reason:
      'LinkRow: role only, on purpose. An accessibilityLabel REPLACES what VoiceOver reads from the children, and five rows carry live status in `right` (Signed in, Active, connected books, "2 new replies"). Left to the children VoiceOver reads label, status and sub in order.',
  },
  {
    file: 'src/components/CalendarGrid.tsx',
    snippet: /accessibilityLabel=\{spokenDate\(date\)\}/,
    rule: 'size',
    reason:
      'Calendar day: 32pt circle in a 36pt row, 2pt slop. Any more slop steals the neighbouring week’s taps; 44pt needs a taller grid, which is a visible layout change — flagged for Designer.',
  },
];

function walk(d: string, out: string[] = []): string[] {
  for (const n of readdirSync(d)) {
    const p = join(d, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}

/** The full opening tag starting at `start` (a '<'), braces and quotes aware. */
function openTag(src: string, start: number): string {
  let depth = 0;
  let q: string | null = null;
  for (let i = start + 1; i < src.length; i++) {
    const c = src[i];
    if (q) {
      if (c === q && src[i - 1] !== '\\') q = null;
      continue;
    }
    if (depth > 0 && (c === '"' || c === "'" || c === '`')) {
      q = c;
      continue;
    }
    if (depth === 0 && c === '"') {
      q = c;
      continue;
    }
    if (c === '{') depth++;
    else if (c === '}') depth--;
    else if (c === '>' && depth === 0) return src.slice(start, i + 1);
  }
  return src.slice(start);
}

/** Body of `name: { … }` inside the file's StyleSheet.create. */
function styleBlock(src: string, name: string): string {
  const at = src.lastIndexOf('StyleSheet.create');
  if (at < 0) return '';
  const tail = src.slice(at);
  const m = new RegExp(`\\n\\s+${name}: \\{`).exec(tail);
  if (!m) return '';
  const base = at + m.index + m[0].length;
  let d = 1;
  let i = base;
  for (; i < src.length && d > 0; i++) {
    if (src[i] === '{') d++;
    else if (src[i] === '}') d--;
  }
  return src.slice(base, i);
}

const a11ySrc = read('src/lib/a11y.ts');
const ROW_SLOP_PAD = Number(/export const ROW_SLOP_PAD = (\d+);/.exec(a11ySrc)?.[1] ?? NaN);
const SPACING: Record<string, number> = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32 };
function num(v: string): number | null {
  const t = v.trim();
  if (/^\d+(\.\d+)?$/.test(t)) return Number(t);
  const s = /^spacing\.(\w+)(?:\s*\+\s*(\d+))?$/.exec(t);
  if (s && SPACING[s[1]] != null) return SPACING[s[1]] + Number(s[2] ?? 0);
  if (t === 'ROW_SLOP_PAD') return ROW_SLOP_PAD;
  return null;
}

function tallEnough(text: string): boolean {
  if (/StyleSheet\.absoluteFill|absoluteFillObject/.test(text)) return true;
  for (const m of text.matchAll(/\b(minHeight|height|paddingVertical|padding): ([^,\n}]+)/g)) {
    const n = num(m[2]);
    if (n == null) continue;
    if ((m[1] === 'minHeight' || m[1] === 'height') && n >= 44) return true;
    if ((m[1] === 'paddingVertical' || m[1] === 'padding') && n >= 12) return true;
  }
  return false;
}

/** Explicit numeric height of the control, if its style states one. */
function explicitHeight(text: string): number | null {
  const m = /(?:^|[\s{,])height: (\d+)/.exec(text);
  return m ? Number(m[1]) : null;
}

/** Vertical slop (top + bottom) when it's all literal numbers / known constants. */
function verticalSlop(tag: string): number | null {
  const n = /hitSlop=\{(\d+)\}/.exec(tag);
  if (n) return 2 * Number(n[1]);
  const o = /hitSlop=\{\{([^}]*)\}\}/.exec(tag);
  if (!o) return null;
  const top = /top: ([\w.]+)/.exec(o[1]);
  const bottom = /bottom: ([\w.]+)/.exec(o[1]);
  const t = top ? num(top[1]) : 0;
  const b = bottom ? num(bottom[1]) : 0;
  return t == null || b == null ? null : t + b;
}

const files = [...walk(join(ROOT, 'src')), join(ROOT, 'App.tsx')];
const allowHit = new Set<string>();
let pressables = 0;
let exemptSwallow = 0;
let exemptHidden = 0;
const missing: string[] = [];
const small: string[] = [];
const badExempt: string[] = [];

for (const f of files) {
  const rel = relative(ROOT, f);
  const src = readFileSync(f, 'utf-8');
  for (const m of src.matchAll(/<Pressable\b/g)) {
    pressables++;
    const tag = openTag(src, m.index!);
    const line = src.slice(0, m.index).split('\n').length;
    const where = `${rel}:${line}`;
    const allowed = (rule: 'label' | 'size') => {
      const hit = ALLOWLIST.find((a) => a.file === rel && a.rule === rule && a.snippet.test(tag));
      if (hit) allowHit.add(`${hit.file}|${hit.rule}`);
      return Boolean(hit);
    };

    if (/accessible=\{false\}/.test(tag)) {
      const above = src.slice(0, m.index).split('\n').slice(-10).join('\n');
      if (/onPress=\{\(\) => \{\}\}/.test(tag) || /accessible=\{false\}[\s\S]*VoiceOver|VoiceOver[\s\S]*accessible=\{false\}/.test(above)) {
        exemptSwallow++;
      } else {
        badExempt.push(where);
      }
      continue;
    }

    const hidden = /accessibilityElementsHidden/.test(tag) && /importantForAccessibility="no-hide-descendants"/.test(tag);
    if (hidden) exemptHidden++;
    const role = /accessibilityRole=/.test(tag);
    const label = /accessibilityLabel=/.test(tag);
    if (!hidden && (!role || !label) && !allowed('label')) {
      missing.push(`${where}${role ? '' : ' role'}${label ? '' : ' label'}`);
    }

    const refs = [...tag.matchAll(/styles\.(\w+)/g)].map((x) => x[1]);
    const styleText = [tag, ...refs.map((r) => styleBlock(src, r))].join('\n');
    const hasSlop = /hitSlop=/.test(tag);
    let sizeOk = hasSlop || tallEnough(styleText);
    const h = explicitHeight(styleText);
    const vs = verticalSlop(tag);
    if (hasSlop && h != null && h < 44 && vs != null && h + vs < 44) sizeOk = false;
    if (!sizeOk && !allowed('size')) small.push(`${where} [${refs.join(',')}]${h != null ? ` h=${h}+${vs ?? 0}` : ''}`);
  }
}

console.log('\nRules 1–4: Pressables');
check(`every Pressable has accessibilityRole + accessibilityLabel (${missing.length} missing)`, missing.length === 0, missing.join('; '));
check(`every Pressable reaches 44pt by style or hitSlop (${small.length} short)`, small.length === 0, small.join('; '));
check('accessible={false} only on tap-swallowing sheets or with a VoiceOver reason above it', badExempt.length === 0, badExempt.join('; '));
check('every allowlist entry is still needed (no stale entries)', ALLOWLIST.every((a) => allowHit.has(`${a.file}|${a.rule}`)),
  ALLOWLIST.filter((a) => !allowHit.has(`${a.file}|${a.rule}`)).map((a) => a.file));
check('every allowlist entry carries a reason', ALLOWLIST.every((a) => a.reason.length > 40));
check('allowlist stays small (≤ 2 entries)', ALLOWLIST.length <= 2, ALLOWLIST.length);
console.log(`  (${pressables} Pressables; ${exemptSwallow} non-elements via accessible={false}; ${exemptHidden} hidden with an accessible alternative; ${ALLOWLIST.length} allowlisted)`);

console.log('\nRule 5: text inputs and switches');
const unlabelled: string[] = [];
let inputs = 0;
for (const f of files) {
  const src = readFileSync(f, 'utf-8');
  for (const m of src.matchAll(/<(TextInput|Switch)\s/g)) {
    inputs++;
    if (!/accessibilityLabel=/.test(openTag(src, m.index!))) {
      unlabelled.push(`${relative(ROOT, f)}:${src.slice(0, m.index).split('\n').length}`);
    }
  }
}
check(`every TextInput / Switch has accessibilityLabel (${inputs} checked)`, unlabelled.length === 0, unlabelled.join('; '));

console.log('\nRule 6: M7 — the betslip bar never covers the last row');
const app = read('App.tsx');
const noBarRoutes = [...(/NO_BETSLIP_BAR_ROUTES = new Set<string>\(\[([^\]]*)\]\)/.exec(app)?.[1] ?? '').matchAll(/'(\w+)'/g)].map((x) => x[1]);
check('App.tsx: NO_BETSLIP_BAR_ROUTES parsed', noBarRoutes.length > 0, noBarRoutes);
const exemptFiles = new Set<string>();
for (const r of noBarRoutes) {
  const comp = new RegExp(`name="${r}"\\s*\\n?\\s*component=\\{(\\w+)\\}`).exec(app)?.[1];
  const imp = comp ? new RegExp(`import \\{[^}]*\\b${comp}\\b[^}]*\\} from '@/([^']+)'`).exec(app)?.[1] : null;
  if (imp) exemptFiles.add(`src/${imp}.tsx`);
}
check('no-bar routes resolve to screen files', exemptFiles.size === noBarRoutes.length, [...exemptFiles]);

function ranges(src: string, open: RegExp, close: string): [number, number][] {
  const out: [number, number][] = [];
  for (const m of src.matchAll(open)) {
    const end = src.indexOf(close, m.index!);
    out.push([m.index!, end < 0 ? src.length : end]);
  }
  return out;
}
function closeOf(src: string, start: number, tagName: string): number {
  const re = new RegExp(`<${tagName}\\b|</${tagName}>`, 'g');
  re.lastIndex = start;
  let depth = 0;
  for (let m = re.exec(src); m; m = re.exec(src)) {
    if (m[0].startsWith('</')) {
      depth--;
      if (depth === 0) return m.index;
    } else {
      const t = openTag(src, m.index);
      if (!t.endsWith('/>')) depth++;
      else if (depth === 0) return m.index + t.length;
    }
  }
  return src.length;
}
const uncovered: string[] = [];
let covered = 0;
for (const f of files) {
  const rel = relative(ROOT, f);
  if (exemptFiles.has(rel)) continue;
  const src = readFileSync(f, 'utf-8');
  const modals = ranges(src, /<Modal\b/g, '</Modal>');
  for (const m of src.matchAll(/(?<![\w.])<(ScrollView|FlatList|SectionList)\s/g)) {
    if (/(useRef|createRef|RefObject)$/.test(src.slice(Math.max(0, m.index! - 12), m.index))) continue;
    const at = m.index!;
    const tag = openTag(src, at);
    if (/\bhorizontal\b/.test(tag)) continue;
    if (modals.some(([a, b]) => at > a && at < b)) continue;
    const ok =
      m[1] === 'ScrollView'
        ? /<BetslipBarSpacer \/>\s*<\/ScrollView>/.test(src.slice(at, closeOf(src, at, 'ScrollView') + '</ScrollView>'.length))
        : /ListFooterComponent=\{[\s\S]*BetslipBarSpacer/.test(tag);
    if (ok) covered++;
    else uncovered.push(`${rel}:${src.slice(0, at).split('\n').length} ${m[1]}`);
  }
}
check(`every vertical list the bar floats over ends with BetslipBarSpacer (${covered} covered)`, uncovered.length === 0, uncovered.join('; '));
check('at least 20 lists covered (the audit saw the bar over every tab)', covered >= 20, covered);
const bar = read('src/components/BetslipBar.tsx');
check('BetslipBar publishes its measured height (+ float gap) from onLayout',
  /onLayout=\{\(e\) => \{\s*barHeight\.current = e\.nativeEvent\.layout\.height;\s*setBetslipBarInset\(barHeight\.current \+ floatGap\);/.test(bar));
check('BetslipBar publishes 0 when hidden and on unmount',
  /setBetslipBarInset\(visible && barHeight\.current > 0 \? barHeight\.current \+ floatGap : 0\)/.test(bar) && /useEffect\(\(\) => \(\) => setBetslipBarInset\(0\), \[\]\)/.test(bar));
check('BetslipBar: the publish effects run before the early return (hooks order)',
  bar.indexOf('setBetslipBarInset(visible') < bar.indexOf('if (!visible) return null;'));
const spacer = read('src/components/BetslipBarSpacer.tsx');
check('BetslipBarSpacer: height = useBetslipBarInset(), nothing while the bar is hidden',
  /const inset = useBetslipBarInset\(\);/.test(spacer) && /if \(inset <= 0\) return null;/.test(spacer) && /height: inset/.test(spacer));

console.log('\nH9 / M8 / L13 — tabs');
const toggle = read('src/components/SportToggle.tsx');
check('SportToggle: tablist container, tab items with selected', /accessibilityRole="tablist"/.test(toggle) && /accessibilityRole="tab"/.test(toggle) && /accessibilityState=\{\{ selected: active \}\}/.test(toggle) && !/accessibilityRole="button"/.test(toggle));
check('SportToggle: slop is the in-bounds room (10 above, 2 below), no negative-margin frame that would overlap the row below',
  /const TOGGLE_ROOM_ABOVE = spacing\.sm \+ 2;/.test(toggle) && /hitSlop=\{\{ top: TOGGLE_ROOM_ABOVE, bottom: 2, left: 2, right: 2 \}\}/.test(toggle) && !/marginVertical: -/.test(toggle));
const record = read('src/screens/TrackRecordScreen.tsx');
check('TrackRecord sport tabs: tablist + tab + selected + label', /accessibilityRole="tablist"/.test(record) && /accessibilityRole="tab"/.test(record) && /accessibilityState=\{\{ selected: active \}\}/.test(record) && /accessibilityLabel=\{s === 'All' \? 'All sports' : s\}/.test(record));
check('TrackRecord sport tabs: ROW_SLOP_PAD slop inside a framed horizontal ScrollView (L13: one row, no wrap)',
  /hitSlop=\{\{ top: ROW_SLOP_PAD, bottom: ROW_SLOP_PAD/.test(record) && /marginTop: -ROW_SLOP_PAD/.test(record) && /paddingVertical: ROW_SLOP_PAD/.test(record) && !/sportTabs: \{[^}]*flexWrap/.test(record));
const home = read('src/screens/PicksHomeScreen.tsx');
check('PicksHome sub-tabs: tablist + tab + selected', /<View style=\{styles\.subTabs\} accessibilityRole="tablist">/.test(home) && /hitSlop=\{\{ top: 8, bottom: 8 \}\}\s*accessibilityRole="tab"\s*accessibilityState=\{\{ selected: active \}\}/.test(home));
check('PicksHome sub-tabs: no negative-margin frame (it overlapped the sport chips above)', !/subTabsFrame/.test(home));
const models = read('src/screens/ModelsScreen.tsx');
check('Models segment: tablist + tab + 9pt slop on a ~27pt pill', /<View style=\{styles\.segmentRow\} accessibilityRole="tablist">/.test(models) && /hitSlop=\{\{ top: 9, bottom: 9/.test(models) && /accessibilityRole="tab"/.test(models));
const groupTabs = read('src/components/GroupTabs.tsx');
check('GroupTabs: tablist + tab + label', /accessibilityRole="tablist"/.test(groupTabs) && /accessibilityRole="tab"/.test(groupTabs) && /accessibilityLabel=\{item\}/.test(groupTabs));

console.log('\nM8 / M5 / M22 — spoken card');
const card = read('src/components/PickCard.tsx');
check('PickCard label carries game status + time (gameStatusSpeech)', /gameStatusSpeech\(gameStatus\(game, liveState\), gameDayLabelET\(game\?\.commence_time\)\)/.test(card));
check('PickCard label carries the stake, in words', /stakeCaption \? `Stake \$\{unitsSpeech\(stakeCaption\)\}` : null/.test(card));
check('PickCard label carries when it posted and the started line', /timing \? timing\.label : null/.test(card) && /startedSpoken,/.test(card));
check('PickCard: Track / Betslip / book offered as accessibilityActions', /accessibilityActions=\{a11yActions\.length > 0 \? a11yActions : undefined\}/.test(card) && /name === 'track' && canTrack/.test(card) && /name === 'slip' && canSlip/.test(card) && /name === 'book' && handoff/.test(card));
check('PickCard: "Game started" line speaks gameStartedSpeech (full book name)', /accessibilityLabel=\{startedSpoken \?\? startedText\}/.test(card) && /gameStartedSpeech\(decisionOdds\(pick\), bookName\(storedQuoteBook\(pick\)\)\)/.test(card));
check('PickCard: "Price check" chip says what it means', /accessibilityLabel="Price check: this price looks off, so edge and EV are hidden"/.test(card));
check('SharpScorePill: "Sharp score N of 100, band" (M5)', /accessibilityLabel=\{sharpScoreSpeech\(score, BAND_WORD\[band\]\)\}/.test(read('src/components/SharpScorePill.tsx')));
const pill = read('src/components/GameStatusPill.tsx');
check('GameStatusPill: live and final speak gameStatusSpeech (M22)', (pill.match(/accessibilityLabel=\{spoken \?\? '(Live|Final)'\}/g) ?? []).length === 2 && /accessibilityLabel=\{spoken \?\? undefined\}/.test(pill));

console.log('\nM9 / M10 / M18 / M19 / M25 / M26');
const perf = read('src/screens/PerformanceScreen.tsx');
check('M10: stake chip 12pt slop (was 6) + role + label', /hitSlop=\{\{ top: 12, bottom: 12, left: 8, right: 8 \}\}\s*accessibilityRole="button"\s*accessibilityLabel=\{`Edit stake, /.test(perf));
check('M10: stake pills are radios with checked state + 8pt slop', /accessibilityRole="radiogroup"/.test(perf) && /hitSlop=\{\{ top: 8, bottom: 8, left: 2, right: 2 \}\}\s*accessibilityRole="radio"\s*accessibilityState=\{\{ checked: active, selected: active \}\}/.test(perf));
check('M10: StakeEditModal buttons labelled, 12pt slop, tap outside closes', /accessibilityLabel="Reset to \$100"/.test(perf) && /accessibilityLabel="Save stake"/.test(perf) && /<View style=\{styles\.stakeModalBackdrop\}>\s*\{\/\*[\s\S]*?\*\/\}\s*<Pressable\s*style=\{StyleSheet\.absoluteFill\}\s*onPress=\{onClose\}/.test(perf));
check('M10: tracked rows offer Untrack / Edit stake as accessibilityActions (Undo toast is PR 5)', /\{ name: 'untrack', label: 'Untrack' \}/.test(perf) && /actionName === 'untrack'\) onRowLongPress\(row\)/.test(perf));
const tip = read('src/components/InfoTooltip.tsx');
check('M18: InfoTooltip icon slop 12 (20 + 24 = 44)', /hitSlop=\{12\}\s*accessibilityRole="button"/.test(tip));
const onboarding = read('src/components/OnboardingModal.tsx');
check('M19: Skip and Next have roles; dots read "Page N of 4"', /accessibilityLabel="Skip intro"/.test(onboarding) && /accessibilityLabel=\{pageLabel\(step, SLIDES\.length\)\}/.test(onboarding) && /accessibilityLabel=\{last \? 'Get started'/.test(onboarding));
const manual = read('src/components/ManualBetModal.tsx');
check('M25: disabled "Add bet" explains why (accessibilityHint)', /accessibilityHint=\{addHint\}/.test(manual) && /`Enter \$\{missing\.join\(' and '\)\} to add this bet\.`/.test(manual) && /accessibilityState=\{\{ disabled: !valid \}\}/.test(manual));
const settings = read('src/screens/SettingsScreen.tsx');
check('M9: helpline row reaches 44 (slop below the divider)', /hitSlop=\{\{ top: 0, bottom: 12, left: 0, right: 0 \}\}/.test(settings));
check('M26: Settings Sign out is minHeight 44', /signOutBtn: \{[^}]*minHeight: 44/.test(settings));
check('Sheets: the tap-outside backdrop is a sibling, never the sheet’s parent',
  ['AddLineSheet', 'HitModeSheet', 'StatGroupSheet', 'PlayerNewsSheet', 'StatePickerSheet', 'ParlayDkHandoff', 'SportsbookPickerSheet', 'InfoTooltip', 'filters/FilterSheet'].every((n) => {
    const s = read(`src/components/${n}.tsx`);
    return /<View style=\{styles\.backdrop\}>/.test(s) && !/<Pressable\s+style=\{styles\.backdrop\}/.test(s);
  }));

console.log('\nlib/a11y.ts (behaviour)');
check('lib/a11y.ts has no imports (pure; loads under plain node)', !/^import /m.test(a11ySrc));

async function behaviour() {
  const a = await import(pathToFileURL(join(ROOT, 'src/lib/a11y.ts')).href);
  check('slopFor(23) → 11/11 (45pt)', JSON.stringify(a.slopFor(23)) === JSON.stringify({ top: 11, bottom: 11, left: 0, right: 0 }), a.slopFor(23));
  check('slopFor(20, 20) → 12 all round', JSON.stringify(a.slopFor(20, 20)) === JSON.stringify({ top: 12, bottom: 12, left: 12, right: 12 }));
  check('slopFor(50) → no slop', JSON.stringify(a.slopFor(50)) === JSON.stringify({ top: 0, bottom: 0, left: 0, right: 0 }));
  check('targetSize(23, 60, ROW_SLOP_PAD frame) ≥ 44', a.targetSize(23, 60, { top: a.ROW_SLOP_PAD, bottom: a.ROW_SLOP_PAD }).height >= a.MIN_TAP);
  check('targetSize(20, 20, 12) = 44 × 44', JSON.stringify(a.targetSize(20, 20, 12)) === JSON.stringify({ height: 44, width: 44 }));
  check('gameStatusSpeech live → "Live, bottom 9th, 2 outs, 3 to 2"',
    a.gameStatusSpeech({ kind: 'live', awayScore: 3, homeScore: 2, inning: 9, inningHalf: 'bottom', outs: 2 }) === 'Live, bottom 9th, 2 outs, 3 to 2');
  check('gameStatusSpeech live, 1 out, top 11th', a.gameStatusSpeech({ kind: 'live', awayScore: 0, homeScore: 0, inning: 11, inningHalf: 'top', outs: 1 }) === 'Live, top 11th, 1 out, 0 to 0');
  check('gameStatusSpeech live, no feed detail → "Live"', a.gameStatusSpeech({ kind: 'live', awayScore: null, homeScore: null, inning: null, inningHalf: null, outs: null }) === 'Live');
  check('gameStatusSpeech final → "Final, 5 to 3"', a.gameStatusSpeech({ kind: 'final', awayScore: 5, homeScore: 3 }) === 'Final, 5 to 3');
  check('gameStatusSpeech pre with day → "Starts Sat 6/14, 10:00 PM ET"', a.gameStatusSpeech({ kind: 'pre', timeLabel: '10:00 PM ET' }, 'Sat 6/14') === 'Starts Sat 6/14, 10:00 PM ET');
  check('gameStatusSpeech pre, no time / ended → null', a.gameStatusSpeech({ kind: 'pre', timeLabel: '' }) === null && a.gameStatusSpeech({ kind: 'ended' }) === null);
  check('unitsSpeech("1.2u → 1.0u") → "1.2 units to win 1.0 units"', a.unitsSpeech('1.2u → 1.0u') === '1.2 units to win 1.0 units', a.unitsSpeech('1.2u → 1.0u'));
  check('sharpScoreSpeech(78, "high")', a.sharpScoreSpeech(78, 'high') === 'Sharp score 78 of 100, high');
  check('pageLabel(1, 4) → "Page 2 of 4"', a.pageLabel(1, 4) === 'Page 2 of 4');
  check('spokenDate("2026-09-28") → "September 28, 2026"', a.spokenDate('2026-09-28') === 'September 28, 2026');
  check('joinLabel drops empties', a.joinLabel(['MLB', null, '', false, '2 signals']) === 'MLB, 2 signals');
}

behaviour()
  .catch((e) => check('lib/a11y.ts behaviour ran', false, String(e)))
  .finally(() => {
    console.log(failures ? `\n${failures} FAILED (${passes} passed)` : `\nALL PASS (${passes} checks)`);
    process.exit(failures ? 1 : 0);
  });
