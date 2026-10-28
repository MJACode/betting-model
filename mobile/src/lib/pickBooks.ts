/**
 * Picks-card sportsbook sheet (Designer boards, Matt approved 2026-10-27).
 *
 * Selected books only, best payout first, then books with no price at this
 * bet. The Best pill is the price that pays most, and only when at least two
 * books have a price — one priced book is "Bet", not "Best".
 *
 * Pure. The card, the sheet and verify_pick_card.ts share this order.
 */
import { americanToDecimal } from './format';
import { LINES_NO_PRICE, linesPriceText } from './linesBoard';
import { bookLabel, bookName, LINE_SHOP_BOOKS, type LineQuote } from './markets';

export const PICK_BOOKS_NOTE =
  'Only books you selected. Best pays most. “—” = no price. Row or Bet opens that book.';

export interface PickSportsbookRow {
  bookmaker: string;
  /** Full name, the row. */
  name: string;
  /** Short label, the controls (DK, FD, HRB). */
  short: string;
  price: number | null;
  /** American odds with a true minus, or the em dash. */
  priceText: string;
  link: string | null;
  /** Wins the comparison. False when fewer than two books have a price. */
  isBest: boolean;
}

function shopOrder(book: string): number {
  const i = (LINE_SHOP_BOOKS as readonly string[]).indexOf(book);
  return i < 0 ? LINE_SHOP_BOOKS.length : i;
}

/**
 * `quotes` are the hand-off's ranked prices (handoffQuotesForPick), already
 * limited to the member's books. `selected` adds the rest of that set with
 * no price, in sportsbook order. Pass null to list only the quotes — a live
 * pick is DraftKings, and a dash would pretend the other books were shopped.
 */
export function pickSportsbookRows(
  quotes: readonly Pick<LineQuote, 'bookmaker' | 'price' | 'link' | 'isBest'>[],
  selected: readonly string[] | null,
): PickSportsbookRow[] {
  const priced = [...quotes].sort((a, b) => {
    const byPrice = americanToDecimal(b.price) - americanToDecimal(a.price);
    if (byPrice !== 0) return byPrice;
    if (a.isBest !== b.isBest) return a.isBest ? -1 : 1;
    return shopOrder(a.bookmaker) - shopOrder(b.bookmaker);
  });
  const seen = new Set(priced.map((q) => q.bookmaker));
  const missing = selected == null ? [] : selected.filter((book) => !seen.has(book));
  const compare = priced.length >= 2;
  const bestDecimal = compare ? americanToDecimal(priced[0].price) : null;
  const rows: PickSportsbookRow[] = priced.map((q) => ({
    bookmaker: q.bookmaker,
    name: bookName(q.bookmaker),
    short: bookLabel(q.bookmaker),
    price: q.price,
    priceText: linesPriceText(q.price),
    link: q.link,
    isBest: bestDecimal != null && americanToDecimal(q.price) === bestDecimal,
  }));
  for (const book of missing) {
    rows.push({
      bookmaker: book,
      name: bookName(book),
      short: bookLabel(book),
      price: null,
      priceText: LINES_NO_PRICE,
      link: null,
      isBest: false,
    });
  }
  return rows;
}
