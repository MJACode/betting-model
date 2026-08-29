/**
 * Standalone verification for the per-book betslip pricing — the "Open with"
 * row and the sportsbook hand-off (priceBooksForParlay / handoffBookFor /
 * legFromPick's bookPrices) in src/lib/parlay.ts. Run with:
 *
 *   npx tsx scripts/verify_betslip.ts
 *
 * Pins:
 *  - legFromPick collects every non-DK book's price for the pick side from
 *    ep.bookRows and NEVER a DraftKings row (DK is always the stored dk_odds).
 *  - DraftKings is always fully priced (a leg requires dk_odds), at the stored
 *    scored price — not a fresher snapshot.
 *  - A book pricing every leg gets combined odds = the product of its own
 *    per-leg decimals; a partial book gets null odds + a coverage count.
 *  - Fully-priced books sort best payout first (ties ALL starred), partial
 *    books after by coverage.
 *  - EV uses the caller's (correlated) joint probability at each book's payout.
 *  - Custom legs (no live pick) are book-agnostic: their entered odds count at
 *    every book, so one custom leg can't demote every book to N-1/N.
 *  - handoffBookFor hands off at the preferred book only when it prices EVERY
 *    leg (with that book's own links); otherwise DraftKings — the button label
 *    must never name a book that can't take the slip.
 *  - betslipSummary (the persistent betslip bar's numbers): the badge counts
 *    every SELECTION while the price covers only the legs that resolve today,
 *    the $10 payout is the stake-inclusive return, and the odds are exactly the
 *    ones the Betslip screen shows — correlation moves a parlay's probability,
 *    never its price.
 *
 *  - canPruneSlip / shouldShowBetslipBar: a selection that no longer resolves
 *    is REMOVED rather than counted, and the bar hides when there is no real
 *    bet in the slip — but only ever against a board we know actually loaded.
 */

import {
  BETSLIP_BAR_STAKE,
  betslipSummary,
  computeParlayMetrics,
  handoffBookFor,
  legFromPick,
  makeCustomLeg,
  canPruneSlip,
  priceBooksForParlay,
  resolveSlipLegs,
  shouldShowBetslipBar,
  type ParlayLeg,
} from '../src/lib/parlay';
import {
  computeCorrelatedMetrics,
  PARLAY_CORRELATION_PRIORS,
} from '../src/lib/parlayCorrelation';
import type { EnrichedPick, Pick } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  console.log(`${cond ? '[PASS]' : '[FAIL]'} ${name}${detail ? ' — ' + detail : ''}`);
  if (!cond) failures++;
}
function approx(a: number | null, b: number, tol = 1e-9): boolean {
  return a != null && Math.abs(a - b) <= tol;
}
const toDec = (am: number) => (am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am));

// ── Fixtures ────────────────────────────────────────────────────────────────

function pick(pickId: number, over: Partial<Pick> = {}): Pick {
  return {
    pick_id: pickId,
    game_id: `MLB_2026-08-28_NYY_BOS_${pickId}`,
    model_id: 'mlb_prop_batter_hits',
    sport: 'MLB',
    pick_side: 'over',
    pick_label: 'Aaron Judge Over 1.5 Hits',
    model_probability: 0.62,
    dk_implied_prob: 0.524,
    edge: 0.096,
    dk_odds: -110,
    dk_bet_link: `dk://leg${pickId}`,
    signal_type: 'BET',
    player_id: String(500000 + pickId),
    scored_line: 1.5,
    result: null,
    game_date: '2026-08-28',
    ...over,
  } as unknown as Pick;
}

function ep(p: Pick, bookRows: EnrichedPick['bookRows']): EnrichedPick {
  return { pick: p, game: null, weather: null, bestOdds: null, bookRows } as unknown as EnrichedPick;
}

// Leg 1: FD -105 (link), MGM -115 (no link). DK stored -110.
const leg1 = legFromPick(
  ep(pick(1), [
    // A DK snapshot row with a DIFFERENT (moved) price — must be ignored.
    { bookmaker: 'draftkings', over_price: -125, under_price: -105, over_link: 'dk://fresh1' },
    { bookmaker: 'fanduel', over_price: -105, under_price: -115, over_link: 'fd://leg1' },
    { bookmaker: 'betmgm', over_price: -115, under_price: -105 },
    // Prices the WRONG side only — not a price for this leg.
    { bookmaker: 'espnbet', under_price: -110 },
  ]),
)!;

// Leg 2: FD +100 (link). DK stored -120.
const leg2 = legFromPick(
  ep(pick(2, { dk_odds: -120, dk_bet_link: 'dk://leg2' }), [
    { bookmaker: 'fanduel', over_price: 100, over_link: 'fd://leg2' },
  ]),
)!;

// ── legFromPick.bookPrices ──────────────────────────────────────────────────

check('leg1 exists and prices two non-DK books', leg1 != null && leg1.bookPrices.length === 2,
  `books=${leg1?.bookPrices.map((b) => b.bookmaker).join(',')}`);
check('DK snapshot row never enters bookPrices',
  leg1.bookPrices.every((b) => b.bookmaker !== 'draftkings'));
check('side price + link resolved per book',
  leg1.bookPrices.find((b) => b.bookmaker === 'fanduel')?.american === -105 &&
    leg1.bookPrices.find((b) => b.bookmaker === 'fanduel')?.link === 'fd://leg1');
check('wrong-side-only book excluded',
  leg1.bookPrices.every((b) => b.bookmaker !== 'espnbet'));
check('decimal conversion on book price',
  approx(leg1.bookPrices.find((b) => b.bookmaker === 'betmgm')?.decimal ?? null, toDec(-115)));
check('leg keeps the STORED DK price, not the fresh snapshot',
  leg1.americanOdds === -110 && approx(leg1.decimalOdds, toDec(-110)));

// ── priceBooksForParlay ─────────────────────────────────────────────────────

const legs: ParlayLeg[] = [leg1, leg2];
const jointProb = 0.4;
const BOOKS = ['draftkings', 'fanduel', 'betmgm', 'espnbet'];
const quotes = priceBooksForParlay(legs, jointProb, BOOKS);

const dk = quotes.find((q) => q.book === 'draftkings')!;
const fd = quotes.find((q) => q.book === 'fanduel')!;
const mgm = quotes.find((q) => q.book === 'betmgm')!;
const espn = quotes.find((q) => q.book === 'espnbet')!;

check('DK fully priced at the stored odds',
  dk.priced === 2 && approx(dk.decimalPayout, toDec(-110) * toDec(-120)));
check('DK carries the stored betslip links', dk.links[0] === 'dk://leg1' && dk.links[1] === 'dk://leg2');
check('FD fully priced at ITS OWN prices',
  fd.priced === 2 && approx(fd.decimalPayout, toDec(-105) * toDec(100)));
check('FD links are FanDuel links', fd.links[0] === 'fd://leg1' && fd.links[1] === 'fd://leg2');
check('partial book: null combined odds + coverage count',
  mgm.priced === 1 && mgm.decimalPayout == null && mgm.americanOdds == null && mgm.ev == null);
check('zero-coverage book still listed', espn.priced === 0 && espn.total === 2);
check('best star on the highest payout (FD beats DK here)',
  fd.isBest && !dk.isBest && !mgm.isBest);
check('fully-priced books sort before partial; best first',
  quotes[0].book === 'fanduel' && quotes[1].book === 'draftkings' &&
    quotes[2].book === 'betmgm' && quotes[3].book === 'espnbet');
check('EV at each book = jointProb × payout − 1',
  approx(fd.ev, jointProb * toDec(-105) * toDec(100) - 1) &&
    approx(dk.ev, jointProb * toDec(-110) * toDec(-120) - 1));

// Ties: same payout at two books → both starred.
const tieQuotes = priceBooksForParlay([leg1], 1, ['draftkings', 'betmgm']);
// leg1: DK -110 vs MGM -115 — not a tie; construct one via a custom leg below.
check('single-leg quotes still price', tieQuotes.length === 2 && tieQuotes[0].isBest);

// Custom legs are book-agnostic — they price at EVERY book at the entered odds.
const custom = makeCustomLeg('My own play', 150);
const withCustom = priceBooksForParlay([leg2, custom], 0.3, ['draftkings', 'fanduel']);
const fdC = withCustom.find((q) => q.book === 'fanduel')!;
const dkC = withCustom.find((q) => q.book === 'draftkings')!;
check('custom leg counts at every book',
  fdC.priced === 2 && dkC.priced === 2 &&
    approx(fdC.decimalPayout, toDec(100) * toDec(150)) &&
    approx(dkC.decimalPayout, toDec(-120) * toDec(150)));
check('empty slip → no quotes', priceBooksForParlay([], 1, BOOKS).length === 0);

// ── handoffBookFor ──────────────────────────────────────────────────────────

const hFd = handoffBookFor(legs, 'fanduel');
check('preferred book prices every leg → hand off there with ITS links',
  hFd.book === 'fanduel' && hFd.links[0] === 'fd://leg1' && hFd.links[1] === 'fd://leg2');

const hMgm = handoffBookFor(legs, 'betmgm');
check('partial preferred book → DraftKings fallback with DK links',
  hMgm.book === 'draftkings' && hMgm.links[0] === 'dk://leg1' && hMgm.links[1] === 'dk://leg2');

const hDk = handoffBookFor(legs, 'draftkings');
check('DK preference stays DK', hDk.book === 'draftkings' && hDk.links[1] === 'dk://leg2');

// ── betslipSummary (the persistent betslip bar) ─────────────────────────────

// The bar resolves the SAME persisted slip keys the Betslip screen does.
const barPickA = pick(11, { dk_odds: -110 });
const barPickB = pick(12, { dk_odds: 150, model_id: 'mlb_moneyline', player_id: null });
const barPicks = [ep(barPickA, []), ep(barPickB, [])];
const keyA = `${barPickA.game_id}|${barPickA.model_id}|${barPickA.player_id ?? ''}`;
const keyB = `${barPickB.game_id}|${barPickB.model_id}|`;
const STALE_KEY = 'MLB_2026-08-27_GONE|mlb_moneyline|';

const twoLeg = resolveSlipLegs(barPicks, [keyA, keyB]);
const twoSummary = betslipSummary(twoLeg.legs, 2);
const expectedPayout = toDec(-110) * toDec(150);

check('two resolved legs → parlay price',
  twoSummary.count === 2 && twoSummary.resolved === 2 && twoSummary.isParlay);
check('combined odds match the screen headline',
  twoSummary.americanOdds === computeParlayMetrics(twoLeg.legs).americanOdds);
check(`$${BETSLIP_BAR_STAKE} pays = stake x combined decimal (stake included)`,
  approx(twoSummary.payoutPerTen, BETSLIP_BAR_STAKE * expectedPayout, 1e-6),
  `${twoSummary.payoutPerTen}`);

// The whole reason the bar can skip the copula pass: correlation changes the
// win probability, never the payout — so the bar and the screen can't disagree.
const correlated = computeCorrelatedMetrics(twoLeg.legs, PARLAY_CORRELATION_PRIORS, () => null);
check('odds are correlation-independent (bar == screen)',
  correlated.americanOdds === twoSummary.americanOdds &&
    approx(correlated.decimalPayout, expectedPayout, 1e-9));

// A single selection is a straight bet, not a parlay.
const oneLeg = resolveSlipLegs(barPicks, [keyA]);
const oneSummary = betslipSummary(oneLeg.legs, 1);
check('single leg prices as a straight bet',
  oneSummary.resolved === 1 && !oneSummary.isParlay &&
    // approx, not ===: the decimal round-trip lands on -109.99999999999999.
    // formatAmerican rounds for display, so the bar reads "-110".
    approx(oneSummary.americanOdds, -110, 1e-6) &&
    approx(oneSummary.payoutPerTen, BETSLIP_BAR_STAKE * toDec(-110), 1e-6));

// A settled / de-listed / now-prob-only selection stops resolving: the badge
// must still count it (the user picked it) while the price covers only what's
// actually priceable.
const partial = resolveSlipLegs(barPicks, [keyA, STALE_KEY, keyB]);
const partialSummary = betslipSummary(partial.legs, 3);
check('badge counts selections, price counts resolved legs',
  partial.missingKeys.length === 1 && partialSummary.count === 3 &&
    partialSummary.resolved === 2 &&
    partialSummary.americanOdds === twoSummary.americanOdds);

// Nothing resolves → no odds at all rather than a made-up number.
const noneSummary = betslipSummary([], 2);
check('nothing priceable → no odds, no payout, still counted',
  noneSummary.count === 2 && noneSummary.resolved === 0 &&
    noneSummary.americanOdds === null && noneSummary.payoutPerTen === null &&
    !noneSummary.isParlay);

// A prob-only selection (no DK price) can never become a leg — same rule the
// betslip screen uses, so the bar can't advertise a price for it.
const probOnly = pick(13, { dk_odds: null, model_id: 'mlb_prop_batter_hr' });
const probKey = `${probOnly.game_id}|${probOnly.model_id}|${probOnly.player_id ?? ''}`;
const probResolved = resolveSlipLegs([ep(probOnly, [])], [probKey]);
check('prob-only selection never prices',
  probResolved.legs.length === 0 && betslipSummary(probResolved.legs, 1).americanOdds === null);

// ── Stale selections: pruned, not carried ──────────────────────────────────
//
// The bug this closes: keys outlive the picks they point at (the game ended,
// the market de-listed), so the badge counted selections that nothing on screen
// read as selected, and the bar sat there forever advertising them.

check('a loaded, non-empty board can prune',
  canPruneSlip({ slipReady: true, loading: false, error: null, boardSize: 12 }));

// Each guard alone must block a prune — every one of these looks exactly like
// "all your selections are gone" from the resolver's point of view.
check('never prune while the board is still loading',
  !canPruneSlip({ slipReady: true, loading: true, error: null, boardSize: 12 }));
check('never prune on a failed fetch',
  !canPruneSlip({ slipReady: true, loading: false, error: 'network down', boardSize: 0 }));
check('never prune against an empty board',
  !canPruneSlip({ slipReady: true, loading: false, error: null, boardSize: 0 }));
check('never prune before the slip is read from storage',
  !canPruneSlip({ slipReady: false, loading: false, error: null, boardSize: 12 }));

// ── Bar visibility ─────────────────────────────────────────────────────────

check('bar shows once a selection prices', shouldShowBetslipBar(twoSummary, false));
check('bar shows a partially-priced slip', shouldShowBetslipBar(partialSummary, false));
check('bar HIDES when nothing in the slip resolves',
  !shouldShowBetslipBar(noneSummary, false));
check('bar hides on an empty slip', !shouldShowBetslipBar(betslipSummary([], 0), false));
// The one case where selections with no price still show: we don't yet know.
check('bar shows while the board is still resolving',
  shouldShowBetslipBar(noneSummary, true));
check('resolving with an empty slip still shows nothing',
  !shouldShowBetslipBar(betslipSummary([], 0), true));

// The screenshot that started this: 3 saved keys, none of them on today's
// board. Old behaviour = "Betslip (3)" forever. New = prune, then hide.
const ghostKeys = [STALE_KEY, 'MLB_2026-08-20_OLD|mlb_moneyline|', 'MLB_2026-08-20_OLD|mlb_prop_pitcher_k|999'];
const ghost = resolveSlipLegs(barPicks, ghostKeys);
const ghostSummary = betslipSummary(ghost.legs, ghostKeys.length);
check('3 ghost selections: all prunable, bar hidden',
  ghost.legs.length === 0 && ghost.missingKeys.length === 3 &&
    canPruneSlip({ slipReady: true, loading: false, error: null, boardSize: barPicks.length }) &&
    !shouldShowBetslipBar(ghostSummary, false));

// ...but a live selection alongside them survives the prune.
const mixed = resolveSlipLegs(barPicks, [STALE_KEY, keyA]);
check('pruning keeps the selections that still resolve',
  mixed.legs.length === 1 && mixed.legs[0].slipKey === keyA &&
    mixed.missingKeys.length === 1 &&
    shouldShowBetslipBar(betslipSummary(mixed.legs, 2), false));

console.log(failures === 0 ? '\nALL BETSLIP CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
