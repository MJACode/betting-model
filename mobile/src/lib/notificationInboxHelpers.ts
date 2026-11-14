/**
 * The notifications inbox, pure half (Matt, 2026-11-14).
 *
 * Every push the worker builds is saved word for word in notification_inbox
 * (data/migrations/notification_inbox_2026_11_14.sql), whether or not this
 * phone has push turned on. The screen lists the last 30 days, bolds what has
 * not been opened, clears one on tap and clears them all with "Read all".
 *
 * NO IMPORTS: this file runs under bare node in
 * tests/test_notification_inbox.py (mobile/scripts/verify_notification_inbox.ts).
 */

export interface InboxItem {
  id: number;
  /** new_bets | dropped | live_signals | line_change | feedback_reply */
  kind: string;
  /** The push's own title, word for word. */
  title: string;
  /** The push's own body, word for word. */
  body: string;
  /** The push's routing payload, the same one a tap on the push reads. */
  data: unknown;
  created_at: string;
  is_read: boolean;
}

export interface InboxSection {
  title: string;
  data: InboxItem[];
}

const ET = 'America/New_York';

function etDay(ms: number): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: ET, year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date(ms));
}

/** A timestamptz as Postgres or PostgREST writes it, in ms; null if unreadable. */
export function parseInboxTime(raw: string | null | undefined): number | null {
  if (!raw) return null;
  // PostgREST sends ISO-8601 for timestamptz, but a space separator and a
  // two-digit offset ("2026-11-14 18:30:19+00") are normalised too, since some
  // engines return Invalid Date for them.
  let s = raw.trim().replace(' ', 'T');
  s = s.replace(/([+-]\d{2})$/, '$1:00');
  const ms = Date.parse(s);
  return Number.isNaN(ms) ? null : ms;
}

/** "Today", "Yesterday" or "Earlier", by the ET calendar day. */
export function dayBucket(createdAt: string, now: number = Date.now()): string {
  const ms = parseInboxTime(createdAt);
  if (ms == null) return 'Earlier';
  const day = etDay(ms);
  if (day === etDay(now)) return 'Today';
  if (day === etDay(now - 24 * 3600 * 1000)) return 'Yesterday';
  return 'Earlier';
}

/** "3:30 PM ET" today and yesterday; "Nov 12 · 3:30 PM ET" before that. */
export function inboxTimeLabel(createdAt: string, now: number = Date.now()): string {
  const ms = parseInboxTime(createdAt);
  if (ms == null) return '';
  const time = new Intl.DateTimeFormat('en-US', {
    timeZone: ET, hour: 'numeric', minute: '2-digit',
  }).format(new Date(ms));
  if (dayBucket(createdAt, now) !== 'Earlier') return `${time} ET`;
  const date = new Intl.DateTimeFormat('en-US', {
    timeZone: ET, month: 'short', day: 'numeric',
  }).format(new Date(ms));
  return `${date} · ${time} ET`;
}

/** Newest first, grouped Today / Yesterday / Earlier. Empty groups are left out. */
export function inboxSections(items: InboxItem[], now: number = Date.now()): InboxSection[] {
  const order = ['Today', 'Yesterday', 'Earlier'];
  const sorted = [...items].sort((a, b) =>
    (parseInboxTime(b.created_at) ?? 0) - (parseInboxTime(a.created_at) ?? 0) || b.id - a.id);
  const groups = new Map<string, InboxItem[]>();
  for (const item of sorted) {
    const key = dayBucket(item.created_at, now);
    const list = groups.get(key) ?? [];
    list.push(item);
    groups.set(key, list);
  }
  return order.filter((t) => groups.has(t)).map((t) => ({ title: t, data: groups.get(t)! }));
}

export function unreadOf(items: InboxItem[]): number {
  return items.reduce((n, i) => n + (i.is_read ? 0 : 1), 0);
}

/** The list after one item is opened. Unchanged when the id is not in it. */
export function withRead(items: InboxItem[], id: number): InboxItem[] {
  return items.map((i) => (i.id === id && !i.is_read ? { ...i, is_read: true } : i));
}

export function withAllRead(items: InboxItem[]): InboxItem[] {
  return items.map((i) => (i.is_read ? i : { ...i, is_read: true }));
}

/** The badge text: nothing at zero, "99+" past 99. */
export function badgeText(unread: number): string | null {
  if (!Number.isFinite(unread) || unread <= 0) return null;
  return unread > 99 ? '99+' : String(Math.floor(unread));
}

/**
 * The inbox row a push came from, read off the push's `data.inboxId`. A push
 * from before the inbox existed has none, and then nothing is marked.
 */
export function inboxIdFromPush(data: unknown): number | null {
  if (data == null || typeof data !== 'object') return null;
  const v = (data as Record<string, unknown>).inboxId;
  const n = typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : NaN;
  return Number.isInteger(n) && n > 0 ? n : null;
}

/** The screen reader's sentence for one row. */
export function inboxRowSpeech(item: InboxItem, now: number = Date.now()): string {
  const parts = [item.is_read ? '' : 'Unread.', item.title, item.body, inboxTimeLabel(item.created_at, now)];
  return parts.filter(Boolean).join(' ');
}
