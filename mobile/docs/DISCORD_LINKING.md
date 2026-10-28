# Discord linking — Whop is Discord-only, Apple unlocks the app

Matt, 2026-08-30, asked for one membership across the app and Discord. Matt,
2026-10-27, reversed the Whop half:

> Whop should only be to collect payment from people who want the Discord
> access only and go through there. If a user comes through the App Store they
> are buying the app and getting Discord access. Tie the users together.

Whop checkout stays outside the app. App Store IAP unlocks the app. Our
Discord role is granted only when that subscription is `active`, not while
it is `trialing`. Linking is how the same person is one row on both sides.

The in-app invite is Apple-paid only (Matt, 2026-10-27, #1061). An active
App Store subscription may open it. Free and trial never see the URL. Trial's
button is "Unlock Discord early" and buys the current plan through StoreKit /
RevenueCat, which ends the trial. Paid's button is "Join Discord". Free and
trial also see "Already in Discord via Whop? Connect Discord to link your
account. Premium in the app is still via Apple." That button is Connect
Discord. There is no Whop checkout URL in the app.

Linking ships **dark**: `DISCORD_LINK_ENABLED` is `false`, and
`discordLinkReady()` also requires `AUTH_ENABLED`.

**Do not flip `AUTH_ENABLED`, `BILLING_ENABLED`, or `DISCORD_LINK_ENABLED`
until `data/migrations/add_discord_link_and_whop_memberships.sql` is applied
in that environment.** The function is not in production. With billing or
Discord linking on, a signed-in `fetchAccess()` calls `my_access()` and
throws if it is missing. That throw is a ship blocker, not an empty state.

---

## Who pays for what

| You pay… | …and you get |
|---|---|
| in the app (App Store / RevenueCat) | the app **and** our subscriber Discord role |
| on Discord (Whop), outside the app | Whop's Discord role only. The app stays locked until an Apple subscription entitles |
| nothing | neither |

A Whop member who also buys in the app is the same person: `discord_access`
stays true and `entitled` becomes true. Cancelling Whop does not remove the
Apple subscription. Cancelling Apple removes app access and **our** role, and
leaves Whop's role alone.

Two roles:

- **`DISCORD_APP_ROLE_ID`** — ours. `syncAppRoleForUser` grants it from the
  Apple subscription and removes it when that subscription lapses.
- **Whop's own role** — Whop's. `whop-webhook` never touches it.

`discord_links.app_role_granted` records that OUR role is on.

### Access is computed, and the app half is Apple-only

`add_discord_link_and_whop_memberships.sql` has **not** been applied. The
definition in that file is the first apply. It does not OR Whop into the app
and then reverse it.

Before this change the unapplied functions were:

```
entitled        = app_subscription OR whop_match
has_app_access  = app_subscription OR whop_match
```

After, in the same file:

```
a = subscriptions.status IN ('trialing','active')
    AND (current_period_end IS NULL OR current_period_end > now())
d = a valid whop_memberships row matches this user

my_access().entitled     = a
my_access().app_access   = a
my_access().discord_access = d
has_app_access()         = auth.uid() IS NOT NULL AND a

source = both     when a AND d
       = app      when a
       = discord  when d AND NOT a   -- Whop matched, app locked
       = none     otherwise
```

`useEntitlement()` uses `entitled` plus a receipt that just completed. It
does not OR `discord_access`.

A Whop row matches on evidence the user controls:

1. the Discord account they linked (one Discord id, one app account);
2. the app account's confirmed email (`auth.users.email_confirmed_at`);
3. the linked Discord account's Discord-verified email.

An unverified address matches nothing.

---

## The flow

```
app: "Connect Discord"
  → discord-link { action: 'start' }        → authorize URL + HMAC state
  → in-app browser, Discord consent
  → signalbase://discord-callback?code&state
  → discord-link { action: 'complete' }
        exchange code (client secret, server-side)
        /users/@me                          → discord id + verified email
        PUT /guilds/{id}/members/{user}     → one-tap join (guilds.join scope)
        upsert discord_links
        syncAppRoleForUser()                → our role only if Apple status is active (not trialing)
        backfill discord id onto a Whop membership with the same verified email
  → app reads my_access()
        entitled is still false when the only payment is Whop
```

Scopes are `identify email guilds.join`. The bot token, the client secret and
every role write live server-side. The app never writes `discord_links` or
`whop_memberships`.

`whop-webhook` upserts `whop_memberships` after an HMAC check on the raw body.
It does not write `subscriptions` and it does not call the role sync.

`revenuecat-webhook` writes `subscriptions`, then calls `syncAppRoleForUser`.
That sync reads `subscriptions` only.

---

## What was built

| Piece | File |
|---|---|
| Flag + redirect | `src/lib/discordConfig.ts` |
| Pure helpers (parsing, copy, errors) | `src/lib/discordHelpers.ts` |
| Link API (start / complete / unlink / read) | `src/lib/discord.ts` |
| Access state (module store, one fetch) | `src/hooks/useAccess.ts` |
| **The gate** — Apple `entitled`, not Whop | `src/hooks/useEntitlement.ts` |
| Join sheet | `src/components/DiscordLinkModal.tsx` |
| Settings connect / disconnect row | `src/screens/SettingsScreen.tsx` |
| OAuth + guild join + role sync | `supabase/functions/discord-link/` |
| Whop membership mirror (identity only) | `supabase/functions/whop-webhook/` |
| Discord bot API helpers | `supabase/functions/_shared/discord.ts` |
| Apple subscription → our Discord role (`active` only) | `supabase/functions/_shared/entitlement.ts` |
| Schema + access RPCs (unapplied, Apple-only) | `data/migrations/add_discord_link_and_whop_memberships.sql` |
| Verification | `scripts/verify_discord_link.ts` |

The app does not embed a Whop checkout URL (App Store 3.1.1). Discord-only
buyers pay on Whop, outside the app.

### `useEntitlement`

Paid signals follow `my_access().entitled` (Apple) or a purchase receipt
that has not landed in the table yet. A Whop-only linked user is not
entitled and hits the paywall for premium app features. Connect Discord
still runs.

---

## Activation

Do this before any flag flip. A flag flip against a database that has no
`my_access()` throws inside `fetchAccess()`.

### 1. Apply the migration

```bash
psql "$DATABASE_URL" -f data/migrations/add_discord_link_and_whop_memberships.sql
```

This is the first apply. The functions it creates are already Apple-only.
Then run `get_advisors(security)` and read the result — the migration
revokes `anon`/`authenticated` by name (CLAUDE.md §7).

### 2. Discord application + bot

1. Discord Developer Portal → New Application → **OAuth2**:
   - copy the **Client ID** and **Client Secret**
   - add the redirect URI **`signalbase://discord-callback`** — it must match
     `DISCORD_REDIRECT_URL` in `discordConfig.ts` and `expo.scheme` in
     `app.json` (`signalbase`).
   - *If Discord rejects the custom scheme*, point the redirect at an HTTPS
     bounce that 302s to the scheme and set `DISCORD_REDIRECT_URI` to it.
2. **Bot** tab → add a bot → copy the token. Permissions: **Manage Roles**.
3. Invite the bot to the server with `scope=bot%20applications.commands` and
   `permissions=268435456` (Manage Roles).
4. Server Settings → Roles → create **`App Subscriber`**, and **drag the bot's
   own role above it**. Discord refuses to let a bot assign a role positioned
   above its own.
5. Copy the role id and the server id (Developer Mode → right-click → Copy ID).

### 3. Whop

1. Create the product that sells Discord access only. Connect the Discord
   app so Whop assigns **its own** role on purchase. Do not point that
   product at an in-app URL.
2. Whop dashboard → Developer → **Webhooks**:
   - URL `https://vvprgnrmzeekokzkrkfu.supabase.co/functions/v1/whop-webhook`
   - events `membership.went_valid` and `membership.went_invalid`
   - copy the signing secret.
3. The app does not embed a Whop checkout URL. Discord-only buyers pay on
   Whop, outside the app. App Store buyers subscribe in the app.

### 4. Secrets

```bash
supabase secrets set \
  DISCORD_CLIENT_ID=... \
  DISCORD_CLIENT_SECRET=... \
  DISCORD_BOT_TOKEN=... \
  DISCORD_GUILD_ID=... \
  DISCORD_APP_ROLE_ID=... \
  DISCORD_REDIRECT_URI=signalbase://discord-callback \
  DISCORD_STATE_SECRET=$(openssl rand -hex 32) \
  WHOP_WEBHOOK_SECRET=...
```

### 5. Deploy

```bash
supabase functions deploy discord-link
supabase functions deploy whop-webhook --no-verify-jwt
supabase functions deploy revenuecat-webhook --no-verify-jwt
```

`discord-link` keeps `verify_jwt` **true**. `whop-webhook` and
`revenuecat-webhook` are `--no-verify-jwt`; authenticity is the HMAC or the
Authorization header over the raw body.

### 6. Test, in this order, after the migration is applied

With a preview build carrying `EXPO_PUBLIC_AUTH_ENABLED=true` and
`EXPO_PUBLIC_DISCORD_LINK_ENABLED=true` (and billing on if you are buying):

1. **Link** — sign in, Settings → Connect Discord. Expect: consent screen,
   back in the app, you are in the server, Settings says "Connected as …".
2. **App → Discord** — buy in the app (sandbox). `my_access().entitled` is
   true for `trialing` or `active`. The `App Subscriber` role is granted only
   once status is `active`, not during the trial.
3. **Whop does not unlock the app** — buy the Whop product with a different
   account, connect that Discord account in the app. Expect: `discord_access`
   true, `entitled` false, the paywall still blocks premium features, our
   App Subscriber role is absent, Whop's role is present.
4. **Revoke, Whop side** — cancel in Whop. `whop_memberships.valid` goes
   false and `discord_access` follows. An Apple subscription on that account,
   if there is one, is unchanged.
5. **Revoke, app side** — cancel in the App Store sandbox and let it expire.
   The `App Subscriber` role comes off and `entitled` goes false. If that
   account also has a Whop membership, Whop's role stays.

```sql
SELECT user_id, discord_username, guild_member, app_role_granted, last_sync_error
FROM discord_links;
SELECT membership_id, email, discord_user_id, status, valid FROM whop_memberships;
SELECT * FROM my_access_for('<user-uuid>');
```

`entitled` on that last row follows the Apple subscription only.

### 7. Ship

Flip the flags only after step 1 has been run in the environment you are
shipping. Pure JS, so the flag change goes over OTA. This change does not
flip any `EXPO_PUBLIC_*` flag.

---

## Known limitations

**1. The gate is still client-side.** `picks` is anon-readable by design.
`public.has_app_access()` is the server-side check and is Apple-only, same
as `my_access().entitled`. Wiring real enforcement still means moving the
website and Claude-mobile onto a service-role key first, then revoking anon
SELECT, then serving signals through a gated RPC. In that order.

**2. Guild-join can fail without the link failing.** The error is recorded
in `discord_links.last_sync_error` and the modal falls back to the plain
invite. They will not hold our role until it is retried.

**3. Role sync failures are recorded, not retried on a schedule.** Nothing
sweeps `last_sync_error`. A later RevenueCat event or a reconnect runs the
sync again.

**4. Unlinking does not kick anyone from the server.** Unlinking takes back
our role, when we had granted it, and deletes the link row.

**5. Invite-on-paid and "Unlock Discord early" landed in #1061.** Flags stay
off. This merge does not add another Settings sentence and does not change
`web/content/terms.md`. The subscription manage alert still says a Discord
membership covers the app; that sentence was already on master.
