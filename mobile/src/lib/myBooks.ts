/**
 * What a pick looks like to ONE member, given the sportsbooks they use
 * (Matt, 2026-10-19: "if someone doesn't have that Sportsbook in their state
 * we shouldn't show it").
 *
 * DISPLAY ONLY. The pick, its stored price, its edge, its stake, the record
 * and every published surface stay at the best bettable book (CLAUDE.md §6,
 * §1c). This only chooses which of the prices we already hold the card shows,
 * and works the edge and expected return out again at that price, so the
 * number on screen is the bet the member can actually place.
 *
 * Three outcomes:
 *   - 'record': the book the pick was found at is one of theirs. The card is
 *     unchanged.
 *   - 'mine':   it is not, but one of their books has the SAME bet (same
 *     side, same line). The card shows their best price, with the edge and
 *     return at that price, and says where the model found it.
 *   - 'none':   none of their books has it. The pick still shows (the app,
 *     Discord and push show the same picks), marked "Not offered at your
 *     books", with no bet button.
 */

/** The fields of a line quote this module reads (markets.LineQuote). */
export interface QuoteLike {
  bookmaker: string;
  price: number;
  link: string | null;
  line: number | null;
  isRecord: boolean;
}

export type MyBooksStatus = 'record' | 'mine' | 'none';

export interface MyBooksView<Q extends QuoteLike = QuoteLike> {
  status: MyBooksStatus;
  /** Their best same-bet quote. Null on 'none'. On 'record' it is the best of
   *  their books, which may be the record book or a better one of theirs. */
  best: Q | null;
  /** Every same-bet quote at their books, best payout first. */
  quotes: Q[];
  /** Edge and expected return at `best.price` on 'mine'. Null otherwise
   *  (the card keeps the pick's own numbers). */
  edge: number | null;
  ev: number | null;
}

function toDecimal(american: number): number {
  return american > 0 ? 1 + american / 100 : 1 + 100 / Math.abs(american);
}

/** model_probability − implied(price): how decision_edge is computed. */
export function edgeAtPrice(modelProbability: number, american: number): number {
  return modelProbability - 1 / toDecimal(american);
}

/** model_probability × decimal − 1: how the card's expected return is computed. */
export function evAtPrice(modelProbability: number, american: number): number {
  return modelProbability * toDecimal(american) - 1;
}

/** The quotes at the member's books, best payout first. A book they have not
 *  chosen is dropped, the record book included. */
export function quotesAtMyBooks<Q extends QuoteLike>(
  quotes: readonly Q[],
  myBooks: readonly string[],
): Q[] {
  const mine = new Set(myBooks);
  return quotes
    .filter((q) => mine.has(q.bookmaker))
    .slice()
    .sort((a, b) => toDecimal(b.price) - toDecimal(a.price));
}

/**
 * The member's view of one pick.
 *
 * `quotes` is every same-bet, still-current quote the card would offer
 * (markets.currentLineQuotes). `recordBook` is the book the pick was decided
 * at (markets.storedQuoteBook; DraftKings for a live pick).
 */
export function myBooksView<Q extends QuoteLike>(params: {
  quotes: readonly Q[];
  recordBook: string;
  myBooks: readonly string[];
  modelProbability: number;
}): MyBooksView<Q> {
  const { quotes, recordBook, myBooks, modelProbability } = params;
  const mine = quotesAtMyBooks(quotes, myBooks);
  const best = mine[0] ?? null;
  if (myBooks.includes(recordBook)) {
    return { status: 'record', best, quotes: mine, edge: null, ev: null };
  }
  if (best == null) {
    return { status: 'none', best: null, quotes: [], edge: null, ev: null };
  }
  return {
    status: 'mine',
    best,
    quotes: mine,
    edge: edgeAtPrice(modelProbability, best.price),
    ev: evAtPrice(modelProbability, best.price),
  };
}

/** "Found at HRB +110" — where the model's own number came from. */
export function foundAtText(bookShort: string, americanText: string): string {
  return `Found at ${bookShort} ${americanText}`;
}

/**
 * The record is kept at the price the pick was decided at, for EVERY model.
 *
 * It used to say "the best price across all books", with one model carved
 * out. That was false: the NCAAB moneyline model
 * (models/ncaab_moneyline_own_spread.py) bets the book with the largest edge,
 * and 269 of its 914 replayed bets sat at a book another book beat on price.
 * The true statement holds for every model, so there is one (2026-11-03).
 * `modelId` stays in the signature so the callers need not change.
 */
const RECORD_NOTE = 'Model records and stats use the price the model found, not your book’s.';

/** Pick Detail's record caption for a member whose own book has the bet. */
export function recordNoteFor(_modelId: string): string {
  return RECORD_NOTE;
}

/** The card's short form of recordNoteFor, after "Found at …". */
export function recordNoteShortFor(_modelId: string): string {
  return 'record kept at that price';
}

export const NOT_AT_MY_BOOKS = 'Not offered at your books';

/**
 * 'none' on an IN-PLAY pick. Its only quote is the deciding book's (a live
 * card carries no other book's price), so 'none' there means that book is not
 * one of theirs, not that none of their books has the bet: DraftKings may hold
 * the same side at the same number. Say what is true in every case.
 */
export function liveNotAtMyBooksText(bookShort: string, americanText: string): string {
  return `${foundAtText(bookShort, americanText)} · not one of your books`;
}
