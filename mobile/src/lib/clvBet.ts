/**
 * The price a pick's CLV is graded at, and the book it was taken at.
 *
 * mike, 2026-10-08: "grade CLV at the price taken". The CLV card prints the
 * bet side of `clv_pct`, so it must print the same price at the same book the
 * capture graded. This is tracking/paper_tracker._bet_price_and_book, line
 * for line:
 *
 *   1. `decision_book` with `decision_odds`, whenever the row carries them;
 *   2. the book the label names, for the four cards that store a soft book's
 *      price in `dk_odds` and name the book only in the label: the
 *      market-relative prop cards ("(FD)" suffix) and the NFL wind/opener
 *      cards ("(Wind 11 mph, FD)");
 *   3. DraftKings, at `dk_odds`.
 *
 * `clv_bet_book`, which every capture writes from 2026-10-08, names the book
 * the capture actually used and wins over the derivation. Rows captured
 * earlier carry NULL there, and for each of them the derivation returns the
 * book they were graded at (measured on every captured row, 2026-10-09).
 *
 * Only those four ids read a label. A parenthesis on any other label (a
 * "(F5)", say) is not a book. The ids and both label maps are pinned to
 * paper_tracker.py by tests/test_clv_card_price_taken.py.
 *
 * `clvLabelBook` is the same three steps without the price. Every other price
 * on the pick screens is named by markets.storedQuoteBook, which returns it,
 * so the header and the CLV card cannot name different books for one price.
 *
 * No imports on purpose: that test runs this file under Node directly, which
 * cannot resolve the app's extensionless imports.
 */

export const CLV_SUFFIX_LABEL_MODELS: readonly string[] = ['nfl_prop_market', 'wnba_prop_market'];
export const CLV_NFL_LABEL_MODELS: readonly string[] = ['nfl_wind_totals', 'nfl_opener_spread'];

// paper_tracker._LABEL_BOOK: the market-relative cards' suffix abbreviations.
export const CLV_SUFFIX_LABEL_BOOK: Readonly<Record<string, string>> = {
  DK: 'draftkings',
  FD: 'fanduel',
  MGM: 'betmgm',
  CZR: 'williamhill_us',
  ESPN: 'espnbet',
  PIN: 'pinnacle',
};

// paper_tracker._NFL_LABEL_BOOK: the NFL wind/opener publisher's abbreviations.
export const CLV_NFL_LABEL_BOOK: Readonly<Record<string, string>> = {
  DK: 'draftkings',
  FD: 'fanduel',
  MGM: 'betmgm',
  CZR: 'williamhill_us',
  ESPN: 'espnbet',
  BR: 'betrivers',
  BOV: 'bovada',
  PIN: 'pinnacle',
};

const SUFFIX_RE = /\(([A-Za-z_]+)\)\s*$/;
const NFL_RE = /,\s*([A-Za-z_]+)\)/;

export interface ClvBookRow {
  model_id?: string | null;
  pick_label?: string | null;
  decision_book?: string | null;
}

export interface ClvBetRow extends ClvBookRow {
  dk_odds?: number | null;
  decision_odds?: number | null;
  clv_bet_book?: string | null;
}

export interface ClvBetQuote {
  /** Book key ("betmgm"), or null when the row carries no price at all. */
  book: string | null;
  /** American odds the bet was taken at, or null. */
  price: number | null;
}

// An unmapped token is a raw book key ("(fliff)"), as on the server.
function fromLabel(token: string, map: Readonly<Record<string, string>>): string {
  return map[token.toUpperCase()] ?? token.toLowerCase();
}

/** The book and price the bet side of `clv_pct` is graded at. */
export function clvBetQuote(p: ClvBetRow): ClvBetQuote {
  const derived = derive(p);
  const recorded = String(p.clv_bet_book ?? '').trim().toLowerCase();
  if (recorded && derived.price != null) return { book: recorded, price: derived.price };
  return derived;
}

/**
 * The book a pick's stored price came from, without the price: the deciding
 * book, else the book the label names (the four label-priced models only),
 * else DraftKings.
 */
export function clvLabelBook(p: ClvBookRow): string {
  const decided = String(p.decision_book ?? '').trim().toLowerCase();
  return decided || labelBook(p);
}

function derive(p: ClvBetRow): ClvBetQuote {
  const decided = String(p.decision_book ?? '').trim().toLowerCase();
  if (p.decision_odds != null && decided) {
    return { book: decided, price: Number(p.decision_odds) };
  }
  if (p.dk_odds == null) return { book: null, price: null };
  return { book: labelBook(p), price: Number(p.dk_odds) };
}

// Steps 2 and 3: the book that owns `dk_odds`.
function labelBook(p: ClvBookRow): string {
  const model = p.model_id ?? '';
  const label = p.pick_label ?? '';
  if (CLV_SUFFIX_LABEL_MODELS.includes(model)) {
    const m = SUFFIX_RE.exec(label);
    return m ? fromLabel(m[1], CLV_SUFFIX_LABEL_BOOK) : 'draftkings';
  }
  if (CLV_NFL_LABEL_MODELS.includes(model)) {
    const m = NFL_RE.exec(label);
    if (m) return fromLabel(m[1], CLV_NFL_LABEL_BOOK);
  }
  return 'draftkings';
}
