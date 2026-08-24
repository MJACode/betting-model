/**
 * Pure helpers for the in-app feedback experience.
 *
 * Deliberately free of any react-native / supabase import so `scripts/
 * verify_feedback.ts` can load it under tsx (the lib/customModelBacktest.ts
 * split, session 113). Anything that touches the network lives in lib/feedback.ts.
 */

export type FeedbackCategory = 'bug' | 'idea' | 'picks' | 'billing' | 'other';
export type FeedbackSender = 'user' | 'support';
export type FeedbackStatus = 'open' | 'answered' | 'closed';

export interface FeedbackThread {
  thread_id: number;
  category: string;
  subject: string;
  status: string;
  created_at: string | null;
  last_message_at: string | null;
  last_read_at: string | null;
  message_count: number;
  unread_count: number;
  last_sender: string | null;
  last_body: string | null;
}

export interface FeedbackMessage {
  message_id: number;
  sender: string;
  body: string;
  created_at: string | null;
}

/** Category chips, in the order they render. Keys match the server whitelist —
 *  anything else is coerced to 'other' by feedback_submit. */
export const FEEDBACK_CATEGORIES: { key: FeedbackCategory; label: string }[] = [
  { key: 'bug', label: 'Something broke' },
  { key: 'picks', label: 'A pick looks wrong' },
  { key: 'idea', label: 'Feature idea' },
  { key: 'billing', label: 'Billing' },
  { key: 'other', label: 'Something else' },
];

export function categoryLabel(key: string): string {
  return FEEDBACK_CATEGORIES.find((c) => c.key === key)?.label ?? 'Something else';
}

/** Mirrors the server cap in feedback_submit. Kept in sync by hand — the server
 *  is the enforcer; this is only so the composer can warn before the round trip. */
export const MAX_FEEDBACK_CHARS = 4000;

export type Validation = { ok: true; body: string } | { ok: false; reason: string };

/** Same rules feedback_submit applies, so the user hears about a problem before
 *  the network does. Trims, because the server trims and would otherwise accept
 *  a message that looked non-empty here. */
export function validateFeedback(raw: string): Validation {
  const body = (raw ?? '').trim();
  if (!body) return { ok: false, reason: 'Write a message first.' };
  if (body.length > MAX_FEEDBACK_CHARS) {
    return {
      ok: false,
      reason: `That's ${body.length.toLocaleString()} characters — keep it under ${MAX_FEEDBACK_CHARS.toLocaleString()}.`,
    };
  }
  return { ok: true, body };
}

/**
 * Parse a timestamp the way our rows actually store it.
 *
 * These columns are TEXT filled by `NOW()::TEXT`, which is Postgres' own format
 * — "2026-08-24 12:34:56.789+00": a SPACE separator and a two-digit offset.
 * That is not ISO-8601, and passing it straight to `new Date()` returns Invalid
 * Date on some JS engines. Normalize to ISO, and return null rather than NaN so
 * a row with an odd timestamp renders without a time instead of "Invalid Date".
 */
export function parseTimestamp(raw: string | null | undefined): number | null {
  if (!raw) return null;
  const s = raw.trim();
  const iso = s.replace(' ', 'T').replace(/([+-]\d{2})$/, '$1:00');
  const parsed = Date.parse(iso);
  if (!Number.isNaN(parsed)) return parsed;
  const fallback = Date.parse(s);
  return Number.isNaN(fallback) ? null : fallback;
}

const MIN = 60_000;
const HOUR = 60 * MIN;
const DAY = 24 * HOUR;

/** Compact "when" for message bubbles and thread rows. */
export function relativeTime(raw: string | null | undefined, now: number = Date.now()): string {
  const ts = parseTimestamp(raw);
  if (ts == null) return '';
  const delta = now - ts;
  if (delta < 0) return 'just now';          // clock skew — never say "in 3 hours"
  if (delta < MIN) return 'just now';
  if (delta < HOUR) return `${Math.floor(delta / MIN)}m ago`;
  if (delta < DAY) return `${Math.floor(delta / HOUR)}h ago`;
  if (delta < 7 * DAY) return `${Math.floor(delta / DAY)}d ago`;
  return new Date(ts).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

/**
 * What the thread row says on the right.
 *
 * 'open' means the ball is with us — including right after a user replies to an
 * answer, which is why feedback_submit resets status to 'open'.
 */
export function statusLabel(thread: Pick<FeedbackThread, 'status' | 'unread_count'>): string {
  if (thread.unread_count > 0) return 'New reply';
  switch (thread.status) {
    case 'answered':
      return 'Replied';
    case 'closed':
      return 'Closed';
    default:
      return 'Waiting on us';
  }
}

export function unreadTotal(threads: FeedbackThread[]): number {
  return threads.reduce((sum, t) => sum + (t.unread_count || 0), 0);
}

/** Newest activity first. The RPC already orders this way; re-sorting keeps the
 *  list stable after an optimistic local insert. */
export function sortThreads(threads: FeedbackThread[]): FeedbackThread[] {
  return [...threads].sort(
    (a, b) => (parseTimestamp(b.last_message_at) ?? 0) - (parseTimestamp(a.last_message_at) ?? 0),
  );
}

/**
 * Turn a Postgres exception into something a person can act on.
 *
 * The RPC raises short, stable strings ('too many messages, try again later',
 * 'message too long', …). Anything unrecognised gets a generic line — never the
 * raw SQL error, which would leak function names into the UI.
 */
export function feedbackErrorMessage(err: unknown): string {
  const raw = typeof err === 'string' ? err : ((err as { message?: string })?.message ?? '');
  const msg = raw.toLowerCase();
  if (msg.includes('too many messages')) {
    return "You've sent a lot in the last hour — try again a bit later.";
  }
  if (msg.includes('too many open conversations')) {
    return 'You have a lot of open conversations. Continue one of those instead.';
  }
  if (msg.includes('message too long')) {
    return `Keep it under ${MAX_FEEDBACK_CHARS.toLocaleString()} characters.`;
  }
  if (msg.includes('empty message')) return 'Write a message first.';
  if (msg.includes('thread not found')) return "That conversation isn't available on this device.";
  if (msg.includes('invalid device')) return "Couldn't identify this device. Restart the app and try again.";
  return "Couldn't send that. Check your connection and try again.";
}
