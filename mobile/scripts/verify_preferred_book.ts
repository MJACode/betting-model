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
 */

import {
  allBookPrices,
  bookLabel,
  bookName,
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

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
