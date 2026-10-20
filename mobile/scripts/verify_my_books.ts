/**
 * Standalone verification for the member's own sportsbooks (lib/myBooks.ts
 * and bestHandoffForPick's allowedBooks). Run with:
 *
 *   npx tsx scripts/verify_my_books.ts
 *
 * Pins (Matt, 2026-10-19): a pick found at a book the member does not use is
 * shown at THEIR best book with the edge and return worked out there; a pick
 * none of their books has is 'none' and gets no hand-off; the record book's
 * own case is unchanged; and the hand-off never names a book outside the set.
 */

import { bestHandoffForPick, currentLineQuotes, MODEL_BOOK } from '../src/lib/markets';
import { edgeAtPrice, evAtPrice, myBooksView, quotesAtMyBooks } from '../src/lib/myBooks';
import type { BookPricedRow, Pick, PickSide } from '../src/types';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}
const near = (a: number | null, b: number) => a != null && Math.abs(a - b) < 1e-9;

function mkPick(over: Partial<Pick> = {}): Pick {
  return {
    pick_id: 1,
    game_id: 'MLB_2026-09-13_NYJ_BUF',
    model_id: 'mlb_over_under',
    sport: 'MLB',
    game_date: '2026-09-13',
    pick_side: 'over' as PickSide,
    pick_label: 'NYJ @ BUF Over 8.5',
    model_probability: 0.598,
    dk_implied_prob: 0.476,
    edge: 0.122,
    dk_odds: 100,
    scored_line: 8.5,
    signal_type: 'BET',
    is_live: false,
    dk_bet_link: 'dk://lock',
    // Decided at Hard Rock +110, the screenshot's Dvorak card.
    decision_odds: 110,
    decision_edge: 0.122,
    decision_book: 'hardrockbet',
    line_book: null,
    ...over,
  } as Pick;
}

const rows: BookPricedRow[] = [
  { bookmaker: 'hardrockbet', over_price: 110, total_line: 8.5, over_link: 'hrb://x' },
  { bookmaker: 'draftkings', over_price: 100, total_line: 8.5, over_link: 'dk://x' },
  { bookmaker: 'fanduel', over_price: -105, total_line: 8.5, over_link: 'fd://x' },
  // Same book, a different number: never the same bet.
  { bookmaker: 'betmgm', over_price: 120, total_line: 9.5, over_link: 'mgm://x' },
];

// ── the arithmetic matches how decision_edge is stored ───────────────────────
check('edge at +110 is p − 1/2.1', near(edgeAtPrice(0.598, 110), 0.598 - 1 / 2.1));
check('EV at −105 is p × (1 + 100/105) − 1', near(evAtPrice(0.598, -105), 0.598 * (1 + 100 / 105) - 1));

// ── quotesAtMyBooks ──────────────────────────────────────────────────────────
{
  const pick = mkPick();
  const all = currentLineQuotes(pick, rows);
  const mine = quotesAtMyBooks(all, ['fanduel', 'draftkings']);
  check('only their books survive, best payout first',
    JSON.stringify(mine.map((q) => q.bookmaker)) === JSON.stringify(['draftkings', 'fanduel']),
    JSON.stringify(mine.map((q) => q.bookmaker)));
  check('a book at a different line is never a quote', !all.some((q) => q.bookmaker === 'betmgm'));
}

// ── myBooksView ──────────────────────────────────────────────────────────────
{
  const pick = mkPick();
  const quotes = currentLineQuotes(pick, rows);
  const view = myBooksView({ quotes, recordBook: 'hardrockbet', myBooks: ['draftkings', 'fanduel'], modelProbability: 0.598 });
  check("found at HRB, member has DK + FD → 'mine' at DK +100", view.status === 'mine' && view.best?.bookmaker === 'draftkings' && view.best.price === 100, JSON.stringify(view.best));
  check('…edge recalculated at +100 (0.098), not the stored 0.122', near(view.edge, 0.598 - 0.5), String(view.edge));
  check('…EV recalculated at +100', near(view.ev, 0.598 * 2 - 1), String(view.ev));

  const own = myBooksView({ quotes, recordBook: 'hardrockbet', myBooks: ['hardrockbet', 'fanduel'], modelProbability: 0.598 });
  check("member has the record book → 'record', no recalculated numbers", own.status === 'record' && own.edge == null && own.ev == null);

  const none = myBooksView({ quotes, recordBook: 'hardrockbet', myBooks: ['betrivers'], modelProbability: 0.598 });
  check("none of their books has it → 'none'", none.status === 'none' && none.best == null && none.quotes.length === 0);

  const mgmOnly = myBooksView({ quotes, recordBook: 'hardrockbet', myBooks: ['betmgm'], modelProbability: 0.598 });
  check("their only book is at a different line → 'none', never MGM's 9.5", mgmOnly.status === 'none');
}

// ── bestHandoffForPick(allowedBooks) ─────────────────────────────────────────
{
  const pick = mkPick();
  const free = bestHandoffForPick(pick, rows);
  check('no set: the hand-off is the best book overall (HRB +110)', free?.bookmaker === 'hardrockbet' && free.price === 110, JSON.stringify(free));
  const dkFd = bestHandoffForPick(pick, rows, null, undefined, ['draftkings', 'fanduel']);
  check('DK + FD: hand-off is DK +100, never HRB', dkFd?.bookmaker === 'draftkings' && dkFd.price === 100, JSON.stringify(dkFd));
  const fdOnly = bestHandoffForPick(pick, rows, null, undefined, ['fanduel']);
  check('FD only: "Bet FD −105" (one book, so not "Best")', fdOnly?.bookmaker === 'fanduel' && fdOnly.price === -105 && fdOnly.verb === 'Bet', JSON.stringify(fdOnly));
  const nothing = bestHandoffForPick(pick, rows, null, undefined, ['betrivers']);
  check('no book of theirs: no hand-off at all', nothing == null, JSON.stringify(nothing));
}
{
  // Live picks are DraftKings only: a member without DK gets no live hand-off.
  const live = mkPick({ is_live: true, decision_book: 'draftkings', decision_odds: -110 });
  check('live, member has DK → DK', bestHandoffForPick(live, [], null, undefined, [MODEL_BOOK])?.bookmaker === MODEL_BOOK);
  check('live, member lacks DK → no hand-off', bestHandoffForPick(live, [], null, undefined, ['fanduel']) == null);
}

if (failures > 0) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log('\nAll my-books checks passed.');
