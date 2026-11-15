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

import { APP_CLAIMING_BOOKS, appClaimedLink, fillBetslipLink, linkNeedsState, linkShape } from '../src/lib/betslipLinks';
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
const verifiedSchemes = Array.from(src.matchAll(/scheme: '([a-z0-9-]+):\/\/'/g), (m) => m[1]!);
const candidateSchemes = Array.from(src.matchAll(/candidateSchemes: \[([^\]]+)\]/g), (m) => m[1]!)
  .flatMap((list) => Array.from(list.matchAll(/'([a-z0-9-]+)'/g), (m) => m[1]!));
check('DraftKings is the one verified scheme', verifiedSchemes.length === 1 && verifiedSchemes[0] === 'dksb', verifiedSchemes.join(','));
// "This should be the same for all the Sportsbook apps" (Matt, 2026-09-05):
// every bettable book asks, by a verified scheme or by candidates.
for (const b of BETTABLE_BOOKS) {
  const from = src.indexOf(`  ${b}: {`);
  const row = src.slice(from, src.indexOf('},', from) + 2);
  check(`${b}: asks whether its app is installed (a verified scheme or candidates)`, /scheme: '[a-z0-9-]+:\/\/'/.test(row) || /candidateSchemes: \['/.test(row), row.trim().slice(0, 80));
}
for (const sch of [...verifiedSchemes, ...candidateSchemes]) {
  check(`${sch}:// is declared in LSApplicationQueriesSchemes — iOS answers canOpenURL for no other scheme`, declared.includes(sch), `declared: ${declared.join(',') || '(none)'}`);
}
check('nothing is declared that no book asks about', declared.every((d) => verifiedSchemes.includes(d) || candidateSchemes.includes(d)), declared.filter((d) => !verifiedSchemes.includes(d) && !candidateSchemes.includes(d)).join(','));
check('the declaration is within Apple\'s cap of 50', declared.length <= 50, String(declared.length));
const detect = src.slice(src.indexOf('export async function isBookAppInstalled'), src.indexOf('/**\n * Open a pre-filled betslip'));
check('a `true` from any scheme, verified or candidate, is proof', detect.includes('[...verified, ...candidates].map(ask)') && detect.includes('if (answers.some((a) => a === true)) return true;'));
check('a `false` is proof only from the verified scheme; candidates leave it unknown', detect.includes('answers.slice(0, verified.length).some((a) => a === false)') && detect.includes('return verifiedSaidNo ? false : null;'));
// A bare brand is as likely a sibling app (FanDuel DFS, BetMGM Casino, Caesars
// Rewards); a yes from it would hide the store from the member it was for.
for (const bare of ['fanduel', 'betmgm', 'caesars', 'williamhill', 'hardrock', 'bally', 'fanatics'] as const) {
  check(`no bare-brand candidate: ${bare}://`, !candidateSchemes.includes(bare));
}
check('the declaration is a native change, so the app version moved off 1.0.0 (OTA cannot carry it; the guard in mobile-ota.yml refuses)', appJson.expo.version !== '1.0.0', appJson.expo.version);
check('installed? is asked only on iOS and only for a book with something to ask; otherwise null', src.includes("if (!app || Platform.OS !== 'ios') return null;") && src.includes('if (verified.length === 0 && candidates.length === 0) return null;'));
check('the question is asked before anything opens', at('isBookAppInstalled(book)') >= 0 && at('isBookAppInstalled(book)') < at('fillBetslipLink'));
const notInstalled = chain.slice(at('installed === false'), at('if (link && link.trim())'));
check('not installed → the App Store, whatever link we hold, then the site — never the app', notInstalled.includes('bookStoreUrl(book)') && notInstalled.includes('tryOpen(app.web)') && !notInstalled.includes('fillBetslipLink') && !notInstalled.includes('app.scheme'));
const isInstalled = chain.slice(at('if (installed === true) {'), at('// Unknown'));
check('installed → the link first, then the app by its scheme, then the site — never the App Store', at('fillBetslipLink') < at('if (installed === true) {') && isInstalled.includes('app.scheme') && isInstalled.includes('tryOpen(app.web)') && !isInstalled.includes('bookStoreUrl'));
// 2026-11-15 (Matt, BetMGM on build 14301: Safari). A scheme is opened from
// two places only: the verified one in the installed branch, and whichever
// said yes, straight after iOS refused the claimed link.
const refused = chain.slice(at('if (viaApp === false && installed === true)'), at('if (link && link.trim())'));
check('iOS refused the claimed link and a scheme says installed → the app by that scheme, before the stored link (Safari)',
  at('if (viaApp === false && installed === true)') > at('viaApp = claimed ? await openUniversalLinkOnly(claimed)')
  && refused.includes('const scheme = await installedBookScheme(book);') && refused.includes('tryOpen(scheme, true)'));
check('a candidate scheme is opened nowhere else', (chain.match(/installedBookScheme\(/g) ?? []).length === 1 && (src.match(/installedBookScheme\(/g) ?? []).length === 2);
const pick = src.slice(src.indexOf('async function installedBookScheme'), src.indexOf('/**\n * Open a pre-filled betslip'));
check('...and only one that answered yes is opened', pick.includes('answers.findIndex((a) => a === true)') && pick.includes('.catch(() => false)') && pick.includes('return i >= 0 ? schemes[i]! : null;'));
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

// ── open in the app, or the App Store (Matt, 2026-11-14: "Make it open the
// App Store if I dont have the app or open the app if I have it") ────────────
// The claimed forms are the ones each host's apple-app-site-association file
// carries (worker job 1224851, 2026-11-12).
const MGM = 'https://sports.{state}.betmgm.com/en/sports?options=20076228-1575284363-2342468393&type=Single';
check('BetMGM: the betslip link moves under /sportsapp/, the only path its app claims, query kept',
  appClaimedLink('betmgm', MGM, 'NJ') === 'https://sports.nj.betmgm.com/en/sportsapp/sports?options=20076228-1575284363-2342468393&type=Single');
check('BetMGM: no link still opens the app, at its claimed root', appClaimedLink('betmgm', null, 'pa') === 'https://sports.pa.betmgm.com/en/sportsapp/sports');
check('BetMGM: a template with no state is never asked about', appClaimedLink('betmgm', MGM, null) === null && appClaimedLink('betmgm', null, null) === null);
check('BetMGM: a link of a shape we have not seen is not rewritten', appClaimedLink('betmgm', 'https://sports.nj.betmgm.com/en/casino?x=1', 'nj') === null);
check('FanDuel and DraftKings: the stored link as it is, else the claimed root',
  appClaimedLink('fanduel', STORED.fanduel!, null) === STORED.fanduel && appClaimedLink('fanduel', null, null) === 'https://sportsbook.fanduel.com/'
  && appClaimedLink('draftkings', null, null) === 'https://sportsbook.draftkings.com/');
check('FanDuel and DraftKings: a link on any other host is not asked about',
  appClaimedLink('fanduel', 'https://account.fanduel.com/x?y=1', null) === null && appClaimedLink('fanduel', 'https://nj.sportsbook.fanduel.com/addToBetslip?marketId=1', null) === null
  && appClaimedLink('draftkings', 'https://www.draftkings.com/x', null) === null && appClaimedLink('draftkings', STORED.draftkings!, null) === STORED.draftkings);
check('Caesars: the filled /us/<state>/bet/ link, else that root for the state',
  appClaimedLink('williamhill_us', STORED.williamhill_us!, 'NJ') === fillBetslipLink(STORED.williamhill_us!, 'nj')
  && appClaimedLink('williamhill_us', null, 'mi') === 'https://sportsbook.caesars.com/us/mi/bet/' && appClaimedLink('williamhill_us', null, null) === null);
for (const b of ['betrivers', 'hardrockbet', 'fanatics', 'ballybet', 'betparx', 'rebet', 'fliff'] as const) {
  check(`${b}: its app claims no link we hold, so iOS is not asked`, appClaimedLink(b, 'https://x.example/bet', 'nj') === null);
}
const viaApp = chain.slice(at('viaApp = claimed ?'), at('if (link && link.trim())'));
check('iOS is asked to open the claimed link in the app only, after the not-installed exit and before anything else opens',
  at('viaApp = claimed ?') > at('installed === false') && chain.includes('const claimed = appClaimedLink(book, link, getBettingState());') && viaApp.includes('openUniversalLinkOnly(claimed)'));
check('...yes is done; no is the App Store only when nothing says the app is installed; cannot-ask falls through to the old chain',
  viaApp.includes('if (viaApp === true) return true;') && /if \(viaApp === false && installed === null\) \{\s*const store = bookStoreUrl\(book\);/.test(viaApp) && !viaApp.includes('tryOpen(app.web)'));
// ── a hand-off that misses the app is written down ──────────────────────────
// The function body only: the helpers after it have comments of their own.
const exits = chain.slice(at('const went = '), at("/**\n * The book's app was opened by its scheme"));
const returns = exits.match(/return [^;]+;/g) ?? [];
const unlogged = returns.filter((r) => !r.includes('went(') && r !== 'return true;' && r !== 'return false;' && r !== 'return ok;');
check('every exit but "iOS opened it in the app" and the state alert goes through the log', unlogged.length === 0 && returns.filter((r) => r.includes('went(')).length >= 9, unlogged.join(' | '));
check('...for the books whose app claims links, on iOS, a null claimed link included', exits.includes("if (APP_CLAIMING_BOOKS.includes(book) && Platform.OS === 'ios') {")
  && APP_CLAIMING_BOOKS.every((b) => appClaimedLink(b, null, 'nj') !== null) && BETTABLE_BOOKS.filter((b) => !APP_CLAIMING_BOOKS.includes(b)).every((b) => appClaimedLink(b, 'https://x.example/bet', 'nj') === null));
check('a scheme open says the bet is not on the slip, when the member comes back', exits.includes("if (route === 'scheme' && ok) sayBetNotOnSlip(book);")
  && /if \(state !== 'active'\) return;[\s\S]{0,260}sub\.remove\(\);[\s\S]{0,260}showToast\(`\$\{bookName\(note\.book\)\} opened without your bet\. Add it there\.`, \{ announce: true/.test(src));
check('...and only after a real trip to the background, not iOS\'s own "Open in ...?" prompt', src.includes("let left = AppState.currentState === 'background';") && src.includes("if (state === 'background') left = true;"));
check('...and a hand-off that never left the app drops its note', /if \(!left\) \{\s*if \(slipNote && Date\.now\(\) - slipNote\.at <= SLIP_NOTE_PROMPT_MS\) return;\s*sub\.remove\(\);\s*slipNoteListening = false;\s*slipNote = null;\s*return;/.test(src));
check('the exit check found the end of the function body', at("/**\n * The book's app was opened by its scheme") > at('const went = '));
check('...one listener however many taps, and not after five minutes away', src.includes('if (slipNoteListening) return;') && src.includes('if (!note || Date.now() - note.at > SLIP_NOTE_MAX_AGE_MS) return;'));
const hlog = read('src/lib/handoffLog.ts');
check('the log uses a kind the RPC accepts (a refused kind stops the crash queue)', hlog.includes("kind: 'js_error'") && read('../data/migrations/app_errors_freeze_kinds_2026_11_06.sql').includes("'js_error'"));
check('one row per book and route per session, the build number and the opened scheme on it', hlog.includes('const key = `${miss.book}:${miss.route}`;') && hlog.includes('if (logged.has(key)) return;') && hlog.includes('nativeBuild: nativeBuild()') && hlog.includes('scheme: miss.scheme ?? null') && hlog.includes('claimed: linkShape(miss.claimed)') && !hlog.includes('miss.claimed,'));
check('the logged link carries no query and no state (the picker says "Stored on this device only")',
  linkShape(appClaimedLink('betmgm', STORED.betmgm!, 'NJ')) === 'sports.<st>.betmgm.com/en/sportsapp/sports'
  && linkShape(appClaimedLink('williamhill_us', null, 'mi')) === 'sportsbook.caesars.com/us/<st>/bet/'
  && linkShape('https://sportsbook.draftkings.com/event/1?outcomes=2') === 'sportsbook.draftkings.com/event/1' && linkShape(null) === null);
const openInApp = read('src/lib/openInApp.ts');
check('the native module is optional: a binary without it answers null, never throws',
  openInApp.includes("requireOptionalNativeModule<OpenInAppNative>('OpenInApp')") && openInApp.includes('if (!native) return null;') && openInApp.includes("Platform.OS === 'ios'"));
const swift = read('modules/open-in-app/ios/OpenInAppModule.swift');
check('the native call is universalLinksOnly under the name the JS asks for',
  swift.includes('Name("OpenInApp")') && swift.includes('AsyncFunction("openUniversalLinkOnly")') && swift.includes('[.universalLinksOnly: true]'));
check('a string iOS cannot parse is an error (cannot ask), never "not installed"', swift.includes('promise.reject("ERR_OPEN_IN_APP_BAD_URL"') && !swift.includes('promise.resolve(false)') && openInApp.includes('return null; // asked and not answered'));
check('the module is autolinked for iOS', read('modules/open-in-app/expo-module.config.json').includes('"OpenInAppModule"'));

// ── the state setting exists and is reachable ────────────────────────────────
const settings = read('src/screens/SettingsScreen.tsx');
check('Settings carries a "Your state" row that opens the picker', settings.includes('Your state') && settings.includes('<StatePickerSheet'));
const hook = read('src/hooks/useBettingState.ts');
check('the state is stored on device and never sent anywhere', hook.includes("AsyncStorage") && !hook.includes('supabase'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
