import { Alert, Linking, Platform } from 'react-native';

/**
 * DraftKings hand-off.
 *
 * There is no public DK API to place a bet programmatically — the only viable
 * "send a bet to DraftKings" path is a pre-filled betslip deep link that opens
 * the DK app (or web) with the selection populated; the user taps "Place Bet"
 * themselves. The link is captured per outcome from The Odds API
 * (includeLinks=true) at score time and stored on the pick as `dk_bet_link`.
 *
 * When no betslip link is available (prob-only picks, markets DK doesn't price
 * via the API), we fall back to the DK app / sportsbook home so the button
 * still gets the user to DraftKings.
 */

const DK_APP_SCHEME = 'dksb://';
const DK_WEB_HOME = 'https://sportsbook.draftkings.com/';
const DK_APP_STORE =
  Platform.OS === 'ios'
    ? 'https://apps.apple.com/us/app/draftkings-sportsbook-casino/id1375031369'
    : 'https://play.google.com/store/apps/details?id=com.draftkings.sportsbook';

/** Brand green used for the "Bet on DraftKings" button. */
export const DK_GREEN = '#53D337';

async function tryOpen(url: string): Promise<boolean> {
  try {
    const supported = await Linking.canOpenURL(url);
    // canOpenURL can be unreliable for https on some platforms — attempt anyway
    // for web URLs, but trust it for custom schemes.
    if (!supported && url.startsWith(DK_APP_SCHEME)) return false;
    await Linking.openURL(url);
    return true;
  } catch {
    return false;
  }
}

/**
 * Open the pre-filled DraftKings betslip for a pick.
 *
 * Fallback chain: stored betslip link → DK app → DK web → App/Play Store.
 * Returns true once something opened.
 */
export async function openBetslip(link: string | null | undefined): Promise<boolean> {
  if (link && link.trim()) {
    if (await tryOpen(link.trim())) return true;
  }

  // No usable betslip link — try to at least land the user in DraftKings.
  if (await tryOpen(DK_APP_SCHEME)) return true;
  if (await tryOpen(DK_WEB_HOME)) return true;
  if (await tryOpen(DK_APP_STORE)) return true;

  Alert.alert(
    'Could not open DraftKings',
    'We couldn’t open the DraftKings app or website on this device.',
  );
  return false;
}
