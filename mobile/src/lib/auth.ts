import { Platform } from 'react-native';
import * as WebBrowser from 'expo-web-browser';
import type { Session } from '@supabase/supabase-js';

import { supabase } from './supabase';
import {
  APP_REVIEW_SIGN_IN_FUNCTION,
  isAppReviewDemoEmail,
  reviewFunctionErrorMessage,
} from './appReview';
import { AUTH_ENABLED, AUTH_REDIRECT_URL, EMAIL_OTP_LENGTH } from './authConfig';
import {
  assertAuthEnabled,
  isValidEmail,
  normalizeOtp,
  parseAuthCallback,
  type AuthProvider,
} from './authHelpers';

/**
 * Auth API (mobile side). Nothing here runs while `AUTH_ENABLED` is false —
 * every network call guards on it first, so an accidental import can't create
 * real accounts in production before we're ready.
 *
 *   - Email  → one-time 6-digit passcode (`signInWithOtp` + `verifyOtp`).
 *              Deliberately NOT a magic link: a code needs no deep-link handler
 *              and can't be broken by an email client that rewrites URLs.
 *              Pure JS. The App Review demo address stays on this path.
 *   - Google → Supabase OAuth in an in-app browser (`expo-web-browser`) using
 *              the PKCE flow. Same path on iOS and Android.
 *   - Apple on iOS → the system sheet (`expo-apple-authentication`), then
 *              `signInWithIdToken`. Not the browser, and not `signInWithOAuth`.
 *              Native module: a new EAS binary, not an OTA onto a binary that
 *              predates it. Loaded only inside `loadAppleAuthentication()`.
 *   - Apple off iOS → the same browser PKCE flow as Google. The sign-in screen
 *              does not show the button there (`showAppleOn`). Delete-account
 *              re-auth for an Apple identity on Android still uses it.
 *
 * Pure helpers live in ./authHelpers (kept free of react-native so the verify
 * script can import them) and are re-exported here.
 */

/**
 * The slice of `expo-apple-authentication` this file calls. Structural so the
 * package is not imported at module scope — see `loadAppleAuthentication`.
 */
interface AppleAuthenticationModule {
  isAvailableAsync: () => Promise<boolean>;
  signInAsync: (options: {
    requestedScopes?: number[];
  }) => Promise<{ identityToken: string | null }>;
  AppleAuthenticationScope: { FULL_NAME: number; EMAIL: number };
}

export { APP_REVIEW_DEMO_EMAIL, isAppReviewDemoEmail } from './appReview';

export {
  AuthDisabledError,
  assertAuthEnabled,
  authErrorMessage,
  isCompleteOtp,
  isValidEmail,
  normalizeOtp,
  parseAuthCallback,
  providerLabel,
  visibleProviders,
  type AuthCallback,
  type AuthProvider,
} from './authHelpers';

/**
 * Send a one-time passcode to `email`. Creates the account on first use, so
 * there's no separate sign-up flow.
 */
export async function sendEmailCode(email: string): Promise<void> {
  assertAuthEnabled(AUTH_ENABLED);
  const address = email.trim().toLowerCase();
  if (!isValidEmail(address)) {
    throw new Error('Enter a valid email address.');
  }
  // The review address never asks Supabase to email a code. The fixed code
  // is checked by the edge function in verifyEmailCode.
  if (isAppReviewDemoEmail(address)) return;
  const { error } = await supabase.auth.signInWithOtp({
    email: address,
    options: { shouldCreateUser: true },
  });
  if (error) throw error;
}

/** Exchange an emailed passcode for a session. */
export async function verifyEmailCode(
  email: string,
  code: string,
): Promise<Session> {
  assertAuthEnabled(AUTH_ENABLED);
  const token = normalizeOtp(code);
  if (token.length !== EMAIL_OTP_LENGTH) {
    throw new Error(`Enter the ${EMAIL_OTP_LENGTH}-digit code from your email.`);
  }
  const address = email.trim().toLowerCase();
  if (isAppReviewDemoEmail(address)) return exchangeReviewCode(address, token);
  const { data, error } = await supabase.auth.verifyOtp({
    email: address,
    token,
    type: 'email',
  });
  if (error) throw error;
  if (!data.session) throw new Error('Sign-in did not return a session.');
  return data.session;
}

/**
 * Exchange the fixed review code for a session. Only the demo address reaches
 * here. Any other address stays on verifyOtp above. The code itself is not
 * in this file: the edge function reads it from APP_REVIEW_DEMO_OTP.
 */
async function exchangeReviewCode(email: string, token: string): Promise<Session> {
  const { data, error } = await supabase.functions.invoke(APP_REVIEW_SIGN_IN_FUNCTION, {
    body: { email, token },
  });
  const payload = (data ?? null) as {
    error?: string;
    access_token?: string;
    refresh_token?: string;
  } | null;
  if (payload?.error) throw new Error(payload.error);
  if (error) throw await reviewInvokeError(error);
  if (!payload?.access_token || !payload.refresh_token) {
    throw new Error('Could not sign in. Check the code and try again.');
  }
  const { data: sessionData, error: sessionError } = await supabase.auth.setSession({
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
  });
  if (sessionError) throw sessionError;
  if (!sessionData.session) throw new Error('Sign-in did not return a session.');
  return sessionData.session;
}

/**
 * `functions.invoke` puts a non-2xx body on `error.context` and leaves `data`
 * null. The function's own sentence is shown only when it is one of the four
 * review strings. A dropped connection stays a network error so the banner
 * can say to check the connection.
 */
async function reviewInvokeError(error: unknown): Promise<Error> {
  const name =
    error && typeof error === 'object' && 'name' in error
      ? String((error as { name?: unknown }).name)
      : '';
  if (name === 'FunctionsFetchError') return new Error('Network request failed');
  if (name === 'FunctionsHttpError') {
    const context = (error as { context?: { json?: () => Promise<unknown> } }).context;
    if (typeof context?.json === 'function') {
      try {
        const message = reviewFunctionErrorMessage(await context.json());
        if (message) return new Error(message);
      } catch {
        // Not JSON, or the body was already read.
      }
    }
  }
  return new Error('Could not sign in. Check the code and try again.');
}

/**
 * The user dismissed the Apple sheet. A cancel stays on the sign-in screen.
 */
function isAppleCancel(err: unknown): boolean {
  if (err == null || typeof err !== 'object' || !('code' in err)) return false;
  return String((err as { code?: unknown }).code ?? '') === 'ERR_REQUEST_CANCELED';
}

/**
 * Load Sign in with Apple. The `require` is the only place the package name
 * is a value, and it runs only after the iOS check. A static import would
 * evaluate the native module for email, Google, and Android too — an OTA
 * bundle that does that crashes on launch where the binary lacks the module.
 */
function loadAppleAuthentication(): AppleAuthenticationModule {
  if (Platform.OS !== 'ios') {
    throw new Error('Sign in with Apple uses the system sheet on iOS only.');
  }
  let mod: unknown;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    mod = require('expo-apple-authentication');
  } catch {
    throw new Error(
      'This build does not include Sign in with Apple. Update to the latest app version.',
    );
  }
  const resolved = mod as AppleAuthenticationModule;
  if (
    typeof resolved?.signInAsync !== 'function' ||
    resolved.AppleAuthenticationScope == null
  ) {
    throw new Error(
      'This build does not include Sign in with Apple. Update to the latest app version.',
    );
  }
  return resolved;
}

/**
 * iOS Sign in with Apple: system sheet, then the identity token. No browser.
 * Returns null when the sheet is dismissed.
 */
async function signInWithAppleNative(): Promise<Session | null> {
  const apple = loadAppleAuthentication();
  if (!(await apple.isAvailableAsync())) {
    throw new Error('Sign in with Apple is not available on this device.');
  }
  let credential: { identityToken: string | null };
  try {
    credential = await apple.signInAsync({
      requestedScopes: [
        apple.AppleAuthenticationScope.FULL_NAME,
        apple.AppleAuthenticationScope.EMAIL,
      ],
    });
  } catch (e) {
    if (isAppleCancel(e)) return null;
    throw new Error("Couldn't sign in with Apple. Try again.");
  }
  const token = credential.identityToken;
  if (!token) throw new Error("Couldn't sign in with Apple. Try again.");
  const { data, error } = await supabase.auth.signInWithIdToken({
    provider: 'apple',
    token,
  });
  if (error || !data.session) {
    throw new Error("Couldn't sign in with Apple. Try again.");
  }
  return data.session;
}

/**
 * Run a provider in an in-app browser and exchange the returned code for a
 * session. Google on both platforms. Apple only when this is not iOS.
 *
 * Returns `null` when the user dismisses the browser — a cancel is a normal
 * outcome, not an error, and the caller should just stay on the sign-in screen.
 */
async function signInWithOAuthBrowser(
  provider: AuthProvider,
): Promise<Session | null> {
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider,
    options: {
      redirectTo: AUTH_REDIRECT_URL,
      // We drive the browser ourselves so we can read the callback URL back.
      skipBrowserRedirect: true,
    },
  });
  if (error) throw error;
  if (!data?.url) throw new Error('Could not start the sign-in flow.');

  const result = await WebBrowser.openAuthSessionAsync(
    data.url,
    AUTH_REDIRECT_URL,
  );
  if (result.type !== 'success') return null; // cancel / dismiss

  const { code, error: callbackError } = parseAuthCallback(result.url);
  if (callbackError) throw new Error(callbackError);
  if (!code) throw new Error('Sign-in did not return an authorization code.');

  const exchanged = await supabase.auth.exchangeCodeForSession(code);
  if (exchanged.error) throw exchanged.error;
  if (!exchanged.data.session) {
    throw new Error('Sign-in did not return a session.');
  }
  return exchanged.data.session;
}

/**
 * Sign in with Apple or Google.
 *
 * On iOS, Apple is the system sheet and `signInWithIdToken`. Every other
 * case is the in-app browser. Returns `null` when the user dismisses the
 * sheet or the browser.
 */
export async function signInWithProvider(
  provider: AuthProvider,
): Promise<Session | null> {
  assertAuthEnabled(AUTH_ENABLED);
  if (provider === 'apple' && Platform.OS === 'ios') {
    return signInWithAppleNative();
  }
  return signInWithOAuthBrowser(provider);
}

export async function signOut(): Promise<void> {
  assertAuthEnabled(AUTH_ENABLED);
  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}

/** Current session, or null. Returns null (never throws) when auth is off. */
export async function getCurrentSession(): Promise<Session | null> {
  if (!AUTH_ENABLED) return null;
  const { data, error } = await supabase.auth.getSession();
  if (error) throw error;
  return data.session;
}
