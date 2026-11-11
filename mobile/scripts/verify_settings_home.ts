/**
 * Settings home is the Option B grid. Drill-ins keep the controls.
 *
 *   node --experimental-strip-types scripts/verify_settings_home.ts
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
function eq(name: string, actual: unknown, expected: unknown): void {
  check(name, actual === expected, `got ${JSON.stringify(actual)}`);
}

const home = await import(pathToFileURL(join(ROOT, 'src/lib/settingsHome.ts')).href);

eq(
  'four books and a state fit a half-width tile',
  home.sportsbooksTileSummary(['DK', 'FD', 'MGM', 'CZR'], 'New York'),
  'DK, FD +2 · New York',
);
eq('one book names itself', home.sportsbooksTileSummary(['DK'], 'New York'), 'DK · New York');
eq(
  'a missing state says so',
  home.sportsbooksTileSummary(['DK', 'FD'], null),
  'DK, FD · Not set',
);
eq(
  'a saved bankroll is amount then unit',
  home.bankrollTileSummary('$2,500', '1u = $25'),
  '$2,500 · 1u = $25',
);
eq(
  'no bankroll does not invent dollars',
  home.bankrollTileSummary(null, '1u = 1%'),
  'Not set · 1u = 1%',
);
eq(
  'notifications on and registered',
  home.notificationsTileSummary(true, 'registered', true),
  'Signals on · registered',
);
eq('notifications off', home.notificationsTileSummary(false, 'registered', true), 'Signals off');
eq(
  'notifications on but not registered',
  home.notificationsTileSummary(true, 'failed', true),
  'Signals on · not registered',
);
eq(
  'notifications still registering',
  home.notificationsTileSummary(true, 'registering', true),
  'Signals on · registering',
);
eq(
  'notifications do not claim off before storage answers',
  home.notificationsTileSummary(false, 'idle', false),
  'Checking this device',
);
eq('explore summary', home.EXPLORE_TILE_SUMMARY, 'Record, Live Signals, intro');
eq('legal summary', home.LEGAL_TILE_SUMMARY, 'Help line · Terms · Privacy');
eq('community with discord', home.communityTileSummary(true, 0), 'X · Feedback · Discord');
eq('community without discord', home.communityTileSummary(false, 0), 'X · Feedback');
eq('community unread replaces the static list', home.communityTileSummary(true, 2), 'X · 2 new replies');
eq('community one reply', home.communityTileSummary(false, 1), 'X · 1 new reply');
eq(
  'account names the email and the plan',
  home.accountTileSummary(true, 'jamie@icloud.com', 'Premium'),
  'jamie@icloud.com · Premium',
);
eq('account signed out', home.accountTileSummary(false, null, null), 'Not signed in');
eq('account signed in without an email', home.accountTileSummary(true, null, 'Free'), 'Signed in · Free');
eq(
  'a long email keeps the plan on the tile',
  home.accountTileSummary(true, 'verylongname@icloud.com', 'Premium', true),
  'verylong…@icloud.com · Premium',
);
eq(
  'voiceover still gets the full address',
  home.accountTileSummary(true, 'verylongname@icloud.com', 'Premium'),
  'verylongname@icloud.com · Premium',
);

const homeSrc = read('src/lib/settingsHome.ts');
check(
  'notification summaries do not name a sport',
  !/sport/i.test(homeSrc.replace(/sportsbooks/gi, '')),
);
check(
  'grid order then legal',
  home.SETTINGS_GRID_SECTIONS.join(',') ===
    'sportsbooks,bankroll,notifications,explore,community,account' &&
    home.SETTINGS_LEGAL_SECTION === 'legal',
);
check('titles match the approved board', home.SETTINGS_SECTION_TITLE.notifications === 'Notifications');
check('legal title', home.SETTINGS_SECTION_TITLE.legal === 'Legal & support');

const settings = read('src/screens/SettingsScreen.tsx');
const homeFn = settings.split('export function SettingsScreen(')[1]?.split('export function SettingsSectionScreen')[0] ?? '';
check('home pushes a section', homeFn.includes("navigate('SettingsSection'"));
check('legal tile is the full-width one', homeFn.includes('wide'));
check('account tile follows the existing flag', /id !== 'account' \|\| showAccountSection/.test(homeFn));
check('bankroll control stays off the home', !homeFn.includes('<BankrollCard'));
check('notification control stays off the home', !homeFn.includes('<NotificationsCard'));
check('terms opens the existing terms url', settings.includes("openLink(TERMS_URL, 'Terms of Use')"));
check('privacy opens the existing privacy url', settings.includes("openLink(PRIVACY_URL, 'Privacy Policy')"));
check('helpline stays on the legal drill-in', /function LegalSection\(\)[\s\S]*?openHelpline/.test(settings));
check('explore still opens the live segment', /view:\s*'live'/.test(settings));
check('replay intro keeps the refresh icon', settings.includes('icon="refresh-outline"'));
check(
  'show account is still auth or billing',
  settings.includes('const showAccountSection = AUTH_ENABLED || billingReady()'),
);

const app = read('App.tsx');
check('Settings home keeps the system header', /name="Settings"\s*\n\s*component=\{SettingsScreen\}/.test(app));
check(
  'section screens hide the system back button',
  /name="SettingsSection"[\s\S]*?headerBackVisible:\s*false/.test(app),
);
check(
  'section screens use the shared Back pill',
  /name="SettingsSection"[\s\S]*?<SettingsSectionBackButton\s*\/>/.test(app),
);
check(
  'section titles use the settings header title',
  /name="SettingsSection"[\s\S]*?<SettingsSectionHeaderTitle/.test(app),
);

const pill = read('src/components/StackBackButton.tsx');
check('settings and player stats share the pill', (pill.match(/<BackPill /g) ?? []).length === 2);
check('an empty settings stack replaces to Settings', /navigation\.replace\('Settings'\)/.test(pill));
check(
  'an empty player stack still replaces to the Stats tab',
  /navigation\.replace\(PLAYER_DETAIL_PARENT\.name/.test(pill),
);

const back = await import(pathToFileURL(join(ROOT, 'src/lib/stackBack.ts')).href);
check(
  'a settings title is wider than the player-name cap',
  back.settingsTitleMaxWidth(390, 1) > back.playerTitleMaxWidth(390, 1),
);
check('Legal & support fits at 390pt', back.settingsTitleMaxWidth(390, 1) >= 180);

const paywall = read('src/screens/PaywallScreen.tsx');
check('paywall still says 8 sports', paywall.includes('all 8 sports') && !paywall.includes('all 7 sports'));

if (failures === 0) console.log('ALL PASS');
else {
  console.log(`${failures} FAILED`);
  process.exit(1);
}
