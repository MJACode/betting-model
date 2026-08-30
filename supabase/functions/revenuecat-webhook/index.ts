// RevenueCat webhook → subscription entitlement (the IAP rail's counterpart
// to stripe-webhook).
//
// RevenueCat validates the App Store / Play receipts; this function just maps
// its events onto our `subscriptions` table. It is the ONLY writer for
// IAP-granted entitlement — the app never writes the table, so a client can't
// fake a purchase.
//
// verify_jwt MUST be false (RevenueCat doesn't send a Supabase JWT).
// Authenticity comes from the Authorization header instead: RevenueCat sends
// whatever value you configure on the webhook, compared constant-time against
// REVENUECAT_WEBHOOK_AUTH.
//
// Identity: the mobile app configures the RevenueCat SDK with
// appUserID = the Supabase auth user id, so `event.app_user_id` IS our
// user_id. Anonymous ids ($RCAnonymousID:…) can only appear if something
// purchased before sign-in — we don't offer that path, so they're logged and
// ignored rather than guessed at.
//
// Secrets:
//   REVENUECAT_WEBHOOK_AUTH   the Authorization header value set in the
//                             RevenueCat webhook config (any long random string)
//   RC_PRODUCT_WEEKLY / RC_PRODUCT_MONTHLY / RC_PRODUCT_ANNUAL
//                             optional store product ids for exact plan
//                             mapping; a substring heuristic is the fallback
//
// Discord: after writing the row this syncs the member's app-subscriber role
// in the guild, so paying in the app grants Discord access and letting the
// subscription lapse takes it back. It only ever touches OUR role — a member
// who also pays through Whop keeps Whop's role and their access. See
// _shared/entitlement.ts.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

import { syncAppRoleForUser } from "../_shared/entitlement.ts";

const AUTH_VALUE = Deno.env.get("REVENUECAT_WEBHOOK_AUTH") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Env-pinned product ids beat the heuristic when configured. */
const PRODUCT_TO_PLAN: Record<string, string> = {
  [Deno.env.get("RC_PRODUCT_WEEKLY") ?? "__w"]: "weekly",
  [Deno.env.get("RC_PRODUCT_MONTHLY") ?? "__m"]: "monthly",
  [Deno.env.get("RC_PRODUCT_ANNUAL") ?? "__a"]: "annual",
};

/**
 * Substring fallback. ORDER MATTERS — 'annual|year' is tested before 'week',
 * because a yearly id like "com...sub.annual" carries no week marker but a
 * "52_week" style id would otherwise resolve to weekly. Kept in sync with
 * planForProductId in mobile/src/lib/iapHelpers.ts.
 *
 * Legacy 'semiannual' ids still map, so a product created during the
 * six-month-plan era does not resolve to the wrong (cheaper) plan name if one
 * is ever replayed. The plan column is display metadata; entitlement never
 * depends on it.
 */
function planForProductId(productId: string): string | null {
  const pinned = PRODUCT_TO_PLAN[productId];
  if (pinned) return pinned;
  const id = productId.toLowerCase();
  if (/annual|year/.test(id)) return "annual";
  if (/six|semi|6mo|6_mo|halfyear|half_year/.test(id)) return "semiannual";
  if (/week|wk/.test(id)) return "weekly";
  if (/month/.test(id)) return "monthly";
  return null;
}

function iso(ms: number | null | undefined): string | null {
  return ms ? new Date(ms).toISOString() : null;
}

interface RcEvent {
  type: string;
  app_user_id?: string;
  original_app_user_id?: string;
  product_id?: string;
  period_type?: string; // TRIAL | INTRO | NORMAL
  purchased_at_ms?: number;
  expiration_at_ms?: number;
  store?: string; // APP_STORE | PLAY_STORE | …
  cancel_reason?: string; // UNSUBSCRIBE | BILLING_ERROR | …
}

/** Map a RevenueCat event onto our Stripe-vocabulary status column. */
function statusFor(ev: RcEvent): {
  status: string;
  cancelAtPeriodEnd: boolean;
} | null {
  const trialing = ev.period_type === "TRIAL";
  switch (ev.type) {
    case "INITIAL_PURCHASE":
    case "RENEWAL":
    case "UNCANCELLATION":
    case "PRODUCT_CHANGE":
    case "NON_RENEWING_PURCHASE":
      return { status: trialing ? "trialing" : "active", cancelAtPeriodEnd: false };
    case "CANCELLATION":
      // Auto-renew switched off (or a refund): access continues to period end,
      // exactly like Stripe's cancel_at_period_end. A billing-error cancel is
      // a payment problem, not a choice.
      if (ev.cancel_reason === "BILLING_ERROR") {
        return { status: "past_due", cancelAtPeriodEnd: true };
      }
      return { status: trialing ? "trialing" : "active", cancelAtPeriodEnd: true };
    case "EXPIRATION":
      return { status: "canceled", cancelAtPeriodEnd: false };
    case "BILLING_ISSUE":
      return { status: "past_due", cancelAtPeriodEnd: false };
    default:
      // TEST, TRANSFER, SUBSCRIPTION_PAUSED, etc. — log-only in v1.
      return null;
  }
}

function resolveUserId(ev: RcEvent): string | null {
  for (const candidate of [ev.app_user_id, ev.original_app_user_id]) {
    if (candidate && UUID_RE.test(candidate)) return candidate;
  }
  return null;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }

  const header = req.headers.get("Authorization") ?? "";
  if (!AUTH_VALUE || !timingSafeEqual(header, AUTH_VALUE)) {
    console.warn("[revenuecat-webhook] rejected: bad Authorization header");
    return new Response("unauthorized", { status: 401 });
  }

  let body: { event?: RcEvent };
  try {
    body = await req.json();
  } catch {
    return new Response("bad json", { status: 400 });
  }
  const ev = body.event;
  if (!ev?.type) return new Response("no event", { status: 400 });

  try {
    const mapped = statusFor(ev);
    if (!mapped) {
      console.log(`[revenuecat-webhook] ${ev.type}: ignored`);
      return new Response(JSON.stringify({ received: true }), { status: 200 });
    }

    const userId = resolveUserId(ev);
    if (!userId) {
      // Anonymous or malformed app_user_id. 200, not 500 — retrying won't
      // make an unmappable event mappable.
      console.warn(
        `[revenuecat-webhook] ${ev.type}: no resolvable user (app_user_id=${ev.app_user_id ?? "?"}) — ignored`,
      );
      return new Response(JSON.stringify({ received: true }), { status: 200 });
    }

    const { error } = await admin.from("subscriptions").upsert(
      {
        user_id: userId,
        rc_app_user_id: ev.app_user_id ?? null,
        store: (ev.store ?? "app_store").toLowerCase(),
        status: mapped.status,
        plan: ev.product_id ? planForProductId(ev.product_id) : null,
        price_id: ev.product_id ?? null,
        current_period_end: iso(ev.expiration_at_ms),
        trial_end: ev.period_type === "TRIAL" ? iso(ev.expiration_at_ms) : null,
        cancel_at_period_end: mapped.cancelAtPeriodEnd,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "user_id" },
    );
    if (error) throw new Error(`upsert failed: ${error.message}`);

    // Now make Discord match. Never throws — the subscription row is already
    // written, and failing this response would make RevenueCat retry an upsert
    // that succeeded. A Discord failure is recorded on the link row instead.
    await syncAppRoleForUser(admin, userId);

    console.log(`[revenuecat-webhook] ${ev.type}: ${userId} → ${mapped.status}`);
    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    // 500 tells RevenueCat to retry — right for a transient DB failure, and
    // harmless for a permanent one since the upsert is idempotent.
    console.error("[revenuecat-webhook] handler failed", e);
    return new Response(e instanceof Error ? e.message : String(e), { status: 500 });
  }
});
