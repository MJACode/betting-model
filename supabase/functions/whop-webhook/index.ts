// Whop webhook → Discord-side membership state.
//
// Whop sells the Discord membership and assigns its own role in the server.
// This function does NOT touch roles — Whop already owns that half. Its job is
// to mirror membership validity into `whop_memberships` so the app can answer
// "this person already pays through Discord, so the app is included."
//
// That mirror is what makes both halves of the rule work:
//   * Whop membership goes VALID   -> the linked app account is entitled, free
//   * Whop membership goes INVALID -> that free access disappears on the next
//                                     read, unless they also pay in the app
//
// Access is COMPUTED on read (public.my_access()), never cached as a grant, so
// a revocation takes effect the moment this row flips — there is no second
// table to keep in step and no window where a cancelled member still holds a
// stale entitlement.
//
// verify_jwt MUST be false (Whop sends no Supabase JWT). Authenticity is an
// HMAC-SHA256 signature over the RAW body, compared constant-time.
//
// Secrets:
//   WHOP_WEBHOOK_SECRET   the signing secret from the Whop webhook settings
//
// Deploy:
//   supabase functions deploy whop-webhook --no-verify-jwt

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

const SECRET = Deno.env.get("WHOP_WEBHOOK_SECRET") ?? "";
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

/**
 * Verify the signature over the raw body.
 *
 * Raw body, not the re-serialized JSON: `JSON.parse` then `JSON.stringify`
 * reorders nothing but does change whitespace and unicode escaping, and the
 * digest is over the exact bytes Whop sent. This is the same mistake the
 * Stripe webhook guards against.
 *
 * Whop has used more than one header name across versions, so we accept any of
 * them and tolerate a `sha256=` prefix.
 */
async function signatureValid(raw: string, header: string): Promise<boolean> {
  if (!SECRET || !header) return false;
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(SECRET),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(raw));
  const expected = [...new Uint8Array(sig)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  const provided = header.replace(/^sha256=/i, "").trim().toLowerCase();
  return timingSafeEqual(provided, expected);
}

interface WhopMembership {
  id?: string;
  user_id?: string;
  user?: { id?: string; email?: string; discord_id?: string };
  email?: string;
  discord_id?: string;
  discord?: { id?: string };
  product_id?: string;
  plan_id?: string;
  status?: string;
  valid?: boolean;
  renewal_period_end?: string | number | null;
  metadata?: Record<string, unknown>;
}

/**
 * Whop's payload shape has moved between API versions and differs by event, so
 * every identity field is read from several plausible places. Anything we
 * can't find stays null — both `discord_user_id` and `email` are match keys,
 * and one of them is enough.
 */
function readDiscordId(m: WhopMembership): string | null {
  const candidates = [
    m.discord_id,
    m.discord?.id,
    m.user?.discord_id,
    typeof m.metadata?.discord_id === "string" ? m.metadata.discord_id : undefined,
  ];
  for (const c of candidates) {
    if (typeof c === "string" && /^\d{5,}$/.test(c)) return c;
  }
  return null;
}

function readEmail(m: WhopMembership): string | null {
  const raw = m.email ?? m.user?.email ?? null;
  return typeof raw === "string" && raw.includes("@") ? raw.trim().toLowerCase() : null;
}

function readPeriodEnd(m: WhopMembership): string | null {
  const raw = m.renewal_period_end;
  if (raw == null) return null;
  // Whop sends seconds-since-epoch on some events and an ISO string on others.
  if (typeof raw === "number") return new Date(raw * 1000).toISOString();
  const parsed = Date.parse(raw);
  return Number.isNaN(parsed) ? null : new Date(parsed).toISOString();
}

/**
 * Does this event's membership grant access?
 *
 * Whop's own `valid` boolean is authoritative when present — it already folds
 * in trials, grace periods and cancellations that run to period end, and
 * re-deriving that from `status` is how the two sides drift apart. The event
 * name is the fallback for payloads that omit it.
 */
function readValid(m: WhopMembership, eventType: string): boolean {
  if (typeof m.valid === "boolean") return m.valid;
  if (eventType.endsWith("went_valid")) return true;
  if (eventType.endsWith("went_invalid")) return false;
  return ["active", "trialing", "completed"].includes((m.status ?? "").toLowerCase());
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("method not allowed", { status: 405 });
  }

  const raw = await req.text();
  const header = req.headers.get("X-Whop-Signature") ??
    req.headers.get("whop-signature") ??
    req.headers.get("X-Whop-Webhook-Signature") ??
    "";

  if (!(await signatureValid(raw, header))) {
    console.warn("[whop-webhook] rejected: bad signature");
    return new Response("unauthorized", { status: 401 });
  }

  let body: { action?: string; event?: string; data?: WhopMembership };
  try {
    body = JSON.parse(raw);
  } catch {
    return new Response("bad json", { status: 400 });
  }

  const eventType = (body.action ?? body.event ?? "").toLowerCase();
  const membership = body.data;
  if (!eventType || !membership) {
    return new Response("no event", { status: 400 });
  }

  const membershipId = membership.id;
  if (!membershipId) {
    // Unmappable, and a retry won't add an id. 200 so Whop stops resending.
    console.warn(`[whop-webhook] ${eventType}: no membership id — ignored`);
    return new Response(JSON.stringify({ received: true }), { status: 200 });
  }

  // Membership lifecycle only. Payment events carry no membership validity we
  // don't already get from went_valid / went_invalid, and acting on them would
  // grant access on a payment that later fails.
  if (!eventType.startsWith("membership")) {
    console.log(`[whop-webhook] ${eventType}: ignored (not a membership event)`);
    return new Response(JSON.stringify({ received: true }), { status: 200 });
  }

  try {
    const valid = readValid(membership, eventType);
    const { error } = await admin.from("whop_memberships").upsert(
      {
        membership_id: membershipId,
        whop_user_id: membership.user_id ?? membership.user?.id ?? null,
        discord_user_id: readDiscordId(membership),
        email: readEmail(membership),
        product_id: membership.product_id ?? null,
        plan_id: membership.plan_id ?? null,
        status: membership.status ?? (valid ? "active" : "inactive"),
        valid,
        renewal_period_end: readPeriodEnd(membership),
        raw: membership,
        updated_at: new Date().toISOString(),
      },
      { onConflict: "membership_id" },
    );
    if (error) throw new Error(`upsert failed: ${error.message}`);

    console.log(
      `[whop-webhook] ${eventType}: ${membershipId} → valid=${valid}`,
    );
    return new Response(JSON.stringify({ received: true }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  } catch (e) {
    // 500 tells Whop to retry — right for a transient DB failure, harmless for
    // a permanent one because the upsert is idempotent.
    console.error("[whop-webhook] handler failed", e);
    return new Response(e instanceof Error ? e.message : String(e), { status: 500 });
  }
});
