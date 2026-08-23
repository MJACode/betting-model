import { Alert, Linking, Platform } from 'react-native';

import { bookName, MODEL_BOOK } from '@/lib/markets';
import { colors } from '@/lib/theme';

/**
 * Sportsbook hand-off.
 *
 * No book exposes a public API to place a bet programmatically — the only
 * viable "send this bet to my book" path is a pre-filled betslip deep link that
 * opens the book's app (or web) with the selection populated; the user taps
 * "Place Bet" themselves. Those links come from The Odds API
 * (includeLinks=true) and are stored per outcome per book, so we can hand off
 * to whichever book the user actually bets at — not just DraftKings.
 *
 * DraftKings is still the book the MODELS price against; this module is purely
 * about where the user places the bet.
 */

/** Where each book's betslip link can fall back to when we have no link. */
interface BookApp {
  /** Custom URL scheme, when we have a verified one. Others fall through to web
   *  rather than guessing a scheme that would silently fail. */
  scheme: string | null;
  web: string;
  /** Store page — only carried for books whose listing we've verified. */
  store: string | null;
}

// Keyed loosely: NFL card picks name whichever book the standalone nfl/ package
// line-shopped (see markets.storedQuoteBook), which can be a book we don't carry
// in LINE_SHOP_BOOKS. Those fall back to DraftKings' entry below rather than
// crashing — the label still names the real book so the user isn't misled.
const BOOK_APPS: Record<string, BookApp> = {
  draftkings: {
    scheme: 'dksb://',
    web: 'https://sportsbook.draftkings.com/',
    store:
      Platform.OS === 'ios'
        ? 'https://apps.apple.com/us/app/draftkings-sportsbook-casino/id1375031369'
        : 'https://play.google.com/store/apps/details?id=com.draftkings.sportsbook',
  },
  fanduel: { scheme: null, web: 'https://sportsbook.fanduel.com/', store: null },
  betmgm: { scheme: null, web: 'https://sports.betmgm.com/', store: null },
  williamhill_us: { scheme: null, web: 'https://sportsbook.caesars.com/', store: null },
  espnbet: { scheme: null, web: 'https://espnbet.com/', store: null },
};

/**
 * Button colors per book.
 *
 * DraftKings keeps its brand green (shipped and verified). Every other book
 * uses the app's own tint rather than an approximated brand hex — a wrong
 * brand color that fails contrast is worse than a consistent one.
 */
export const DK_GREEN = '#53D337';

export function bookButtonColors(book: string): { bg: string; fg: string } {
  return book === 'draftkings'
    ? { bg: DK_GREEN, fg: '#000' }
    : { bg: colors.tint, fg: '#fff' };
}

// The button's label ("Bet on FanDuel") lives in markets.ts alongside the book
// names, so it stays importable from plain-Node verify scripts.
export { betOnBookLabel } from '@/lib/markets';

async function tryOpen(url: string, isScheme = false): Promise<boolean> {
  try {
    const supported = await Linking.canOpenURL(url);
    // canOpenURL is unreliable for https on some platforms — attempt anyway for
    // web URLs, but trust it for custom schemes.
    if (!supported && isScheme) return false;
    await Linking.openURL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Open a pre-filled betslip at `book`.
 *
 * Fallback chain: the betslip link → the book's app (where we have a verified
 * scheme) → the book's website → its store page. Returns true once something
 * opened.
 */
export async function openBookBetslip(
  book: string,
  link: string | null | undefined,
): Promise<boolean> {
  if (link && link.trim()) {
    if (await tryOpen(link.trim())) return true;
  }

  const app = BOOK_APPS[book] ?? BOOK_APPS[MODEL_BOOK];
  if (app.scheme && (await tryOpen(app.scheme, true))) return true;
  if (await tryOpen(app.web)) return true;
  if (app.store && (await tryOpen(app.store))) return true;

  Alert.alert(
    `Could not open ${bookName(book)}`,
    `We couldn’t open the ${bookName(book)} app or website on this device.`,
  );
  return false;
}

/**
 * DraftKings hand-off. Parlays are priced leg-by-leg off DraftKings odds, so
 * that flow hands off to DK regardless of the user's display preference.
 */
export function openBetslip(link: string | null | undefined): Promise<boolean> {
  return openBookBetslip(MODEL_BOOK, link);
}
