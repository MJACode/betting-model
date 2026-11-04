// App Review sign-in. One email, one fixed code, both from secrets.
//
// verify_jwt is false: the caller has no session yet. The gate is the two
// secrets plus the attempt table. Deploy with:
//   supabase functions deploy app-review-sign-in --no-verify-jwt
//
// Secrets (Supabase dashboard → Edge Functions → Secrets):
//   APP_REVIEW_DEMO_EMAIL   must be review@signalbase-ai.com (the app
//                           constant). Any other value never receives a call
//                           from this app.
//   APP_REVIEW_DEMO_OTP     six digits. Never committed. Unset it after
//                           App Review approves the binary.
//
// Wrong codes are counted per caller, and again across every caller.
// The table stores a SHA-256 of the edge address (cf-connecting-ip, else
// the last x-forwarded-for hop), not the address and not the first hop.
// A full per-caller bucket, or more than 200 failures in an hour from
// everyone, is 429 before the code is compared. A database error on that
// count is 503, not "not configured".
//
// SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_ROLE_KEY are injected.
//
// The attempt table is data/migrations/app_review_sign_in_attempts_2026_11_04.sql.
// It is not in ACTIVE_MIGRATIONS. Until that SQL is applied by hand, this
// function refuses every code, including the right one.

import { createClient, type SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

import {
  REVIEW_CODE_MISMATCH,
  REVIEW_FAILURE_WINDOW_MS,
  REVIEW_GLOBAL_WINDOW_MS,
  REVIEW_MINT_FAILED,
  REVIEW_NOT_CONFIGURED,
  REVIEW_TOO_MANY,
  REVIEW_UNAVAILABLE,
  clientIpFromHeaders,
  hashAttemptBucket,
  normalizeReviewEmail,
  reviewBypassConfigured,
  reviewCredentialsMatch,
  reviewFailureLimitReached,
  reviewGlobalFailureLimitReached,
} from "../_shared/appReviewSignIn.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const ANON_KEY = Deno.env.get("SUPABASE_ANON_KEY") ?? "";

const ATTEMPTS = "app_review_sign_in_attempts";

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

function notConfigured(): Response {
  return json({ error: REVIEW_NOT_CONFIGURED }, 404);
}

function unavailable(): Response {
  return json({ error: REVIEW_UNAVAILABLE }, 503);
}

function alreadyRegistered(error: { code?: string }): boolean {
  return (error.code ?? "").toLowerCase() === "email_exists";
}

async function attemptsTableReady(admin: SupabaseClient): Promise<boolean> {
  const { error } = await admin
    .from(ATTEMPTS)
    .select("id", { count: "exact", head: true })
    .limit(1);
  return !error;
}

async function recentGlobalFailures(admin: SupabaseClient): Promise<number | null> {
  const since = new Date(Date.now() - REVIEW_GLOBAL_WINDOW_MS).toISOString();
  const { count, error } = await admin
    .from(ATTEMPTS)
    .select("id", { count: "exact", head: true })
    .gte("attempted_at", since);
  if (error || count == null) return null;
  return count;
}

async function overFailureLimit(
  admin: SupabaseClient,
  bucket: string,
): Promise<boolean | null> {
  const perCaller = await recentFailures(admin, bucket);
  if (perCaller == null) return null;
  const everyone = await recentGlobalFailures(admin);
  if (everyone == null) return null;
  return reviewFailureLimitReached(perCaller) || reviewGlobalFailureLimitReached(everyone);
}

async function recentFailures(
  admin: SupabaseClient,
  bucket: string,
): Promise<number | null> {
  const since = new Date(Date.now() - REVIEW_FAILURE_WINDOW_MS).toISOString();
  const { count, error } = await admin
    .from(ATTEMPTS)
    .select("id", { count: "exact", head: true })
    .eq("bucket", bucket)
    .gte("attempted_at", since);
  if (error || count == null) return null;
  return count;
}

async function recordFailure(admin: SupabaseClient, bucket: string): Promise<boolean> {
  const { error } = await admin.from(ATTEMPTS).insert({
    bucket,
    attempted_at: new Date().toISOString(),
  });
  if (error) return false;
  const dayAgo = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString();
  await admin.from(ATTEMPTS).delete().lt("attempted_at", dayAgo);
  return true;
}

async function ensureUser(admin: SupabaseClient, email: string): Promise<boolean> {
  const { error } = await admin.auth.admin.createUser({
    email,
    email_confirm: true,
  });
  if (!error) return true;
  return alreadyRegistered(error);
}

async function mintSession(
  admin: SupabaseClient,
  anon: SupabaseClient,
  email: string,
): Promise<{ access_token: string; refresh_token: string } | null> {
  if (!await ensureUser(admin, email)) return null;
  const link = await admin.auth.admin.generateLink({ type: "magiclink", email });
  const properties = link.data?.properties as { hashed_token?: string } | undefined;
  const tokenHash = properties?.hashed_token;
  if (link.error || !tokenHash) return null;
  const verified = await anon.auth.verifyOtp({
    token_hash: tokenHash,
    type: "magiclink",
  });
  const session = verified.data?.session;
  if (verified.error || !session?.access_token || !session.refresh_token) return null;
  return {
    access_token: session.access_token,
    refresh_token: session.refresh_token,
  };
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: REVIEW_NOT_CONFIGURED }, 405);

  const emailSecret = Deno.env.get("APP_REVIEW_DEMO_EMAIL");
  const otpSecret = Deno.env.get("APP_REVIEW_DEMO_OTP");
  if (!reviewBypassConfigured(emailSecret, otpSecret)) return notConfigured();
  if (!SUPABASE_URL || !SERVICE_ROLE || !ANON_KEY) return notConfigured();

  const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  if (!await attemptsTableReady(admin)) return notConfigured();

  // The per-caller cap and the hourly ceiling are both checked before the
  // code is compared. The address is cf-connecting-ip, else the last
  // forwarded hop. The first hop is ignored.
  const bucket = await hashAttemptBucket(
    clientIpFromHeaders(
      req.headers.get("cf-connecting-ip"),
      req.headers.get("x-forwarded-for"),
    ),
  );
  const blocked = await overFailureLimit(admin, bucket);
  if (blocked == null) return unavailable();
  if (blocked) return json({ error: REVIEW_TOO_MANY }, 429);

  let body: { email?: unknown; token?: unknown };
  try {
    body = await req.json();
  } catch {
    return json({ error: REVIEW_CODE_MISMATCH }, 401);
  }
  const email = typeof body.email === "string" ? body.email : "";
  const token = typeof body.token === "string" ? body.token : "";

  const expectedEmail = normalizeReviewEmail(emailSecret ?? "");
  if (!reviewCredentialsMatch(email, token, expectedEmail, (otpSecret ?? "").trim())) {
    if (!await recordFailure(admin, bucket)) return unavailable();
    const blockedAfter = await overFailureLimit(admin, bucket);
    if (blockedAfter == null) return unavailable();
    if (blockedAfter) return json({ error: REVIEW_TOO_MANY }, 429);
    return json({ error: REVIEW_CODE_MISMATCH }, 401);
  }

  const anon = createClient(SUPABASE_URL, ANON_KEY, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const session = await mintSession(admin, anon, expectedEmail);
  if (!session) return json({ error: REVIEW_MINT_FAILED }, 500);
  return json(session, 200);
});
