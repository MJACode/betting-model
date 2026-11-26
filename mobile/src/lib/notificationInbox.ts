/**
 * The pure half of the notifications inbox.
 *
 * No React, no Supabase, no expo-notifications. The screen, the bell and the
 * verify script all share this so a muted sport cannot be counted in one
 * place and shown in another.
 *
 * The window is 7 days rolling from `now`, not a calendar week. A row whose
 * sport is muted is hidden from the list, the pill, the bell and the badge.
 * A row with no sport (feedback, the Settings test, a multi-sport summary)
 * stays. Started and settled picks are not a special case here: a one-pick
 * alert still routes to that pick.
 */

import { etDate } from '@/lib/format';

export const INBOX_RETENTION_MS = 7 * 24 * 60 * 60 * 1000;

export interface InboxRoute {
  v?: number;
  type?: string;
  pickId?: number | string;
  threadId?: number | string;
  sport?: string | null;
  inboxId?: string;
  [key: string]: unknown;
}

export interface InboxRow {
  id: string;
  kind: string;
  title: string;
  body: string;
  sport: string | null;
  route: InboxRoute;
  notification_id: string;
  sent_at: string;
  read_at: string | null;
}

export type InboxSection = 'TODAY' | 'EARLIER';

export function mutedSports(prefs: { sport: string; enabled: boolean }[]): Set<string> {
  return new Set(prefs.filter((p) => p.enabled === false).map((p) => p.sport));
}

export function visibleInbox(rows: InboxRow[], muted: Set<string>, now: Date): InboxRow[] {
  const cutoff = now.getTime() - INBOX_RETENTION_MS;
  return rows.filter((row) => {
    const at = new Date(row.sent_at).getTime();
    if (Number.isNaN(at) || at < cutoff) return false;
    if (row.sport && muted.has(row.sport)) return false;
    return true;
  });
}

export function unreadRows(rows: InboxRow[]): InboxRow[] {
  return rows.filter((row) => row.read_at == null);
}

export function unreadCount(rows: InboxRow[]): number {
  return unreadRows(rows).length;
}

/** The ET calendar day before `today` (YYYY-MM-DD). */
function etDayBefore(today: string): string {
  const [y, m, d] = today.split('-').map(Number);
  const utc = new Date(Date.UTC(y, m - 1, d));
  utc.setUTCDate(utc.getUTCDate() - 1);
  const mm = String(utc.getUTCMonth() + 1).padStart(2, '0');
  const dd = String(utc.getUTCDate()).padStart(2, '0');
  return `${utc.getUTCFullYear()}-${mm}-${dd}`;
}

export function inboxSection(sentAt: string, now: Date): InboxSection {
  const at = new Date(sentAt);
  if (Number.isNaN(at.getTime())) return 'EARLIER';
  return etDate(at) === etDate(now) ? 'TODAY' : 'EARLIER';
}

/** 8m today, Yesterday, Mon, Nov 12. The day boundary is America/New_York,
 *  the same clock as the boards, not the phone's local midnight. */
export function inboxTimeLabel(sentAt: string, now: Date): string {
  const at = new Date(sentAt);
  if (Number.isNaN(at.getTime())) return '';
  const today = etDate(now);
  const sent = etDate(at);
  if (sent === today) {
    const mins = Math.max(0, Math.round((now.getTime() - at.getTime()) / 60000));
    if (mins < 60) return mins < 1 ? 'now' : `${mins}m`;
    return `${Math.round(mins / 60)}h`;
  }
  if (sent === etDayBefore(today)) return 'Yesterday';
  const days = (Date.parse(today) - Date.parse(sent)) / 86400000;
  if (days >= 0 && days < 7) {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      weekday: 'short',
    }).format(at);
  }
  return new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    month: 'short',
    day: 'numeric',
  }).format(at);
}

/** The grey line under the body. The words are the frames'. */
export function inboxRouteCaption(row: InboxRow): string {
  if (row.kind === 'test') return 'Test · opens Picks · Today';
  const type = row.route?.type;
  const pickId = row.route?.pickId;
  const hasPick = pickId != null && pickId !== '';
  if (type === 'feedback_reply' || row.kind === 'feedback_reply') {
    return 'Feedback · opens this thread';
  }
  if (type === 'line_change' || row.kind === 'line_change') {
    return 'Tracked bet · opens this pick';
  }
  if (hasPick && (type === 'live_signals' || row.kind === 'live_signals')) {
    return 'Live · opens this pick';
  }
  if (hasPick && (type === 'dropped' || row.kind === 'dropped')) {
    return 'Today · opens this pick';
  }
  if (type === 'byom_bet' || row.kind === 'byom_bet') return 'My models · opens this model';
  if (hasPick) return 'Signals · opens this pick';
  if (type === 'live_signals') return 'Live · opens Picks · Live Signals';
  if (type === 'new_bets') return 'Signals · opens Picks · Signals';
  if (type === 'dropped') return 'Today · opens Picks · Today';
  return 'Opens this alert';
}

/** Ionicon name. Every one is drawn in tint, never bet green. */
export function inboxIconName(row: InboxRow): string {
  if (row.kind === 'test') return 'paper-plane';
  if (row.kind === 'feedback_reply') return 'chatbubble-ellipses';
  if (row.kind === 'live_signals') return 'locate';
  if (row.kind === 'new_bets') return 'flash';
  // A bet from the member's own model, not an official pick (2026-11-25).
  if (row.kind === 'byom_bet') return 'construct';
  if (row.kind === 'dropped') return 'analytics';
  if (row.kind === 'line_change') {
    return /against/i.test(row.title) ? 'trending-down' : 'trending-up';
  }
  return 'notifications';
}

export function newInboxId(): string {
  const cryptoObj = globalThis.crypto;
  if (cryptoObj && typeof cryptoObj.randomUUID === 'function') return cryptoObj.randomUUID();
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}
