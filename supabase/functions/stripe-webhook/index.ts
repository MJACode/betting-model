// Stripe webhook → subscription entitlement.
//
// This function is the ONLY thing that grants or revokes access. The app never
// writes `subscriptions`, and the checkout function only records the customer
// id — so a client cannot fake an entitlement, even by replaying a success URL.
//
// verify_jwt MUST be false (Stripe doesn't send a Supabase JWT). Authenticity
// comes from the Stripe-Signature header instead, verified below.
//
// Secrets:
//   STRIPE_SECRET_KEY       sk_test_… / sk_live_…
//   STRIPE_WEBHOOK_SECRET   whsec_… (from the Stripe dashboard endpoint)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

const STRIPE_API = "https://api.stripe.com/v1";
const STRIPE_KEY = Deno.env.get("STRIPE_SECRET_KEY") ?? "";
const WEBHOOK_SECRET = Deno.env.get("STRIPE_WEBHOOK_SECRET") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

/** Reject events older than this to blunt replay attacks. Stripe's default. */
const TOLERANCE_SEC = 300;

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

// ── Signature verification ──────────────────────────────────────────────────
// Implemented directly rather than via the Stripe SDK so there's no ambiguity
// about what's being checked: HMAC-SHA256 over `${timestamp}.${rawBody}`,
// compared against the v1 signature, in constant time, within the tolerance.

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

function toHex(buf: ArrayBuffer): string {
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function verifySignature(
  rawBody: string,
  header: string | null,
): Promise<{ ok: boolean; reason?: string }> {
  if (!WEBHOOK_SECRET) return { ok: false, reason: "STRIPE_WEBHOOK_SECRET not set" };
  if (!header) return { ok: false, reason: "missing Stripe-Signature" };

  // Header looks like: t=1492774577,v1=<hex>,v1=<hex>
  let timestamp = "";
  const signatures: string[] = [];
  for (const part of header.split(",")) {
    const [k, v] = part.split("=", 2);
    if (k?.trim() === "t") timestamp = v ?? "";
    if (k?.trim() === "v1" && v) signatures.push(v);
  }
  if (!timestamp || signatures.length === 0) {
    return { ok: false, reason: "malformed Stripe-Signature" };
  }

  const age = Math.abs(Math.floor(Date.now() / 1000) - Number(timestamp));
  if (!Number.isFinite(age) || age > TOLERANCE_SEC) {
    return { ok: false, reason: "timestamp outside tolerance" };
  }

  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(WEBHOOK_SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const mac = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(`${timestamp}.${rawBody}`),
  );
  const expected = toHex(mac);

  // Stripe may send several v1 signatures during a secret rotation.
  const ok = signatures.some((s) => timingSafeEqual(s, expected));
  return ok ? { ok: true } : { ok: false, reason: "signature mismatch" };
}

// ── Entitlement mapping ─────────────────────────────────────────────────────

const PRICE_TO_PLAN: Record<string, string> = {
  [Deno.env.get("STRIPE_PRICE_MONTHLY") ?? "__m"]: "monthly",
  [Deno.env.get("STRIPE_PRICE_SEMIANNUAL") ?? "__s"]: "semiannual",
  [Deno.env.get("STRIPE_PRICE_ANNUAL") ?? "__a"]: "annual",
};

function iso(unix: number | null | undefined): string | null {
  return unix ? new Date(unix * 1000).toISOString() : null;
}

async function stripeGet(path: string): Promise<any> {
  const res = await fetch(`${STRIPE_API}${path}`, {
    headers: { Authorization: `Bearer ${STRIPE_KEY}` },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error?.message ?? `Stripe ${path}`);
  return data;
}

/**
 * Resolve which of our users a Stripe subscription belongs to.
 *
 * Prefers the metadata we stamped at checkout; falls back to the customer id we
 * already recorded. The fallback matters for subscriptions created outside our
 * checkout flow (a manual one in the Stripe dashboard, say).
 */
async function resolveUserId(sub: any): Promise<string | null> {
  const fromMeta = sub?.metadata?.supabase_user_id;
  if (fromMeta) return fromMeta as string;

  const customerId = typeof sub.customer === "string" ? sub.customer : sub.customer?.id;
  if (!customerId) return null;

  const { data } = await admin
    .from("subscriptions")
    .select("user_id")
    .eq("stripe_customer_id", customerId)
    .maybeSingle();
  if (data?.user_id) return data.user_id as string;

  // Last resort: the customer object itself carries the id we set at creation.
  try {
    const customer = await stripeGet(`/customers/${customerId}`);
    return customer?.metadata?.supabase_user_id ?? null;
  } catch {
    return null;
  }
}

async function applySubscription(sub: any): Promise<string> {
  const userId = await resolveUserId(sub);
  if (!userId) return "no user resolved — ignored";

  const priceId: string | undefined = sub?.items?.data?.[0]?.price?.id;
  const plan = sub?.metadata?.plan ?? (priceId ? PRICE_TO_PLAN[priceId] : null);
  const customerId = typeof sub.customer === "string" ? sub.customer : sub.customer?.id;

  const { error } = await admin.from("subscriptions").upsert(
    {
      user_id: userId,
      stripe_customer_id: customerId ?? null,
      stripe_subscription_id: sub.id,
      status: sub.status,
      plan: plan ?? null,
      price_id: priceId ?? null,
      current_period_end: iso(sub.current_period_end),
      trial_end: iso(sub.trial_end),
      cancel_at_period_end: Boolean(sub.cancel_at_period_end),
      updated_at: new Date().toISOString(),
    },
    { onConflict: "user_id" },
  );
  if (error) throw new Error(`upsert failed: ${error.message}`);
  return `${userId} → ${sub.status}`;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") return new Response("method not allowed", { status: 405 });

  // Signature must be computed over the RAW body — parsing first would change
  // the bytes and every signature would fail.
  const rawBody = await req.text();
  const check = await verifySignature(rawBody, req.headers.get("Stripe-Signature"));
  if (!check.ok) {
    console.warn("[stripe-webhook] rejected:", check.reason);
    return new Response(`invalid signature: ${check.reason}`, { status: 400 });
  }

  let event: any;
  try {
    event = JSON.parse(rawBody);
  } catch {
    return new Response("bad json", { status: 400 });
  }

  try {
    let result = "ignored";
    switch (event.type) {
      case "checkout.session.completed": {
        const session = event.data.object;
        if (session.subscription) {
          const sub = await stripeGet(`/subscriptions/${session.subscription}`);
          // Checkout metadata is the most reliable attribution we have.
          sub.metadata = {
            ...(sub.metadata ?? {}),
            supabase_user_id:
              sub?.metadata?.supabase_user_id ??
              session?.metadata?.supabase_user_id ??
              session?.client_reference_id,
            plan: sub?.metadata?.plan ?? session?.metadata?.plan,
          };
          result = await applySubscription(sub);
        }
        break;
      }
      case "customer.subscription.created":
      case "customer.subscription.updated":
      case "customer.subscription.deleted":
      case "customer.subscription.paused":
      case "customer.subscription.resumed":
        result = await applySubscription(event.data.object);
        break;
      default:
        break;
    }
    console.log(`[stripe-webhook] ${event.type}: ${result}`);
    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    // 500 tells Stripe to retry — right for a transient DB failure, and
    // harmless for a permanent one since the upsert is idempotent.
    console.error("[stripe-webhook] handler failed", e);
    return new Response(e instanceof Error ? e.message : String(e), { status: 500 });
  }
});
