# Supabase Edge Functions

| Function | verify_jwt | Purpose | Runbook |
|---|---|---|---|
| `sharpsports` | true | Actions `context` (start Booklink) and `bets` (read/refresh synced bets). Called by the app with the Supabase anon JWT. | below |
| `sharpsports-webhook` | false | Receives SharpSports webhooks (secret-authenticated) and re-triggers a sync. | below |
| `stripe-checkout` / `stripe-portal` | true | Billing on the Stripe rail — built and dark. | `mobile/docs/BILLING.md` |
| `stripe-webhook` | **false** | Stripe entitlement → `subscriptions`. Signature verified over the raw body. | `mobile/docs/BILLING.md` |
| `revenuecat-webhook` | **false** | IAP entitlement → `subscriptions`, **and** the Discord role sync. Authorization header, constant-time. | `mobile/docs/BILLING.md` |
| `discord-link` | true | Discord OAuth link, one-tap guild join, role sync, unlink. A link asserts who someone IS, so it must never be makeable on another account's behalf. | `mobile/docs/DISCORD_LINKING.md` |
| `whop-webhook` | **false** | Whop membership state → `whop_memberships`, which is what lets a Discord-paid member into the app for free. HMAC over the raw body. | `mobile/docs/DISCORD_LINKING.md` |

`_shared/discord.ts` (bot API) and `_shared/entitlement.ts` (the two-way
membership rule) are imported by `discord-link` and `revenuecat-webhook`.
**Deno resolves relative imports at deploy time, so a change to either file
requires redeploying every function that imports it.**

---

## SharpSports sportsbook linking

These functions power read-only sportsbook account linking + bet-history sync
(DraftKings, FanDuel, …) via [SharpSports](https://sharpsports.io). The
SharpSports **private** key lives only here — never in the mobile app.

Data lands in `linked_sportsbook_accounts` + `synced_bets` (RLS on, **no anon
policy** — the app reads only through `sharpsports`, scoped by the device
`internalId`).

## One-time setup (Matt)

1. **Create a SharpSports account** → grab **sandbox** keys from the dashboard
   (`public_sandbox_…`, `private_sandbox_…`). Live keys require a paid plan.

2. **Set the Edge Function secrets** (Supabase dashboard → Edge Functions →
   Secrets, or CLI):

   ```bash
   supabase secrets set \
     SHARPSPORTS_PUBLIC_KEY=public_sandbox_xxx \
     SHARPSPORTS_PRIVATE_KEY=private_sandbox_xxx \
     SHARPSPORTS_WEBHOOK_SECRET=$(openssl rand -hex 16)
   ```

   `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` are injected automatically.

3. **Deploy** (already deployed once via MCP; re-deploy after edits):

   ```bash
   supabase functions deploy sharpsports
   supabase functions deploy sharpsports-webhook --no-verify-jwt
   ```

4. **Register the webhook** in the SharpSports dashboard (or it's passed
   automatically via `context`) pointing at:
   `https://<project-ref>.functions.supabase.co/sharpsports-webhook?secret=<SHARPSPORTS_WEBHOOK_SECRET>`
   for events `bettorAccount.verified`, `bettorAccount.unverified`,
   `refreshResponse.created`.

## Sandbox testing

Booklink test credentials: username `gooduser`, password `Test1`. Link a
sandbox book in the app, then pull-to-refresh on Performance to see the seeded
bet history.

## Note on field mapping

SharpSports' exact JSON field names are taken from their docs and may differ
slightly per account. Every betSlip is stored whole in `synced_bets.raw`, and
the app reads our own tables — so a field rename is a localized fix in
`sharpsports/index.ts` (`pullAndUpsert`).
