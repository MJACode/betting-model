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
  /** Custom URL scheme, when we have a VERIFIED one (DraftKings, session 47).
   *  It opens the app, and its `canOpenURL` answer is trusted both ways —
   *  `false` means not installed. */
  scheme: string | null;
  /** UNVERIFIED schemes the book's app may register (Matt, 2026-09-05: "This
   *  should be the same for all the Sportsbook apps" — and no public source
   *  names any book's scheme but DraftKings'). Used to ASK only, never to
   *  open: a `true` from any of them proves the app is installed, since iOS
   *  answers `true` only for a scheme some installed app registered; a `false`
   *  proves nothing — the guess may simply be wrong — and leaves the answer
   *  unknown, which is today's behaviour. So a wrong guess costs nothing and
   *  a right one opens the app. Every entry, verified or not, must be declared
   *  in app.json's `LSApplicationQueriesSchemes` or iOS answers `false`
   *  regardless (verify_book_links.ts pins it; Apple caps the list at 50). */
  candidateSchemes?: string[];
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
  fanduel: { scheme: null, candidateSchemes: ['fanduelsportsbook', 'fanduel-sportsbook', 'fdsportsbook', 'fanduel'], web: 'https://sportsbook.fanduel.com/', store: ios('id1413721906') },
  betmgm: { scheme: null, candidateSchemes: ['betmgm', 'betmgmsports', 'betmgm-sports'], web: 'https://sports.betmgm.com/', store: ios('id1430875409') },
  williamhill_us: { scheme: null, candidateSchemes: ['caesarssportsbook', 'caesars', 'williamhill', 'czrsportsbook'], web: 'https://sportsbook.caesars.com/', store: ios('id1413099571') },
  espnbet: { scheme: null, web: 'https://espnbet.com/', store: null },
  bovada: { scheme: null, web: 'https://www.bovada.lv/', store: null },
  pinnacle: { scheme: null, web: 'https://www.pinnacle.com/', store: null },
  // The five us2-region books + Fanatics (config.py, 2026-09-03). No verified
  // schemes. The per-outcome betslip link from the odds feed is the primary
  // route; the store and then the site are the fallbacks when a row carries
  // no link.
  fanatics: { scheme: null, candidateSchemes: ['fanaticssportsbook', 'fanatics-sportsbook', 'fanaticsbet'], web: 'https://sportsbook.fanatics.com/', store: ios('id1616738407') },
  betrivers: { scheme: null, candidateSchemes: ['betrivers', 'betriverssportsbook'], web: 'https://www.betrivers.com/', store: ios('id1635357259') },
  hardrockbet: { scheme: null, candidateSchemes: ['hardrockbet', 'hardrocksportsbook'], web: 'https://www.hardrock.bet/', store: ios('id1572525917') },
  ballybet: { scheme: null, candidateSchemes: ['ballybet', 'ballybetsportsbook'], web: 'https://www.ballybet.com/', store: ios('id1590852096') },
  // betPARX ships one app PER STATE (MD, PA, NJ) — resolved from the member's
  // state below; with none set there is no single page to send them to.
  betparx: { scheme: null, candidateSchemes: ['betparx', 'betparxsportsbook'], web: 'https://www.betparx.com/', store: null },
  rebet: { scheme: null, candidateSchemes: ['rebet'], web: 'https://play.rebet.app/', store: ios('id6468762763') },
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

/** Open a book's App Store page, with the same failure path as the betslip
 *  hand-off (an Alert, never a silent no-op). */
export async function openBookStore(book: string, state: string | null = getBettingState()): Promise<boolean> {
  const store = bookStoreUrl(book, state);
  if (store && (await tryOpen(store))) return true;
  Alert.alert(`Could not open the App Store`, `We couldn’t open ${bookName(book)}’s App Store page on this device.`);
  return false;
}

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
 * Is the book's app on this phone? `true` / `false` when the build can ask,
 * `null` when it cannot — and an unknown is NOT a no.
 *
 * iOS answers `canOpenURL` for a custom scheme only when the scheme is
 * declared in the build's `LSApplicationQueriesSchemes` (app.json), and
 * answers `false` — indistinguishable from "not installed" — for any other.
 * So every scheme asked about here is declared there (verify_book_links.ts
 * pins it). A verified scheme (`scheme`) is trusted both ways; an unverified
 * candidate (`candidateSchemes`) only when it says yes — see BookApp. Android
 * needs a `<queries>` element the app does not declare, so it stays unknown
 * there. (Matt, 2026-09-05: "If I have the app for that Sportsbook, it should
 * just open my app" and "This should be the same for all the Sportsbook
 * apps.")
 */
export async function isBookAppInstalled(book: string): Promise<boolean | null> {
  const app = BOOK_APPS[book];
  if (!app || Platform.OS !== 'ios') return null;
  const verified = app.scheme ? [app.scheme] : [];
  const candidates = (app.candidateSchemes ?? []).map((c) => `${c}://`);
  if (verified.length === 0 && candidates.length === 0) return null;
  // A `true` from ANY scheme is proof: iOS says yes only for a scheme some
  // installed app registered. A `false` is proof only from the verified one.
  let verifiedSaidNo = false;
  for (const url of [...verified, ...candidates]) {
    try {
      if (await Linking.canOpenURL(url)) return true;
      if (verified.includes(url)) verifiedSaidNo = true;
    } catch {
      // asked and not answered: no evidence either way
    }
  }
  return verifiedSaidNo ? false : null;
}

/**
 * Open a pre-filled betslip at `book`.
 *
 * Whether the book's app is installed decides the route when the build can
 * tell (`isBookAppInstalled`):
 *
 *   installed  → the betslip link (a universal link iOS routes to the app,
 *                with the bet on the slip), else the app itself by its
 *                VERIFIED scheme (a candidate is never opened — it might be
 *                another app's), else the book's site, itself a universal
 *                link iOS routes to the app. Never the App Store: a member
 *                who has the app is sent to a page whose only button is
 *                "Open" (Matt, 2026-09-05, with that page on screen).
 *   not        → the App Store, whatever link we hold — the bet is not
 *                placeable without the app (Matt, 2026-09-04) — else the site.
 *   unknown    → link → store → site, the pre-detection chain: a filled
 *                universal link opens the app when it is there and Safari
 *                when it is not, and with no link the store is where a member
 *                without the app needs to be. The hand-off sheet also offers
 *                the store outright in this case (ParlayDkHandoff).
 *
 * Returns true once something opened.
 */
export async function openBookBetslip(
  book: string,
  link: string | null | undefined,
): Promise<boolean> {
  const app = BOOK_APPS[book] ?? BOOK_APPS[MODEL_BOOK];
  const installed = await isBookAppInstalled(book);

  if (installed === false) {
    const store = bookStoreUrl(book);
    if (store && (await tryOpen(store))) return true;
    if (await tryOpen(app.web)) return true;
    return couldNotOpen(book);
  }

  if (link && link.trim()) {
    const filled = fillBetslipLink(link, getBettingState());
    if (filled) {
      if (await tryOpen(filled)) return true;
    } else if (linkNeedsState(link)) {
      // The link is a template and the member has not said which state their
      // account is in. The alert is the WHOLE answer: falling through to the
      // store or the site would send them somewhere unrelated to the setting
      // they were just asked to change (UX review).
      Alert.alert(
        `Which state do you bet in?`,
        `${bookName(book)} links need your state to open the app with the bet on your slip. Set it under Settings → Your state.`,
      );
      return false;
    }
  }

  if (installed === true) {
    if (app.scheme && (await tryOpen(app.scheme, true))) return true;
    if (await tryOpen(app.web)) return true;
    return couldNotOpen(book);
  }

  // Unknown: the scheme cannot be queried on this build, so it is not tried.
  // The STORE before the site — a member who has the app sees its page with
  // "Open"; one who does not is where they need to be to get it (Matt,
  // 2026-09-04) — the book's web root helps neither, since the bet is not on
  // it.
  const store = bookStoreUrl(book);
  if (store && (await tryOpen(store))) return true;
  if (await tryOpen(app.web)) return true;
  return couldNotOpen(book);
}

function couldNotOpen(book: string): false {
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
