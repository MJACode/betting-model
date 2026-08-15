/**
 * Verifies the multi-book price helpers in lib/markets.ts.
 *
 * Run: npx tsx scripts/verify_preferred_book.ts
 *
 * Covers the behavior the Settings "Your sportsbook" preference and the
 * All books card depend on:
 *   - priceForBook picks the right book, and returns null (never a guess) when
 *     that book didn't price the side
 *   - allBookPrices sorts by PAYOUT (decimal), not raw American number
 *   - the "best" badge covers ties
 *   - prop rows (line, no total_line/spread_home) work through the same helpers
 *   - lineShopForPick still only fires when a non-DK book genuinely beats DK
 *   - displayQuoteForPick resolves what the card shows: the chosen book first,
 *     then a FLAGGED DraftKings fallback, then the price stored on the pick —
 *     and returns null rather than inventing a number
 */

import {
  allBookPrices,
  betOnBookLabel,
  bookLabel,
  bookName,
  displayQuoteForPick,
  lineShopForPick,
  priceForBook,
  LINE_SHOP_BOOKS,
  MODEL_BOOK,
} from '../src/lib/markets';
import type { BookPricedRow, Pick } from '../src/types';

let passed = 0;
let failed = 0;

function check(name: string, cond: boolean, detail = '') {
  if (cond) {
    console.log(`  PASS  ${name}`);
    passed++;
  } else {
    console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
    failed++;
  }
}

// ── Fixtures ────────────────────────────────────────────────────────────────

const gameRows: BookPricedRow[] = [
  { bookmaker: 'draftkings', home_price: -110, away_price: -110, total_line: 8.5 },
  { bookmaker: 'fanduel', home_price: -105, away_price: -115, total_line: 8.5 },
  { bookmaker: 'betmgm', home_price: 100, away_price: -120, total_line: 9 },
  // Caesars prices only the away side here — uneven coverage is normal.
  { bookmaker: 'williamhill_us', away_price: -108, total_line: 8.5 },
];

const propRows: BookPricedRow[] = [
  { bookmaker: 'draftkings', over_price: -130, under_price: 110, line: 1.5 },
  { bookmaker: 'fanduel', over_price: -115, under_price: -105, line: 1.5 },
];

const pick = (side: string, dk: number | null): Pick =>
  ({ pick_side: side, dk_odds: dk } as unknown as Pick);

// ── Book metadata ───────────────────────────────────────────────────────────

check('DraftKings is the model book', MODEL_BOOK === 'draftkings');
check('five books are carried', LINE_SHOP_BOOKS.length === 5);
check('DK is first in display order', LINE_SHOP_BOOKS[0] === 'draftkings');
check(
  'Caesars uses the Odds API key williamhill_us',
  LINE_SHOP_BOOKS.includes('williamhill_us') && bookName('williamhill_us') === 'Caesars',
);
check('williamhill_us labels as CZR', bookLabel('williamhill_us') === 'CZR');
check('legacy caesars key still labels as CZR', bookLabel('caesars') === 'CZR');
check('unknown book degrades to a short label', bookLabel('somebook') === 'SOME');

// ── priceForBook ────────────────────────────────────────────────────────────

check(
  'priceForBook returns the selected book price',
  priceForBook(gameRows, 'home', 'fanduel')?.price === -105,
);
check(
  'priceForBook returns null when the book did not price the side',
  priceForBook(gameRows, 'home', 'williamhill_us') === null,
);
check(
  'priceForBook returns null for a book we have no row for',
  priceForBook(gameRows, 'home', 'espnbet') === null,
);
check(
  'priceForBook works on prop rows',
  priceForBook(propRows, 'over', 'fanduel')?.price === -115,
);

// ── allBookPrices ───────────────────────────────────────────────────────────

const homeQuotes = allBookPrices(gameRows, 'home', 'h2h');
check('allBookPrices skips books with no price on the side', homeQuotes.length === 3);
check(
  'allBookPrices sorts by payout, not raw American number',
  homeQuotes[0].bookmaker === 'betmgm' && homeQuotes[0].price === 100,
  `got ${homeQuotes.map((q) => q.bookmaker).join(',')}`,
);
check('best flag set on the top payout', homeQuotes[0].isBest === true);
check('non-best rows are not flagged', homeQuotes[1].isBest === false);

const awayQuotes = allBookPrices(gameRows, 'away', 'h2h');
check('every book pricing the away side is included', awayQuotes.length === 4);
// Away prices: DK -110, FD -115, MGM -120, CZR -108 → Caesars pays most.
check(
  'away best is the shortest-juice price (-108 beats -110/-115/-120)',
  awayQuotes[0].price === -108 && awayQuotes[0].bookmaker === 'williamhill_us',
  `got ${awayQuotes[0].bookmaker} ${awayQuotes[0].price}`,
);

// Ties: two books at the same price should both be badged.
const tied = allBookPrices(
  [
    { bookmaker: 'draftkings', home_price: -110 },
    { bookmaker: 'fanduel', home_price: -110 },
    { bookmaker: 'betmgm', home_price: -120 },
  ],
  'home',
  'h2h',
);
check('tied best prices are all badged', tied.filter((q) => q.isBest).length === 2);
check('worse price is not badged in a tie', tied[2].isBest === false);

// Lines come through so a better price on a worse number is visible.
const totalQuotes = allBookPrices(gameRows, 'home', 'totals');
check(
  'totals line is attached to each quote',
  totalQuotes.find((q) => q.bookmaker === 'betmgm')?.line === 9 &&
    totalQuotes.find((q) => q.bookmaker === 'fanduel')?.line === 8.5,
);

const propQuotes = allBookPrices(propRows, 'over', 'batter_hits');
check('prop quotes carry the prop line', propQuotes[0].line === 1.5);
check(
  'prop best is the shortest juice (-115 beats -130)',
  propQuotes[0].bookmaker === 'fanduel' && propQuotes[0].isBest,
);

check('allBookPrices on empty input returns []', allBookPrices([], 'home', 'h2h').length === 0);

// ── lineShopForPick (existing behavior must not regress) ────────────────────

check(
  'lineShop fires when a non-DK book beats DK',
  lineShopForPick(pick('home', -110), gameRows)?.bookmaker === 'betmgm',
);
check(
  'lineShop is null when DK is already best',
  lineShopForPick(pick('away', -105), [
    { bookmaker: 'draftkings', away_price: -105 },
    { bookmaker: 'fanduel', away_price: -120 },
  ]) === null,
);
check('lineShop is null with no rows', lineShopForPick(pick('home', -110), []) === null);
check(
  'lineShop works on prop rows too',
  lineShopForPick(pick('over', -130), propRows)?.bookmaker === 'fanduel',
);

// ── displayQuoteForPick (what the card actually shows) ─────────────────────

/** A pick with the model_id the market helpers key off. */
const mlPick = (side: string, dk: number | null, line: number | null = null): Pick =>
  ({
    pick_side: side,
    dk_odds: dk,
    scored_line: line,
    model_id: 'mlb_moneyline',
    dk_bet_link: 'https://dk.example/stored',
  }) as unknown as Pick;

const linkedRows: BookPricedRow[] = [
  {
    bookmaker: 'draftkings',
    home_price: -110,
    away_price: -110,
    total_line: 8.5,
    home_link: 'https://dk.example/home',
  },
  {
    bookmaker: 'fanduel',
    home_price: -105,
    away_price: -115,
    total_line: 9,
    home_link: 'https://fd.example/home',
  },
];

const fd = displayQuoteForPick(mlPick('home', -110), linkedRows, 'fanduel');
check('shows the chosen book’s price', fd?.bookmaker === 'fanduel' && fd?.price === -105);
check('chosen book is not flagged as a fallback', fd?.isPreferred === true && fd?.isFallback === false);
check('carries the chosen book’s betslip link', fd?.link === 'https://fd.example/home');

// Caesars prices nothing here — the user must not be shown DK's number as theirs.
const fallback = displayQuoteForPick(mlPick('home', -110), linkedRows, 'williamhill_us');
check(
  'falls back to DraftKings when the chosen book has no price',
  fallback?.bookmaker === MODEL_BOOK && fallback?.price === -110,
);
check('fallback is flagged', fallback?.isFallback === true && fallback?.isPreferred === false);

// A DK user must see the price the EDGE was computed from (stored on the pick),
// not a fresher snapshot — the movement chip is what surfaces drift.
const dkUser = displayQuoteForPick(mlPick('home', -135), linkedRows, 'draftkings');
check('DK user gets DK, not flagged as a fallback', dkUser?.isPreferred === true && dkUser?.isFallback === false);
check('DK user sees the scored price, not the latest snapshot', dkUser?.price === -135);

// A pick with no per-book snapshot at all still renders (prob-only markets,
// odds feed lag) — from what the scorer stored on the pick.
const stored = displayQuoteForPick(mlPick('home', -120, 8.5), [], 'fanduel');
check('falls back to the pick’s stored DK price', stored?.price === -120 && stored?.isFallback === true);
check('stored fallback keeps the stored betslip link', stored?.link === 'https://dk.example/stored');
check(
  'no price anywhere returns null (never a guess)',
  displayQuoteForPick(mlPick('home', null), [], 'fanduel') === null,
);

// The line matters as much as the price — FD hangs this bet off 9, DK off 8.5.
const totalsPick = {
  pick_side: 'over',
  dk_odds: -110,
  scored_line: 8.5,
  model_id: 'mlb_over_under',
  dk_bet_link: null,
} as unknown as Pick;
const totalsRows: BookPricedRow[] = [
  { bookmaker: 'draftkings', over_price: -110, total_line: 8.5 },
  { bookmaker: 'fanduel', over_price: -105, total_line: 9 },
];
const fdTotal = displayQuoteForPick(totalsPick, totalsRows, 'fanduel');
check('totals quote carries the chosen book’s own line', fdTotal?.line === 9);

const propPick = {
  pick_side: 'over',
  dk_odds: -130,
  scored_line: 1.5,
  model_id: 'mlb_prop_batter_hits',
  dk_bet_link: null,
} as unknown as Pick;
const fdProp = displayQuoteForPick(propPick, propRows, 'fanduel');
check(
  'prop quote resolves through the prop market',
  fdProp?.bookmaker === 'fanduel' && fdProp?.price === -115 && fdProp?.line === 1.5,
);

// ── Book hand-off metadata ────────────────────────────────────────────────
// (bookButtonColors lives in sportsbookLinks.ts, which pulls in react-native —
//  not importable here. It's a two-branch color lookup, covered by tsc.)

check('bet button label names the book', betOnBookLabel('fanduel') === 'Bet on FanDuel');
check('bet button label for DK', betOnBookLabel(MODEL_BOOK) === 'Bet on DraftKings');

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
