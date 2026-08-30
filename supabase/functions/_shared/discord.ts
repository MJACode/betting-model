// Discord bot API helpers, shared by discord-link, whop-webhook and
// revenuecat-webhook.
//
// ============================================================================
// THE ROLE IS THE ENTITLEMENT CARRIER, AND EACH SIDE REVOKES ONLY ITS OWN.
// ============================================================================
// Two roles exist in the guild:
//
//   DISCORD_APP_ROLE_ID   granted by US when an app subscription entitles.
//   (Whop's own role)     granted by Whop when someone buys through Discord.
//
// We never touch Whop's role, and Whop never touches ours. That is what makes
// "remove access from one and it goes from the other" correct rather than
// destructive: a member who lets their App Store subscription lapse but still
// pays Whop keeps their Whop role and their access, because only OUR role came
// off. `discord_links.app_role_granted` records that ours is on, so revocation
// is a fact we hold rather than a guess about the guild's current state.
//
// Secrets (Supabase → Edge Functions → Secrets):
//   DISCORD_BOT_TOKEN   bot token, needs Manage Roles + Create Instant Invite
//   DISCORD_GUILD_ID    the server id
//   DISCORD_APP_ROLE_ID the role WE grant to app subscribers

const API = "https://discord.com/api/v10";

export const BOT_TOKEN = Deno.env.get("DISCORD_BOT_TOKEN") ?? "";
export const GUILD_ID = Deno.env.get("DISCORD_GUILD_ID") ?? "";
export const APP_ROLE_ID = Deno.env.get("DISCORD_APP_ROLE_ID") ?? "";

/** Configured well enough to touch the guild at all? */
export function discordConfigured(): boolean {
  return Boolean(BOT_TOKEN && GUILD_ID && APP_ROLE_ID);
}

export class DiscordApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: string,
    message: string,
  ) {
    super(message);
    this.name = "DiscordApiError";
  }
}

/**
 * One request to the Discord API, with a single retry on 429.
 *
 * Rate limits are per-route and Discord tells us exactly how long to wait, so a
 * single honoured retry converts almost every 429 into a success. The wait is
 * clamped: a bad `retry_after` must not be able to stall an Edge Function until
 * it is killed (the same clamp the Discord notifier uses on the Python side).
 */
async function botFetch(
  path: string,
  init: RequestInit & { retry?: boolean } = {},
): Promise<Response> {
  const { retry = true, ...rest } = init;
  const res = await fetch(`${API}${path}`, {
    ...rest,
    headers: {
      Authorization: `Bot ${BOT_TOKEN}`,
      "Content-Type": "application/json",
      ...(rest.headers ?? {}),
    },
  });

  if (res.status === 429 && retry) {
    let waitMs = 1000;
    try {
      const body = await res.clone().json();
      const secs = Number(body?.retry_after ?? 1);
      if (Number.isFinite(secs)) waitMs = Math.min(Math.max(secs, 0) * 1000, 5000);
    } catch {
      // Keep the default wait — a malformed 429 body is not a reason to give up.
    }
    await new Promise((r) => setTimeout(r, waitMs));
    return botFetch(path, { ...init, retry: false });
  }
  return res;
}

async function expectOk(res: Response, what: string): Promise<void> {
  // 204 No Content is the success shape for most role/member writes.
  if (res.ok) return;
  const body = await res.text().catch(() => "");
  throw new DiscordApiError(res.status, body, `${what} failed (${res.status}): ${body}`);
}

/**
 * Add the user to the guild using the OAuth token they just granted us
 * (`guilds.join` scope). This is what makes the app's "Join the Discord" button
 * one tap instead of an invite link the user has to accept in another app.
 *
 * Returns true if we added them, false if they were already a member — Discord
 * signals that with 204 vs 201, and both are success.
 */
export async function addGuildMember(
  discordUserId: string,
  accessToken: string,
): Promise<boolean> {
  const res = await botFetch(`/guilds/${GUILD_ID}/members/${discordUserId}`, {
    method: "PUT",
    body: JSON.stringify({ access_token: accessToken }),
  });
  if (res.status === 201) return true;
  if (res.status === 204) return false;
  await expectOk(res, "guild join");
  return false;
}

/** Is this Discord account currently in the guild? */
export async function isGuildMember(discordUserId: string): Promise<boolean> {
  const res = await botFetch(`/guilds/${GUILD_ID}/members/${discordUserId}`);
  if (res.status === 404) return false;
  await expectOk(res, "guild member lookup");
  return true;
}

/** Grant OUR app-subscriber role. Idempotent — Discord 204s on a re-add. */
export async function addAppRole(discordUserId: string): Promise<void> {
  const res = await botFetch(
    `/guilds/${GUILD_ID}/members/${discordUserId}/roles/${APP_ROLE_ID}`,
    { method: "PUT" },
  );
  await expectOk(res, "role grant");
}

/**
 * Remove OUR app-subscriber role. Never Whop's.
 *
 * A 404 means the member (or the role on them) is already gone, which is the
 * state we wanted — treat it as success so a departed member can't wedge the
 * sync in a retry loop forever.
 */
export async function removeAppRole(discordUserId: string): Promise<void> {
  const res = await botFetch(
    `/guilds/${GUILD_ID}/members/${discordUserId}/roles/${APP_ROLE_ID}`,
    { method: "DELETE" },
  );
  if (res.status === 404) return;
  await expectOk(res, "role revoke");
}

export interface DiscordUser {
  id: string;
  username: string;
  global_name?: string | null;
  discriminator?: string;
  avatar?: string | null;
  email?: string | null;
  verified?: boolean;
}

/** Exchange an OAuth authorization code for tokens. */
export async function exchangeCode(
  code: string,
  redirectUri: string,
  clientId: string,
  clientSecret: string,
): Promise<{ access_token: string; refresh_token?: string; scope: string }> {
  const res = await fetch(`${API}/oauth2/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      client_id: clientId,
      client_secret: clientSecret,
      grant_type: "authorization_code",
      code,
      redirect_uri: redirectUri,
    }),
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new DiscordApiError(res.status, body, `token exchange failed: ${body}`);
  }
  return await res.json();
}

/** Who did that token authenticate? */
export async function fetchOAuthUser(accessToken: string): Promise<DiscordUser> {
  const res = await fetch(`${API}/users/@me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new DiscordApiError(res.status, body, `identify failed: ${body}`);
  }
  return await res.json();
}

/** Best display name for the Settings card: global name, else username. */
export function displayName(user: DiscordUser): string {
  return user.global_name?.trim() || user.username;
}
