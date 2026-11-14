/**
 * Bet all (Matt, 2026-11-14): every pre-game signal for a sport, sent to the
 * member's books as SINGLE bets, at the best line per bet (the default) or
 * at one sportsbook. Run with:
 *
 *   npx tsx scripts/verify_bet_all.ts
 *
 * Pins:
 *  - combineSinglesLinks never asks a book for a parlay: BetMGM goes out
 *    type=Single (the parlay hand-off sends type=combo), Caesars keeps the
 *    stored link's dl=betslip, mixed books and books without a measured
 *    multi-selection form (Hard Rock, BetRivers) return null.
 *  - bestLinePlan puts each selected pick at its best book, biggest book
 *    first, and leaves unselected picks out.
 *  - oneBookPlan names the picks the book does not have instead of dropping
 *    them, and bookCoverage ranks books by picks covered, then at best.
 *  - Each leg's stake is sized at that book's price, as the card sizes it.
 *  - Live picks and non-BET rows never reach Bet all, and the board says so.
 *  - PickCard and Bet all read one price view (lib/pickPriceView.ts).
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { combineBetslipLinks, combineSinglesLinks } from '../src/lib/betslipLinks';
import {
  BET_ALL_LIVE_NOTE,
  betAllCandidates,
  betAllMainSkip,
  bestLinePlan,
  bookCoverage,
  oneBookPlan,
  planTotals,
  type BetAllPick,
} from '../src/lib/betAll';
import { passesActionFilter, stakeFor } from '../src/lib/thresholds';
import type { EnrichedPick, Pick } from '../src/types';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// Real stored links, v_latest_odds_all_books, NCAAB 2026-11-15.
const MGM_A = 'https://sports.{state}.betmgm.com/en/sports?options=20103627-1578569105-2351317299&type=Single';
const MGM_B = 'https://sports.{state}.betmgm.com/en/sports?options=20103720-1578609952-2351416509&type=Single';
const CZR_A = 'https://sportsbook.caesars.com/us/{state}/bet?selectionIds=98937e2b-ac3d-312b-923f-cd4ac96907b0&dl=betslip';
const CZR_B = 'https://sportsbook.caesars.com/us/{state}/bet?selectionIds=1317a8f4-dc9d-3533-88b2-e38fb82e1c88&dl=betslip';
const DK_A = 'https://sportsbook.draftkings.com/?outcomes=0HC87240184N1650_1';
const DK_B = 'https://sportsbook.draftkings.com/?outcomes=0OU87240174O14350_1';
const FD_A = 'https://sportsbook.fanduel.com/addToBetslip?marketId=42.625275650&selectionId=13130';
const FD_B = 'https://sportsbook.fanduel.com/addToBetslip?marketId=42.625257317&selectionId=7017823';
const HRB_A = 'https://app.hardrock.bet/?deep_link_value=betslip/1004224301003571622';
const HRB_B = 'https://app.hardrock.bet/?deep_link_value=betslip/1004224301003571623';

// ── singles links ────────────────────────────────────────────────────────
const mgm = combineSinglesLinks([MGM_A, MGM_B]);
check('BetMGM singles link carries both options',
  mgm === 'https://sports.{state}.betmgm.com/en/sports?options=20103627-1578569105-2351317299,20103720-1578609952-2351416509&type=Single', mgm ?? 'null');
check('BetMGM singles link never asks for a parlay', !!mgm && !mgm.includes('combo'));
check('the parlay hand-off still asks BetMGM for a combo', (combineBetslipLinks([MGM_A, MGM_B]) ?? '').includes('type=combo'));
const czr = combineSinglesLinks([CZR_A, CZR_B]);
check('Caesars singles link keeps dl=betslip',
  czr === 'https://sportsbook.caesars.com/us/{state}/bet?selectionIds=98937e2b-ac3d-312b-923f-cd4ac96907b0,1317a8f4-dc9d-3533-88b2-e38fb82e1c88&dl=betslip', czr ?? 'null');
check('DraftKings joins outcomes with +',
  combineSinglesLinks([DK_A, DK_B]) === 'https://sportsbook.draftkings.com/?outcomes=0HC87240184N1650_1+0OU87240174O14350_1');
check('FanDuel indexes both selections',
  combineSinglesLinks([FD_A, FD_B]) === 'https://sportsbook.fanduel.com/addToBetslip?marketId[0]=42.625275650&selectionId[0]=13130&marketId[1]=42.625257317&selectionId[1]=7017823');
check('Hard Rock has no multi-pick form', combineSinglesLinks([HRB_A, HRB_B]) === null);
check('mixed books never join', combineSinglesLinks([DK_A, FD_B]) === null);
check('a book switched off gets one link per pick', combineSinglesLinks([DK_A, DK_B], ['fanduel']) === null);
check('one link is returned as is', combineSinglesLinks([DK_A]) === DK_A);

// ── plans ────────────────────────────────────────────────────────────────
function pk(id: number, label: string, kelly = 0.02, stakeUnits: number | null = null): Pick {
  return { pick_id: id, pick_label: label, kelly_fraction: kelly, stake_units: stakeUnits } as unknown as Pick;
}
function bp(id: number, label: string, quotes: [string, number, string | null][]): BetAllPick {
  return {
    key: String(id),
    pick: pk(id, label),
    label,
    quotes: quotes.map(([bookmaker, price, link]) => ({ bookmaker, price, link })),
  };
}
const picks: BetAllPick[] = [
  bp(1, 'Drake -3.5', [['fanduel', -105, FD_A], ['draftkings', -110, DK_A]]),
  bp(2, 'Over 152.5', [['fanduel', -102, FD_B], ['draftkings', -112, DK_B]]),
  bp(3, 'Under 141.5', [['hardrockbet', -108, HRB_A], ['fanduel', -112, null]]),
  bp(4, 'Rider ML', [['williamhill_us', 145, CZR_A]]),
];
const all = new Set(picks.map((p) => p.key));

const best = bestLinePlan(picks, all);
// A tie in picks goes to the app's sportsbook order (Caesars before Hard Rock).
check('best line: one step per best book', best.map((s) => s.bookmaker).join(',') === 'fanduel,williamhill_us,hardrockbet',
  best.map((s) => s.bookmaker).join(','));
check('best line: the biggest book opens with one link', best[0]!.links.length === 1 && best[0]!.legs.length === 2);
check('best line: every leg is at its best price', best.every((s) => s.legs.every((l) => l.atBest)));
const without2 = bestLinePlan(picks, new Set(['1', '3', '4']));
check('an unticked pick is not sent', !without2.some((s) => s.legs.some((l) => l.key === '2')));

const cov = bookCoverage(picks, all, ['draftkings', 'fanduel', 'hardrockbet', 'williamhill_us']);
check('coverage ranks the book with the most picks first', cov[0]?.bookmaker === 'fanduel' && cov[0]?.covered === 3,
  JSON.stringify(cov[0]));
check('coverage counts picks at the best price', cov[0]?.atBest === 2);

const fd = oneBookPlan(picks, all, 'fanduel');
check('one book: the picks it has are one step', fd.step?.legs.length === 3);
check('one book: the pick it lacks is named', fd.missing.map((p) => p.key).join(',') === '4');
check('one book: a leg with no link is listed to add by hand', fd.step?.unlinked.length === 1 && fd.step.links.length === 1);
const under = fd.step?.legs.find((l) => l.key === '3');
check('one book: a worse price is not marked best', under?.atBest === false);
check('stake is sized at that book’s price',
  under != null && under.stake.risk === stakeFor(0.02, -112, null).risk && under.stake.risk !== stakeFor(0.02, -108, null).risk);
const t = planTotals(best);
check('totals add every leg', t.legs === 4 && Math.abs(t.win - best.flatMap((s) => s.legs).reduce((n, l) => n + l.stake.win, 0)) < 1e-9);

// ── what never reaches Bet all ───────────────────────────────────────────
// A live BET that clears its model's cut (ncaab_live_spread_h1, min edge 0)
// and was posted, so only the live rule can keep it out.
const live = { pick: { ...pk(9, 'Live Over 140.5'), is_live: true, signal_type: 'BET', game_id: 'g',
  model_id: 'ncaab_live_spread_h1', model_probability: 0.6, dk_odds: -110, decision_odds: -110, edge: 0.08,
  result: null, discordPublish: 'published' }, game: null, weather: null } as unknown as EnrichedPick;
check('the live fixture clears its cut', passesActionFilter(live.pick));
const avoid = { pick: { ...pk(10, 'Under 150.5'), signal_type: 'AVOID', game_id: 'g' }, game: null, weather: null } as unknown as EnrichedPick;
const none = betAllCandidates([live, avoid], () => null, ['draftkings']);
check('live and non-BET rows are neither sent nor listed', none.picks.length === 0 && none.skipped.length === 0);
check('the live call-out is the decided copy', BET_ALL_LIVE_NOTE === 'Pre-game signals only. Live bets aren’t included.');

// ── wiring ──────────────────────────────────────────────────────────────
const card = read('src/components/PickCard.tsx');
const lib = read('src/lib/betAll.ts');
const home = read('src/screens/PicksHomeScreen.tsx');
const sheet = read('src/components/BetAllSheet.tsx');
check('PickCard reads the shared price view', card.includes('pickPriceView(item, liveState, myBooks, myBooksReady)'));
check('Bet all reads the same price view', lib.includes('pickPriceView(item, liveState, myBooks, true)'));
check('Bet all is offered on Signals only', home.includes("view === 'signals' && myBooksReady"));
check('the board shows the live call-out beside the button', home.includes('{BET_ALL_LIVE_NOTE}'));
check('the sheet defaults to Best line', sheet.includes("useState<BetAllMode>('best')"));
check('the sheet never builds a parlay', !/parlay|combineBetslipLinks|useParlaySlip/i.test(sheet.replace(/not Parlay|Parlay\)|parlay\./g, '')));
check('Placed tracks every leg of that book', sheet.includes('step?.legs.forEach((l) => onTrack(l.pick))'));

// ── UX review fixes ──────────────────────────────────────────────────────
check('the board names the main reason nothing is ready',
  betAllMainSkip([{ reason: 'started' }, { reason: 'notAtMyBooks' }, { reason: 'notAtMyBooks' }]) === '2 not at your books');
check('another book’s price says where the model found it', sheet.includes('foundAtText(bookLabel(record), formatAmerican(modelPrice))'));
check('mid-send the backdrop does not close the sheet', sheet.includes("onPress={phase === 'send' ? undefined : onClose}"));
check('the X asks before dropping an unanswered book', sheet.includes('if (pendingAnswer) setConfirmStop(true);'));
check('VoiceOver hears the placed question', sheet.includes('AccessibilityInfo.announceForAccessibility('));
check('the app’s own segmented control', sheet.includes('<SegmentTabs'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
