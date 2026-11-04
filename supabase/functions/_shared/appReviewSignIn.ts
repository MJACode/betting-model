/**
 * App Review fixed-code gate. Pure: no Deno, no Supabase client.
 *
 * The bypass is off unless both secrets are set and the code secret is
 * exactly six digits. A missing secret is not a default code. Comparison
 * always walks a fixed width so a short guess is not faster.
 */

export const REVIEW_FAILURE_LIMIT = 8;
export const REVIEW_FAILURE_WINDOW_MS = 15 * 60 * 1000;
export const REVIEW_GLOBAL_FAILURE_LIMIT = 200;
export const REVIEW_GLOBAL_WINDOW_MS = 60 * 60 * 1000;

export const REVIEW_NOT_CONFIGURED = "Review sign-in is not configured.";
export const REVIEW_UNAVAILABLE = "Review sign-in is unavailable. Try again.";
export const REVIEW_CODE_MISMATCH = "That code doesn't match. Check it and try again.";
export const REVIEW_TOO_MANY = "Too many tries. Wait a few minutes and try again.";
export const REVIEW_MINT_FAILED = "Could not sign in. Try again.";

const COMPARE_WIDTH = 320;

export function normalizeReviewEmail(raw: string): string {
  return raw.trim().toLowerCase();
}

/** Digits only, clamped to the passcode length. A shorter result cannot match. */
export function normalizeReviewOtp(raw: string): string {
  return raw.replace(/\D/g, "").slice(0, 6);
}

export function reviewBypassConfigured(
  emailSecret: string | undefined | null,
  otpSecret: string | undefined | null,
): boolean {
  const email = normalizeReviewEmail(emailSecret ?? "");
  const otp = (otpSecret ?? "").trim();
  if (!email.includes("@") || email.length > 254) return false;
  return /^\d{6}$/.test(otp);
}

function fixedEqual(given: string, expected: string): boolean {
  const left = given.slice(0, COMPARE_WIDTH);
  const right = expected.slice(0, COMPARE_WIDTH);
  let diff = left.length === right.length ? 0 : 1;
  for (let i = 0; i < COMPARE_WIDTH; i++) {
    const a = i < left.length ? left.charCodeAt(i) : 0;
    const b = i < right.length ? right.charCodeAt(i) : 0;
    diff |= a ^ b;
  }
  return diff === 0;
}

/**
 * True only when both the address and the code match. Both compares always
 * run. The expected code is normalized the same way as the guess, and
 * `reviewBypassConfigured` has already required it to be six digits.
 */
export function reviewCredentialsMatch(
  givenEmail: string,
  givenOtp: string,
  expectedEmail: string,
  expectedOtp: string,
): boolean {
  const emailOk = fixedEqual(
    normalizeReviewEmail(givenEmail),
    normalizeReviewEmail(expectedEmail),
  );
  const otpOk = fixedEqual(
    normalizeReviewOtp(givenOtp),
    normalizeReviewOtp(expectedOtp),
  );
  return emailOk && otpOk;
}

/** `recentFailures` includes the failure just recorded. */
export function reviewFailureLimitReached(recentFailures: number): boolean {
  return recentFailures > REVIEW_FAILURE_LIMIT;
}

/** Hourly ceiling across every caller. `count` includes the failure just recorded. */
export function reviewGlobalFailureLimitReached(count: number): boolean {
  return count > REVIEW_GLOBAL_FAILURE_LIMIT;
}

/**
 * The edge's own address, not a hop the caller can invent.
 *
 * `cf-connecting-ip` is set by Cloudflare in front of Supabase. If it is
 * missing, the last `x-forwarded-for` hop is the one the proxy appended.
 * The first hop is caller-controlled and is ignored.
 */
export function clientIpFromHeaders(
  cfConnectingIp: string | null | undefined,
  forwardedFor: string | null | undefined,
): string {
  const cf = (cfConnectingIp ?? "").trim();
  if (cf) return cf;
  const hops = (forwardedFor ?? "")
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
  const last = hops.length > 0 ? hops[hops.length - 1] : "";
  if (last) return last;
  return "unknown";
}

/** SHA-256 hex. The attempt table stores this, not the address. */
export async function hashAttemptBucket(ip: string): Promise<string> {
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(ip),
  );
  return [...new Uint8Array(digest)]
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
