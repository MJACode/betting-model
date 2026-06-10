// SharpSports webhook receiver (verify_jwt=false — SharpSports has no Supabase JWT).
//
// SharpSports POSTs events here (bettor.created, bettorAccount.verified,
// bettorAccount.unverified, refreshResponse.created). We authenticate with a
// shared secret (?secret=… appended to the webhook URL we register) and then
// re-trigger a sync by invoking the main `sharpsports` function with the
// service-role key. All SharpSports/DB logic stays in one place (sharpsports).
//
// Secret: SHARPSPORTS_WEBHOOK_SECRET (optional but recommended).

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
const WEBHOOK_SECRET = Deno.env.get("SHARPSPORTS_WEBHOOK_SECRET") ?? "";

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

function pick(obj: any, ...keys: string[]): string | null {
  for (const k of keys) {
    const v = k.split(".").reduce((o, p) => (o == null ? o : o[p]), obj);
    if (v !== undefined && v !== null) return String(v);
  }
  return null;
}

async function internalIdFor(event: any): Promise<string | null> {
  const direct = pick(
    event,
    "internalId",
    "bettor.internalId",
    "data.bettor.internalId",
    "bettorAccount.bettor.internalId",
  );
  if (direct) return direct;

  // Only a bettor id on the event — resolve via a previously-stored account.
  const bettorId = pick(event, "bettor.id", "bettorId", "data.bettor.id");
  if (!bettorId) return null;
  const { data } = await admin
    .from("linked_sportsbook_accounts")
    .select("internal_id")
    .eq("bettor_id", bettorId)
    .limit(1)
    .maybeSingle();
  return data?.internal_id ?? null;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("POST only", { status: 405 });
  }
  if (WEBHOOK_SECRET) {
    const url = new URL(req.url);
    const provided = url.searchParams.get("secret") ?? req.headers.get("x-webhook-secret");
    if (provided !== WEBHOOK_SECRET) {
      return new Response("unauthorized", { status: 401 });
    }
  }

  let event: any;
  try {
    event = await req.json();
  } catch {
    return new Response("invalid JSON", { status: 400 });
  }

  const internalId = await internalIdFor(event);
  if (!internalId) {
    // Nothing to sync (e.g. event we can't map yet). Ack so SharpSports doesn't retry forever.
    return new Response("ok (no internalId)", { status: 200 });
  }

  // Re-trigger a fresh pull through the main function (service-role authorized).
  const fnUrl = `${SUPABASE_URL.replace(".supabase.co", ".functions.supabase.co")}/sharpsports`;
  try {
    await fetch(fnUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${SERVICE_ROLE}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ action: "bets", internalId, refresh: true }),
    });
  } catch (e) {
    console.error("sync trigger failed", e);
  }

  return new Response("ok", { status: 200 });
});
