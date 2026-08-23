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
| Auth API | `src/lib/auth.ts` | Email OTP + Apple/Google OAuth, all guarded |
| Session state | `src/hooks/useAuth.ts` | Module store, one Supabase subscription, AppState-driven refresh |
| Sign-in screen | `src/screens/SignInScreen.tsx` | Registered as the `SignIn` route; nothing links to it |
| Settings entry | `src/screens/SettingsScreen.tsx` | Account card renders **only** when `AUTH_ENABLED` |
| Verification | `scripts/verify_auth.ts` | 41 assertions — `npx tsx scripts/verify_auth.ts` |

Scope is **session only**, by design. Signing in does not yet move any data:
bankroll, Kelly settings, custom models, saved parlays, tracked bets and manual
bets all stay device-local exactly as they are today. Account-scoped data is a
deliberate follow-on (see *Not built yet*).

### Why these three methods, and why no rebuild

All three run in pure JavaScript, so the whole feature ships over the existing
**Mobile OTA update (production)** workflow — no EAS rebuild, no new native
module, no `package.json` change.

- **Email** is a 6-digit passcode (`signInWithOtp` → `verifyOtp`), not a magic
  link. A code never leaves the app, so there's no deep-link handler to get
  wrong and no risk of a corporate mail scanner burning the link by prefetching
  it.
- **Apple and Google** use Supabase OAuth in an in-app browser via
  `expo-web-browser` — already a dependency (SharpSports uses it) — with the
  **PKCE** flow, so the authorization code that comes back is useless without
  the verifier held in this app's storage.

The trade worth knowing: the Apple button opens a web sheet rather than the
native one-tap sheet. `expo-apple-authentication` would be nicer, but it is a
native module, and per the OTA rule in `CLAUDE.md` a JS bundle importing a
native module missing from the installed binary **crashes on launch**. The
upgrade path is in *Optional: native Apple sheet* below.

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

1. Apple Developer → Certificates, Identifiers & Profiles.
2. Create a **Services ID** (e.g. `com.mja.bettingpicks.web`) with *Sign in with
   Apple* enabled.
3. Register the return URL Supabase gives you on its Apple provider page
   (`https://vvprgnrmzeekokzkrkfu.supabase.co/auth/v1/callback`).
4. Create a **Sign in with Apple key** (.p8), note the Key ID and Team ID.
5. Supabase → Authentication → Providers → **Apple**: paste the Services ID as
   the client ID, plus the Team ID, Key ID and the .p8 contents.

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

JS-only, so: **Actions → Mobile OTA update (production) → Run workflow**.

### 7. Smoke test

- Settings shows an **Account** card (it renders nowhere while the flag is off).
- Tap it → sign-in screen. On iOS: Apple, Google, then email. On Android:
  Google, then email.
- Email a code to yourself, verify, land back in Settings showing your address.
- Force-quit and relaunch — you're still signed in (session persistence).
- Sign out → the card returns to "Not signed in".
- Cancel the Apple/Google browser sheet → returns to the sign-in screen with no
  error (a cancel is not a failure).
- **Regression check that matters:** while signed in, confirm Picks, Track
  Record, Stats and Models all still load. The pre-flight above says they will,
  but confirm it on a device before shipping.

---

## App Store note (guideline 4.8)

If Google sign-in is offered on iOS, Sign in with Apple must be offered too.
`AUTH_PROVIDERS` and `showAppleOn` are set up that way already, and
`verify_auth.ts` asserts iOS never shows Google without Apple. If you ship
email-only first, set `apple: false, google: false` in `AUTH_PROVIDERS` — don't
leave Google on alone.

---

## Optional: native Apple sheet

Only if the web sheet proves to be a conversion problem. This is **not** an OTA
change:

1. `npx expo install expo-apple-authentication`
2. Add `"expo-apple-authentication"` to `plugins` in `app.json`.
3. In `src/lib/auth.ts`, branch `signInWithProvider('apple')` on iOS to
   `AppleAuthentication.signInAsync({ requestedScopes: [FULL_NAME, EMAIL] })`
   and pass the returned `identityToken` to
   `supabase.auth.signInWithIdToken({ provider: 'apple', token })`.
4. **EAS rebuild + TestFlight.** Do not OTA a bundle importing this module —
   installed binaries without it will crash on launch.

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
