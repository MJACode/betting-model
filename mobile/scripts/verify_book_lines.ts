/**
 * Verifies the "Betting lines" row helpers in lib/markets.ts — the per-pick
 * chip row that replaced the single "Bet on DraftKings" button and the on-card
 * sportsbook switch (Matt, 2026-09-03).
 *
 * Run: npx tsx scripts/verify_book_lines.ts
 *
 * Pins:
 *   - the book list mirrors config.py: 13 fetched, 10 bettable, 3 reference
 *   - pickLineQuotes: same line only, bettable books only, the record chip is
 *     always present at the STORED price, the scorer's best-price stamp fills
 *     a missing book, best-first order with ties badged, live picks → DK only
 *   - selectLineChips: keeps best-first order, pins the record chip and the
 *     user's book when it must drop chips, reports how many it hid
 */

import {
  BETTABLE_BOOKS,
  LINE_SHOP_BOOKS,
  REFERENCE_ONLY_BOOKS,
  bookLabel,
  bookName,
  isBettableBook,
  pickLineQuotes,
  selectLineChips,
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
const books = (qs: { bookmaker: string }[]) => qs.map((q) => q.bookmaker).join(',');

// ── Book list mirrors config.py ─────────────────────────────────────────────
// config.LINE_SHOP_BOOKMAKERS (13) and BEST_LINE_EXCLUDE_BOOKMAKERS (3).
check('13 books fetched', LINE_SHOP_BOOKS.length === 13, `${LINE_SHOP_BOOKS.length}`);
check('3 reference-only books', REFERENCE_ONLY_BOOKS.length === 3);
check('10 bettable books', BETTABLE_BOOKS.length === 10, `${BETTABLE_BOOKS.length}`);
check('DraftKings is bettable', isBettableBook(MODEL_BOOK));
check('Pinnacle is not', !isBettableBook('pinnacle'));
check('Bovada is not', !isBettableBook('bovada'));
check('ESPN BET is not (mike, 2026-09-03)', !isBettableBook('espnbet'));
check('an unknown key is not bettable', !isBettableBook('somebook'));
check(
  'every book has a real name and a short label',
  LINE_SHOP_BOOKS.every((b) => bookName(b) !== b && bookLabel(b).length <= 5),
  LINE_SHOP_BOOKS.map((b) => `${b}=${bookLabel(b)}`).join(' '),
);
check('the six new books are named', bookName('fanatics') === 'Fanatics' && bookName('hardrockbet') === 'Hard Rock Bet' && bookName('betparx') === 'betPARX');

// ── Fixtures ────────────────────────────────────────────────────────────────
const totalsPick = (extra: Partial<Pick> = {}): Pick =>
  ({
    pick_side: 'under',
    dk_odds: -117,
    scored_line: 8.5,
    model_id: 'mlb_over_under',
    pick_label: 'CHC vs MIL Under 8.5',
    dk_bet_link: 'https://dk.example/under',
    best_book: null,
    best_odds: null,
    best_bet_link: null,
    is_live: null,
    ...extra,
  }) as unknown as Pick;

const totalsRows: BookPricedRow[] = [
  // DK's CURRENT snapshot has moved off the stored -117 — the chip must not follow it.
  { bookmaker: 'draftkings', under_price: -125, total_line: 8.5, under_link: 'https://dk.example/now' },
  { bookmaker: 'fanduel', under_price: -110, total_line: 8.5, under_link: 'https://fd.example/under' },
  { bookmaker: 'betmgm', under_price: 100, total_line: 8.5 },
  // Caesars hangs the same price off 9.0 — a DIFFERENT bet, never a chip.
  { bookmaker: 'williamhill_us', under_price: 105, total_line: 9 },
  // Pinnacle is the best number on the board and cannot be bet from the US.
  { bookmaker: 'pinnacle', under_price: 110, total_line: 8.5 },
  { bookmaker: 'espnbet', under_price: 102, total_line: 8.5 },
  // Fanatics has no line column at all on this row — can't confirm the bet.
  { bookmaker: 'fanatics', under_price: 101 },
  { bookmaker: 'betrivers', under_price: -112, total_line: 8.5 },
];

// ── pickLineQuotes ──────────────────────────────────────────────────────────
const q = pickLineQuotes(totalsPick(), totalsRows);
check('same-line, bettable books only', books(q) === 'betmgm,fanduel,betrivers,draftkings', books(q));
check('best first', q[0].bookmaker === 'betmgm' && q[0].isBest);
check('only the top payout is badged best', q.filter((x) => x.isBest).length === 1);
const dk = q.find((x) => x.bookmaker === MODEL_BOOK)!;
check('record chip is the STORED price, not the moved snapshot', dk.price === -117 && dk.isRecord, `${dk.price}`);
check('record chip carries the stored betslip link', dk.link === 'https://dk.example/under');
check('other chips carry their own links', q.find((x) => x.bookmaker === 'fanduel')?.link === 'https://fd.example/under');
check('Caesars at 9.0 is excluded (different bet)', !q.some((x) => x.bookmaker === 'williamhill_us'));
check('Pinnacle excluded even though it pays most', !q.some((x) => x.bookmaker === 'pinnacle'));
check('ESPN BET excluded', !q.some((x) => x.bookmaker === 'espnbet'));
check('a row with no line on a lined market is excluded', !q.some((x) => x.bookmaker === 'fanatics'));

// Ties: two books at the same payout are both best; record wins the tie order.
const tied = pickLineQuotes(
  totalsPick({ dk_odds: -110 }),
  [{ bookmaker: 'fanduel', under_price: -110, total_line: 8.5 }],
);
check('tied prices are both best', tied.length === 2 && tied.every((x) => x.isBest));
check('record chip sorts first in a tie', tied[0].bookmaker === MODEL_BOOK);

// Moneyline: no line to match on, so every bettable book prices in.
const mlRows: BookPricedRow[] = [
  { bookmaker: 'fanduel', home_price: 105 },
  { bookmaker: 'pinnacle', home_price: 108 },
  { bookmaker: 'hardrockbet', home_price: 102 },
];
const ml = pickLineQuotes(
  totalsPick({ pick_side: 'home', model_id: 'mlb_moneyline', scored_line: null, dk_odds: 100 }),
  mlRows,
);
check('moneyline needs no line match', books(ml) === 'fanduel,hardrockbet,draftkings', books(ml));

// No rows at all: the record chip alone (older picks, pruned odds).
const alone = pickLineQuotes(totalsPick(), []);
check('no rows → the record chip alone', alone.length === 1 && alone[0].isRecord && alone[0].isBest);
check('no price anywhere → no chips', pickLineQuotes(totalsPick({ dk_odds: null }), []).length === 0);

// The scorer's stamp fills a book today's rows don't carry — the same number
// the Discord post's "also … @ …" line quotes.
const stamped = pickLineQuotes(
  totalsPick({ best_book: 'betmgm', best_odds: 100, best_bet_link: 'https://mgm.example/stamp' }),
  [],
);
check('best_* stamp becomes a chip when the rows lack that book', books(stamped) === 'betmgm,draftkings', books(stamped));
check('stamp chip carries best_bet_link', stamped[0].link === 'https://mgm.example/stamp');
const stampedDup = pickLineQuotes(
  totalsPick({ best_book: 'fanduel', best_odds: -105 }),
  [{ bookmaker: 'fanduel', under_price: -110, total_line: 8.5 }],
);
check('a live row for the stamped book wins over the stamp', stampedDup.find((x) => x.bookmaker === 'fanduel')?.price === -110);
check(
  'a stamp naming a reference book is ignored',
  pickLineQuotes(totalsPick({ best_book: 'pinnacle', best_odds: 120 }), []).length === 1,
);

// Live: DraftKings only, whatever the rows say.
const live = pickLineQuotes(totalsPick({ is_live: true }), totalsRows);
check('live pick → the DK record chip only', live.length === 1 && live[0].bookmaker === MODEL_BOOK && live[0].isRecord);

// Prop rows resolve through the prop market's `line` column.
const prop = pickLineQuotes(
  totalsPick({ pick_side: 'over', model_id: 'mlb_prop_batter_hits', scored_line: 1.5, dk_odds: -130 }),
  [
    { bookmaker: 'fanduel', over_price: -115, line: 1.5 },
    { bookmaker: 'betmgm', over_price: -105, line: 0.5 },
  ],
);
check('prop chips match on the prop line', books(prop) === 'fanduel,draftkings', books(prop));

// NFL: the record chip is the card's soft book, at the stored price, and DK's
// own row is a normal chip beside it.
const nfl = pickLineQuotes(
  totalsPick({
    pick_side: 'away',
    model_id: 'nfl_opener_spread',
    pick_label: 'NYJ @ MIA — NYJ +5 (Opener -1.5 vs Pinnacle, MGM) · 1.00u',
    scored_line: -5,
    dk_odds: -124,
  }),
  [{ bookmaker: 'draftkings', away_price: -110, spread_home: -5 }],
);
check('NFL record chip is the soft book', nfl.some((x) => x.bookmaker === 'betmgm' && x.isRecord && x.price === -124));
check('DK is a normal chip on an NFL pick', nfl.some((x) => x.bookmaker === MODEL_BOOK && !x.isRecord));

// ── selectLineChips ─────────────────────────────────────────────────────────
const many = pickLineQuotes(
  totalsPick({ dk_odds: -120 }),
  [
    { bookmaker: 'fanduel', under_price: 100, total_line: 8.5 },
    { bookmaker: 'betmgm', under_price: -105, total_line: 8.5 },
    { bookmaker: 'williamhill_us', under_price: -108, total_line: 8.5 },
    { bookmaker: 'fanatics', under_price: -110, total_line: 8.5 },
    { bookmaker: 'betrivers', under_price: -112, total_line: 8.5 },
    { bookmaker: 'hardrockbet', under_price: -115, total_line: 8.5 },
  ],
);
check('fixture: 7 quotes, DK last', many.length === 7 && many[6].bookmaker === MODEL_BOOK);

const fits = selectLineChips(many.slice(0, 3), MODEL_BOOK, 4);
check('everything fits → nothing hidden', fits.shown.length === 3 && fits.hidden === 0);

const dkUser = selectLineChips(many, MODEL_BOOK, 4);
check('DK user: record chip kept even though it ranks last', dkUser.shown.some((x) => x.bookmaker === MODEL_BOOK));
// Top 4 by payout are FD, MGM, CZR, FAN; DK (rank 7) is pinned, so the weakest
// of those four — Fanatics — gives up its slot.
check('DK user: the weakest shown chip gave up its slot', !dkUser.shown.some((x) => x.bookmaker === 'fanatics'), books(dkUser.shown));
check('DK user: best-first order preserved', books(dkUser.shown) === 'fanduel,betmgm,williamhill_us,draftkings', books(dkUser.shown));
check('DK user: hidden count', dkUser.hidden === 3, `${dkUser.hidden}`);

const hrUser = selectLineChips(many, 'hardrockbet', 4);
check(
  'Hard Rock user: both their book and the record chip are pinned',
  hrUser.shown.some((x) => x.bookmaker === 'hardrockbet') && hrUser.shown.some((x) => x.bookmaker === MODEL_BOOK),
  books(hrUser.shown),
);
check('Hard Rock user: the best price is still first', hrUser.shown[0].bookmaker === 'fanduel');
check('Hard Rock user: still 4 chips', hrUser.shown.length === 4 && hrUser.hidden === 3);

const pinUser = selectLineChips(many, 'pinnacle', 4);
check('a preferred book with no chip changes nothing', books(pinUser.shown) === books(dkUser.shown));

console.log(`\n${passed} passed, ${failed} failed`);
process.exit(failed > 0 ? 1 : 0);
