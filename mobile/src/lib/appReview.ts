/**
 * App Review demo address. Not a secret.
 *
 * The fixed code is not in the app. Supabase secrets
 * `APP_REVIEW_DEMO_EMAIL` and `APP_REVIEW_DEMO_OTP` are the only place the
 * bypass will accept a code, and the email secret has to be this address
 * or the app never calls the function for it. Paste values live in
 * `mobile/APP_STORE_METADATA.md`.
 */

export const APP_REVIEW_DEMO_EMAIL = 'review@signalbase-ai.com';

export const APP_REVIEW_SIGN_IN_FUNCTION = 'app-review-sign-in';

export function isAppReviewDemoEmail(raw: string): boolean {
  return raw.trim().toLowerCase() === APP_REVIEW_DEMO_EMAIL;
}

/** Code step for this address only. */
export function appReviewCodePrompt(otpLength: number): string {
  return `Enter the ${otpLength}-digit code from App Review Information. No email is sent for this address.`;
}

/**
 * Sentences the edge function returns. Kept here so the app can show them
 * and so a stray function body cannot become the banner.
 */
export const REVIEW_SIGN_IN_ERRORS = [
  'Review sign-in is not configured.',
  'Review sign-in is unavailable. Try again.',
  "That code doesn't match. Check it and try again.",
  'Too many tries. Wait a few minutes and try again.',
  'Could not sign in. Try again.',
] as const;

export function reviewFunctionErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== 'object' || !('error' in body)) return null;
  const message = (body as { error?: unknown }).error;
  if (typeof message !== 'string') return null;
  return (REVIEW_SIGN_IN_ERRORS as readonly string[]).includes(message) ? message : null;
}
