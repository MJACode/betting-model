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
const read = (rel: string) => readFileSync(join(ROOT, rel), 'utf8');
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
check('the pill is at least 44pt wide and tall', /minWidth:\s*44/.test(pill) && /minHeight:\s*44/.test(pill));
check(
  'the pill has hitSlop inside the bar, not down into the player name',
  /hitSlop=\{\{\s*top:\s*12,\s*bottom:\s*0/.test(pill),
);
check(
  'the label stays one line and caps at 2×',
  /numberOfLines=\{1\}/.test(pill) && /maxFontSizeMultiplier=\{2\}/.test(pill),
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
check(
  'a 390pt window at 1× leaves the name short of the pill',
  back.playerTitleMaxWidth(390, 1) === 162,
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
