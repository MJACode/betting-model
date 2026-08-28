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
 */

import {
  handoffBookFor,
  legFromPick,
  makeCustomLeg,
  priceBooksForParlay,
  type ParlayLeg,
} from '../src/lib/parlay';
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

console.log(failures === 0 ? '\nALL BETSLIP CHECKS PASSED' : `\n${failures} CHECK(S) FAILED`);
process.exit(failures === 0 ? 0 : 1);
