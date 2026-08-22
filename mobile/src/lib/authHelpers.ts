import { AUTH_PROVIDERS, EMAIL_OTP_LENGTH, showAppleOn } from './authConfig';

/**
 * Pure auth helpers — no React, no react-native, no expo, no Supabase.
 *
 * Deliberately split out from lib/auth.ts so scripts/verify_auth.ts can import
 * them: anything that reaches react-native (directly, or transitively via the
 * Supabase client's AsyncStorage) can't be transformed by tsx/esbuild, which is
 * the same reason lib/customModelBacktest.ts exists separately from its hook.
 *
 * lib/auth.ts re-exports everything here, so callers only ever import from
 * '@/lib/auth'.
 */

export type AuthProvider = 'apple' | 'google';

/** Thrown when an auth call is made while the feature flag is off. */
export class AuthDisabledError extends Error {
  constructor() {
    super('Authentication is not enabled in this build.');
    this.name = 'AuthDisabledError';
  }
}

/**
 * Guard every network entry point in lib/auth.ts. Takes the flag as an argument
 * rather than reading it directly so it stays pure and testable.
 */
export function assertAuthEnabled(enabled: boolean): void {
  if (!enabled) throw new AuthDisabledError();
}

/**
 * Good-enough email shape check: one `@`, a non-empty local part, and a dotted
 * domain. Deliberately permissive — the authoritative check is Supabase
 * actually delivering the code. This only exists to catch typos before we spend
 * a round trip.
 */
export function isValidEmail(raw: string): boolean {
  const email = raw.trim();
  if (email.length === 0 || email.length > 254) return false;
  if (/\s/.test(email)) return false;
  return /^[^@]+@[^@.]+(\.[^@.]+)+$/.test(email);
}

/** Strip everything but digits and clamp to the passcode length. */
export function normalizeOtp(raw: string): string {
  return raw.replace(/\D/g, '').slice(0, EMAIL_OTP_LENGTH);
}

/** True once the user has typed a full-length passcode. */
export function isCompleteOtp(raw: string): boolean {
  return normalizeOtp(raw).length === EMAIL_OTP_LENGTH;
}

export interface AuthCallback {
  code: string | null;
  error: string | null;
}

/**
 * Pull the PKCE `code` (or an error) out of the URL the provider redirects back
 * to. Reads the query string and the fragment: PKCE puts `code` in the query,
 * but a provider misconfigured for the implicit flow returns tokens in the
 * fragment, and we want that to surface as a clear error rather than a silent
 * "nothing happened".
 */
export function parseAuthCallback(url: string): AuthCallback {
  const read = (part: string | undefined): URLSearchParams =>
    new URLSearchParams(part ?? '');

  const [beforeHash, hash] = url.split('#');
  const query = read(beforeHash.split('?')[1]);
  const fragment = read(hash);

  const errorDescription =
    query.get('error_description') ?? fragment.get('error_description');
  const errorCode = query.get('error') ?? fragment.get('error');
  if (errorCode || errorDescription) {
    return { code: null, error: errorDescription || errorCode };
  }

  const code = query.get('code') ?? fragment.get('code');
  if (code) return { code, error: null };

  if (fragment.get('access_token')) {
    return {
      code: null,
      error:
        'This provider returned an implicit-flow token. Set the Supabase client to the PKCE flow.',
    };
  }

  return { code: null, error: null };
}

/**
 * Which provider buttons to render, given the flags and the platform.
 * Platform is passed in (not read from react-native) to keep this pure.
 */
export function visibleProviders(platform: string): AuthProvider[] {
  const out: AuthProvider[] = [];
  if (AUTH_PROVIDERS.apple && showAppleOn.includes(platform)) out.push('apple');
  if (AUTH_PROVIDERS.google) out.push('google');
  return out;
}

export function providerLabel(provider: AuthProvider): string {
  return provider === 'apple' ? 'Sign in with Apple' : 'Continue with Google';
}

/**
 * Turn whatever Supabase (or the browser flow) threw into something worth
 * showing a user. Supabase's raw strings are mostly fine, but a few are
 * jargon-y enough to be worth rewriting, and a bare network failure reads as
 * "something went wrong" without this.
 */
export function authErrorMessage(err: unknown): string {
  const raw =
    err instanceof Error
      ? err.message
      : typeof err === 'string'
        ? err
        : 'Something went wrong. Please try again.';

  const lower = raw.toLowerCase();
  if (lower.includes('token has expired') || lower.includes('otp_expired')) {
    return 'That code has expired. Request a new one.';
  }
  if (lower.includes('invalid token') || lower.includes('token is invalid')) {
    return "That code doesn't match. Check it and try again.";
  }
  if (
    lower.includes('email rate limit') ||
    lower.includes('over_email_send_rate_limit')
  ) {
    return 'Too many codes requested. Wait a minute and try again.';
  }
  if (lower.includes('network') || lower.includes('fetch failed')) {
    return 'No connection. Check your network and try again.';
  }
  if (lower.includes('provider is not enabled')) {
    return 'That sign-in method is not set up yet.';
  }
  return raw;
}
