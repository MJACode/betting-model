
/**
 * Pure Discord-linking helpers — no React, no react-native, no expo, no
 * Supabase, so scripts/verify_discord_link.ts can import them. Same split as
 * authHelpers / billingHelpers.
 *
 * lib/discord.ts re-exports everything here, so callers only ever import from
 * '@/lib/discord'.
 */

import { errorText } from './errors';

/** Where a user's access came from, as reported by public.my_access(). */
export type AccessSource = 'app' | 'discord' | 'both' | 'none';

/** The row public.my_access() returns. One read, the whole picture. */
export interface AccessRow {
  entitled: boolean;
  source: AccessSource;
  app_access: boolean;
  discord_access: boolean;
  discord_linked: boolean;
  discord_username: string | null;
  guild_member: boolean;
  app_role_granted: boolean;
}

/** The shape a signed-out (or flag-off) caller gets. Access to nothing. */
export const NO_ACCESS: AccessRow = {
  entitled: false,
  source: 'none',
  app_access: false,
  discord_access: false,
  discord_linked: false,
  discord_username: null,
  guild_member: false,
  app_role_granted: false,
};

export class DiscordLinkDisabledError extends Error {
  constructor() {
    super('Discord linking is not enabled in this build.');
    this.name = 'DiscordLinkDisabledError';
  }
}

/** Guard every network entry point. Takes the flag so it stays pure. */
export function assertDiscordLinkEnabled(ready: boolean): void {
  if (!ready) throw new DiscordLinkDisabledError();
}

/**
 * Normalize whatever the RPC returns into an AccessRow.
 *
 * Postgres set-returning functions come back as an array through PostgREST,
 * and a `.single()` on a zero-row result is an error rather than null — so
 * both shapes, and the empty one, are handled here rather than at three call
 * sites.
 *
 * An unreadable payload resolves to NO_ACCESS. That is the safe direction for
 * a boolean nobody should be able to fake, and the caller (useEntitlement)
 * deliberately keeps its LAST GOOD value on a failed fetch, so a blip cannot
 * paywall a paying user mid-slate.
 */
export function parseAccess(raw: unknown): AccessRow {
  const row = Array.isArray(raw) ? raw[0] : raw;
  if (!row || typeof row !== 'object') return NO_ACCESS;
  const r = row as Record<string, unknown>;
  const bool = (k: string): boolean => r[k] === true;
  const source = r.source;
  return {
    entitled: bool('entitled'),
    source:
      source === 'app' || source === 'discord' || source === 'both'
        ? source
        : 'none',
    app_access: bool('app_access'),
    discord_access: bool('discord_access'),
    discord_linked: bool('discord_linked'),
    discord_username:
      typeof r.discord_username === 'string' && r.discord_username.trim() !== ''
        ? r.discord_username
        : null,
    guild_member: bool('guild_member'),
    app_role_granted: bool('app_role_granted'),
  };
}

/**
 * Pull the OAuth `code` (or an error) out of the URL Discord redirects back
 * to. Discord uses the query string; the fragment is read too so a
 * misconfigured implicit-flow app surfaces a clear error rather than a silent
 * "nothing happened". Same shape as parseAuthCallback.
 */
export interface DiscordCallback {
  code: string | null;
  state: string | null;
  error: string | null;
}

export function parseDiscordCallback(url: string): DiscordCallback {
  const read = (part: string | undefined): URLSearchParams =>
    new URLSearchParams(part ?? '');

  const [beforeHash, hash] = url.split('#');
  const query = read(beforeHash.split('?')[1]);
  const fragment = read(hash);

  const errorDescription =
    query.get('error_description') ?? fragment.get('error_description');
  const errorCode = query.get('error') ?? fragment.get('error');
  if (errorCode || errorDescription) {
    // access_denied is the user tapping Cancel on Discord's consent screen —
    // a normal outcome, and the caller renders it as one rather than a failure.
    return {
      code: null,
      state: null,
      error: errorCode === 'access_denied' ? 'cancelled' : errorDescription || errorCode,
    };
  }

  const code = query.get('code') ?? fragment.get('code');
  const state = query.get('state') ?? fragment.get('state');
  return { code: code ?? null, state: state ?? null, error: null };
}

/**
 * One line describing the Discord connection.
 *
 * A Whop membership ties the person. It does not pay for the app, so this
 * line never says that it does. An Apple subscription still includes our
 * Discord role.
 */
export function describeDiscordLink(access: AccessRow): string {
  if (!access.discord_linked) {
    return access.discord_access
      ? 'A Discord membership matches this account. Connect Discord to tie them together.'
      : 'Connect your Discord account to join the subscriber server.';
  }
  const who = access.discord_username ?? 'Discord';
  if (access.app_role_granted) {
    return `Connected as ${who} — your subscription includes the Discord.`;
  }
  if (access.discord_access) {
    return `Connected as ${who}.`;
  }
  if (access.guild_member) {
    return `Connected as ${who}. Subscribe to unlock the subscriber channels.`;
  }
  return `Connected as ${who}.`;
}

/**
 * Paywall line for where access came from. Empty when there is nothing to
 * say, so the caller can skip it. A Whop-only match (`source === 'discord'`)
 * does not unlock the app and gets no "included" line.
 */
export function accessSourceCopy(access: AccessRow): string {
  switch (access.source) {
    case 'app':
    case 'both':
      return 'Your subscription includes access to the subscriber Discord.';
    default:
      return '';
  }
}

/**
 * The Apple-paid invite. Not exported: a screen that wants it has to go
 * through discordInviteIfPaid, and only after the App Store row is active.
 */
const APPLE_PAID_DISCORD_INVITE = 'https://discord.gg/JWMUzK9Da';

/**
 * The invite URL, or null. `paid` means an active Apple subscription, not a
 * trial and not a Whop membership. Free and trial must not be handed a string
 * they could render or open.
 */
export function discordInviteIfPaid(
  paid: boolean,
  inviteUrl: string = APPLE_PAID_DISCORD_INVITE,
): string | null {
  if (!paid) return null;
  const url = inviteUrl.trim();
  return url.length > 0 ? url : null;
}

/** Turn a link failure into something worth showing a user. */
export function discordErrorMessage(err: unknown): string {
  const raw = errorText(err, 'Something went wrong. Please try again.');

  const lower = raw.toLowerCase();
  if (lower.includes('already connected to a different')) {
    return 'That Discord account is already connected to another Signalbase account.';
  }
  if (lower.includes('expired')) {
    return 'That request timed out. Tap Connect Discord again.';
  }
  if (lower.includes('not configured')) {
    return 'Discord linking is not set up yet. Try again later.';
  }
  if (lower.includes('not signed in')) {
    return 'Sign in first to connect Discord.';
  }
  if (lower.includes('roles')) {
    return "Couldn't update your Discord roles. Try again shortly.";
  }
  if (lower.includes('network') || lower.includes('fetch failed')) {
    return 'No connection. Check your network and try again.';
  }
  return raw;
}
