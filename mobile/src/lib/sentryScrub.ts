/**
 * Strip personal data and secrets from a Sentry event before it leaves the
 * device (lib/sentry.ts beforeSend / beforeBreadcrumb).
 *
 * sendDefaultPii is already off. This is the second pass: a breadcrumb, a
 * request header or a message can still carry an email, a bearer token, a
 * JWT, an API key, a password or a query-string token. The device id tag is
 * not one of those and is left alone.
 */

const SENSITIVE_KEY =
  /^(email|e-mail|ip|ip_address|ipaddress|password|passwd|secret|token|access_token|refresh_token|id_token|api_key|apikey|api-key|authorization|proxy-authorization|cookie|set-cookie)$/i;

const JWT = /eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}/g;

const BEARER = /Bearer\s+[A-Za-z0-9\-._~+/]+=*/gi;

const BASIC = /Basic\s+[A-Za-z0-9+/]+=*/gi;

const EMAIL = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/g;

const QUERY_SECRET =
  /([?&\s](?:token|access_token|refresh_token|id_token|api_key|apikey|key|password|passwd|secret|auth|authorization)=)[^&#\s]*/gi;

const KEYED_SECRET =
  /((?:api[_-]?key|token|password|passwd|secret|authorization)\s*[:=]\s*["']?)[^"',\s}&]+/gi;

const API_KEY_PREFIX = /\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]+/g;

const REDACTED = '[redacted]';

export function scrubString(value: string): string {
  return value
    .replace(JWT, REDACTED)
    .replace(BEARER, `Bearer ${REDACTED}`)
    .replace(BASIC, `Basic ${REDACTED}`)
    .replace(QUERY_SECRET, `$1${REDACTED}`)
    .replace(KEYED_SECRET, `$1${REDACTED}`)
    .replace(API_KEY_PREFIX, REDACTED)
    .replace(EMAIL, REDACTED);
}

function scrubValue(value: unknown, seen: WeakSet<object>): unknown {
  if (typeof value === 'string') return scrubString(value);
  if (value === null || typeof value !== 'object') return value;
  if (seen.has(value)) return value;
  seen.add(value);
  if (Array.isArray(value)) return value.map((item) => scrubValue(item, seen));
  const out: Record<string, unknown> = {};
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    out[key] = SENSITIVE_KEY.test(key) ? REDACTED : scrubValue(item, seen);
  }
  return out;
}

/** beforeSend. Returns the event with secrets removed. Never drops it. */
export function scrubSentryEvent<T>(event: T): T {
  return scrubValue(event, new WeakSet()) as T;
}

/** beforeBreadcrumb. Same rules as an event. */
export function scrubBreadcrumb<T>(breadcrumb: T): T {
  return scrubValue(breadcrumb, new WeakSet()) as T;
}
