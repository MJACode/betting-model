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

/** The one line that says the record is not at the member's price. */
export const RECORD_AT_BEST_BOOK_NOTE =
  'Model records and stats use the best price across all books.';

export const NOT_AT_MY_BOOKS = 'Not offered at your books';
