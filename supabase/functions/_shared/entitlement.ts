// Our App Subscriber Discord role, matched to the Apple subscription.
//
// Called from two places:
//   * discord-link       — a user just connected (or disconnected) Discord
//   * revenuecat-webhook — an app subscription started, renewed or lapsed
//
// The Whop webhook does not call this file. A Whop membership is Discord-only
// and never grants or revokes our role. App access is public.my_access() /
// has_app_access(), which read `subscriptions` only.

import type { SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";
import {
  addAppRole,
  discordConfigured,
  removeAppRole,
} from "./discord.ts";

/** Statuses that entitle. Mirrors mobile/src/lib/billingHelpers.ts::isEntitled. */
const ENTITLING = new Set(["trialing", "active"]);

/**
 * Does the app-side subscription entitle right now?
 *
 * Status AND period end — an `active` row whose period lapsed (a webhook we
 * missed) must not grant access forever. A null period end entitles: that is a
 * row written before the webhook filled it in, and locking out a just-paid
 * user is the worse failure. Same rule as the SQL in
 * app_subscription_access_for() and the TS in isEntitled(); all three have to
 * agree or a user sees a different answer depending on who asked.
 */
export function subscriptionEntitles(
  row: { status?: string; current_period_end?: string | null } | null | undefined,
): boolean {
  if (!row?.status || !ENTITLING.has(row.status)) return false;
  if (!row.current_period_end) return true;
  const end = Date.parse(row.current_period_end);
  if (Number.isNaN(end)) return true;
  return end > Date.now();
}

export interface RoleSyncResult {
  /** No link row, or Discord isn't configured — nothing to do, not a failure. */
  skipped: boolean;
  reason?: string;
  granted?: boolean;
  revoked?: boolean;
}

/**
 * Make this user's Discord role match their APP subscription.
 *
 * Reads only `subscriptions`. This grants and revokes OUR role, which is the
 * App Store purchase. A Whop member's Discord role is Whop's. Touching it
 * here would strip a member who is still paying Whop for Discord.
 *
 * Never throws. Every caller is a webhook whose primary job (writing the
 * subscription row) has already succeeded, and failing that write's response
 * because Discord was briefly unreachable would make the store retry a
 * successful upsert. The failure is recorded on the link row instead
 * (`last_sync_error`), where it is visible and re-syncable.
 */
export async function syncAppRoleForUser(
  admin: SupabaseClient,
  userId: string,
): Promise<RoleSyncResult> {
  if (!discordConfigured()) {
    return { skipped: true, reason: "discord not configured" };
  }

  const { data: link, error: linkErr } = await admin
    .from("discord_links")
    .select("discord_user_id, app_role_granted")
    .eq("user_id", userId)
    .maybeSingle();
  if (linkErr) {
    console.warn(`[entitlement] link lookup failed for ${userId}: ${linkErr.message}`);
    return { skipped: true, reason: "link lookup failed" };
  }
  if (!link?.discord_user_id) {
    // Nothing linked yet. When they do link, discord-link runs this same sync,
    // so a subscriber who connects Discord later still gets the role.
    return { skipped: true, reason: "no discord link" };
  }

  const { data: sub } = await admin
    .from("subscriptions")
    .select("status, current_period_end")
    .eq("user_id", userId)
    .maybeSingle();

  const shouldHold = subscriptionEntitles(sub);
  const holds = Boolean(link.app_role_granted);

  // Already in the desired state. Re-asserting is harmless (both Discord calls
  // are idempotent) but costs a round trip on every renewal webhook.
  if (shouldHold === holds) return { skipped: true, reason: "already in sync" };

  try {
    if (shouldHold) await addAppRole(link.discord_user_id);
    else await removeAppRole(link.discord_user_id);
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error(`[entitlement] role sync failed for ${userId}: ${message}`);
    await admin
      .from("discord_links")
      .update({
        last_sync_error: message.slice(0, 500),
        last_synced_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      })
      .eq("user_id", userId);
    return { skipped: true, reason: message };
  }

  await admin
    .from("discord_links")
    .update({
      app_role_granted: shouldHold,
      last_sync_error: null,
      last_synced_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    })
    .eq("user_id", userId);

  console.log(
    `[entitlement] ${userId} -> app role ${shouldHold ? "granted" : "revoked"}`,
  );
  return { skipped: false, granted: shouldHold, revoked: !shouldHold };
}
