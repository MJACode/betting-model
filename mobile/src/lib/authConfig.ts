/**
 * Authentication feature flag + provider configuration.
 *
 * ============================================================================
 * AUTH IS BUILT BUT NOT ACTIVE. `AUTH_ENABLED` is the single kill switch.
 * ============================================================================
 *
 * While it is `false`:
 *   - No sign-in entry point renders anywhere in the app (Settings shows nothing).
 *   - The Supabase client keeps `persistSession: false` — exactly today's
 *     behavior, so no session is ever written to AsyncStorage.
 *   - `useAuth()` reports status 'disabled' and never touches the network.
 *   - Every call in `lib/auth.ts` throws before it can reach Supabase.
 *
 * The screens and hooks still compile and typecheck, so this cannot silently
 * rot — it just has no reachable path from the UI.
 *
 * To turn it on, see `mobile/docs/AUTHENTICATION.md`. Flipping this constant is
 * the LAST step, not the first: the Supabase dashboard has to be configured for
 * each provider first, or users hit a dead end.
 */

/**
 * Master switch. `false` = auth is completely dark.
 *
 * Overridable per-build without a code change via the `EXPO_PUBLIC_AUTH_ENABLED`
 * env var (set it to `true` in an EAS profile to exercise the real flow in a
 * preview build while production stays dark).
 */
export const AUTH_ENABLED: boolean =
  (process.env.EXPO_PUBLIC_AUTH_ENABLED ?? 'false').toLowerCase() === 'true';

/**
 * Which sign-in methods the sign-in screen offers.
 *
 * These are independent of `AUTH_ENABLED` — turning a provider off here hides
 * that button even once auth is live, which is how you'd ship email-only first
 * and add the social buttons after the Apple/Google consoles are configured.
 *
 * NOTE (App Store review, guideline 4.8): if you ship Google sign-in on iOS you
 * MUST also offer Sign in with Apple. Don't set `google: true, apple: false`
 * for an iOS build.
 */
export const AUTH_PROVIDERS = {
  /** Email one-time passcode (6-digit). No native module, no deep link needed. */
  email: true,
  /** Sign in with Apple. Shown on iOS only by default — see `showAppleOn`. */
  apple: true,
  /** Google. Browser-based OAuth, works on both platforms. */
  google: true,
} as const;

/**
 * Platforms that show the Apple button. Sign in with Apple works on Android via
 * the web flow, but it's an unusual thing to offer there, so it's iOS-only.
 */
export const showAppleOn: readonly string[] = ['ios'];

/**
 * Where the OAuth provider sends the user back to.
 *
 * Must match `expo.scheme` in app.json (`signalbase`) AND be listed under
 * Supabase → Authentication → URL Configuration → Redirect URLs, or the
 * provider will refuse the round trip.
 *
 * Hardcoded rather than derived via `expo-linking` so this stays a pure-JS,
 * OTA-deliverable change — adding a native module would require a rebuild.
 */
export const AUTH_REDIRECT_URL = 'signalbase://auth-callback';

/** Length of the emailed one-time passcode. Supabase's default is 6. */
export const EMAIL_OTP_LENGTH = 6;
