/**
 * Multi-pick sportsbook deep-link carryover.
 *
 * Run with:  npx tsx scripts/verify_betslip_combine.ts
 *
 * The hand-off sheet used to open only the first linked leg (`firstLink` in
 * ParlayDkHandoff). Matt's report: several picks ready to convert, only one
 * landed in the book. These checks pin the combiner AND the sheet wiring so
 * that cannot silently return.
 *
 * Link shapes are the real ones stored on 2026-09-20 (latest_odds /
 * latest_prop_odds / picks.dk_bet_link). Combiners exist only for books
 * whose multi-selection form is measured (public DK URL, FanDuel share
 * URLs, official BetMGM docs, Caesars selectionIds, ESPN BET [0] indexes).
 * Hard Rock and BetRivers stay uncombined — inventing a URL is the other
 * way to drop picks.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import {
  betslipCombineKind,
  combineBetslipLinks,
  fillBetslipLink,
} from '../src/lib/betslipLinks';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// Real stored single-leg URLs (2026-09-20).
const DK_A = 'https://sportsbook.draftkings.com/?outcomes=0HC86378564N450_1';
const DK_B = 'https://sportsbook.draftkings.com/?outcomes=0ML86378564_1';
const DK_C = 'https://sportsbook.draftkings.com/?outcomes=0OU86378564O5550_1';
// Encoded `#` in a prop outcome id — must survive the join as %23, not as #.
const DK_HASH = 'https://sportsbook.draftkings.com/?outcomes=0QA334322121%232150672240_13L88808Q11286860163Q20';
const FD_A = 'https://sportsbook.fanduel.com/addToBetslip?marketId=42.607149349&selectionId=1010478';
const FD_B = 'https://sportsbook.fanduel.com/addToBetslip?marketId=42.601183933&selectionId=102431838';
const MGM_A = 'https://sports.{state}.betmgm.com/en/sports?options=19666574-1554174999-2284641605&type=Single';
const MGM_B = 'https://sports.{state}.betmgm.com/en/sports?options=19666575-1554194063-2284694088&type=Single';
const CZR_A = 'https://sportsbook.caesars.com/us/{state}/bet/betslip?selectionIds=ddd462ae-d8e7-3141-ad92-f869562f0947';
const CZR_B = 'https://sportsbook.caesars.com/us/{state}/bet/betslip?selectionIds=00014429-ea6d-3021-a4ed-4f09c63f90a2';
const ESPN_A = 'https://sportsbook.thescore.bet/?market_selection_id[0]=69f3be9a-5eec-4362-857c-112cdad962ef&odds_numerator[0]=2&odds_denominator[0]=1';
const ESPN_B = 'https://sportsbook.thescore.bet/?market_selection_id[0]=0000d1ed-b880-49e5-8f81-f42d5de83e66&odds_numerator[0]=2&odds_denominator[0]=1';
const HR_A = 'https://app.hardrock.bet/?deep_link_value=betslip/4281365642801709466';
const HR_B = 'https://app.hardrock.bet/?deep_link_value=betslip/1000041160976236962';
const BR_A = 'https://{state}.betrivers.com/?page=sportsbook#event/1024787252?coupon={pickType}|4343506253|{wagerAmount}';
const BR_B = 'https://{state}.betrivers.com/?page=sportsbook#event/1028914917?coupon={pickType}|4323941275|{wagerAmount}';

// A public DraftKings 3-outcome URL (the book's own separator).
const DK_PUBLIC_3 =
  'https://sportsbook.draftkings.com/?outcomes=0ML82122622_1+0ML82122631_3+0OU82162897O21950_1';

// ── empty / single / identity ──────────────────────────────────────────────
check('no links → null', combineBetslipLinks([]) === null);
check('nulls only → null', combineBetslipLinks([null, undefined, '  ']) === null);
check('one DK link returns that link', combineBetslipLinks([DK_A]) === DK_A);
check('duplicate of the same link is still one pick', combineBetslipLinks([DK_A, DK_A]) === DK_A);

// ── DraftKings ─────────────────────────────────────────────────────────────
const dk3 = combineBetslipLinks([DK_A, DK_B, DK_C]);
check(
  'three DK legs join with + and keep every outcome id',
  dk3 ===
    'https://sportsbook.draftkings.com/?outcomes=0HC86378564N450_1+0ML86378564_1+0OU86378564O5550_1',
  dk3 ?? 'null',
);
check('the first-only URL is NOT what a 3-pick DK slip opens', dk3 !== DK_A && (dk3?.includes('0ML86378564_1') ?? false));
const dkHash = combineBetslipLinks([DK_A, DK_HASH]);
check(
  'a %23 in a DK outcome id is not decoded into a fragment #',
  (dkHash?.includes('0QA334322121%232150672240_13L88808Q11286860163Q20') ?? false) &&
    !dkHash?.includes('#2150672240'),
  dkHash ?? 'null',
);
check(
  'a DK URL that is already multi-outcome is flattened, not nested',
  combineBetslipLinks([DK_PUBLIC_3, DK_A])?.split('outcomes=')[1]?.split(/[+,]/).length === 4,
);

// ── FanDuel ────────────────────────────────────────────────────────────────
const fd = combineBetslipLinks([FD_A, FD_B]);
check(
  'two FanDuel legs become indexed marketId/selectionId pairs',
  fd ===
    'https://sportsbook.fanduel.com/addToBetslip?marketId[0]=42.607149349&selectionId[0]=1010478&marketId[1]=42.601183933&selectionId[1]=102431838',
  fd ?? 'null',
);
check('FanDuel combine is not the first link', fd !== FD_A);

// ── BetMGM ─────────────────────────────────────────────────────────────────
const mgm = combineBetslipLinks([MGM_A, MGM_B]);
check(
  'two BetMGM legs comma-join options and set type=combo',
  mgm ===
    'https://sports.{state}.betmgm.com/en/sports?options=19666574-1554174999-2284641605,19666575-1554194063-2284694088&type=combo',
  mgm ?? 'null',
);
check('{state} survives BetMGM combine so fillBetslipLink can still run', mgm?.includes('{state}') === true);
check(
  'filled BetMGM combo is NJ and is not a leftover template',
  fillBetslipLink(mgm!, 'NJ') ===
    'https://sports.nj.betmgm.com/en/sports?options=19666574-1554174999-2284641605,19666575-1554194063-2284694088&type=combo',
);

// ── Caesars ────────────────────────────────────────────────────────────────
const czr = combineBetslipLinks([CZR_A, CZR_B]);
check(
  'two Caesars legs comma-join selectionIds and keep {state}',
  czr ===
    'https://sportsbook.caesars.com/us/{state}/bet/betslip?selectionIds=ddd462ae-d8e7-3141-ad92-f869562f0947,00014429-ea6d-3021-a4ed-4f09c63f90a2',
  czr ?? 'null',
);
check(
  'filled Caesars combo is PA',
  fillBetslipLink(czr!, 'pa') ===
    'https://sportsbook.caesars.com/us/pa/bet/betslip?selectionIds=ddd462ae-d8e7-3141-ad92-f869562f0947,00014429-ea6d-3021-a4ed-4f09c63f90a2',
);

// ── ESPN BET ───────────────────────────────────────────────────────────────
const espn = combineBetslipLinks([ESPN_A, ESPN_B]);
check(
  'two ESPN BET legs re-index market_selection_id[0] and [1]',
  espn ===
    'https://sportsbook.thescore.bet/?market_selection_id[0]=69f3be9a-5eec-4362-857c-112cdad962ef&odds_numerator[0]=2&odds_denominator[0]=1&market_selection_id[1]=0000d1ed-b880-49e5-8f81-f42d5de83e66&odds_numerator[1]=2&odds_denominator[1]=1',
  espn ?? 'null',
);

// ── books we do NOT invent a multi-leg URL for ─────────────────────────────
check('Hard Rock has no measured multi-leg form → null (not a guessed comma-join)', combineBetslipLinks([HR_A, HR_B]) === null);
check('BetRivers coupon is single-selection → null', combineBetslipLinks([BR_A, BR_B]) === null);
check('mixed books → null, never a DK URL wearing FanDuel ids', combineBetslipLinks([DK_A, FD_A]) === null);
check('Hard Rock is unclassified', betslipCombineKind(HR_A) === null);
check('BetRivers is unclassified', betslipCombineKind(BR_A) === null);
check('DraftKings classifies', betslipCombineKind(DK_A) === 'draftkings');
check('FanDuel classifies', betslipCombineKind(FD_A) === 'fanduel');
check('BetMGM classifies', betslipCombineKind(MGM_A) === 'betmgm');
check('Caesars classifies', betslipCombineKind(CZR_A) === 'caesars');
check('ESPN BET classifies', betslipCombineKind(ESPN_A) === 'espnbet');

// ── the sheet actually uses the combiner (the regression that shipped) ─────
const handoff = read('src/components/ParlayDkHandoff.tsx');
check('the sheet imports combineBetslipLinks', handoff.includes("from '@/lib/betslipLinks'") && handoff.includes('combineBetslipLinks('));
check('the sheet does not open firstLink', !handoff.includes('firstLink'));
check('openBookBetslip receives the combined URL', /openBookBetslip\(\s*book,\s*openLink\s*\)/.test(handoff));
check(
  'a book we cannot join still falls back to the first linked leg',
  handoff.includes('combined ?? linked[0]'),
);
check(
  'the note claims all N legs when the combiner joined every one',
  handoff.includes('with all ${combinedCount} legs on your slip'),
);
check(
  'a partial combine does not tell the user to tap Add on a row that has no Add button',
  handoff.includes("The other leg isn't on a link") &&
    !handoff.includes('Add the rest below'),
);
const row = read('src/components/BetslipBooksRow.tsx');
check(
  'the Place-this-bet tooltip no longer says books cannot take a parlay from a link',
  !row.includes("Books can’t accept a whole parlay from a link") &&
    row.includes('every linked leg on that book'),
);

console.log(failures === 0 ? '\nALL BETSLIP-COMBINE CHECKS PASSED' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
