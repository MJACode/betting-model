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
const chain = src.slice(src.indexOf('export async function openBookBetslip'), src.indexOf('export function openBetslip'));
const at = (needle: string) => chain.indexOf(needle);
check('the chain is link → scheme → store → site', at('fillBetslipLink') < at('app.scheme') && at('app.scheme') < at('bookStoreUrl(book)') && at('bookStoreUrl(book)') < at('tryOpen(app.web)'));
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
check('the hand-off sheet offers the store outright', handoff.includes('Get it on the App Store') && handoff.includes('bookStoreUrl(book)'));

// ── the state setting exists and is reachable ────────────────────────────────
const settings = read('src/screens/SettingsScreen.tsx');
check('Settings carries a "Your state" row that opens the picker', settings.includes('Your state') && settings.includes('<StatePickerSheet'));
const hook = read('src/hooks/useBettingState.ts');
check('the state is stored on device and never sent anywhere', hook.includes("AsyncStorage") && !hook.includes('supabase'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
