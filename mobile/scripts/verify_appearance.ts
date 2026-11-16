/**
 * Appearance — System / Light / Dark (Matt, 2026-11-16).
 *
 *   npx tsx scripts/verify_appearance.ts
 *
 * Pins the pure rules in src/lib/appearance.ts, and the wiring that makes a
 * choice reach theme.ts before any StyleSheet is built:
 *   - default Light (opt in), unknown stored values fall back to it;
 *   - System follows the phone, an unknown phone answer is light;
 *   - the footnote / tile line say "reopen" only while a switch is pending;
 *   - the entry reads the key and boots the scheme BEFORE requiring App, and
 *     imports nothing that loads theme.ts at the top;
 *   - theme.ts picks its palette from bootScheme();
 *   - no reloadAsync anywhere (lib/otaUpdate.ts, the 2026-10-19 crash).
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join } from 'node:path';

import {
  APPEARANCE_DEFAULT,
  APPEARANCE_OPTIONS,
  APPEARANCE_STORAGE_KEY,
  appearanceFootnote,
  appearanceTileSummary,
  bootPref,
  bootScheme,
  parseAppearancePref,
  resolveScheme,
  setBootAppearance,
} from '../src/lib/appearance';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8').replace(/\r\n/g, '\n');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

check('default is Light (opt in)', APPEARANCE_DEFAULT === 'light');
check('three options, System first', APPEARANCE_OPTIONS.map((o) => o.label).join(',') === 'System,Light,Dark');
check('stored values parse', parseAppearancePref('dark') === 'dark' && parseAppearancePref('system') === 'system');
check('missing / junk falls back to Light', parseAppearancePref(null) === 'light' && parseAppearancePref('Dark') === 'light');
check('System follows the phone', resolveScheme('system', 'dark') === 'dark' && resolveScheme('system', 'light') === 'light');
check('System with no phone answer is light', resolveScheme('system', null) === 'light');
check('explicit choice ignores the phone', resolveScheme('light', 'dark') === 'light' && resolveScheme('dark', 'light') === 'dark');

check('no boot: light', bootScheme() === 'light' && bootPref() === 'light');
setBootAppearance('dark', 'dark');
check('boot sets the running scheme', bootScheme() === 'dark' && bootPref() === 'dark');

check('pending switch says reopen', appearanceFootnote('dark', 'light', 'light') === 'Close and reopen Signalbase to switch to Dark.');
check('pending switch back to light', appearanceFootnote('light', 'dark', 'dark') === 'Close and reopen Signalbase to switch to Light.');
check('no pending switch: when it applies', appearanceFootnote('system', 'dark', 'dark') === 'A change applies the next time you open Signalbase.');
check('tile: plain label when nothing pending', appearanceTileSummary('dark', 'dark', 'light') === 'Dark');
check('tile: reopen while pending', appearanceTileSummary('system', 'light', 'dark') === 'System · reopen to apply');

const entry = read('index.tsx');
const pkg = JSON.parse(read('package.json')) as { main: string };
check('package.json main is index.tsx', pkg.main === 'index.tsx', pkg.main);
check('entry reads the appearance key', /AsyncStorage\.getItem\(APPEARANCE_STORAGE_KEY\)/.test(entry) && APPEARANCE_STORAGE_KEY === 'appearance.v1');
const bootAt = entry.indexOf('setBootAppearance(pref, scheme)');
const requireAt = entry.indexOf("require('./App')");
check('scheme is set BEFORE App is required', bootAt > 0 && requireAt > bootAt);
const topImports = entry.match(/^import [\s\S]*? from '([^']+)';/gm) ?? [];
check(
  'entry imports nothing that loads theme.ts at the top',
  topImports.every((l) => !/\.\/App'|@\/|lib\/theme|screens|components/.test(l)),
  topImports.join(' | '),
);
check('entry has a timeout so the app always opens', /setTimeout\(\(\) => start\(null\), BOOT_TIMEOUT_MS\)/.test(entry));

const theme = read('src/lib/theme.ts');
check('theme picks its palette from the boot scheme', /export const isDark = bootScheme\(\) === 'dark';/.test(theme) && /export const colors = isDark \? darkColors : lightColors;/.test(theme));
const app = read('App.tsx');
check('navigation theme follows the scheme', /const NAV_BASE = isDark \? DarkTheme : DefaultTheme;/.test(app));
check('status bar follows the scheme', /<StatusBar style=\{isDark \? 'light' : 'dark'\} \/>/.test(app));

const settings = read('src/screens/SettingsScreen.tsx');
check('Settings has the Appearance drill-in', /case 'appearance':\n\s*return <AppearanceSection \/>;/.test(settings));
check('options are radios with selected state', /accessibilityRole="radio"/.test(settings) && /accessibilityState=\{\{ selected, checked: selected \}\}/.test(settings));

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(name)) out.push(p);
  }
  return out;
}
const reloaders = [...walk(join(ROOT, 'src')), join(ROOT, 'index.tsx'), join(ROOT, 'App.tsx')].filter((f) =>
  /reloadAsync\s*\(|DevSettings\.reload/.test(readFileSync(f, 'utf-8').replace(/\/\/.*$|\/\*[\s\S]*?\*\//gm, '')),
);
check('nothing reloads the JS runtime to apply a theme', reloaders.length === 0, reloaders.join(', '));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
