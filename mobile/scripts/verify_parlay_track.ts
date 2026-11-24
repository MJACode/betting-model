/**
 * "Track bet" on the betslip and on a saved parlay (Matt, 2026-11-24: "No way
 * for me to add this to tracker"). Run with:
 *
 *   npx tsx scripts/verify_parlay_track.ts
 *
 * Pins the pre-fill the button hands the Your bets form:
 *  - the description is EVERY leg's label, word for word (CLAUDE.md §00) —
 *    a leg whose game started stays in; an empty slip gives an empty string;
 *  - the book and price are the starred "Place this bet at" tile (or the only
 *    full quote); blank when a leg is out of the price or no book qualifies;
 *    a same-game ESTIMATE names the book and leaves the odds blank;
 *  - a saved slip names the book its card's "Bet on" button opens, and fills
 *    the card's price only when that book is DraftKings and every leg was
 *    DraftKings-priced.
 */

import {
  computeParlayMetrics,
  makeCustomLeg,
  parlayTrackPrefill,
  priceBooksForParlay,
  savedParlayTrackPrefill,
  type BetslipBookQuote,
  type ParlayLeg,
} from '../src/lib/parlay';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

function quote(book: string, americanOdds: number | null, isModelBook = false): BetslipBookQuote {
  return {
    book,
    priced: americanOdds == null ? 1 : 2,
    total: 2,
    decimalPayout: null,
    americanOdds,
    multipliedDecimal: null,
    sgpEstimated: false,
    entered: false,
    ev: null,
    isBest: false,
    isModelBook,
    links: [],
  };
}

const a = makeCustomLeg('Alperen Sengun Over 5.5 Rebounds', -790);
const b = makeCustomLeg('LAL ML', -800);
const best = (q: BetslipBookQuote): BetslipBookQuote => ({ ...q, isBest: true });

// ── description ─────────────────────────────────────────────────────────────
{
  const p = parlayTrackPrefill([a, b], [a, b], []);
  check(
    'description lists every leg label verbatim',
    p.description === '2-leg parlay: Alperen Sengun Over 5.5 Rebounds · LAL ML',
    p.description,
  );
  const one = parlayTrackPrefill([b], [b], []);
  check('a single leg is just its label', one.description === 'LAL ML', one.description);
  check('an empty slip gives an empty description', parlayTrackPrefill([], [], []).description === '');
}

// ── book + price: the starred tile ──────────────────────────────────────────
{
  const p = parlayTrackPrefill([a, b], [a, b], [best(quote('betrivers', -101)), quote('draftkings', -107, true)]);
  check('book is the starred quote, by display name', p.book === 'BetRivers', String(p.book));
  check('odds are the starred quote', p.oddsAmerican === -101, String(p.oddsAmerican));
}
{
  // The real sort and star, on legs every book prices equally: a tie goes to DraftKings.
  const quotes = priceBooksForParlay([a, b], 1, ['fanduel', 'draftkings']);
  const p = parlayTrackPrefill([a, b], [a, b], quotes);
  const dk = computeParlayMetrics([a, b]).americanOdds;
  check('a tie goes to DraftKings', p.book === 'DraftKings', String(p.book));
  check('tie price is the combined price', p.oddsAmerican === Math.round(dk), `${p.oddsAmerican} vs ${dk}`);
}
{
  const p = parlayTrackPrefill([a, b], [a, b], [quote('fanduel', null), quote('draftkings', null, true)]);
  check('no full quote → no book', p.book === null, String(p.book));
  check('no full quote → no price', p.oddsAmerican === null, String(p.oddsAmerican));
}
{
  // Two full quotes and no star (the row drops it when typed and estimated mix).
  const p = parlayTrackPrefill([a, b], [a, b], [quote('betrivers', -101), quote('draftkings', -107, true)]);
  check('two full quotes, no star → no book', p.book === null, String(p.book));
  const only = parlayTrackPrefill([a, b], [a, b], [quote('fanduel', -120), quote('draftkings', null, true)]);
  check(
    'one full quote, no star → that book',
    only.book === 'FanDuel' && only.oddsAmerican === -120,
    `${only.book} ${only.oddsAmerican}`,
  );
}
{
  const est = best({ ...quote('fanduel', -120), sgpEstimated: true });
  const p = parlayTrackPrefill([a, b], [a, b], [est]);
  check('same-game estimate → book named', p.book === 'FanDuel', String(p.book));
  check('same-game estimate → odds left blank', p.oddsAmerican === null, String(p.oddsAmerican));
  const typed = parlayTrackPrefill([a, b], [a, b], [best({ ...quote('fanduel', -118), entered: true })]);
  check('a price the member typed → filled', typed.oddsAmerican === -118, String(typed.oddsAmerican));
}
{
  // A leg whose game started is out of the price but still in the bet.
  const p = parlayTrackPrefill([a, b], [a], [best(quote('draftkings', -790, true))]);
  check('started leg stays in the description', p.description.startsWith('2-leg parlay:'), p.description);
  check('started leg → no book, no price', p.oddsAmerican === null && p.book === null, `${p.book} ${p.oddsAmerican}`);
}

// ── saved parlays ───────────────────────────────────────────────────────────
{
  const p = savedParlayTrackPrefill([a, b], 'draftkings');
  const dk = Math.round(computeParlayMetrics([a, b]).americanOdds);
  check('saved slip at DK: card price', p.oddsAmerican === dk, `${p.oddsAmerican} vs ${dk}`);
  check('saved slip at DK: DraftKings', p.book === 'DraftKings', String(p.book));
  const fd = savedParlayTrackPrefill([a, b], 'fanduel');
  check('saved slip opening FanDuel: FanDuel named', fd.book === 'FanDuel', String(fd.book));
  check('saved slip opening FanDuel: odds blank, not DK’s', fd.oddsAmerican === null, String(fd.oddsAmerican));
  const offDk: ParlayLeg = { ...b, dkPriced: false, pricedAt: 'fanduel' };
  const q = savedParlayTrackPrefill([a, offDk], 'draftkings');
  check('saved slip with a non-DK leg: odds blank', q.oddsAmerican === null, String(q.oddsAmerican));
  check('empty saved slip: no price', savedParlayTrackPrefill([], 'draftkings').oddsAmerican === null);
}

if (failures > 0) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log('\nall checks passed');
