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
  betAllSkipSummary,
  betAllSports,
  bestLinePlan,
  bookCoverage,
  oneBookPlan,
  quoteForBestLine,
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
function bp(
  id: number,
  label: string,
  quotes: [string, number, string | null, number?][],
  scored: number | null = null,
): BetAllPick {
  return {
    key: String(id),
    pick: { ...pk(id, label), scored_line: scored } as unknown as Pick,
    label,
    quotes: quotes.map(([bookmaker, price, link, line]) => ({ bookmaker, price, link, line: line ?? null })),
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

// ── a best price with no link, at the pick's own number ─────────────────
// Measured 2026-11-18: Caesars alternate +10.5 had −140 and no selection id;
// DraftKings had −142 and a link. The main Caesars number was +9.
const DK_ALT = 'https://sportsbook.draftkings.com/?outcomes=0HC87302851P1050_1';
const liu = bp(21, 'Long Island University +10.5', [
  ['williamhill_us', -140, null, 10.5],
  ['draftkings', -142, DK_ALT, 10.5],
], 10.5);
const liuPlan = bestLinePlan([liu], new Set(['21']));
check('Caesars −140 with no link at +10.5 goes to DraftKings −142',
  liuPlan.length === 1 && liuPlan[0]!.bookmaker === 'draftkings'
  && liuPlan[0]!.legs[0]!.price === -142 && liuPlan[0]!.legs[0]!.link === DK_ALT
  && liuPlan[0]!.links.length === 1 && liuPlan[0]!.unlinked.length === 0
  && liuPlan[0]!.legs[0]!.atBest === false);
const liuNan = bp(27, 'Long Island University +10.5', [
  ['williamhill_us', -140, 'NaN', 10.5],
  ['draftkings', -142, DK_ALT, 10.5],
], 10.5);
check('a stored "NaN" is no link, so the same pick still goes to DraftKings',
  quoteForBestLine(liuNan).bookmaker === 'draftkings');
check('one sportsbook still opens the book the member picked, link or not',
  oneBookPlan([liu], new Set(['21']), 'williamhill_us').step?.unlinked.length === 1
  && oneBookPlan([liu], new Set(['21']), 'draftkings').step?.links[0] === DK_ALT);

const stayLinked = bp(22, 'Drake -3.5', [
  ['fanduel', -105, FD_A, -3.5],
  ['draftkings', -110, DK_A, -3.5],
], -3.5);
const stayPlan = bestLinePlan([stayLinked], new Set(['22']));
check('a linked best book stays put',
  stayPlan[0]!.bookmaker === 'fanduel' && stayPlan[0]!.legs[0]!.price === -105 && stayPlan[0]!.legs[0]!.atBest === true);

const noLink = bp(23, 'Utah State -30.5', [
  ['williamhill_us', 105, null, -30.5],
  ['draftkings', 101, null, -30.5],
], -30.5);
const noLinkPlan = bestLinePlan([noLink], new Set(['23']));
check('no linked book at that number stays unlinked on the best price',
  noLinkPlan[0]!.bookmaker === 'williamhill_us' && noLinkPlan[0]!.legs[0]!.price === 105
  && noLinkPlan[0]!.links.length === 0 && noLinkPlan[0]!.unlinked.length === 1);
const nanOnly = bp(28, 'Utah State -30.5', [
  ['williamhill_us', 105, 'NaN', -30.5],
  ['draftkings', 101, 'NaN', -30.5],
], -30.5);
const nanPlan = bestLinePlan([nanOnly], new Set(['28']));
check('a "NaN" link and no usable book stays unlinked on the best price',
  nanPlan[0]!.bookmaker === 'williamhill_us' && nanPlan[0]!.links.length === 0 && nanPlan[0]!.unlinked.length === 1);

const otherNumber = bp(24, 'Long Island University +10.5', [
  ['fanduel', -105, FD_A, 9.5],
  ['williamhill_us', -140, null, 10.5],
], 10.5);
const otherPlan = bestLinePlan([otherNumber], new Set(['24']));
check('a linked book at a different number is not used',
  otherPlan[0]!.bookmaker === 'williamhill_us' && otherPlan[0]!.legs[0]!.price === -140
  && otherPlan[0]!.links.length === 0 && otherPlan[0]!.unlinked.length === 1);

const rider = bp(25, 'Rider ML', [['williamhill_us', 145, CZR_A]]);
const mixed = bestLinePlan([liu, stayLinked, noLink, otherNumber, rider], new Set(['21', '22', '23', '24', '25']));
const mixedBy = new Map(mixed.map((s) => [s.bookmaker, s]));
check('a mixed card keeps each pick on its own book',
  mixed.map((s) => s.bookmaker).join(',') === 'williamhill_us,draftkings,fanduel'
  && mixedBy.get('draftkings')!.legs.map((l) => l.key).join(',') === '21'
  && mixedBy.get('fanduel')!.legs.map((l) => l.key).join(',') === '22'
  && mixedBy.get('williamhill_us')!.legs.map((l) => l.key).join(',') === '23,24,25'
  && mixedBy.get('williamhill_us')!.unlinked.map((l) => l.key).join(',') === '23,24'
  && mixedBy.get('williamhill_us')!.links.length === 1
  && mixedBy.get('draftkings')!.links[0] === DK_ALT);
const covRouted = bookCoverage([liu], new Set(['21']), ['draftkings', 'williamhill_us']);
check('coverage still counts the best price, not the book the link moved the pick to',
  covRouted.find((c) => c.bookmaker === 'williamhill_us')?.atBest === 1
  && covRouted.find((c) => c.bookmaker === 'draftkings')?.atBest === 0);

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
check('the sheet note carries the live call-out', sheet.includes('{BET_ALL_LIVE_NOTE}'));
check('the row says Bet all · N ready in the sport, never See why (Matt, 2026-11-27)',
  home.includes('`Bet all · ${betAllReady} ready in ${sportDisplayName(sport)}`') && !home.includes("'See why'"));
check('the sheet defaults to Best line', sheet.includes("useState<BetAllMode>('best')"));
check('the best-line list uses the same book as the plan',
  sheet.includes('quoteForBestLine(p)') && sheet.includes('quoteForBestLine(p).bookmaker'));
check('one sportsbook still reads that book’s own quote',
  sheet.includes('p.quotes.find((x) => x.bookmaker === chosenBook)'));
check('the sheet never builds a parlay', !/parlay|combineBetslipLinks|useParlaySlip/i.test(sheet.replace(/not Parlay|Parlay\)|parlay\./g, '')));
check('each pick has its own Placed tick that tracks or untracks it (Matt, 2026-11-20)',
  sheet.includes('if (isTracked(leg.pick)) onUntrack(leg.pick);') && sheet.includes('else onTrack([leg.pick]);'));
check('Placed all tracks only the picks not yet tracked', sheet.includes('const rest = step.legs.filter((l) => !isTracked(l.pick)).map((l) => l.pick);'));
check('the tick reads tracked state, not a sheet-local copy', sheet.includes('const on = isTracked(l.pick);'));
check('no per-book "Did you place" question and no "Stop Bet all?" warning (Matt, 2026-11-20)',
  !sheet.includes('Did you place') && !sheet.includes('Stop Bet all') && !sheet.includes('setConfirmStop'));
check('the screen wires tracking both ways', home.includes('isTracked={tracked.isTracked}') && home.includes('onUntrack={tracked.untrackPick}'));

// ── UX review fixes ──────────────────────────────────────────────────────
check('the board names the main reason nothing is ready',
  betAllMainSkip([{ reason: 'started' }, { reason: 'notAtMyBooks' }, { reason: 'notAtMyBooks' }]) === '2 not at your books');
check('the main reason is plural for a count over one (\'5 games started\', not \'5 game started\')',
  betAllMainSkip([{ reason: 'started' }, { reason: 'started' }]) === '2 games started'
  && betAllMainSkip([{ reason: 'started' }]) === '1 game started');
check('another book’s price says where the model found it', sheet.includes('foundAtText(bookLabel(record), formatAmerican(modelPrice))'));
check('VoiceOver is told to tick placed bets on return', sheet.includes('Tick each bet you placed to track it.'));
check('the app’s own segmented control', sheet.includes('<SegmentTabs'));

// ── Bet all sports, and the skip line (Matt, 2026-11-27) ─────────────────
check('the banner names every skip, most common first',
  betAllSkipSummary([{ reason: 'started' }, { reason: 'oldPrice' }, { reason: 'oldPrice' }]) === '3 not included: 2 old prices, 1 game started');
check('one skip reads singular', betAllSkipSummary([{ reason: 'oldPrice' }]) === '1 not included: 1 old price');
check('nothing skipped says nothing', betAllSkipSummary([]) === null);
check('the sheet says the skips whenever any are left out, not only at zero ready',
  sheet.includes('skipped.length > 0 ? `${betAllSkipSummary(skipped)}. ${BET_ALL_LIVE_NOTE}`'));
{
  const mk = (sport: string, id: number) => ({ pick: { sport, pick_id: id } as unknown as Pick });
  check('betAllSports counts only sports with a pick to send, each once (UX review)',
    JSON.stringify(betAllSports({ picks: [mk('NFL', 1), mk('UFC', 2), mk('NFL', 5)] as never, skipped: [mk('NCAAF', 4)] as never })) === '["NFL","UFC"]');
}
check('Bet all sports reads every sport’s signals, not the filtered tab',
  home.includes('const open = allData.filter(') && home.includes('betAllCandidates(open,'));
check('Bet all sports leaves finished games out', home.includes("!== 'final',\n    );\n    return betAllCandidates(open"));
check('one row opens Bet all on this sport when there is anything to send or skip',
  home.includes('const showBetAllRow =') && home.includes('{showBetAllRow ? (') && home.includes('onPress={() => setBetAllOpen(true)}'));
check('the sheet’s candidates are not gated, and a sheet with none is closed (UX review)',
  !home.includes('length >= 2 ? c : null') && home.includes('if (betAllOpen && betAllSheet == null) setBetAllOpen(false);'));
check('the sheet opens on the current sport and does not remember the toggle',
  sheet.includes("useState<'sport' | 'all'>('sport')") && sheet.includes("setScope('sport')"));
check('the toggle counts ready picks only',
  sheet.includes('sportCandidates.picks.length') && sheet.includes('allCandidates.picks.length')
  && sheet.includes('All sports (${allReady})'));
check('the banner and the sheet use one word for a skip', sheet.includes('>Not included</Text>'));
check('the all-sports sheet groups rows by sport, not a prefix on the footnote',
  sheet.includes('bySport(ps).map(') && !sheet.includes('            {sportPrefix(p.pick)}\n'));
check('the Bet all row keeps a bottom margin the chips’ reach stops at', /betAllReadyRow: \{[^}]*marginBottom: spacing\.sm/.test(home));
check('the all-sports sheet names each pick’s sport', sheet.includes("const showSport = scope === 'all'") && sheet.includes('const sportPrefix = (pick: Pick) =>'));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
process.exit(failures === 0 ? 0 : 1);
