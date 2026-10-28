/**
 * Discord account linking — feature flag and configuration.
 *
 * ============================================================================
 * APPLE UNLOCKS THE APP. WHOP IS DISCORD-ONLY. This is the link flag.
 * ============================================================================
 *
 * Matt, 2026-10-27: Whop is Discord-only checkout, outside the App Store.
 * App Store IAP unlocks the app and our Discord role. Linking ties the same
 * person across both. A Whop membership does not unlock the app.
 *
 * Two roles in the guild: the one WE grant for an Apple subscription, and the
 * one Whop grants for its Discord product. Each side only ever revokes its
 * own, so a lapsed App Store subscription does not strip Whop's role.
 *
 * Do not set DISCORD_LINK_ENABLED, AUTH_ENABLED, or BILLING_ENABLED until
 * `add_discord_link_and_whop_memberships.sql` is applied in that environment.
 * With either gate on, `fetchAccess()` calls `my_access()` and throws if the
 * function is missing.
 *
 * While `DISCORD_LINK_ENABLED` is false:
 *   - Settings does not open the invite. The invite is Apple-paid only.
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
