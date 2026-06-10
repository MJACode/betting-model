# Supabase Edge Functions — SharpSports sportsbook linking

These functions power read-only sportsbook account linking + bet-history sync
(DraftKings, FanDuel, …) via [SharpSports](https://sharpsports.io). The
SharpSports **private** key lives only here — never in the mobile app.

| Function | verify_jwt | Purpose |
|---|---|---|
| `sharpsports` | true | Actions `context` (start Booklink) and `bets` (read/refresh synced bets). Called by the app with the Supabase anon JWT. |
| `sharpsports-webhook` | false | Receives SharpSports webhooks (secret-authenticated) and re-triggers a sync. |

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
