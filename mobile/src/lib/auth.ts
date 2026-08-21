import * as WebBrowser from 'expo-web-browser';
import type { Session } from '@supabase/supabase-js';

import { supabase } from './supabase';
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
 * Three methods, all pure JS so the whole feature ships over OTA with no native
 * module and no EAS rebuild:
 *
 *   - Email  → one-time 6-digit passcode (`signInWithOtp` + `verifyOtp`).
 *              Deliberately NOT a magic link: a code needs no deep-link handler
 *              and can't be broken by an email client that rewrites URLs.
 *   - Apple  → Supabase OAuth in an in-app browser (`expo-web-browser`, already
 *   - Google   a dependency for SharpSports) using the PKCE flow.
 *
 * The Apple button uses the web flow rather than the native sheet. That is a
 * deliberate trade: `expo-apple-authentication` gives a nicer one-tap sheet but
 * is a native module, which means an EAS rebuild and — per the OTA rule in
 * CLAUDE.md — a bundle importing it would crash on any installed binary that
 * predates that rebuild. See docs/AUTHENTICATION.md for the upgrade path.
 *
 * Pure helpers live in ./authHelpers (kept free of react-native so the verify
 * script can import them) and are re-exported here.
 */

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
  const { data, error } = await supabase.auth.verifyOtp({
    email: email.trim().toLowerCase(),
    token,
    type: 'email',
  });
  if (error) throw error;
  if (!data.session) throw new Error('Sign-in did not return a session.');
  return data.session;
}

/**
 * Run an OAuth provider in an in-app browser and exchange the returned code for
 * a session.
 *
 * Returns `null` when the user dismisses the browser — a cancel is a normal
 * outcome, not an error, and the caller should just stay on the sign-in screen.
 */
export async function signInWithProvider(
  provider: AuthProvider,
): Promise<Session | null> {
  assertAuthEnabled(AUTH_ENABLED);

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
