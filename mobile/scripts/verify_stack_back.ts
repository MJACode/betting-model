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

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

const ROOT = join(import.meta.dirname, '..');
const read = (rel: string) => readFileSync(join(ROOT, rel), 'utf8');

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
  'the navigator still uses the arrow-only system back everywhere else',
  /headerBackButtonDisplayMode:\s*'minimal'/.test(app),
);

const pill = read('src/components/StackBackButton.tsx');
check('the pill is labelled Back', /accessibilityLabel="Back"/.test(pill));
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
