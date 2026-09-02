import { Alert, Linking, Platform } from 'react-native';

import appConfig from '../../app.json';
import { APP_URL } from '@/lib/shareRecord';

/**
 * Where Signalbase lives outside the app.
 *
 * X is live (@signalbasepicks, set 2026-08-30) and Discord is live (invite set
 * 2026-08-24). Everything that links out of the app reads from this file, so
 * pointing a handle at a different account is a one-line change here — no
 * screen edits, no copy edits.
 *
 * TWITTER_URL is the bare profile URL on purpose: the `?s=`/`?t=` params on a
 * link copied out of the X share sheet are per-share tracking tokens, not part
 * of the address, and they do not belong in a link we ship to every user.
 *
 * DISCORD_URL is a permanent invite link — if it is ever regenerated or set to
 * expire, replace it here.
 */
/** Re-exported so the share message and the Settings footer can never drift. */
export const WEBSITE_URL = APP_URL;
export const TWITTER_URL = 'https://x.com/signalbasepicks';
export const DISCORD_URL = 'https://discord.gg/JWMUzK9Da';
export const SUPPORT_EMAIL = 'matt.alksninis@gmail.com';

/**
 * The legal row under the paywall. App Review requires functional links to the
 * terms and the privacy policy from any screen that sells a subscription
 * (guideline 3.1.2) — a dead link there is a rejection, so both pages must be
 * live before BILLING_ENABLED flips.
 *
 * EULA points at Apple's standard licence, which is the default that applies
 * when an app does not supply its own. Replace it only if we ever write one.
 */
export const PRIVACY_URL = `${APP_URL}/privacy`;
export const TERMS_URL = `${APP_URL}/terms`;
export const EULA_URL =
  'https://www.apple.com/legal/internet-services/itunes/dev/stdeula/';

export const APP_VERSION = appConfig.expo.version;

/**
 * Open an external URL, and say something useful when we can't.
 *
 * `canOpenURL` returns false on a device with no browser/handler for the
 * scheme, and `openURL` itself rejects if the OS refuses. Either way the user
 * gets the address rather than a dead tap.
 */
export async function openLink(url: string, label: string): Promise<void> {
  try {
    const canOpen = await Linking.canOpenURL(url);
    if (!canOpen) throw new Error('cannot open');
    await Linking.openURL(url);
  } catch {
    Alert.alert(`Couldn't open ${label}`, url);
  }
}

/** Mail composer pre-filled with the version/platform we need for triage. */
export async function openFeedback(): Promise<void> {
  const subject = `Signalbase feedback (v${APP_VERSION})`;
  const body = [
    '',
    '',
    '———',
    `App version: ${APP_VERSION}`,
    `Platform: ${Platform.OS} ${Platform.Version}`,
    'Please describe your feedback above this line.',
  ].join('\n');
  const url = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(
    subject,
  )}&body=${encodeURIComponent(body)}`;

  try {
    const canOpen = await Linking.canOpenURL(url);
    if (!canOpen) throw new Error('no mail client');
    await Linking.openURL(url);
  } catch {
    Alert.alert(
      'No email app found',
      `Send your feedback to ${SUPPORT_EMAIL} and we'll take a look.`,
    );
  }
}
