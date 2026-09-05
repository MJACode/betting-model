import { Alert, Linking, Platform } from 'react-native';

import { getBettingState } from '@/hooks/useBettingState';
import { fillBetslipLink, linkNeedsState } from '@/lib/betslipLinks';
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
  // App Store pages (2026-09-04, Matt: "If I don't have the Sportsbook for
  // one of them it should take me to the App Store to download it"). Every
  // id below is Apple's own, taken from the apps.apple.com URL of the book's
  // listing — none is guessed. iOS only: Google Play package names are not
  // verified, so Android keeps the web fallback.
  fanduel: { scheme: null, web: 'https://sportsbook.fanduel.com/', store: ios('id1413721906') },
  betmgm: { scheme: null, web: 'https://sports.betmgm.com/', store: ios('id1430875409') },
  williamhill_us: { scheme: null, web: 'https://sportsbook.caesars.com/', store: ios('id1413099571') },
  espnbet: { scheme: null, web: 'https://espnbet.com/', store: null },
  bovada: { scheme: null, web: 'https://www.bovada.lv/', store: null },
  pinnacle: { scheme: null, web: 'https://www.pinnacle.com/', store: null },
  // The five us2-region books + Fanatics (config.py, 2026-09-03). No verified
  // schemes. The per-outcome betslip link from the odds feed is the primary
  // route; the store and then the site are the fallbacks when a row carries
  // no link.
  fanatics: { scheme: null, web: 'https://sportsbook.fanatics.com/', store: ios('id1616738407') },
  betrivers: { scheme: null, web: 'https://www.betrivers.com/', store: ios('id1635357259') },
  hardrockbet: { scheme: null, web: 'https://www.hardrock.bet/', store: ios('id1572525917') },
  ballybet: { scheme: null, web: 'https://www.ballybet.com/', store: ios('id1590852096') },
  // betPARX ships one app PER STATE (MD, PA, NJ) — resolved from the member's
  // state below; with none set there is no single page to send them to.
  betparx: { scheme: null, web: 'https://www.betparx.com/', store: null },
  rebet: { scheme: null, web: 'https://play.rebet.app/', store: ios('id6468762763') },
};

/** An App Store page, iOS only (the id is Apple's; see BOOK_APPS). */
function ios(id: string): string | null {
  return Platform.OS === 'ios' ? `https://apps.apple.com/us/app/${id}` : null;
}

const BETPARX_STORE_BY_STATE: Record<string, string> = {
  md: 'id1662448269',
  pa: 'id1605805308',
  nj: 'id1605805764',
};

/** The App Store page for a book, when we hold Apple's own id for it. */
export function bookStoreUrl(book: string, state: string | null = getBettingState()): string | null {
  if (book === 'betparx') {
    const id = state ? BETPARX_STORE_BY_STATE[state] : undefined;
    return id ? ios(id) : null;
  }
  return BOOK_APPS[book]?.store ?? null;
}

/**
 * Button colors per book.
 *
 * DraftKings keeps its brand green (shipped and verified). Every other book
 * uses the app's own tint rather than an approximated brand hex — a wrong
 * brand color that fails contrast is worse than a consistent one.
 */
export const DK_GREEN = colors.bookDraftKings;

export function bookButtonColors(book: string): { bg: string; fg: string } {
  return book === 'draftkings'
    ? { bg: DK_GREEN, fg: '#000' }
    : { bg: colors.tint, fg: '#fff' };
}

// The button's label ("Bet on FanDuel") lives in markets.ts alongside the book
// names, so it stays importable from plain-Node verify scripts.
export { betOnBookLabel } from '@/lib/markets';

export { fillBetslipLink, linkNeedsState } from '@/lib/betslipLinks';

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
 * Fallback chain: the betslip link (placeholders filled) → the book's app
 * (where we have a verified scheme) → its App Store page → the book's
 * website. Returns true once something opened.
 *
 * WHAT CANNOT BE DETECTED: whether the app is installed. iOS answers
 * canOpenURL only for schemes declared in LSApplicationQueriesSchemes, and the
 * build declares none, so a filled universal link is opened and iOS itself
 * decides — the app when it is installed, Safari when it is not. The hand-off
 * sheet therefore also offers the store page outright (ParlayDkHandoff).
 */
export async function openBookBetslip(
  book: string,
  link: string | null | undefined,
): Promise<boolean> {
  if (link && link.trim()) {
    const filled = fillBetslipLink(link, getBettingState());
    if (filled) {
      if (await tryOpen(filled)) return true;
    } else if (linkNeedsState(link)) {
      // The link is a template and the member has not said which state their
      // account is in. Say so once, then open the book's site rather than a
      // URL that cannot resolve.
      Alert.alert(
        `Which state do you bet in?`,
        `${bookName(book)} links need your state to open the app with the bet on your slip. Set it under Settings → Your state.`,
      );
    }
  }

  const app = BOOK_APPS[book] ?? BOOK_APPS[MODEL_BOOK];
  if (app.scheme && (await tryOpen(app.scheme, true))) return true;
  // No usable link and no app scheme we can query: the STORE before the site.
  // A member who has the app sees its page with "Open"; one who does not is
  // where they need to be to get it (Matt, 2026-09-04) — the book's web root
  // helps neither, since the bet is not on it.
  const store = bookStoreUrl(book);
  if (store && (await tryOpen(store))) return true;
  if (await tryOpen(app.web)) return true;

  Alert.alert(
    `Could not open ${bookName(book)}`,
    `We couldn’t open the ${bookName(book)} app or website on this device.`,
  );
  return false;
}

/**
 * The DraftKings-specific hand-off. The parlay flow does NOT come through here:
 * it chooses its book with `handoffBookFor` (the member's own book when it
 * prices every leg, else DraftKings) and opens it via openBookBetslip.
 */
export function openBetslip(link: string | null | undefined): Promise<boolean> {
  return openBookBetslip(MODEL_BOOK, link);
}
