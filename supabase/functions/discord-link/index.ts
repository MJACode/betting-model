// Discord account linking for the mobile app.
//
// The user taps "Connect Discord", authorizes in an in-app browser, and comes
// back linked, in the server, and holding whichever role their membership
// entitles them to. Four actions, all requiring the caller's Supabase JWT
// (verify_jwt = true), because a link is an assertion about WHO someone is and
// must never be makeable on another account's behalf:
//
//   start     -> the Discord authorize URL to open, plus a signed state
//   complete  -> exchange the returned code, store the link, join the guild,
//                sync the role
//   unlink    -> remove our role, delete the link row
//   status    -> the current link + access picture (my_access())
//
// SCOPES: identify, email, guilds.join.
//   identify   — the Discord user id, which is the durable join key
//   email      — lets a Whop membership bought with the same address match
//                automatically, so a Discord subscriber who signs into the app
//                is entitled without any extra step. Only Discord-VERIFIED
//                addresses are ever trusted (see discord_access_for()).
//   guilds.join— one-tap join, instead of handing back an invite link the user
//                has to accept in another app.
//
// Secrets:
//   DISCORD_CLIENT_ID / DISCORD_CLIENT_SECRET   the Discord application
//   DISCORD_BOT_TOKEN / DISCORD_GUILD_ID / DISCORD_APP_ROLE_ID  (see _shared)
//   DISCORD_REDIRECT_URI    must match app.json's scheme + the Discord portal
//   DISCORD_STATE_SECRET    HMAC key for the CSRF state (any long random string)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

import {
  addGuildMember,
  discordConfigured,
  displayName,
  exchangeCode,
  fetchOAuthUser,
  isGuildMember,
  removeAppRole,
} from "../_shared/discord.ts";
import { syncAppRoleForUser } from "../_shared/entitlement.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";

const CLIENT_ID = Deno.env.get("DISCORD_CLIENT_ID") ?? "";
const CLIENT_SECRET = Deno.env.get("DISCORD_CLIENT_SECRET") ?? "";
const REDIRECT_URI = Deno.env.get("DISCORD_REDIRECT_URI") ??
  "signalbase://discord-callback";
const STATE_SECRET = Deno.env.get("DISCORD_STATE_SECRET") ?? "";

const SCOPES = "identify email guilds.join";
const STATE_TTL_MS = 10 * 60 * 1000; // 10 minutes — long enough to sign in, short enough to matter

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });

// ── CSRF state ───────────────────────────────────────────────────────────────
// `${userId}.${expiry}.${hmac}`. Signed rather than stored: there is no row to
// clean up, no table to grow, and the state is self-validating. It binds the
// browser round trip to the user who started it, so a code obtained in someone
// else's browser can't be redeemed against this account.

async function hmac(message: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(STATE_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(message),
  );
  return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

async function issueState(userId: string): Promise<string> {
  const expiry = Date.now() + STATE_TTL_MS;
  const payload = `${userId}.${expiry}`;
  return `${payload}.${await hmac(payload)}`;
}

async function verifyState(state: string, userId: string): Promise<boolean> {
  const parts = state.split(".");
  if (parts.length !== 3) return false;
  const [stateUser, expiryRaw, sig] = parts;
  if (stateUser !== userId) return false;
  const expiry = Number(expiryRaw);
  if (!Number.isFinite(expiry) || expiry < Date.now()) return false;
  return timingSafeEqual(sig, await hmac(`${stateUser}.${expiryRaw}`));
}

// ── Caller identity ──────────────────────────────────────────────────────────

async function callerId(req: Request): Promise<string | null> {
  const authHeader = req.headers.get("Authorization") ?? "";
  if (!authHeader.startsWith("Bearer ")) return null;
  const scoped = createClient(SUPABASE_URL, ANON_KEY, {
    global: { headers: { Authorization: authHeader } },
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const { data, error } = await scoped.auth.getUser();
  if (error || !data.user) return null;
  return data.user.id;
}

/** The access picture, read through the same RPC the app uses. */
async function accessFor(userId: string) {
  const { data, error } = await admin.rpc("my_access_for", { p_user_id: userId });
  if (error || !data) return null;
  return Array.isArray(data) ? data[0] : data;
}

// ── Actions ──────────────────────────────────────────────────────────────────

async function handleStart(userId: string) {
  if (!CLIENT_ID || !STATE_SECRET) {
    return json({ error: "Discord linking is not configured yet." }, 503);
  }
  const state = await issueState(userId);
  const url = new URL("https://discord.com/oauth2/authorize");
  url.searchParams.set("client_id", CLIENT_ID);
  url.searchParams.set("redirect_uri", REDIRECT_URI);
  url.searchParams.set("response_type", "code");
  url.searchParams.set("scope", SCOPES);
  url.searchParams.set("state", state);
  // Always re-show the consent screen. Without it a user who taps Connect on a
  // second account is silently re-linked to the Discord account their browser
  // still holds, with no way to notice.
  url.searchParams.set("prompt", "consent");
  return json({ url: url.toString(), state, redirect_uri: REDIRECT_URI });
}

async function handleComplete(userId: string, code: string, state: string) {
  if (!CLIENT_ID || !CLIENT_SECRET || !STATE_SECRET) {
    return json({ error: "Discord linking is not configured yet." }, 503);
  }
  if (!code) return json({ error: "Missing authorization code." }, 400);
  if (!(await verifyState(state, userId))) {
    return json({ error: "That link request expired. Try again." }, 400);
  }

  let tokens: { access_token: string; scope?: string };
  let profile;
  try {
    tokens = await exchangeCode(code, REDIRECT_URI, CLIENT_ID, CLIENT_SECRET);
    profile = await fetchOAuthUser(tokens.access_token);
  } catch (e) {
    console.error("[discord-link] oauth failed", e);
    return json({ error: "Discord sign-in failed. Try again." }, 400);
  }

  // One Discord account backs at most one app account. Enforced by a UNIQUE
  // constraint too, but caught here so the user gets a sentence instead of a
  // constraint violation.
  const { data: existing } = await admin
    .from("discord_links")
    .select("user_id")
    .eq("discord_user_id", profile.id)
    .maybeSingle();
  if (existing && existing.user_id !== userId) {
    return json(
      {
        error:
          "That Discord account is already connected to a different Signalbase account.",
      },
      409,
    );
  }

  // Join the guild with the token the user just granted. A failure here is NOT
  // fatal: the link is still worth keeping (it is what makes a Whop membership
  // match), and the app falls back to showing the invite link.
  let joined = false;
  let guildMember = false;
  let joinError: string | null = null;
  if (discordConfigured()) {
    try {
      joined = await addGuildMember(profile.id, tokens.access_token);
      guildMember = true;
    } catch (e) {
      joinError = e instanceof Error ? e.message : String(e);
      console.warn(`[discord-link] guild join failed for ${profile.id}: ${joinError}`);
      try {
        guildMember = await isGuildMember(profile.id);
      } catch {
        guildMember = false;
      }
    }
  }

  const now = new Date().toISOString();
  const { error: upsertErr } = await admin.from("discord_links").upsert(
    {
      user_id: userId,
      discord_user_id: profile.id,
      discord_username: displayName(profile),
      discord_avatar: profile.avatar ?? null,
      discord_email: profile.email ?? null,
      // Discord's own flag. An unverified address is attacker-chosen and must
      // never auto-match a paid Whop membership.
      discord_email_verified: Boolean(profile.verified && profile.email),
      guild_member: guildMember,
      last_synced_at: now,
      last_sync_error: joinError,
      updated_at: now,
    },
    { onConflict: "user_id" },
  );
  if (upsertErr) {
    console.error("[discord-link] upsert failed", upsertErr);
    return json({ error: "Could not save the connection. Try again." }, 500);
  }

  // If they already pay in the app, they should walk away holding the role.
  await syncAppRoleForUser(admin, userId);

  // Backfill the Discord id onto a Whop membership bought with the same
  // verified email. Whop knows the buyer's email long before it knows their
  // Discord id, and this is the moment we can join the two — after which the
  // membership matches on id even if they later change the email on either side.
  if (profile.email && profile.verified) {
    // `.eq`, not `.ilike`: an email containing `_` or `%` is a wildcard to
    // ilike, and one stray underscore would attach someone else's membership
    // to this account. whop-webhook lowercases on write, so an exact match on
    // the lowered address is both correct and case-insensitive.
    const { error: backfillErr } = await admin
      .from("whop_memberships")
      .update({ discord_user_id: profile.id, updated_at: now })
      .is("discord_user_id", null)
      .eq("email", profile.email.trim().toLowerCase());
    if (backfillErr) {
      console.warn("[discord-link] whop backfill failed", backfillErr.message);
    }
  }

  return json({
    ok: true,
    joined,
    guild_member: guildMember,
    discord_username: displayName(profile),
    access: await accessFor(userId),
  });
}

async function handleUnlink(userId: string) {
  const { data: link } = await admin
    .from("discord_links")
    .select("discord_user_id, app_role_granted")
    .eq("user_id", userId)
    .maybeSingle();

  // Take our role back first. If that fails we keep the link row: dropping it
  // would leave a role granted with no record that we granted it, and nothing
  // would ever revoke it.
  if (link?.discord_user_id && link.app_role_granted && discordConfigured()) {
    try {
      await removeAppRole(link.discord_user_id);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      console.error(`[discord-link] unlink role removal failed: ${message}`);
      return json(
        { error: "Could not update your Discord roles. Try again shortly." },
        502,
      );
    }
  }

  const { error } = await admin.from("discord_links").delete().eq("user_id", userId);
  if (error) {
    console.error("[discord-link] delete failed", error);
    return json({ error: "Could not disconnect. Try again." }, 500);
  }
  // We deliberately do NOT kick them from the guild. Leaving a server is the
  // member's choice; unlinking is about this app's record of who they are.
  return json({ ok: true, access: await accessFor(userId) });
}

async function handleStatus(userId: string) {
  return json({ ok: true, access: await accessFor(userId) });
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }

  const userId = await callerId(req);
  if (!userId) return json({ error: "Not signed in." }, 401);

  let body: { action?: string; code?: string; state?: string };
  try {
    body = await req.json();
  } catch {
    return json({ error: "bad json" }, 400);
  }

  try {
    switch (body.action) {
      case "start":
        return await handleStart(userId);
      case "complete":
        return await handleComplete(userId, body.code ?? "", body.state ?? "");
      case "unlink":
        return await handleUnlink(userId);
      case "status":
        return await handleStatus(userId);
      default:
        return json({ error: `Unknown action: ${body.action ?? "(none)"}` }, 400);
    }
  } catch (e) {
    console.error("[discord-link] handler failed", e);
    return json({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
