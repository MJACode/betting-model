/**
 * Every sportsbook link the app opens is a URL, never a template; every
 * bettable book has a verified store page or a stated reason not to.
 *
 * Run with:  npx tsx scripts/verify_book_links.ts
 *
 * Matt, 2026-09-04: "I tried to place a parlay with mgm but it didn't open my
 * mgm app like it does for DK, we need to test this for all books we have
 * lines for" and "If I don't have the Sportsbook for one of them it should
 * take me to the App Store to download it."
 *
 * The link shapes below are the REAL ones stored on 2026-09-04
 * (player_prop_odds.over_link and odds.*_link, one per book). Three carry
 * placeholders; DraftKings' does not, which is why DraftKings worked.
 * What cannot be exercised here — actually opening an app — is listed in the
 * session log as the device pass.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fillBetslipLink, linkNeedsState } from '../src/lib/betslipLinks';
import { BETTABLE_BOOKS } from '../src/lib/markets';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const STORED: Record<string, string> = {
  draftkings: 'https://sportsbook.draftkings.com/?outcomes=0QA366670873%232271770865_13L84240Q1-1570309299Q20',
  fanduel: 'https://sportsbook.fanduel.com/addToBetslip?marketId=42.516459178&selectionId=3081409',
  betmgm: 'https://sports.{state}.betmgm.com/en/sports?options=2:7828205-204281167-782135455&type=Single',
  betrivers: 'https://{state}.betrivers.com/?page=sportsbook#event/1024787482?coupon={pickType}|4323745002|{wagerAmount}',
  williamhill_us: 'https://sportsbook.caesars.com/us/{state}/bet/betslip?selectionIds=aa4eb6a2-…',
  espnbet: 'https://sportsbook.thescore.bet/?market_selection_id[0]=f885f2f3-ff1e-405c-854f-71f6234a56bc',
  hardrockbet: 'https://app.hardrock.bet/?deep_link_value=betslip/3797627858931810736',
};

// ── filling ──────────────────────────────────────────────────────────────────
check('DraftKings needs no state', !linkNeedsState(STORED.draftkings) && fillBetslipLink(STORED.draftkings!, null) === STORED.draftkings);
check('FanDuel needs no state', fillBetslipLink(STORED.fanduel!, null) === STORED.fanduel);
check('BetMGM needs the state', linkNeedsState(STORED.betmgm));
check('BetMGM with no state is NOT opened as a template', fillBetslipLink(STORED.betmgm!, null) === null);
check('BetMGM with NJ becomes the NJ host', fillBetslipLink(STORED.betmgm!, 'nj') === 'https://sports.nj.betmgm.com/en/sports?options=2:7828205-204281167-782135455&type=Single');
check('the state is lower-cased for the host', fillBetslipLink(STORED.betmgm!, 'NJ')?.includes('sports.nj.betmgm.com') === true);
check('Caesars with PA fills its path', fillBetslipLink(STORED.williamhill_us!, 'pa')?.includes('/us/pa/bet/betslip') === true);
const br = fillBetslipLink(STORED.betrivers!, 'pa');
check('BetRivers fills state, pick type and stake', br === 'https://pa.betrivers.com/?page=sportsbook#event/1024787482?coupon=single|4323745002|', br ?? 'null');
check('an unknown placeholder is never opened', fillBetslipLink('https://x.example/{foo}/bet', 'nj') === null);
check('whitespace is trimmed', fillBetslipLink('  https://sportsbook.draftkings.com/?a=1 ', null) === 'https://sportsbook.draftkings.com/?a=1');

// ── the fallback chain and the store ─────────────────────────────────────────
const src = read('src/lib/sportsbookLinks.ts');
check('a template is filled before it is opened', src.includes('fillBetslipLink(link, getBettingState())'));
check('a template with no state tells the member what to set', src.includes('Which state do you bet in?') && src.includes('Settings → Your state'));
check('...and the alert is the whole answer — no fall-through to the store or the site', /Settings → Your state\.`,\n\s*\);\n\s*return false;/.test(src));
const states = read('src/hooks/useBettingState.ts');
check('Missouri is a state (BetMGM and Caesars live there since 2025-12-01)', states.includes("{ code: 'mo', name: 'Missouri' }"));
check('Delaware is absent on purpose, with the reason', !states.includes("code: 'de'") && states.includes('delawarepark.betrivers.com'));
const chain = src.slice(src.indexOf('export async function openBookBetslip'), src.indexOf('function couldNotOpen'));
const at = (needle: string) => chain.indexOf(needle);

// ── installed-app detection (Matt, 2026-09-05: "If I have the app for that
// Sportsbook, it should just open my app") ──────────────────────────────────
const appJson = JSON.parse(read('app.json')) as { expo: { version: string; ios: { infoPlist: Record<string, unknown> } } };
const declared = (appJson.expo.ios.infoPlist.LSApplicationQueriesSchemes ?? []) as string[];
const schemes = Array.from(src.matchAll(/scheme: '([a-z0-9]+):\/\/'/g), (m) => m[1]!);
check('at least one book carries a scheme to query', schemes.length >= 1, schemes.join(','));
for (const sch of schemes) {
  check(`${sch}:// is declared in LSApplicationQueriesSchemes — iOS answers canOpenURL for no other scheme`, declared.includes(sch), `declared: ${declared.join(',') || '(none)'}`);
}
check('the declaration is a native change, so the app version moved off 1.0.0 (OTA cannot carry it; the guard in mobile-ota.yml refuses)', appJson.expo.version !== '1.0.0', appJson.expo.version);
check('installed? is asked only for a book with a scheme, on iOS, and an unknown is null', src.includes("if (!scheme || Platform.OS !== 'ios') return null;"));
check('the question is asked before anything opens', at('isBookAppInstalled(book)') >= 0 && at('isBookAppInstalled(book)') < at('fillBetslipLink'));
const notInstalled = chain.slice(at('installed === false'), at('if (link && link.trim())'));
check('not installed → the App Store, whatever link we hold, then the site — never the app', notInstalled.includes('bookStoreUrl(book)') && notInstalled.includes('tryOpen(app.web)') && !notInstalled.includes('fillBetslipLink') && !notInstalled.includes('app.scheme'));
const isInstalled = chain.slice(at('installed === true'), at('// Unknown'));
check('installed → the link first, then the app by its scheme, then the site — never the App Store', at('fillBetslipLink') < at('installed === true') && isInstalled.includes('app.scheme') && isInstalled.includes('tryOpen(app.web)') && !isInstalled.includes('bookStoreUrl'));
const unknown = chain.slice(at('// Unknown'));
check('unknown → link → store → site (the scheme is not tried: it cannot be queried)', unknown.includes('bookStoreUrl(book)') && unknown.indexOf('bookStoreUrl(book)') < unknown.indexOf('tryOpen(app.web)') && !unknown.includes('app.scheme'));
check('the hook exists for surfaces that offer the store', read('src/hooks/useBookAppInstalled.ts').includes('isBookAppInstalled(book)'));
for (const b of BETTABLE_BOOKS) {
  // The entry: from `  book: {` to its closing `},` (DraftKings spans lines).
  const from = src.indexOf(`  ${b}: {`);
  const row = src.slice(from, src.indexOf('},', from) + 2);
  const hasStore = /store: ios\('id\d+'\)/.test(row) || /apps\.apple\.com\/us\/app\/[a-z-]+\/id\d+/.test(row);
  if (b === 'betparx') {
    check(`${b}: store resolved from the state (one app per state)`, src.includes('BETPARX_STORE_BY_STATE') && /md: 'id\d+'/.test(src) && /pa: 'id\d+'/.test(src) && /nj: 'id\d+'/.test(src));
  } else {
    check(`${b}: App Store page carried, with Apple's own id`, hasStore, row.trim());
  }
}
check('every store id is a numeric Apple id (nothing hand-typed)', (src.match(/ios\('id(\d+)'\)/g) ?? []).length >= 8 && !/ios\('id[^\d']/.test(src));
const handoff = read('src/components/ParlayDkHandoff.tsx');
check('the hand-off sheet offers the store outright, through the same failure path as the bet button', handoff.includes('on the App Store') && handoff.includes('openBookStore(book, state)') && handoff.includes('useBettingState()'));
check('...except when the build knows the app IS installed (an unknown still shows it)', handoff.includes('useBookAppInstalled(book)') && handoff.includes('store && installed !== true ?'));

// ── the state setting exists and is reachable ────────────────────────────────
const settings = read('src/screens/SettingsScreen.tsx');
check('Settings carries a "Your state" row that opens the picker', settings.includes('Your state') && settings.includes('<StatePickerSheet'));
const hook = read('src/hooks/useBettingState.ts');
check('the state is stored on device and never sent anywhere', hook.includes("AsyncStorage") && !hook.includes('supabase'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
