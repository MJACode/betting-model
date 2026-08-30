import * as WebBrowser from 'expo-web-browser';

import { supabase } from './supabase';
import {
  DISCORD_LINK_FUNCTION,
  DISCORD_REDIRECT_URL,
  discordLinkReady,
} from './discordConfig';
import {
  NO_ACCESS,
  assertDiscordLinkEnabled,
  parseAccess,
  parseDiscordCallback,
  type AccessRow,
} from './discordHelpers';

/**
 * Discord linking API (mobile side).
 *
 * Nothing here runs while `discordLinkReady()` is false — every network call
 * guards on it first, so an accidental import can't start linking real
 * accounts before the Discord application, the bot and the Whop webhook are
 * configured.
 *
 * Pure JS end to end (expo-web-browser is already a dependency for SharpSports
 * and auth), so the whole feature ships over OTA with no native module and no
 * EAS rebuild — unlike IAP.
 *
 * THE APP NEVER GRANTS ANYTHING. It opens a browser, hands the returned code
 * to the `discord-link` edge function, and reads back the result. The bot
 * token, the client secret and the role writes all live server-side, which is
 * what stops a client claiming a membership it did not buy.
 *
 * Pure helpers live in ./discordHelpers and are re-exported here.
 */

export {
  DiscordLinkDisabledError,
  NO_ACCESS,
  accessSourceCopy,
  assertDiscordLinkEnabled,
  describeDiscordLink,
  discordErrorMessage,
  parseAccess,
  parseDiscordCallback,
  type AccessRow,
  type AccessSource,
  type DiscordCallback,
} from './discordHelpers';

interface FunctionResponse {
  ok?: boolean;
  error?: string;
  url?: string;
  state?: string;
  joined?: boolean;
  guild_member?: boolean;
  discord_username?: string;
  access?: unknown;
}

/** One call to the edge function, with its error shapes flattened. */
async function callLinkFunction(
  body: Record<string, unknown>,
): Promise<FunctionResponse> {
  const { data, error } = await supabase.functions.invoke(DISCORD_LINK_FUNCTION, {
    body,
  });
  // A non-2xx from the function surfaces as `error` with the body stringified
  // somewhere inside it, and as `data.error` when the function returned JSON.
  // Prefer the function's own sentence — it is the one written for a user.
  const payload = (data ?? null) as FunctionResponse | null;
  if (payload?.error) throw new Error(payload.error);
  if (error) throw error;
  if (!payload) throw new Error('Discord did not respond. Try again.');
  return payload;
}

export interface LinkResult {
  outcome: 'linked' | 'cancelled';
  /** True when this call is what put them in the server (vs already a member). */
  joined: boolean;
  access: AccessRow;
}

/**
 * Run the whole link flow: ask the function for an authorize URL, open it,
 * hand the code back.
 *
 * Returns `cancelled` when the user dismisses the browser or declines on
 * Discord's consent screen — a cancel is a normal outcome, not an error, and
 * the caller should just close the sheet.
 */
export async function linkDiscord(): Promise<LinkResult> {
  assertDiscordLinkEnabled(discordLinkReady());

  const start = await callLinkFunction({ action: 'start' });
  if (!start.url) throw new Error('Could not start the Discord connection.');

  const result = await WebBrowser.openAuthSessionAsync(
    start.url,
    DISCORD_REDIRECT_URL,
  );
  if (result.type !== 'success') {
    return { outcome: 'cancelled', joined: false, access: NO_ACCESS };
  }

  const callback = parseDiscordCallback(result.url);
  if (callback.error === 'cancelled') {
    return { outcome: 'cancelled', joined: false, access: NO_ACCESS };
  }
  if (callback.error) throw new Error(callback.error);
  if (!callback.code) {
    throw new Error('Discord did not return an authorization code.');
  }

  // `state` comes back from Discord, but fall back to the one we were issued:
  // the function verifies it against an HMAC bound to this user either way, so
  // a stripped query param costs a retry rather than a failure.
  const completed = await callLinkFunction({
    action: 'complete',
    code: callback.code,
    state: callback.state ?? start.state ?? '',
  });

  return {
    outcome: 'linked',
    joined: completed.joined === true,
    access: parseAccess(completed.access),
  };
}

/**
 * Disconnect the Discord account.
 *
 * Takes back the role WE granted, and nothing else — a member who also pays
 * through Whop keeps that role and stays in the server. We never kick anyone:
 * leaving a server is the member's own choice.
 */
export async function unlinkDiscord(): Promise<AccessRow> {
  assertDiscordLinkEnabled(discordLinkReady());
  const res = await callLinkFunction({ action: 'unlink' });
  return parseAccess(res.access);
}

/**
 * The caller's whole access picture, straight from `public.my_access()`.
 *
 * Read through the RPC rather than by selecting the tables, because the answer
 * is an OR across a subscription the user can read and a Whop membership they
 * cannot (it carries other people's emails). One round trip, one truth.
 *
 * Returns NO_ACCESS rather than throwing when linking is off — callers treat
 * that as "the flag decides", not as an error.
 */
export async function fetchAccess(): Promise<AccessRow> {
  const { data, error } = await supabase.rpc('my_access');
  if (error) throw error;
  return parseAccess(data);
}
