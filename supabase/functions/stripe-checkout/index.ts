// Stripe Checkout session creator.
//
// The app calls this with the signed-in user's Supabase JWT (verify_jwt=true).
// It finds or creates that user's Stripe Customer, then returns a Checkout
// Session URL the app opens in a browser. Stripe collects payment; our
// stripe-webhook function is what actually grants entitlement.
//
// Two rules this function exists to enforce, both of which matter:
//
//  1. The PRICE IS CHOSEN SERVER-SIDE. The client sends a plan key
//     ("monthly" | "semiannual" | "annual"), never a price id — otherwise
//     anyone could post a $0 price id of their own and check out against it.
//  2. The USER COMES FROM THE JWT, never the request body, so a caller can't
//     create a subscription attached to somebody else's account.
//
// Secrets (supabase secrets set):
//   STRIPE_SECRET_KEY            sk_test_… / sk_live_…
//   STRIPE_PRICE_MONTHLY         price_…  ($29.99 / month)
//   STRIPE_PRICE_SEMIANNUAL      price_…  ($129.99 / 6 months)
//   STRIPE_PRICE_ANNUAL          price_…  ($199.99 / year)
//   STRIPE_TRIAL_DAYS            optional, defaults to 7
//   BILLING_RETURN_URL           optional, defaults to the app scheme below
// SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are injected automatically.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

const STRIPE_API = "https://api.stripe.com/v1";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...cors, "Content-Type": "application/json" },
  });
}

const STRIPE_KEY = Deno.env.get("STRIPE_SECRET_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const TRIAL_DAYS = Number(Deno.env.get("STRIPE_TRIAL_DAYS") ?? "7");
const RETURN_URL =
  Deno.env.get("BILLING_RETURN_URL") ?? "signalbase://billing-return";

/** plan key → price id. Server-side only; the client never sends a price id. */
const PRICES: Record<string, string> = {
  monthly: Deno.env.get("STRIPE_PRICE_MONTHLY") ?? "",
  semiannual: Deno.env.get("STRIPE_PRICE_SEMIANNUAL") ?? "",
  annual: Deno.env.get("STRIPE_PRICE_ANNUAL") ?? "",
};

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

/** Stripe's REST API is form-encoded, so nested params need bracket keys. */
function form(params: Record<string, string | number | boolean | undefined>) {
  const body = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") body.set(k, String(v));
  }
  return body;
}

async function stripe(
  path: string,
  body?: URLSearchParams,
  method = "POST",
): Promise<any> {
  const res = await fetch(`${STRIPE_API}${path}`, {
    method,
    headers: {
      Authorization: `Bearer ${STRIPE_KEY}`,
      "Content-Type": "application/x-www-form-urlencoded",
    },
    body,
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data?.error?.message ?? `Stripe ${path} → ${res.status}`);
  }
  return data;
}

/**
 * Reuse the user's Stripe Customer if we've already made one, else create it.
 * Reusing matters: a second customer for the same person splits their billing
 * history and can let them start a second concurrent subscription.
 */
async function customerFor(userId: string, email: string | null) {
  const { data: existing } = await admin
    .from("subscriptions")
    .select("stripe_customer_id")
    .eq("user_id", userId)
    .maybeSingle();

  if (existing?.stripe_customer_id) return existing.stripe_customer_id as string;

  const customer = await stripe(
    "/customers",
    form({
      email: email ?? undefined,
      "metadata[supabase_user_id]": userId,
    }),
  );

  // Record it immediately so a failed checkout doesn't orphan the customer and
  // cause a duplicate on the next attempt.
  await admin.from("subscriptions").upsert(
    {
      user_id: userId,
      stripe_customer_id: customer.id,
      status: "incomplete",
      updated_at: new Date().toISOString(),
    },
    { onConflict: "user_id" },
  );

  return customer.id as string;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    if (!STRIPE_KEY) return json({ error: "STRIPE_SECRET_KEY not set" }, 500);

    // Identify the caller from their JWT — never from the request body.
    const authHeader = req.headers.get("Authorization") ?? "";
    const token = authHeader.replace(/^Bearer\s+/i, "");
    if (!token) return json({ error: "Not signed in." }, 401);

    const { data: userData, error: userErr } = await admin.auth.getUser(token);
    if (userErr || !userData?.user) {
      return json({ error: "Not signed in." }, 401);
    }
    const user = userData.user;

    const body = await req.json().catch(() => ({}));
    const plan = String(body?.plan ?? "");
    const priceId = PRICES[plan];
    if (!priceId) {
      return json(
        { error: `Unknown or unconfigured plan: ${plan || "(none)"}` },
        400,
      );
    }

    // Don't let an already-subscribed user start a second subscription.
    const { data: current } = await admin
      .from("subscriptions")
      .select("status")
      .eq("user_id", user.id)
      .maybeSingle();
    if (current && ["trialing", "active"].includes(current.status)) {
      return json({ error: "You already have an active subscription." }, 409);
    }

    const customerId = await customerFor(user.id, user.email ?? null);

    const params = form({
      mode: "subscription",
      customer: customerId,
      "line_items[0][price]": priceId,
      "line_items[0][quantity]": 1,
      success_url: `${RETURN_URL}?status=success`,
      cancel_url: `${RETURN_URL}?status=cancelled`,
      // Carried onto the subscription so the webhook can attribute it even if
      // the checkout.session event is missed or arrives out of order.
      "subscription_data[metadata][supabase_user_id]": user.id,
      "subscription_data[metadata][plan]": plan,
      "metadata[supabase_user_id]": user.id,
      "metadata[plan]": plan,
      allow_promotion_codes: true,
      client_reference_id: user.id,
    });
    if (TRIAL_DAYS > 0) {
      params.set("subscription_data[trial_period_days]", String(TRIAL_DAYS));
    }

    const session = await stripe("/checkout/sessions", params);
    return json({ url: session.url, sessionId: session.id });
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
