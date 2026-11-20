/**
 * Back on the player / prop detail screen.
 *
 *   node --experimental-strip-types scripts/verify_stack_back.ts
 *
 * The system "< Back" pill is UIKit. On iOS 27 it stops popping after a
 * modal, and a tap on it may never reach JS. The replacement is a React
 * pill with a fallback when the stack is empty, laid out under the status
 * bar, with a 44pt target above any title overlay. Hidden modals must not
 * keep taking taps.
 */

import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
// LF, whatever the checkout: git on Windows (core.autocrlf) writes CRLF, and
// the patterns below end a function on a newline, a brace, a newline. The
// repo itself stores LF.
const read = (rel: string) => readFileSync(join(ROOT, rel), 'utf8').replace(/\r\n/g, '\n');
const listTsx = (dir: string): string[] =>
  readdirSync(join(ROOT, dir), { recursive: true, encoding: 'utf8' })
    .filter((f) => f.endsWith('.tsx'))
    .map((f) => join(dir, f));

let failures = 0;
function check(name: string, ok: boolean, detail = ''): void {
  if (ok) console.log(`[PASS] ${name}`);
  else {
    failures += 1;
    console.log(`[FAIL] ${name} ${detail}`);
  }
}

function code(text: string): string {
  return text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

const back = await import(pathToFileURL(join(ROOT, 'src/lib/stackBack.ts')).href);

check('a stack with history pops', back.stackBackDecision(true) === 'pop');
check('an empty stack replaces', back.stackBackDecision(false) === 'replace');
check(
  'the empty-stack parent is the Stats tab (the player list)',
  back.PLAYER_DETAIL_PARENT.name === 'Tabs' && back.PLAYER_DETAIL_PARENT.screen === 'Stats',
);

const app = code(read('App.tsx'));
const screen = /<Stack\.Screen\s+name="PlayerStats"[\s\S]*?options=\{\{([\s\S]*?)\}\}/.exec(app);
check('PlayerStats screen options are present', screen != null);
const opts = screen?.[1] ?? '';
check('PlayerStats keeps its header', /headerShown:\s*true/.test(opts));
check('PlayerStats header is not transparent', /headerTransparent:\s*false/.test(opts));
check('PlayerStats hides the system back button', /headerBackVisible:\s*false/.test(opts));
check('PlayerStats edge swipe-back is on', /gestureEnabled:\s*true/.test(opts));
check(
  'PlayerStats full-screen swipe stays off (horizontal chip rows)',
  /fullScreenGestureEnabled:\s*false/.test(opts),
);
check('PlayerStats uses the JS back pill', /headerLeft:\s*\(\)\s*=>\s*<PlayerStatsBackButton\s*\/>/.test(opts));
check(
  'minimal mode stays set for any screen that turns the system back on',
  /headerBackButtonDisplayMode:\s*'minimal'/.test(app),
);

const pill = read('src/components/StackBackButton.tsx');
check('the pill is labelled Back', /accessibilityLabel="Back"/.test(pill));
const titleStyle = /title:\s*\{([^}]+)\}/.exec(pill)?.[1] ?? '';
check(
  'the player name is textPrimary, not the header tint',
  /color:\s*colors\.textPrimary/.test(titleStyle) && !/color:\s*tintColor/.test(code(pill)),
);
// 2026-11-17: 36pt, not 44. On iOS 26+ UIKit fits a header view into 36pt and
// react-native-screens 4.16 leaves our content at its top, so a 44pt square
// drew the chevron 4pt low in its glass bubble (stackBack.HEADER_ITEM_HEIGHT).
check('header items are 36pt tall', back.HEADER_ITEM_HEIGHT === 36);
check(
  'the pill is a 36pt square, not a 44pt one',
  /width:\s*HEADER_ITEM_HEIGHT/.test(pill) && /height:\s*HEADER_ITEM_HEIGHT/.test(pill) && !/min(Width|Height):\s*44/.test(pill),
);
check(
  'the chevron is a fixed 22pt with the Large Content Viewer, not scaled past the 36pt square',
  back.BACK_CHEVRON_SIZE === 22 &&
    /size=\{BACK_CHEVRON_SIZE\}/.test(pill) &&
    /accessibilityShowsLargeContentViewer/.test(pill),
);
for (const screen of ['src/screens/ByomBuilderScreen.tsx', 'src/screens/ByomDetailScreen.tsx']) {
  const src = read(screen);
  const btn = /headerBtn:\s*\{([^}]+)\}/.exec(src)?.[1] ?? '';
  check(`${screen}: its header button is 36pt tall`, /height:\s*HEADER_ITEM_HEIGHT/.test(btn) && !/minHeight:\s*44/.test(btn));
  check(`${screen}: its header button declares a 4pt vertical hitSlop`, /hitSlop=\{\{\s*top:\s*4,\s*bottom:\s*4\s*\}\}/.test(src));
  check(
    `${screen}: its label stops growing at accessibility Medium, so it fits the 36pt item`,
    /maxFontSizeMultiplier=\{HEADER_TEXT_MAX_FONT_MULTIPLIER\}/.test(src) &&
      /accessibilityShowsLargeContentViewer/.test(src) &&
      back.HEADER_TEXT_MAX_FONT_MULTIPLIER < 2.143,
  );
}
check(
  'the pill declares hitSlop (≈52pt wide, bar-height tall once forwarded), not down into the player name',
  /hitSlop=\{\{\s*top:\s*12,\s*bottom:\s*4,\s*left:\s*8,\s*right:\s*8/.test(pill),
);
// 2026-11-16 (Matt): chevron only. iOS 26+ draws a glass bubble behind the
// left slot; with the word "Back" in it the bubble hugged the text and read
// as a cramped grey pill. A centered square makes it a circle.
const pillFn = code(/function BackPill[\s\S]*?\n}\n/.exec(pill)?.[0] ?? '');
check('the Back button function is present', pillFn.length > 0);
check('the Back button draws a chevron', /name="chevron-back"/.test(pillFn));
check('the Back button draws no "Back" word (chevron only)', !/<Text\b/.test(pillFn));
const pillStyle = /pill:\s*\{([^}]+)\}/.exec(pill)?.[1] ?? '';
check(
  'the chevron is centered in its square (the iOS bubble becomes a circle)',
  /alignItems:\s*'center'/.test(pillStyle) && /justifyContent:\s*'center'/.test(pillStyle),
);
check('the pill sits above an overlapping title', /zIndex:\s*20/.test(pill) && /elevation:\s*20/.test(pill));
check(
  'the pill pops, and replaces the Stats tab when it cannot',
  /stackBackDecision\(navigation\.canGoBack\(\)\)/.test(pill) &&
    /navigation\.goBack\(\)/.test(pill) &&
    /navigation\.replace\(PLAYER_DETAIL_PARENT\.name/.test(pill),
);

// 2026-11-15: UIKit's arrow-only Back went dead on Pick Detail (opened from a
// push). Every pushed screen now draws the React pill by default.
const nav = /<Stack\.Navigator\b[\s\S]*?screenOptions=\{\{([\s\S]*?)\}\}/.exec(app)?.[1] ?? '';
check('every pushed screen hides the system back button', /headerBackVisible:\s*false/.test(nav));
check(
  'every pushed screen draws the JS back pill',
  /headerLeft:\s*\(\)\s*=>\s*<StackBackButton\s*\/>/.test(nav),
);
check(
  'the default pill pops, and resets to the tabs when it cannot',
  /export function StackBackButton\(\)[\s\S]*?stackBackDecision\(navigation\.canGoBack\(\)\)[\s\S]*?navigation\.goBack\(\)[\s\S]*?navigation\.reset\(\{\s*index:\s*0,\s*routes:\s*\[\{\s*name:\s*'Tabs'\s*\}\]/.test(
    pill,
  ),
);
check(
  'the Back tap is logged before it navigates (a hung pop still leaves the crumb)',
  /const path = decide\(\);\s*noteBack\(path\);\s*go\(path\);/.test(code(pill)),
);
// No screen turns UIKit's Back back on: headerBackVisible true (or a
// variable) beside a headerLeft draws two Backs, and brings the dead one back.
const offenders: string[] = [];
for (const rel of ['App.tsx', ...listTsx('src')]) {
  const src = code(read(rel));
  for (const m of src.matchAll(/headerBackVisible:\s*([^,}\n]+)/g)) {
    if (m[1].trim() !== 'false') offenders.push(`${rel}: ${m[0].trim()}`);
  }
}
check('no screen turns the system back button back on', offenders.length === 0, offenders.join('; '));

check(
  'the safe-area provider is seeded so the header inset is not 0 on the first frame',
  /initialMetrics=\{initialWindowMetrics\}/.test(app),
);

const player = code(read('src/screens/PlayerStatsScreen.tsx'));
check(
  'the player name is a single truncating header title',
  /headerTitle: \(props\) => <PlayerStatsHeaderTitle \{\.\.\.props\} \/>/.test(player),
);
check('the Back button reserves 44pt at 1× and 2×', back.backButtonWidth(1) === 44 && back.backButtonWidth(2) === 44);
check(
  'a 390pt window at 1× leaves the name short of the button (390 − 2 × (16 + 44 + 8))',
  back.playerTitleMaxWidth(390, 1) === 254,
);
check(
  'a Settings section title gets the same room as the player name',
  back.settingsTitleMaxWidth(390, 1) === 254,
);
check(
  'font scale above 2 does not widen the reserved pill',
  back.playerTitleMaxWidth(390, 3) === back.playerTitleMaxWidth(390, 2),
);
check('the title never collapses below 80pt', back.playerTitleMaxWidth(200, 2) === 80);

const modal = code(read('src/components/TrackedModal.tsx'));
check(
  'a hidden modal does not take touches',
  /pointerEvents=\{visible \? 'box-none' : 'none'\}/.test(modal),
);

if (failures === 0) console.log('ALL PASS');
else {
  console.log(`${failures} FAILED`);
  process.exit(1);
}
