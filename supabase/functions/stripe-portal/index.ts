// Stripe Billing Portal session.
//
// Returns a URL where the signed-in user can update their card, switch plan, or
// cancel. This is not optional polish: App Store guideline 3.1.2 requires a
// clear way to manage and cancel a subscription, and card networks expect a
// self-serve cancel path. Building the equivalent by hand would be far more
// code and more ways to get refunds wrong.
//
// Secrets: STRIPE_SECRET_KEY, optional BILLING_RETURN_URL.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

const STRIPE_API = "https://api.stripe.com/v1";
const STRIPE_KEY = Deno.env.get("STRIPE_SECRET_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const RETURN_URL =
  Deno.env.get("BILLING_RETURN_URL") ?? "signalbase://billing-return";

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

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });

  try {
    if (!STRIPE_KEY) return json({ error: "STRIPE_SECRET_KEY not set" }, 500);

    const token = (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "");
    if (!token) return json({ error: "Not signed in." }, 401);

    const { data: userData, error: userErr } = await admin.auth.getUser(token);
    if (userErr || !userData?.user) return json({ error: "Not signed in." }, 401);

    // The customer id comes from OUR table keyed by the JWT's user — never from
    // the request body, or a caller could open someone else's billing portal.
    const { data: row } = await admin
      .from("subscriptions")
      .select("stripe_customer_id")
      .eq("user_id", userData.user.id)
      .maybeSingle();

    if (!row?.stripe_customer_id) {
      return json({ error: "No billing account yet." }, 404);
    }

    const body = new URLSearchParams({
      customer: row.stripe_customer_id,
      return_url: RETURN_URL,
    });

    const res = await fetch(`${STRIPE_API}/billing_portal/sessions`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${STRIPE_KEY}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body,
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data?.error?.message ?? `Stripe portal → ${res.status}`);
    }

    return json({ url: data.url });
  } catch (e) {
    return json({ error: e instanceof Error ? e.message : String(e) }, 500);
  }
});
