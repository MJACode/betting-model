// SharpSports integration — account link (Booklink context) + read-only bet sync.
//
// One function, two actions (POST body { action }):
//   - "context": create a Booklink context for a device, return the hosted
//     link URL the app opens so the user can log into their sportsbook.
//   - "bets":    read this device's linked accounts + synced bets from our DB
//     (optionally pull fresh from SharpSports first when { refresh: true }).
//
// The SharpSports PRIVATE key lives only here (Edge Function secret) — never on
// device. The app authenticates with the Supabase anon JWT (verify_jwt=true);
// this function uses the service role to write the RLS-protected tables.
//
// Secrets (set via `supabase secrets set`):
//   SHARPSPORTS_PUBLIC_KEY   — public_… / public_sandbox_… (Booklink context)
//   SHARPSPORTS_PRIVATE_KEY  — private_… (bettor / betSlip reads, refresh)
//   SHARPSPORTS_WEBHOOK_URL  — optional; defaults to the sharpsports-webhook fn
//
// NOTE: SharpSports' exact JSON field names are taken from their docs and may
// differ slightly per account. Every upsert stores the full payload in `raw`,
// and reads come from our own tables, so a field rename is a localized fix.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.49.4";

const SS_BASE = "https://api.sharpsports.io/v1";
const SS_UI = "https://ui.sharpsports.io/link";

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

const PUBLIC_KEY = Deno.env.get("SHARPSPORTS_PUBLIC_KEY") ?? "";
const PRIVATE_KEY = Deno.env.get("SHARPSPORTS_PRIVATE_KEY") ?? "";
const SUPABASE_URL = Deno.env.get("SUPABASE_URL") ?? "";
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false, autoRefreshToken: false },
});

// ── SharpSports REST helpers ────────────────────────────────────────────────
async function ssGet(path: string): Promise<any> {
  const res = await fetch(`${SS_BASE}${path}`, {
    headers: { Authorization: `Token ${PRIVATE_KEY}` },
  });
  if (!res.ok) throw new Error(`SharpSports GET ${path} → ${res.status}`);
  return res.json();
}

async function ssPost(path: string, key: string, body?: unknown): Promise<any> {
  const res = await fetch(`${SS_BASE}${path}`, {
    method: "POST",
    headers: {
      Authorization: `Token ${key}`,
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`SharpSports POST ${path} → ${res.status}`);
  return res.json().catch(() => ({}));
}

function pick<T = unknown>(obj: any, ...keys: string[]): T | null {
  for (const k of keys) {
    const v = k.split(".").reduce((o, p) => (o == null ? o : o[p]), obj);
    if (v !== undefined && v !== null) return v as T;
  }
  return null;
}

function asArray(data: any): any[] {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.data)) return data.data;
  return [];
}

// ── Account link (Booklink context) ─────────────────────────────────────────
async function createContext(internalId: string): Promise<Response> {
  if (!PUBLIC_KEY) return json({ error: "SHARPSPORTS_PUBLIC_KEY not set" }, 500);
  const secret = Deno.env.get("SHARPSPORTS_WEBHOOK_SECRET") ?? "";
  const base =
    Deno.env.get("SHARPSPORTS_WEBHOOK_URL") ??
    `${SUPABASE_URL.replace(".supabase.co", ".functions.supabase.co")}/sharpsports-webhook`;
  const webhookUrl = secret ? `${base}?secret=${encodeURIComponent(secret)}` : base;

  const ctx = await ssPost("/context", PUBLIC_KEY, {
    internalId,
    webhookUrl,
  });
  const cid = pick<string>(ctx, "cid", "id");
  if (!cid) return json({ error: "no context id returned", raw: ctx }, 502);
  return json({ cid, url: `${SS_UI}/${cid}` });
}

// ── Bettor / account / betslip sync ─────────────────────────────────────────
async function resolveBettors(internalId: string): Promise<any[]> {
  // Preferred: filter by internalId. Fall back to listing + client filter.
  try {
    const data = await ssGet(`/bettors?internalId=${encodeURIComponent(internalId)}`);
    const arr = asArray(data);
    if (arr.length) return arr;
  } catch (_) {
    /* fall through */
  }
  const all = asArray(await ssGet(`/bettors`));
  return all.filter((b) => pick(b, "internalId", "internal_id") === internalId);
}

function americanFromBetSlip(b: any): number | null {
  const am = pick<number | string>(b, "oddsAmerican", "americanOdds", "odds.american");
  if (am != null) return Number(am);
  return null;
}

function isSettled(status: string | null): boolean {
  if (!status) return false;
  return ["won", "lost", "push", "refunded", "settled", "cashout", "void"].includes(
    status.toLowerCase(),
  );
}

async function pullAndUpsert(internalId: string): Promise<{ accounts: number; bets: number }> {
  const bettors = await resolveBettors(internalId);
  let accounts = 0;
  let bets = 0;

  for (const bettor of bettors) {
    const bettorId = pick<string>(bettor, "id", "bettorId");
    if (!bettorId) continue;

    // Best-effort refresh so subsequent reads are current. Non-fatal.
    try {
      await ssPost(`/bettors/${bettorId}/refresh`, PRIVATE_KEY);
    } catch (_) {
      /* refresh is async/eventual; ignore */
    }

    // Linked accounts (one per book/region).
    try {
      const accs = asArray(await ssGet(`/bettors/${bettorId}/bettorAccounts`));
      for (const a of accs) {
        const accId = pick<string>(a, "id", "bettorAccountId");
        if (!accId) continue;
        const verified = pick<boolean>(a, "verified", "isVerified");
        const status =
          pick<string>(a, "status") ?? (verified === false ? "unverified" : "verified");
        const row = {
          internal_id: internalId,
          bettor_id: bettorId,
          bettor_account_id: accId,
          book: pick<string>(a, "book.name", "bookName", "book"),
          book_abbr: (pick<string>(a, "book.abbr", "bookAbbr") ?? "")
            .toString()
            .toLowerCase() || null,
          book_region: pick<string>(a, "bookRegion.name", "bookRegion", "region.name"),
          status,
          linked_at: pick<string>(a, "verifiedAt", "createdAt", "linkedAt"),
          updated_at: new Date().toISOString(),
        };
        await admin.from("linked_sportsbook_accounts").upsert(row, {
          onConflict: "bettor_account_id",
        });
        accounts++;
      }
    } catch (e) {
      console.error(`bettorAccounts(${bettorId}) failed`, e);
    }

    // Bet history (betSlips).
    try {
      const slips = asArray(await ssGet(`/bettors/${bettorId}/betSlips`));
      for (const s of slips) {
        const betId = pick<string>(s, "id", "betSlipId");
        if (!betId) continue;
        const status = pick<string>(s, "status", "outcome");
        const stake = pick<number>(s, "atRisk", "stake", "wager");
        const payout = pick<number>(s, "toWin", "atPayout", "payout");
        const profit = pick<number>(s, "netProfit", "profit");
        const row = {
          internal_id: internalId,
          bettor_id: bettorId,
          bet_id: betId,
          book: pick<string>(s, "book.name", "bookName", "book"),
          type: pick<string>(s, "type", "betType"),
          status,
          placed_at: pick<string>(s, "timePlaced", "datePlaced", "placedAt"),
          settled_at: pick<string>(s, "timeSettled", "settledAt"),
          odds_american: americanFromBetSlip(s),
          stake: stake != null ? Number(stake) : null,
          payout: payout != null ? Number(payout) : null,
          profit: profit != null ? Number(profit) : null,
          settled: isSettled(status),
          raw: s,
          updated_at: new Date().toISOString(),
        };
        await admin.from("synced_bets").upsert(row, { onConflict: "bet_id" });
        bets++;
      }
    } catch (e) {
      console.error(`betSlips(${bettorId}) failed`, e);
    }
  }
  return { accounts, bets };
}

async function readBets(internalId: string): Promise<Response> {
  const [{ data: accounts }, { data: bets }] = await Promise.all([
    admin
      .from("linked_sportsbook_accounts")
      .select("bettor_account_id, book, book_abbr, book_region, status, linked_at")
      .eq("internal_id", internalId),
    admin
      .from("synced_bets")
      .select(
        "bet_id, book, type, status, placed_at, settled_at, odds_american, stake, payout, profit, settled",
      )
      .eq("internal_id", internalId)
      .order("placed_at", { ascending: false })
      .limit(500),
  ]);

  const settled = (bets ?? []).filter((b) => b.settled);
  const profit = settled.reduce((sum, b) => sum + (Number(b.profit) || 0), 0);
  const wins = settled.filter((b) => (b.status ?? "").toLowerCase() === "won").length;
  const summary = {
    total_bets: (bets ?? []).length,
    settled_bets: settled.length,
    open_bets: (bets ?? []).length - settled.length,
    net_profit: Math.round(profit * 100) / 100,
    win_rate: settled.length ? wins / settled.length : null,
  };
  return json({ accounts: accounts ?? [], bets: bets ?? [], summary });
}

// ── Router ──────────────────────────────────────────────────────────────────
Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "POST only" }, 405);

  let body: any;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid JSON body" }, 400);
  }

  const internalId = (body?.internalId ?? "").toString().trim();
  if (!internalId) return json({ error: "internalId required" }, 400);

  try {
    switch (body?.action) {
      case "context":
        return await createContext(internalId);
      case "bets": {
        if (body?.refresh) await pullAndUpsert(internalId);
        return await readBets(internalId);
      }
      default:
        return json({ error: "unknown action" }, 400);
    }
  } catch (e) {
    console.error("sharpsports error", e);
    return json({ error: String(e) }, 500);
  }
});
