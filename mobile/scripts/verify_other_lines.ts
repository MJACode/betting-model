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
 *   6. The DECIDING book whose line has moved is not listed at the lock
 *      (Matt, 2026-11-15, "GB -3.5", FanDuel -110): its rung at the pick's
 *      number at today's price, or else its line now as a different line.
 */

import {
  bestHandoffForPick,
  decidingBookOnlyAtMovedLine,
  currentLineQuotes,
  gameRowsForPick,
  handoffQuotesForPick,
  heroAmericanForPick,
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

// 6 ─ the deciding book has moved its line (production rows, 2026-11-15
// 14:17 UTC, NFL_2026_10_MIN_GB). The card said "FD line now −2.5 (−120)"
// and the sheet listed FanDuel −110 as if it still had −3.5 at the lock.
{
  const gb = {
    pick_id: 4375914,
    game_id: 'NFL_2026_10_MIN_GB',
    model_id: 'nfl_opener_spread',
    sport: 'NFL',
    game_date: '2026-11-15',
    pick_side: 'home' as PickSide,
    pick_label: 'MIN @ GB — GB -3.5 · NEW 0m',
    model_probability: 0.556,
    dk_odds: -110,
    scored_line: -3.5,
    signal_type: 'BET',
    is_live: false,
    decision_odds: -110,
    decision_book: 'fanduel',
    line_book: null,
  } as unknown as Pick;
  const gbMain: Row[] = [
    { market: 'spreads', bookmaker: 'betmgm', spread_home: -2.5, home_price: -118, home_link: 'mgm://m' },
    { market: 'spreads', bookmaker: 'draftkings', spread_home: -3, home_price: -102, home_link: 'dk://m' },
    { market: 'spreads', bookmaker: 'fanatics', spread_home: -2.5, home_price: -120, home_link: null },
    { market: 'spreads', bookmaker: 'fanduel', spread_home: -2.5, home_price: -120, home_link: 'fd://m' },
    { market: 'spreads', bookmaker: 'williamhill_us', spread_home: -2.5, home_price: -121, home_link: 'czr://m' },
  ];
  const gbLadder: Row[] = [
    { market: 'alternate_spreads', bookmaker: 'betmgm', spread_home: -3.5, home_price: 110, home_link: 'mgm://a35' },
    { market: 'alternate_spreads', bookmaker: 'draftkings', spread_home: -3.5, home_price: 104, home_link: 'dk://a35' },
    { market: 'alternate_spreads', bookmaker: 'fanatics', spread_home: -3.5, home_price: 115, home_link: null },
    { market: 'alternate_spreads', bookmaker: 'fanduel', spread_home: -3.5, home_price: 108, home_link: 'fd://a35' },
  ];
  const sheetFor = (rows: BookPricedRow[]) => {
    const hero = heroAmericanForPick(gb, null, rows);
    const quotes = handoffQuotesForPick(gb, rows, hero, undefined, myBooks);
    const others = otherLineQuotesForPick(gb, rows, myBooks)
      .map((q) => ({ ...q, lineText: `GB ${q.line}` }));
    return { hero, handoff: bestHandoffForPick(gb, rows, hero, undefined, myBooks), sheet: pickSportsbookRows(quotes, myBooks, others) };
  };

  // FanDuel still has −3.5, on its ladder, at +108.
  const withRung = sheetFor(gameRowsForPick(gb, 'spreads', [...gbMain, ...gbLadder]));
  check('the card sees FanDuel at −2.5 (−120) now', withRung.hero?.movedLine === -2.5 && withRung.hero?.price === -120);
  const fdRung = withRung.sheet.find((r) => r.bookmaker === 'fanduel');
  check(
    'FanDuel is listed at its −3.5 price today, +108, not the −110 lock',
    fdRung?.price === 108 && fdRung.otherLine === false,
    `${fdRung?.price} otherLine=${fdRung?.otherLine}`,
  );
  check('and opens its −3.5 rung', fdRung?.link === 'fd://a35', String(fdRung?.link));
  check('Fanatics +115 is still Best and the hand-off', withRung.sheet[0].bookmaker === 'fanatics' && withRung.sheet[0].isBest
    && withRung.handoff?.bookmaker === 'fanatics' && withRung.handoff?.price === 115);
  const czr = withRung.sheet.find((r) => r.bookmaker === 'williamhill_us');
  check('Caesars, with no −3.5, is at its own line', czr?.otherLine === true && czr.price === -121);
  check('no book listed twice', new Set(withRung.sheet.map((r) => r.bookmaker)).size === withRung.sheet.length);

  // FanDuel has no −3.5 at all: its row is its line now, like Caesars.
  const noRung = sheetFor(gameRowsForPick(gb, 'spreads', [...gbMain, ...gbLadder.filter((r) => r.bookmaker !== 'fanduel')]));
  const fdMoved = noRung.sheet.find((r) => r.bookmaker === 'fanduel');
  check(
    'no −3.5 at FanDuel: listed at −2.5 (−120) as a different line',
    fdMoved?.otherLine === true && fdMoved.price === -120 && fdMoved.lineText === 'GB -2.5' && !fdMoved.isBest,
    `${fdMoved?.price} otherLine=${fdMoved?.otherLine} ${fdMoved?.lineText}`,
  );
  check('and opens the −2.5 row, not the lock slip', fdMoved?.link === 'fd://m', String(fdMoved?.link));
  check('the hand-off is never FanDuel at the lock', noRung.handoff?.bookmaker === 'fanatics');

  // The deciding book best at its rung: the hand-off is the rung, never the
  // moved line's price on the control.
  const fdBest = sheetFor(gameRowsForPick(gb, 'spreads', [
    ...gbMain,
    ...gbLadder.map((r) => (r.bookmaker === 'fanduel' ? { ...r, home_price: 125 } : r)),
  ]));
  check(
    'FanDuel best at its rung hands off to +125 at −3.5',
    fdBest.handoff?.bookmaker === 'fanduel' && fdBest.handoff.price === 125 && fdBest.handoff.link === 'fd://a35',
    JSON.stringify(fdBest.handoff),
  );

  check('rung: a FanDuel hand-off is the pick\'s own bet', !decidingBookOnlyAtMovedLine(gb, gameRowsForPick(gb, 'spreads', [...gbMain, ...gbLadder]), withRung.hero));
  check('no rung: a FanDuel hand-off is its moved line', decidingBookOnlyAtMovedLine(gb, gameRowsForPick(gb, 'spreads', gbMain), noRung.hero));

  // DraftKings decided it, its line moved on the latest-DK row, and the
  // all-books rows hold no DraftKings row: the lock chip stays (no dash).
  {
    const dkPick = { ...gb, decision_book: 'draftkings' } as Pick;
    const rows = gameRowsForPick(dkPick, 'spreads', [...gbMain, ...gbLadder].filter((r) => r.bookmaker !== 'draftkings'));
    const latest = { market: 'spreads', bookmaker: 'draftkings', spread_home: -2.5, home_price: -120 } as never;
    const hero = heroAmericanForPick(dkPick, latest, rows);
    const sheet = pickSportsbookRows(
      handoffQuotesForPick(dkPick, rows, hero, undefined, myBooks), myBooks,
      otherLineQuotesForPick(dkPick, rows, myBooks).map((q) => ({ ...q, lineText: `GB ${q.line}` })),
    );
    const dk = sheet.find((r) => r.bookmaker === 'draftkings');
    check('moved on the latest row only: DraftKings is not a dash', hero?.movedLine === -2.5 && dk?.price != null, `${hero?.movedLine} ${dk?.price}`);
  }

  // A deciding book we hold no row for keeps its lock chip (missing ≠ moved).
  const noFd = gameRowsForPick(gb, 'spreads', [...gbMain, ...gbLadder].filter((r) => r.bookmaker !== 'fanduel'));
  check(
    'no FanDuel row at all: not offered as another line',
    !otherLineQuotesForPick(gb, noFd, myBooks).some((q) => q.bookmaker === 'fanduel'),
  );
}

if (failures > 0) {
  console.log(`\n${failures} check(s) FAILED`);
  process.exit(1);
}
console.log('\nAll checks passed.');
