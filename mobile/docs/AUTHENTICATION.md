# Authentication — built, wired, and deliberately switched off

Signalbase now has a complete sign-in layer (Apple, Google, email passcode) that
is **inactive**. Nothing in the app navigates to it, no session is persisted, and
every auth call throws before it can reach Supabase.

This document is the runbook for turning it on. Do the Supabase/console work
*first* — flipping the flag before the providers are configured drops users on a
dead end.

---

## What was built

| Piece | File | Notes |
|---|---|---|
| Kill switch + provider flags | `src/lib/authConfig.ts` | `AUTH_ENABLED` is the one switch |
| Pure helpers | `src/lib/authHelpers.ts` | No RN/expo imports, so the verify script can load them |
| Auth API | `src/lib/auth.ts` | Email OTP, iOS native Apple, Google browser OAuth, all guarded |
| Session state | `src/hooks/useAuth.ts` | Module store, one Supabase subscription, AppState-driven refresh |
| Sign-in screen | `src/screens/SignInScreen.tsx` | Required on cold open once `AUTH_ENABLED` is on. No skip. |
| Settings entry | `src/screens/SettingsScreen.tsx` | Account card renders **only** when `AUTH_ENABLED` |
| Verification | `scripts/verify_auth.ts` | `npx tsx scripts/verify_auth.ts` |
| App Review code | `scripts/verify_app_review_sign_in.ts` | One demo email. The fixed code is a Supabase secret |

When `AUTH_ENABLED` is on, SignIn is the first screen. There is no guest path
and no "Signing in is optional" line. Terms and Privacy open
`signalbase-ai.com`. Models and tracked bets stay on the device. A successful
sign-in opens the paywall when billing is also on and the account is not
entitled; closing it leaves the free shell (Record and the picks teaser).
Signals and Live Signals open that same paywall. The other tabs stay locked.
A restored session does not show the paywall again until a locked tab or
Unlock is tapped.

Scope is **session only**, by design. Signing in does not yet move any data:
bankroll, Kelly settings, custom models, saved parlays, tracked bets and manual
bets all stay device-local exactly as they are today. Account-scoped data is a
deliberate follow-on (see *Not built yet*).

Two things now hang off an account and are documented separately: the
subscription (`docs/BILLING.md`) and the **Discord membership link**
(`docs/DISCORD_LINKING.md`). Both require `AUTH_ENABLED`, and both enforce that
pairing in code rather than leaving it to be discovered in production —
`billingReady()` and `discordLinkReady()`. Turning auth on is therefore the
first of the three flips, not a standalone one.

### Why these three methods

- **Email** is a 6-digit passcode (`signInWithOtp` → `verifyOtp`), not a magic
  link. A code never leaves the app, so there's no deep-link handler to get
  wrong and no risk of a corporate mail scanner burning the link by prefetching
  it. The App Review demo address stays on this path. Pure JS.
- **Google** uses Supabase OAuth in an in-app browser via `expo-web-browser`
  with the **PKCE** flow, on iOS and Android. The authorization code that
  comes back is useless without the verifier held in this app's storage.
- **Apple on iOS** is the system sheet (`expo-apple-authentication`), then
  `supabase.auth.signInWithIdToken({ provider: 'apple', token })` with the
  `identityToken`. It does not call `signInWithOAuth` and it does not open
  `ASWebAuthenticationSession` against `*.supabase.co`. This is the supported
  iOS path. See *Native Apple sheet* below — it requires a new EAS binary.
- **Apple off iOS** stays on that same browser PKCE flow. `showAppleOn` is
  `['ios']`, so the sign-in screen does not offer Apple on Android. Delete
  account can still re-authenticate an Apple identity on Android through the
  browser, because the native sheet does not exist there.

`expo-apple-authentication` is loaded with a dynamic `require` inside
`loadAppleAuthentication()`, and that function returns before the `require`
unless `Platform.OS` is `ios`. Email, Google, and Android do not evaluate the
native module. A static `import` from that package is the launch crash the OTA
rule exists to prevent.

---

## Pre-flight: this is already safe

Verified against the live database (project `vvprgnrmzeekokzkrkfu`) while
building this:

- **All 39 RLS policies** in `public` apply to `authenticated` (34 name it
  explicitly; 5 use the `public` role, which covers every role).
- **Zero tables or views** grant `SELECT` to `anon` but not `authenticated`.
- **Zero RPCs** grant `EXECUTE` to `anon` but not `authenticated`.

So a signed-in user keeps full read access to picks, games, odds, stats, the
track record and every RPC. **Signing in cannot break the app's data access** —
which is the failure mode that usually bites when auth is added to an
anon-key app. `auth.users` is currently empty (0 users, 0 identities), so there
is no legacy account state to reconcile.

---

## Activation

Do not flip `AUTH_ENABLED`, `BILLING_ENABLED`, or `DISCORD_LINK_ENABLED` until
`data/migrations/add_discord_link_and_whop_memberships.sql` is applied in that
environment. That file is the first apply of `my_access()` / `has_app_access()`,
and both are Apple-only. With billing or Discord linking on, a signed-in
`fetchAccess()` calls `my_access()` and throws if the function is missing.
That throw is a ship blocker.

### 1. Supabase → Authentication → URL Configuration

Add the redirect URL to the allow-list, or Apple/Google will refuse the round
trip:

```
signalbase://auth-callback
```

This must stay in sync with `AUTH_REDIRECT_URL` in `src/lib/authConfig.ts` and
`expo.scheme` in `app.json` (`signalbase`).

### 2. Email provider

Supabase → Authentication → Providers → **Email**: enabled (it is by default).

**Critical:** the default confirmation email template only renders a magic
*link*. This app asks for a **code**, so the template must include the token.
Authentication → Emails → *Magic Link*, add:

```
Your Signalbase sign-in code is: {{ .Token }}
```

Skip this and users will receive an email with no code in it and no way to
finish signing in.

Also worth doing before launch: Supabase's built-in SMTP is rate-limited and not
meant for production volume. Configure a custom SMTP sender (Authentication →
Emails → SMTP Settings) or codes will start bouncing under load.

### 3. Apple

Google, and an Apple re-auth on Android, still use the web OAuth flow, so the
Services ID setup stays. iOS uses the native identity token, which needs the
bundle id in the same Client IDs list.

1. Apple Developer → Certificates, Identifiers & Profiles.
2. The App ID `com.mja.bettingpicks` has **Sign in with Apple** enabled. Leave
   the Server-to-Server notification endpoint blank (Supabase Auth does not
   use it).
3. Create a **Services ID** (e.g. `com.mja.bettingpicks.web`) with *Sign in with
   Apple* enabled, grouped with that App ID.
4. Register the return URL Supabase gives you on its Apple provider page
   (`https://vvprgnrmzeekokzkrkfu.supabase.co/auth/v1/callback`).
5. Create a **Sign in with Apple key** (.p8), note the Key ID and Team ID.
6. Supabase → Authentication → Providers → **Apple**: Team ID, Key ID, and the
   .p8 contents, plus **Client IDs**:
   - The **Services ID is the first entry.** Supabase uses the first client ID
     for the web `signInWithOAuth` flow. If the bundle id is first, native
     sign-in still works and Apple rejects the web flow.
   - Also list the App ID **`com.mja.bettingpicks`**. The native identity
     token's audience is that bundle id. `signInWithIdToken` rejects the token
     when the bundle id is missing from Client IDs.
   - Do not add `host.exp.Exponent` for this app. That audience is Expo Go.
     Production and TestFlight use `com.mja.bettingpicks` only.

This repo does not change the Supabase dashboard. The Client IDs edit is a
dashboard step, done before the new binary is what TestFlight testers run.

### 4. Google

1. Google Cloud Console → APIs & Services → Credentials → **OAuth client ID**,
   type *Web application*.
2. Authorized redirect URI: the same Supabase callback URL as above.
3. Supabase → Authentication → Providers → **Google**: paste the client ID and
   secret.

Because we use the browser flow, one **web** client covers both iOS and Android
— no per-platform native client IDs needed.

### 5. Flip the switch

Either edit `src/lib/authConfig.ts`:

```ts
export const AUTH_ENABLED: boolean = true;
```

…or, to test in a preview build while production stays dark, set the env var in
the relevant EAS profile:

```
EXPO_PUBLIC_AUTH_ENABLED=true
```

### 6. Ship

Native Apple does **not** ship over the air. `app.json` `version` is `1.2.0`
and `runtimeVersion` follows `appVersion`, so an OTA is only offered to a
binary built at 1.2.0. The 1.1.0 TestFlight binary keeps the browser Apple
flow until it is replaced.

Run **Mobile TestFlight build** (`mobile-build.yml`) for an iOS production
binary, then submit that build. Do not force-publish an OTA of this change
onto 1.1.0. The OTA job refuses the push on its own, because `package.json`
and `app.json` changed.

Email and Google stay pure JS. A later JS-only fix can OTA once a 1.2.0
binary is what is installed. Android does not load the Apple module; it still
needs a 1.2.0 binary before it receives those later OTAs, because the runtime
version is the app version on every platform.

### 7. Smoke test

- Settings shows an **Account** card (it renders nowhere while the flag is off).
- Tap it → sign-in screen. On iOS: Apple, Google, then email. On Android:
  Google, then email.
- Email a code to yourself, verify, land back in Settings showing your address.
- Force-quit and relaunch — you're still signed in (session persistence).
- Sign out → the card returns to "Not signed in".
- On iOS, Continue with Apple opens the system sheet. It does not open a
  browser to `*.supabase.co`. Cancel that sheet → the sign-in screen, no error.
- Cancel the Google browser sheet → the sign-in screen, no error. Android
  shows Google and email, and no Apple button.
- **Regression check that matters:** while signed in, confirm Picks, Track
  Record, Stats and Models all still load. The pre-flight above says they will,
  but confirm it on a device before shipping.

---

## App Review demo account

Apple's reviewer signs in as `review@signalbase-ai.com`. The app has no
password field. The six-digit code is not in this repo. The repo is public,
so a code that has been committed is burned. Matt picks a fresh code, pastes
it only into App Store Connect (the Password field), and sets the secret to
the same value.

The address is `APP_REVIEW_DEMO_EMAIL` in `src/lib/appReview.ts`. For that
address only, Email me a code does not call `signInWithOtp`, and the code
step calls the `app-review-sign-in` edge function. Continue with Apple and
Continue with Google do the same when that email is already in the field,
including when someone who is not the reviewer types it. An empty field
still starts Apple or Google.

The function accepts the code only when both secrets are set:

```
APP_REVIEW_DEMO_EMAIL=review@signalbase-ai.com
APP_REVIEW_DEMO_OTP=<fresh six-digit code, App Store Connect only>
```

`APP_REVIEW_DEMO_EMAIL` has to be that exact address. A different secret
never receives a call from this app. Deploy only after Matt says the code
is no longer in git:

```
supabase functions deploy app-review-sign-in --no-verify-jwt
```

Then apply `data/migrations/app_review_sign_in_attempts_2026_11_04.sql` in
the SQL editor. It is not in `ACTIVE_MIGRATIONS`, so the worker will not
apply it. Until that table exists, the function refuses every code,
including the right one. The function creates the auth user on the first
success. No mailbox is required.

Wrong codes are counted per caller and across every caller. The table
stores a SHA-256 of the edge address (`cf-connecting-ip`, otherwise the
last `x-forwarded-for` hop), not the address and not the first hop. Eight
failures in 15 minutes fill that caller's bucket. More than 200 failures
in an hour, from every caller together, refuse the next request before
the code is compared. A database error on the count is 503. Deleting the
review account still asks for this code, because reauth uses the same
verify path.

After App Review approves the binary, unset `APP_REVIEW_DEMO_OTP`, or replace
it with a new code that was not the one just submitted. Leaving the secret
set keeps the demo address open. Do not write the old or the new code into
the repo.

## App Store note (guideline 4.8)

If Google sign-in is offered on iOS, Sign in with Apple must be offered too.
`AUTH_PROVIDERS` and `showAppleOn` are set up that way already, and
`verify_auth.ts` asserts iOS never shows Google without Apple. If you ship
email-only first, set `apple: false, google: false` in `AUTH_PROVIDERS` — don't
leave Google on alone.

---

## Native Apple sheet (iOS)

This is the supported iOS Apple path. It is already wired. It is not an
optional follow-up, and it is not an OTA.

`signInWithProvider('apple')` on iOS calls `AppleAuthentication.signInAsync`
with the full-name and email scopes, then
`supabase.auth.signInWithIdToken({ provider: 'apple', token: identityToken })`.
The sign-in screen renders the system Continue with Apple button (white,
corner radius matching the other buttons) when that module is in the binary.
Dismissing the sheet returns null, the same as dismissing the Google browser.
A binary that does not contain the native module keeps a plain white button
with black "Continue with Apple" text, and the sign-in call throws a sentence
asking for the latest app version. It does not fall back to the browser.
Any other Apple failure is “Couldn't sign in with Apple. Try again.”

What the new binary needs, beyond the JS:

- `expo-apple-authentication` (`npx expo install`, SDK 54), dependency in
  `package.json`.
- `app.json`: plugin `"expo-apple-authentication"` (entitlement
  `com.apple.developer.applesignin` = `Default`, plus mixed localizations) and
  `ios.usesAppleSignIn: true`. Bundle id stays `com.mja.bettingpicks`.
- `version` `1.2.0`, so `runtimeVersion` does not match the 1.1.0 binaries.
- A new **EAS iOS production build**, then TestFlight. Until that build is
  installed, TestFlight is still the old browser flow.

Supabase Apple provider, before that build is the one testers use: Client IDs
include `com.mja.bettingpicks`, and the Services ID stays the first entry so
Google's sibling web flow (and Android Apple re-auth) keep working. The
identity token's `aud` is the bundle id. A Services-ID-only client list accepts
the browser flow and rejects the native token.

Apple sends the person's name on the first authorization only, and not inside
the identity token. This app does not write that name to user metadata.

---

## Not built yet (deliberate)

Signing in currently owns nothing but the session. When account-scoped data is
wanted, the work is:

- `user_id` columns + owner RLS policies on `tracked_bets`,
  `device_push_tokens`, `linked_sportsbook_accounts`, `synced_bets` (all three
  already carry `device_id`, so there's a natural claim key).
- New tables for what is presently AsyncStorage-only: custom models, saved
  parlays, manual bets, bankroll/Kelly/preferred-book settings.
- A one-time "claim this device's data" migration on first sign-in — and a
  decision about what happens when a second device signs into the same account
  with conflicting local state.

The UI copy is written to match that reality — the Settings card and the
sign-in screen both say data stays on this device and make **no cross-device
sync promise**. Both strings carry a comment; update them when account-scoped
data actually lands, and not before.
