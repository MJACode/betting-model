/**
 * Standalone verification for a pick's line at the member's OWN books when
 * the book that found it is not one of theirs (Matt, 2026-11-12). Run with:
 *
 *   npx tsx scripts/verify_other_lines.ts
 *
 * The fixture is the production case: "Coppin State +10.5" (home, scored_line
 * 10.5) decided at Hard Rock +120, a member with BetMGM, DraftKings, Fanatics,
 * FanDuel and Caesars. Their MAIN lines were +12.5 / +11.5; BetMGM (+115) and
 * DraftKings (+111) had +10.5 only on the alternate ladder, and the card said
 * "Not offered at your books".
 *
 * Pins:
 *   1. gameRowsForPick adds a book's ladder rung at the pick's number, after
 *      every main row, and drops rungs at other numbers.
 *   2. With the rungs, myBooksView is 'mine' at BetMGM +115, not 'none'.
 *   3. Without them (the old read), it was 'none' — the bug, reproduced.
 *   4. otherLineQuotesForPick lists each of their books with no +10.5 at its
 *      own number, nearest first, never a book outside their set.
 *   5. pickSportsbookRows puts those after the same-line rows, never Best.
 */

import {
  currentLineQuotes,
  gameRowsForPick,
  otherLineQuotesForPick,
} from '../src/lib/markets';
import { myBooksView } from '../src/lib/myBooks';
import { pickSportsbookRows } from '../src/lib/pickBooks';
import type { BookPricedRow, Pick, PickSide } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const pick = {
  pick_id: 1,
  game_id: 'NCAAB_2026-11-12_bradley_coppin-state',
  model_id: 'ncaab_spread',
  sport: 'NCAAB',
  game_date: '2026-11-12',
  pick_side: 'home' as PickSide,
  pick_label: 'Coppin State +10.5',
  model_probability: 0.4924,
  dk_odds: -115,
  scored_line: 10.5,
  signal_type: 'BET',
  is_live: false,
  decision_odds: 120,
  decision_book: 'hardrockbet',
  line_book: null,
} as unknown as Pick;

type Row = BookPricedRow & { market: string };
const main: Row[] = [
  { market: 'spreads', bookmaker: 'hardrockbet', spread_home: 10.5, home_price: 120, home_link: 'hrb://m' },
  { market: 'spreads', bookmaker: 'betrivers', spread_home: 10.5, home_price: 118, home_link: 'br://m' },
  { market: 'spreads', bookmaker: 'betmgm', spread_home: 12.5, home_price: -110, home_link: 'mgm://m' },
  { market: 'spreads', bookmaker: 'draftkings', spread_home: 12.5, home_price: -115, home_link: 'dk://m' },
  { market: 'spreads', bookmaker: 'fanatics', spread_home: 12.5, home_price: -115, home_link: null },
  { market: 'spreads', bookmaker: 'fanduel', spread_home: 11.5, home_price: -102, home_link: 'fd://m' },
];
const ladder: Row[] = [
  { market: 'alternate_spreads', bookmaker: 'betmgm', spread_home: 10.5, home_price: 115, home_link: 'mgm://a105' },
  { market: 'alternate_spreads', bookmaker: 'draftkings', spread_home: 10.5, home_price: 111, home_link: 'dk://a105' },
  // A rung at another number: a sister pick's line, never this one's.
  { market: 'alternate_spreads', bookmaker: 'draftkings', spread_home: 9.5, home_price: 129, home_link: 'dk://a95' },
  // A book whose MAIN row is already +10.5 keeps its main row.
  { market: 'alternate_spreads', bookmaker: 'betrivers', spread_home: 10.5, home_price: 118, home_link: 'br://a105' },
];
const myBooks = ['betmgm', 'draftkings', 'fanatics', 'fanduel', 'williamhill_us'];

// 1 ─ the merge
const merged = gameRowsForPick(pick, 'spreads', [...main, ...ladder]);
check('every main row is kept, first', merged.slice(0, main.length).every((r, i) => r === main[i]));
check(
  'BetMGM and DraftKings +10.5 rungs are added',
  merged.some((r) => r.bookmaker === 'betmgm' && r.market === 'alternate_spreads' && r.spread_home === 10.5)
    && merged.some((r) => r.bookmaker === 'draftkings' && r.market === 'alternate_spreads' && r.spread_home === 10.5),
);
check('the +9.5 rung is dropped', !merged.some((r) => r.spread_home === 9.5));
check('BetRivers keeps its main row only', merged.filter((r) => r.bookmaker === 'betrivers').length === 1);
check('no ladder → main unchanged', gameRowsForPick(pick, 'spreads', main).length === main.length);

// 2 & 3 ─ the member's view
const view = (rows: BookPricedRow[]) =>
  myBooksView({
    quotes: currentLineQuotes(pick, rows),
    recordBook: 'hardrockbet',
    myBooks,
    modelProbability: pick.model_probability,
  });
const before = view(main);
check('main lines only: none (the reported bug)', before.status === 'none', before.status);
const after = view(merged);
check('with rungs: mine', after.status === 'mine', after.status);
check('their best is BetMGM +115', after.best?.bookmaker === 'betmgm' && after.best?.price === 115);
check('BetMGM hands off to its +10.5 rung link', after.best?.link === 'mgm://a105');
check(
  'edge is re-worked at +115',
  after.edge != null && Math.abs(after.edge - (0.4924 - 1 / 2.15)) < 1e-9,
  String(after.edge),
);

// 4 ─ other numbers at their books
const other = otherLineQuotesForPick(pick, merged, myBooks);
const books = other.map((q) => q.bookmaker).sort();
check('other lines: FanDuel and Fanatics only', JSON.stringify(books) === '["fanatics","fanduel"]', JSON.stringify(books));
check('FanDuel is at +11.5 −102', other.some((q) => q.bookmaker === 'fanduel' && q.line === 11.5 && q.price === -102));
check('no book outside their set', other.every((q) => myBooks.includes(q.bookmaker)));
const noneOther = otherLineQuotesForPick(pick, main, myBooks);
check(
  'main lines only: all four of their priced books at another number',
  noneOther.map((q) => q.bookmaker).sort().join(',') === 'betmgm,draftkings,fanatics,fanduel',
);
check('a live pick offers no other line', otherLineQuotesForPick({ ...pick, is_live: true } as Pick, main, myBooks).length === 0);
check(
  'a moneyline offers no other line',
  otherLineQuotesForPick({ ...pick, model_id: 'ncaab_moneyline_own_spread' } as Pick, main, myBooks).length === 0,
);

// 5 ─ the sheet
const sheet = pickSportsbookRows(
  [
    { bookmaker: 'betmgm', price: 115, link: 'mgm://a105', isBest: true },
    { bookmaker: 'draftkings', price: 111, link: 'dk://a105', isBest: false },
  ],
  myBooks,
  [
    { bookmaker: 'fanduel', price: -102, link: 'fd://m', lineText: 'Coppin State +11.5' },
    { bookmaker: 'fanatics', price: -115, link: null, lineText: 'Coppin State +12.5' },
  ],
);
check('same-line rows first', sheet[0].bookmaker === 'betmgm' && sheet[1].bookmaker === 'draftkings');
check('BetMGM is Best', sheet[0].isBest);
check(
  'other lines follow in the given order, never Best',
  sheet[2].bookmaker === 'fanduel' && sheet[3].bookmaker === 'fanatics'
    && sheet.slice(2, 4).every((r) => r.otherLine && !r.isBest),
);
check('other line row carries its bet', sheet[2].lineText === 'Coppin State +11.5');
check('Caesars, with nothing, is a dash row last', sheet[4].bookmaker === 'williamhill_us' && sheet[4].price == null);
check('no book listed twice', new Set(sheet.map((r) => r.bookmaker)).size === sheet.length);

if (failures > 0) {
  console.log(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nAll checks passed.');
