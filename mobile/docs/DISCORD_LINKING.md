# One membership, two surfaces — Discord linking, built and switched off

Matt, 2026-08-30: *"make sure the email for the app is linked to give them
access to discord and vice versa. If someone has discord they should be able to
get an account on the app at no additional cost because they will pay via
discord. If access is removed from one, it should be removed from the other."*

That is now built. Like auth and billing before it, it ships **dark**:
`DISCORD_LINK_ENABLED` in `src/lib/discordConfig.ts` is `false`, and linking
also requires `AUTH_ENABLED` — `discordLinkReady()` enforces the pair, because
a link binds a Discord account to an app ACCOUNT and a device id dies on
reinstall.

---

## The rule, and the one idea that makes it work

| You pay… | …and you get |
|---|---|
| in the app (App Store / RevenueCat) | the app **and** the subscriber Discord |
| on Discord (Whop) | the Discord **and** the app, at no extra cost |
| nothing, on either side | neither |

**The Discord role is the entitlement carrier, and each side only ever revokes
the role it granted.** Two roles exist in the guild:

- **`DISCORD_APP_ROLE_ID`** — ours. Granted when an app subscription entitles,
  removed when it lapses.
- **Whop's own role** — Whop's. We never touch it.

That split is what makes "remove access from one and it goes from the other"
correct rather than destructive. A member who cancels in the App Store but is
still paying Whop loses **our** role and keeps theirs — and keeps their access,
because they are still paying. If a single shared role carried both, cancelling
either side would strip a member who had paid for the other.

`discord_links.app_role_granted` records that OUR role is on, so revocation is
a fact we hold rather than a guess about the guild's current state.

### Access is computed, never cached as a grant

`public.my_access()` ORs the two sources on every read:

```
entitled = (subscriptions row is trialing/active AND not past its period end)
        OR (a valid whop_memberships row matches this user)
```

There is no second table to keep in step, and no window where a cancelled
member still holds a stale entitlement — a Whop membership going invalid takes
app access away on the very next read.

A Whop membership matches a user three ways, all of which are evidence the user
actually controls the identity:

1. the **Discord account they explicitly linked** (unique per app account);
2. the app account's own **confirmed** email (`auth.users.email_confirmed_at`);
3. the linked Discord account's **Discord-verified** email.

An unverified address on either side matches nothing. Trusting one would let
anybody claim a paid membership by typing the buyer's address.

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
        syncAppRoleForUser()                → grant our role if they're subscribed
        backfill discord id onto a Whop membership bought with the same email
  → app reads my_access()
```

Scopes are `identify email guilds.join`. The bot token, the client secret and
every role write live server-side; **the app never grants anything**, which is
what stops a client claiming a membership it did not buy.

---

## What was built

| Piece | File |
|---|---|
| Flag + redirect + Whop checkout URL | `src/lib/discordConfig.ts` |
| Pure helpers (parsing, copy, errors) | `src/lib/discordHelpers.ts` |
| Link API (start / complete / unlink / read) | `src/lib/discord.ts` |
| Access state (module store, one fetch) | `src/hooks/useAccess.ts` |
| **The gate** — use this to decide access | `src/hooks/useEntitlement.ts` |
| Join sheet | `src/components/DiscordLinkModal.tsx` |
| Settings connect / disconnect row | `src/screens/SettingsScreen.tsx` |
| OAuth + guild join + role sync | `supabase/functions/discord-link/` |
| Whop membership mirror | `supabase/functions/whop-webhook/` |
| Discord bot API helpers | `supabase/functions/_shared/discord.ts` |
| The two-way rule, one place | `supabase/functions/_shared/entitlement.ts` |
| Schema + access RPCs | `data/migrations/add_discord_link_and_whop_memberships.sql` |
| Verification (44 assertions) | `scripts/verify_discord_link.ts` |

### `useEntitlement`, not `useSubscription`

`useSubscription().entitled` only knows about the `subscriptions` table. A
member who paid through Whop has no row there, so gating on it would charge
them twice for what they already bought. `LiveScreen` and `PicksHomeScreen`
were moved onto `useEntitlement()`; the only remaining caller of the narrower
hook is the Settings subscription card, which is *describing* the app
subscription rather than deciding access.

**Any new gate uses `useEntitlement()`.**

---

## Activation

Do all of it before flipping the flag — a half-configured link drops users on a
dead end.

### 1. Apply the migration

```bash
psql "$DATABASE_URL" -f data/migrations/add_discord_link_and_whop_memberships.sql
```

Then run `get_advisors(security)` and **read the result, not the intent** — the
migration revokes `anon`/`authenticated` by name, but that check is the backstop
(CLAUDE.md §7).

### 2. Discord application + bot

1. Discord Developer Portal → New Application → **OAuth2**:
   - copy the **Client ID** and **Client Secret**
   - add the redirect URI **`signalbase://discord-callback`** — it must match
     `DISCORD_REDIRECT_URL` in `discordConfig.ts` and `expo.scheme` in
     `app.json` (`signalbase`).
   - *If Discord rejects the custom scheme*, point the redirect at an HTTPS
     bounce that 302s to the scheme and set `DISCORD_REDIRECT_URI` to it. That
     is the only change needed; nothing else reads the value.
2. **Bot** tab → add a bot → copy the token. Permissions: **Manage Roles**.
3. Invite the bot to the server with `scope=bot%20applications.commands` and
   `permissions=268435456` (Manage Roles).
4. Server Settings → Roles → create **`App Subscriber`**, and **drag the bot's
   own role above it**. Discord refuses to let a bot assign a role positioned
   above its own — this is the single most common reason role grants 403.
5. Copy the role id and the server id (Developer Mode → right-click → Copy ID).

### 3. Whop

1. Create the product that sells Discord access; connect the Discord app so
   Whop assigns **its own** role on purchase.
2. Whop dashboard → Developer → **Webhooks**:
   - URL `https://vvprgnrmzeekokzkrkfu.supabase.co/functions/v1/whop-webhook`
   - events `membership.went_valid` and `membership.went_invalid`
   - copy the signing secret.
3. Copy the checkout URL into `EXPO_PUBLIC_WHOP_CHECKOUT_URL` if you want the
   "Get access on Discord" button on the paywall. Leave it unset and the button
   simply doesn't render.

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
supabase functions deploy revenuecat-webhook --no-verify-jwt   # now syncs the role
```

`discord-link` keeps `verify_jwt` **true** — a link is an assertion about who
someone is and must never be makeable on another account's behalf.
`whop-webhook` must be `--no-verify-jwt` (Whop sends no Supabase JWT;
authenticity is the HMAC over the raw body).

### 6. Test, in this order

With a preview build carrying `EXPO_PUBLIC_AUTH_ENABLED=true` and
`EXPO_PUBLIC_DISCORD_LINK_ENABLED=true`:

1. **Link** — sign in, Settings → Connect Discord. Expect: consent screen, back
   in the app, you are in the server, Settings says "Connected as …".
2. **App → Discord** — buy in the app (sandbox). Within seconds you hold the
   `App Subscriber` role.
3. **Discord → app** — buy the Whop product with a *different* account, connect
   that Discord account in the app. Expect: entitled, Settings shows "Discord",
   paywall never appears, nothing charged.
4. **Revoke, Whop side** — cancel/refund in Whop. `whop_memberships.valid` goes
   false; app access disappears on the next read.
5. **Revoke, app side** — cancel in the App Store sandbox and let it expire. The
   `App Subscriber` role comes off; if that account also has a Whop membership,
   confirm it **keeps** Whop's role and its access.

```sql
SELECT user_id, discord_username, guild_member, app_role_granted, last_sync_error
FROM discord_links;
SELECT membership_id, email, discord_user_id, status, valid FROM whop_memberships;
SELECT * FROM my_access_for('<user-uuid>');
```

### 7. Ship

Flip `DISCORD_LINK_ENABLED` (and `AUTH_ENABLED`). Pure JS, so it goes over OTA
— no EAS rebuild, unlike IAP.

---

## Known limitations, stated plainly

**1. The gate is still client-side.** `picks` is anon-readable by design (the
website and the Claude-mobile workflow both query it with the anon key), so the
gate stops ordinary users, not someone reading the table directly.
`public.has_app_access()` is the honest server-side check and now supersedes
`has_active_subscription()` — which cannot see a Whop-paid member and would
lock out everyone who bought through Discord. Wiring real enforcement still
means moving the website and Claude-mobile onto a service-role key first, then
revoking anon SELECT, then serving signals through a gated RPC. In that order.

**2. Guild-join can fail without the link failing.** A bot outage or a declined
scope leaves the user linked but not in the server; the error is recorded in
`discord_links.last_sync_error` and the modal falls back to the plain invite.
They just won't hold the subscriber role until it is retried.

**3. Role sync failures are recorded, not retried on a schedule.** Nothing
sweeps `last_sync_error` yet. If Discord is down during a renewal batch, those
members keep whatever role they had until something re-triggers a sync (any
subsequent RevenueCat event, or re-connecting). A periodic reconciliation job
is the obvious follow-on and is deliberately not built yet.

**4. Unlinking does not kick anyone from the server.** Leaving is the member's
own choice; unlinking is about our record of who they are.
