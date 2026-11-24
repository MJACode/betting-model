/**
 * "Track bet" on the betslip and on a saved parlay (Matt, 2026-11-24: "No way
 * for me to add this to tracker"). Run with:
 *
 *   npx tsx scripts/verify_parlay_track.ts
 *
 * Pins the pre-fill the button hands the Your bets form:
 *  - the description is the legs' labels, word for word (CLAUDE.md §00);
 *  - the book and price are the top "Place this bet at" quote — best payout,
 *    DraftKings first on a tie — and both are blank when no book prices every
 *    leg, never a number no book posted;
 *  - a saved slip uses the price its card shows, and names DraftKings only
 *    when every leg was DraftKings-priced.
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

// ── description ─────────────────────────────────────────────────────────────
{
  const p = parlayTrackPrefill([a, b], []);
  check(
    'description lists every leg label verbatim',
    p.description === '2-leg parlay: Alperen Sengun Over 5.5 Rebounds · LAL ML',
    p.description,
  );
  const one = parlayTrackPrefill([b], []);
  check('a single leg is just its label', one.description === 'LAL ML', one.description);
}

// ── book + price: the top quote ─────────────────────────────────────────────
{
  const p = parlayTrackPrefill([a, b], [quote('betrivers', -101), quote('draftkings', -107, true)]);
  check('book is the top quote, by display name', p.book === 'BetRivers', String(p.book));
  check('odds are the top quote', p.oddsAmerican === -101, String(p.oddsAmerican));
}
{
  // The real sort, on legs every book prices equally: a tie goes to DraftKings.
  const quotes = priceBooksForParlay([a, b], 1, ['fanduel', 'draftkings']);
  const p = parlayTrackPrefill([a, b], quotes);
  const dk = computeParlayMetrics([a, b]).americanOdds;
  check('a tie goes to DraftKings', p.book === 'DraftKings', String(p.book));
  check('tie price is the combined price', p.oddsAmerican === Math.round(dk), `${p.oddsAmerican} vs ${dk}`);
}
{
  const p = parlayTrackPrefill([a, b], [quote('fanduel', null), quote('draftkings', null, true)]);
  check('no full quote → no book', p.book === null, String(p.book));
  check('no full quote → no price', p.oddsAmerican === null, String(p.oddsAmerican));
}

// ── saved parlays ───────────────────────────────────────────────────────────
{
  const p = savedParlayTrackPrefill([a, b]);
  const dk = Math.round(computeParlayMetrics([a, b]).americanOdds);
  check('saved slip: card price', p.oddsAmerican === dk, `${p.oddsAmerican} vs ${dk}`);
  check('saved slip, all DK-priced: DraftKings', p.book === 'DraftKings', String(p.book));
  const offDk: ParlayLeg = { ...b, dkPriced: false, pricedAt: 'fanduel' };
  const q = savedParlayTrackPrefill([a, offDk]);
  check('saved slip with a non-DK leg: book left blank', q.book === null, String(q.book));
  check('empty saved slip: no price', savedParlayTrackPrefill([]).oddsAmerican === null);
}

if (failures > 0) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log('\nall checks passed');
