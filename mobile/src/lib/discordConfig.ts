/**
 * Discord account linking — feature flag and configuration.
 *
 * ============================================================================
 * ONE MEMBERSHIP, TWO SURFACES. This is the flag for the Discord half.
 * ============================================================================
 *
 * The rule Matt set (2026-08-30):
 *   * Pay in the app  -> you get access to the subscriber Discord.
 *   * Pay via Discord (Whop) -> the app costs you nothing extra.
 *   * Lose access on one side -> you lose it on the other.
 *
 * Mechanically that is one linked identity plus two roles in the guild: the
 * one WE grant for app subscribers, and the one Whop grants for Discord
 * subscribers. Each side only ever revokes its own, so a member who lets their
 * App Store subscription lapse but still pays Whop keeps their access — which
 * is correct, they are still paying.
 *
 * While `DISCORD_LINK_ENABLED` is false:
 *   - Settings shows the plain "Join our Discord" invite row exactly as today.
 *   - No Connect button renders, and no edge function is ever called.
 *   - `useDiscordLink()` reports status 'disabled' and never touches the network.
 *
 * Linking DEPENDS ON AUTH, for the same reason billing does: a link binds a
 * Discord account to an app ACCOUNT, and a device id cannot survive a
 * reinstall. `discordLinkReady()` enforces the pair.
 *
 * Activation runbook: mobile/docs/DISCORD_LINKING.md
 */

import { AUTH_ENABLED } from './authConfig';

/** Master switch. Overridable via EXPO_PUBLIC_DISCORD_LINK_ENABLED. */
export const DISCORD_LINK_ENABLED: boolean =
  (process.env.EXPO_PUBLIC_DISCORD_LINK_ENABLED ?? 'false').toLowerCase() === 'true';

/** Linking is only meaningful once users can have accounts. */
export function discordLinkReady(): boolean {
  return DISCORD_LINK_ENABLED && AUTH_ENABLED;
}

/**
 * Where Discord sends the user back to after they authorize.
 *
 * Must match `expo.scheme` in app.json (`signalbase`), the redirect URI
 * registered on the Discord application, and `DISCORD_REDIRECT_URI` in the
 * edge function's secrets. All four, or the round trip dead-ends.
 *
 * Hardcoded rather than derived via expo-linking, so this stays a pure-JS,
 * OTA-deliverable change — same reasoning as AUTH_REDIRECT_URL.
 */
export const DISCORD_REDIRECT_URL = 'signalbase://discord-callback';

/** The edge function that owns the OAuth exchange and the role sync. */
export const DISCORD_LINK_FUNCTION = 'discord-link';

/**
 * Where a Discord-side membership is actually sold. Shown to a signed-in user
 * with no access as the alternative to the App Store — some people would
 * rather buy where the community is.
 *
 * PLACEHOLDER until the Whop product is live; the "Get access on Discord" row
 * is hidden while this is empty rather than linking somewhere broken.
 */
export const WHOP_CHECKOUT_URL: string =
  process.env.EXPO_PUBLIC_WHOP_CHECKOUT_URL ?? '';
