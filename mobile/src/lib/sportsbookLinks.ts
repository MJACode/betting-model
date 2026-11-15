import { Alert, AppState, Linking, Platform } from 'react-native';

import { showToast } from '@/components/Toast';

import { getBettingState, loadBettingState } from '@/hooks/useBettingState';
import { appClaimedLink, fillBetslipLink, linkNeedsState } from '@/lib/betslipLinks';
import { noteHandoffMiss, type HandoffRoute } from '@/lib/handoffLog';
import { bookName, MODEL_BOOK } from '@/lib/markets';
import { openInAppAvailable, openUniversalLinkOnly } from '@/lib/openInApp';
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
   *  names any book's scheme but DraftKings'). Used to ASK, and opened in one case only
   *  (`installedBookScheme`: iOS has just refused the link the app claims):
   *  a `true` from any of them proves the app is installed, since iOS
   *  answers `true` only for a scheme some installed app registered; a `false`
   *  proves nothing — the guess may simply be wrong — and leaves the answer
   *  unknown, which is today's behaviour. So a wrong guess costs nothing and
   *  a right one opens the app. Every entry, verified or not, must be declared
   *  in app.json's `LSApplicationQueriesSchemes` or iOS answers `false`
   *  regardless (verify_book_links.ts pins it; Apple caps the list at 50).
   *  A candidate must name the SPORTSBOOK product, never the bare brand:
   *  `fanduel://` is as likely FanDuel's fantasy app, `betmgm://` its casino,
   *  `caesars://` its rewards app — and a yes from a sibling app would hide
   *  the store from the member it was meant for (UX review). */
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
  fanduel: { scheme: null, candidateSchemes: ['fanduelsportsbook', 'fanduel-sportsbook', 'fdsportsbook'], web: 'https://sportsbook.fanduel.com/', store: ios('id1413721906') },
  betmgm: { scheme: null, candidateSchemes: ['betmgmsports', 'betmgm-sports', 'betmgmsportsbook'], web: 'https://sports.betmgm.com/', store: ios('id1430875409') },
  williamhill_us: { scheme: null, candidateSchemes: ['caesarssportsbook', 'czrsportsbook', 'williamhillsportsbook'], web: 'https://sportsbook.caesars.com/', store: ios('id1413099571') },
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
    ? { bg: DK_GREEN, fg: colors.textPrimary }
    : { bg: colors.tint, fg: colors.textInverse };
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
  // Asked in parallel — this sits on the tap-to-open path (UX review).
  const ask = (url: string): Promise<boolean | null> =>
    Linking.canOpenURL(url).catch(() => null); // asked and not answered: no evidence either way
  const answers = await Promise.all([...verified, ...candidates].map(ask));
  if (answers.some((a) => a === true)) return true;
  const verifiedSaidNo = answers.slice(0, verified.length).some((a) => a === false);
  return verifiedSaidNo ? false : null;
}

/**
 * The scheme that says this book's app is installed, to OPEN the app with.
 * Null when none says yes.
 *
 * A candidate is a guess at the book's scheme, so it is opened in one case
 * only: iOS has just refused the link the book's app claims
 * (`openBookBetslip`), and this scheme answered yes, which iOS does only for
 * a scheme an installed app registered. Every candidate names the sportsbook
 * product, never the bare brand (BookApp), so that app is the book's.
 */
async function installedBookScheme(book: string): Promise<string | null> {
  const app = BOOK_APPS[book];
  if (!app || Platform.OS !== 'ios') return null;
  const schemes = [...(app.scheme ? [app.scheme] : []), ...(app.candidateSchemes ?? []).map((c) => `${c}://`)];
  const answers = await Promise.all(schemes.map((u) => Linking.canOpenURL(u).catch(() => false)));
  const i = answers.findIndex((a) => a === true);
  return i >= 0 ? schemes[i]! : null;
}

/**
 * Open a pre-filled betslip at `book`.
 *
 * Whether the book's app is installed decides the route when the build can
 * tell (`isBookAppInstalled`):
 *
 *   installed  → the betslip link (a universal link iOS routes to the app,
 *                with the bet on the slip). If iOS refuses that link, the
 *                app itself by the scheme that said it is installed
 *                (`installedBookScheme`). Else the stored link, the app by
 *                its VERIFIED scheme, the book's site. Never the App Store: a member
 *                who has the app is sent to a page whose only button is
 *                "Open" (Matt, 2026-09-05, with that page on screen).
 *   not        → the App Store, whatever link we hold — the bet is not
 *                placeable without the app (Matt, 2026-09-04) — else the site.
 *   unknown    → first, iOS is asked to open the link the book's app
 *                CLAIMS, in the app only (`appClaimedLink`, lib/openInApp.ts;
 *                Matt, 2026-11-14: "Make it open the App Store if I dont have
 *                the app or open the app if I have it"). Yes: the app is
 *                open. No: no installed app took it, so the App Store. A
 *                build that cannot ask (Android, or a binary older than the
 *                native module), or a book whose app claims no link we hold,
 *                keeps the old chain: link → store → site. The hand-off
 *                sheet also offers the store outright (ParlayDkHandoff).
 *
 * Returns true once something opened.
 */
export async function openBookBetslip(
  book: string,
  link: string | null | undefined,
  opts?: { sameBookOnly?: boolean },
): Promise<boolean> {
  // A control labelled for this book must not open another. Fliff decided
  // picks until 2026-09-20 (and is reference-only here from 2026-11-10,
  // markets.ts) and has no entry here; the fallback below is DraftKings, which
  // is the right hand-off for an unnamed NFL quote and the wrong one for a
  // Fliff row.
  if (opts?.sameBookOnly && !BOOK_APPS[book]) {
    return openThisBooksLinkOnly(book, link);
  }
  const app = BOOK_APPS[book] ?? BOOK_APPS[MODEL_BOOK];
  // Awaited, never the synchronous read: on the first tap after launch that
  // read is null and a member with a state set was asked for one.
  const state = await loadBettingState();
  const installed = await isBookAppInstalled(book);
  const claimed = appClaimedLink(book, link, state);
  let viaApp: boolean | null = null;
  // Every exit that is not "iOS opened the claimed link in the app" is
  // written down (lib/handoffLog.ts), for every book with an app entry.
  // `claimed` null is itself one of the causes, so it is logged too.
  const went = (route: HandoffRoute, ok: boolean, scheme?: string): boolean => {
    if (BOOK_APPS[book] && Platform.OS === 'ios') {
      noteHandoffMiss({ book, route, installed, claimed, viaApp, moduleInBinary: openInAppAvailable, scheme });
    }
    // The app is open with nothing on its slip, and the button said the bet
    // would be there (UX review).
    if (route === 'scheme' && ok) sayBetNotOnSlip(book);
    return ok;
  };

  if (installed === false) {
    const store = bookStoreUrl(book, state);
    if (store && (await tryOpen(store))) return went('store', true);
    if (await tryOpen(app.web)) return went('web', true);
    return went('failed', couldNotOpen(book));
  }

  // Ask iOS itself: open the link this book's app claims, in the app or not
  // at all. For BetMGM that is a different link from the stored one, so it is
  // tried whenever the app is not known to be missing. `false` means no
  // installed app took it. With no verified scheme to say otherwise
  // (`installed === null`) that is the "not installed" answer, so the App
  // Store. `null` means this build cannot ask.
  viaApp = claimed ? await openUniversalLinkOnly(claimed) : null;
  if (viaApp === true) return true;
  if (viaApp === false && installed === null) {
    const store = bookStoreUrl(book, state);
    if (store && (await tryOpen(store))) return went('store', true);
  }
  // iOS refused the link while a scheme says the app IS installed (Matt,
  // 2026-11-15, BetMGM on build 14301: Safari). Either the app does not take
  // the link we hold, or the member once chose "open in Safari" for that
  // site, which iOS remembers. The stored link goes to Safari either way
  // (BetMGM's is a path its app does not claim), where the bet may be on
  // the slip. The app is opened instead, with no bet on the slip: a
  // deliberate trade ("open the app if I have it", Matt, 2026-11-14).
  if (viaApp === false && installed === true) {
    const scheme = await installedBookScheme(book);
    if (scheme && (await tryOpen(scheme, true))) return went('scheme', true, scheme);
  }

  if (link && link.trim()) {
    const filled = fillBetslipLink(link, state);
    if (filled) {
      if (await tryOpen(filled)) return went('link', true);
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

  // The app is installed and nothing above put the bet in it: open the app.
  // Fanatics sends no betslip link at all, and this branch used to end on the
  // book's website (Matt, 2026-11-15: "It opens the website. It should be App
  // Store to download or the actual app if the user has it"). The verified
  // scheme first, then the one that said the app is installed; the site only
  // when neither opens.
  if (installed === true) {
    if (app.scheme && (await tryOpen(app.scheme, true))) return went('scheme', true, app.scheme);
    const scheme = await installedBookScheme(book);
    if (scheme && (await tryOpen(scheme, true))) return went('scheme', true, scheme);
    if (await tryOpen(app.web)) return went('web', true);
    return went('failed', couldNotOpen(book));
  }

  // Unknown: the scheme cannot be queried on this build, so it is not tried.
  // The STORE before the site — a member who has the app sees its page with
  // "Open"; one who does not is where they need to be to get it (Matt,
  // 2026-09-04) — the book's web root helps neither, since the bet is not on
  // it.
  const store = bookStoreUrl(book, state);
  if (store && (await tryOpen(store))) return went('store', true);
  if (await tryOpen(app.web)) return went('web', true);
  return went('failed', couldNotOpen(book));
}

/**
 * The book's app was opened by its scheme, so nothing is on its slip. Said
 * once, when the member comes back: a toast shown before the open would run
 * out while this app is in the background.
 */
const SLIP_NOTE_MAX_AGE_MS = 5 * 60_000;
const SLIP_NOTE_PROMPT_MS = 10_000;
let slipNote: { book: string; at: number } | null = null;
let slipNoteListening = false;

function sayBetNotOnSlip(book: string): void {
  // One pending note and one listener, however many taps: the latest book
  // wins. Coming back after five minutes is not about this hand-off any more.
  slipNote = { book, at: Date.now() };
  if (slipNoteListening) return;
  slipNoteListening = true;
  // Only coming back from the background counts. A system prompt ("Open in
  // ...?", not seen on a device here) takes an app inactive and back to
  // active without leaving it, and a note shown then is gone before the
  // member reaches the book. Active again with no trip out, past the time
  // a prompt takes to answer: the hand-off never left, so the note is
  // dropped, not kept for whatever the member leaves for next.
  let left = AppState.currentState === 'background';
  const sub = AppState.addEventListener('change', (state) => {
    if (state === 'background') left = true;
    if (state !== 'active') return;
    if (!left) {
      if (slipNote && Date.now() - slipNote.at <= SLIP_NOTE_PROMPT_MS) return;
      sub.remove();
      slipNoteListening = false;
      slipNote = null;
      return;
    }
    sub.remove();
    slipNoteListening = false;
    const note = slipNote;
    slipNote = null;
    if (!note || Date.now() - note.at > SLIP_NOTE_MAX_AGE_MS) return;
    showToast(`${bookName(note.book)} opened without your bet. Add it there.`, { announce: true, durationMs: 4000 });
  });
}

function couldNotOpen(book: string): false {
  Alert.alert(
    `Could not open ${bookName(book)}`,
    `We couldn’t open the ${bookName(book)} app or website on this device.`,
  );
  return false;
}

/**
 * This book's own betslip link, and nothing else. Used when the row names a
 * book we have no app entry for: opening DraftKings from a Fliff button is a
 * different bet. No link, or a link that will not open, is the same alert as
 * every other book.
 */
async function openThisBooksLinkOnly(
  book: string,
  link: string | null | undefined,
): Promise<boolean> {
  if (link && link.trim()) {
    const filled = fillBetslipLink(link, await loadBettingState());
    if (filled) {
      if (await tryOpen(filled)) return true;
    } else if (linkNeedsState(link)) {
      Alert.alert(
        `Which state do you bet in?`,
        `${bookName(book)} links need your state to open the app with the bet on your slip. Set it under Settings → Your state.`,
      );
      return false;
    }
  }
  return couldNotOpen(book);
}

/**
 * The DraftKings-specific hand-off. The parlay flow does NOT come through here:
 * it chooses its book with `handoffBookFor` (the member's own book when it
 * prices every leg, else DraftKings) and opens it via openBookBetslip.
 */
export function openBetslip(link: string | null | undefined): Promise<boolean> {
  return openBookBetslip(MODEL_BOOK, link);
}
