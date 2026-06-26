/**
 * Standalone verification for line-shopped parlay pricing (lineShopParlay in
 * src/lib/parlay.ts). Run with:
 *
 *   npx tsx scripts/verify_line_shop.ts
 *
 * Pins: no shoppable leg → null; a best-book leg lifts the combined payout and
 * EV above the all-DK parlay (evDelta > 0); EV uses the passed-in joint prob (so
 * it stays consistent with the card's correlated number); book set + count are
 * de-duped; props (no bestBook) never shop.
 */

import {
  lineShopParlay,
  parlayHasLineShop,
  type BestBookPrice,
  type ParlayLeg,
} from '../src/lib/parlay';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}
function approx(a: number, b: number, tol = 1e-9): boolean {
  return Math.abs(a - b) <= tol;
}
const toDec = (am: number) => (am > 0 ? 1 + am / 100 : 1 + 100 / Math.abs(am));

function leg(pickId: number, american: number, best: BestBookPrice | null): ParlayLeg {
  return {
    pickId,
    slipKey: `G${pickId}|mlb_moneyline|`,
    gameId: `G${pickId}`,
    modelId: 'mlb_moneyline',
    isGameLine: true,
    isFavorite: american < 0,
    label: `leg ${pickId}`,
    modelProb: 0.6,
    decimalOdds: toDec(american),
    americanOdds: american,
    legEdge: 0,
    bestBook: best,
    pick: null,
    game: null,
  };
}
function best(bookmaker: string, american: number): BestBookPrice {
  return { bookmaker, american, decimal: toDec(american), link: null };
}

// 1. No shoppable leg → null, predicate false.
{
  const legs = [leg(1, -110, null), leg(2, 120, null)];
  check('No best book → lineShopParlay null', lineShopParlay(legs, 0.36, 0) === null);
  check('No best book → parlayHasLineShop false', parlayHasLineShop(legs) === false);
}

// 2. One leg beats DK → payout & EV rise; evDelta > 0; EV uses jointProb.
{
  // DK: -110 (1.909) × +120 (2.20) = 4.20. FD on leg 1: +100 (2.00).
  const legs = [leg(1, -110, best('fanduel', 100)), leg(2, 120, null)];
  const jointProb = 0.34;
  const dkPayout = toDec(-110) * toDec(120);
  const dkEv = jointProb * dkPayout - 1;
  const ls = lineShopParlay(legs, jointProb, dkEv);
  check('Shoppable leg → non-null', ls != null);
  if (ls) {
    const expectedPayout = toDec(100) * toDec(120);
    check('Best-book payout uses FD price', approx(ls.decimalPayout, expectedPayout), `${ls.decimalPayout} vs ${expectedPayout}`);
    check('EV uses passed jointProb', approx(ls.ev, jointProb * expectedPayout - 1));
    check('EV improves vs all-DK', ls.ev > dkEv && ls.evDelta > 0, `ev=${ls.ev.toFixed(4)} dkEv=${dkEv.toFixed(4)} delta=${ls.evDelta.toFixed(4)}`);
    check('shoppedCount = 1', ls.shoppedCount === 1);
    check('books = [fanduel]', ls.books.length === 1 && ls.books[0] === 'fanduel');
  }
}

// 3. Two books, deduped.
{
  const legs = [
    leg(1, -110, best('fanduel', 105)),
    leg(2, 120, best('betmgm', 140)),
    leg(3, -130, best('fanduel', -115)),
  ];
  const ls = lineShopParlay(legs, 0.2, -0.1);
  check('Three shopped legs counted', ls?.shoppedCount === 3, `got ${ls?.shoppedCount}`);
  check('Book set de-duped to {fanduel, betmgm}', ls != null && ls.books.length === 2 && ls.books.includes('fanduel') && ls.books.includes('betmgm'), `books=${ls?.books.join(',')}`);
}

console.log(failures === 0 ? '\nAll line-shop checks passed.' : `\n${failures} check(s) FAILED.`);
process.exit(failures === 0 ? 0 : 1);
