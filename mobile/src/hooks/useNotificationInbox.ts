import { useCallback, useEffect, useState } from 'react';
import * as Notifications from 'expo-notifications';

import { readAuthUserId } from '@/hooks/useAuth';
import { applyUnreadBadge, dismissInboxNotifications } from '@/lib/notificationBadge';
import {
  mutedSports,
  newInboxId,
  unreadCount,
  visibleInbox,
  type InboxRow,
} from '@/lib/notificationInbox';
import { buildTestMessage } from '@/lib/pushTest';
import { supabase } from '@/lib/supabase';

/**
 * One inbox for every tab. The store is module-level so the bell on Picks
 * and the bell on Stats cannot disagree, and so marking a row read clears
 * every badge in the same turn.
 *
 * Reads fail closed to an empty list when the hand migration is not applied
 * yet: the bell stays, the count is zero, and a push still arrives the way
 * it did before this screen existed.
 */

export interface InboxSnapshot {
  rows: InboxRow[];
  muted: Set<string>;
  unread: number;
  loading: boolean;
  /** True after the first load for this user settles, including signed out. */
  loaded: boolean;
  error: string | null;
  userId: string | null;
}

const listeners = new Set<(s: InboxSnapshot) => void>();

let snapshot: InboxSnapshot = {
  rows: [],
  muted: new Set(),
  unread: 0,
  loading: false,
  loaded: false,
  error: null,
  userId: null,
};

let inflight: Promise<void> | null = null;
let inflightFor: string | null | undefined;
/** Last server page, before the mute filter, so unmuting a sport can show it. */
let fetched: InboxRow[] = [];

function emit(next: InboxSnapshot) {
  snapshot = next;
  listeners.forEach((fn) => fn(snapshot));
}

async function load(userId: string | null): Promise<void> {
  if (!userId) {
    fetched = [];
    emit({ rows: [], muted: new Set(), unread: 0, loading: false, loaded: true, error: null, userId: null });
    await applyUnreadBadge(0, Notifications);
    return;
  }
  emit({ ...snapshot, loading: true, error: null, userId });
  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  const [inbox, prefs] = await Promise.all([
    supabase
      .from('notification_inbox')
      .select('id, kind, title, body, sport, route, notification_id, sent_at, read_at')
      .eq('user_id', userId)
      .gte('sent_at', since)
      .order('sent_at', { ascending: false }),
    supabase.from('notification_sport_prefs').select('sport, enabled').eq('user_id', userId),
  ]);
  if (inbox.error || prefs.error) {
    const message = inbox.error?.message || prefs.error?.message || 'Could not load notifications';
    // A missing table (migration not applied) is an empty inbox, not an error
    // the reader can act on. Anything else is shown with a retry.
    const missing = /notification_inbox|notification_sport_prefs|schema cache|PGRST205|does not exist/i.test(
      message,
    );
    if (missing) fetched = [];
    emit({
      rows: missing ? [] : snapshot.rows,
      muted: missing ? new Set() : snapshot.muted,
      unread: missing ? 0 : snapshot.unread,
      loading: false,
      loaded: true,
      error: missing ? null : message,
      userId,
    });
    if (missing) await applyUnreadBadge(0, Notifications);
    return;
  }
  const muted = mutedSports((prefs.data ?? []) as { sport: string; enabled: boolean }[]);
  fetched = (inbox.data ?? []) as InboxRow[];
  const rows = visibleInbox(fetched, muted, new Date());
  const unread = unreadCount(rows);
  emit({ rows, muted, unread, loading: false, loaded: true, error: null, userId });
  await applyUnreadBadge(unread, Notifications);
}

export function refreshNotificationInbox(userId?: string | null): Promise<void> {
  const id = userId === undefined ? readAuthUserId() : userId;
  if (inflight && inflightFor === id) return inflight;
  inflightFor = id;
  inflight = load(id).finally(() => {
    inflight = null;
  });
  return inflight;
}

export function useNotificationInbox(): InboxSnapshot & {
  refresh: () => Promise<void>;
  markRead: (row: InboxRow) => Promise<void>;
  markAllRead: () => Promise<void>;
  dismissVisible: () => Promise<void>;
  setSportEnabled: (sport: string, enabled: boolean) => Promise<void>;
} {
  const [local, setLocal] = useState(snapshot);
  useEffect(() => {
    setLocal(snapshot);
    const listener = (s: InboxSnapshot) => setLocal(s);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const refresh = useCallback(() => refreshNotificationInbox(readAuthUserId()), []);

  const markRead = useCallback(async (row: InboxRow) => {
    if (row.read_at != null) return;
    const readAt = new Date().toISOString();
    fetched = fetched.map((r) => (r.id === row.id ? { ...r, read_at: readAt } : r));
    const rows = visibleInbox(fetched, snapshot.muted, new Date());
    const unread = unreadCount(rows);
    emit({ ...snapshot, rows, unread });
    await applyUnreadBadge(unread, Notifications);
    await dismissInboxNotifications([row.notification_id], Notifications);
    const userId = snapshot.userId;
    if (!userId) return;
    const { error } = await supabase
      .from('notification_inbox')
      .update({ read_at: readAt })
      .eq('id', row.id)
      .eq('user_id', userId);
    if (error) void refreshNotificationInbox(userId);
  }, []);

  const markAllRead = useCallback(async () => {
    const unread = snapshot.rows.filter((r) => r.read_at == null);
    if (unread.length === 0) return;
    const readAt = new Date().toISOString();
    const ids = new Set(unread.map((r) => r.id));
    fetched = fetched.map((r) => (ids.has(r.id) ? { ...r, read_at: readAt } : r));
    const rows = visibleInbox(fetched, snapshot.muted, new Date());
    emit({ ...snapshot, rows, unread: 0 });
    await applyUnreadBadge(0, Notifications);
    await dismissInboxNotifications(unread.map((r) => r.notification_id), Notifications);
    const userId = snapshot.userId;
    if (!userId) return;
    const { error } = await supabase
      .from('notification_inbox')
      .update({ read_at: readAt })
      .eq('user_id', userId)
      .in('id', unread.map((r) => r.id));
    if (error) void refreshNotificationInbox(userId);
  }, []);

  const dismissVisible = useCallback(async () => {
    await dismissInboxNotifications(
      snapshot.rows.map((r) => r.notification_id),
      Notifications,
    );
  }, []);

  const setSportEnabled = useCallback(async (sport: string, enabled: boolean) => {
    const userId = snapshot.userId ?? readAuthUserId();
    if (!userId) return;
    const muted = new Set(snapshot.muted);
    if (enabled) muted.delete(sport);
    else muted.add(sport);
    const rows = visibleInbox(fetched, muted, new Date());
    emit({ ...snapshot, muted, rows, unread: unreadCount(rows) });
    await applyUnreadBadge(unreadCount(rows), Notifications);
    const { error } = await supabase.from('notification_sport_prefs').upsert(
      { user_id: userId, sport, enabled, updated_at: new Date().toISOString() },
      { onConflict: 'user_id,sport' },
    );
    if (error) void refreshNotificationInbox(userId);
  }, []);

  return { ...local, refresh, markRead, markAllRead, dismissVisible, setSportEnabled };
}

/** The Settings test push, recorded so it shows in the inbox. No sport. */
export async function recordTestNotification(inboxId: string): Promise<void> {
  const userId = readAuthUserId();
  if (!userId) return;
  const message = buildTestMessage('unused', inboxId);
  const { error } = await supabase.from('notification_inbox').insert({
    user_id: userId,
    kind: 'test',
    title: message.title,
    body: message.body,
    sport: null,
    route: message.data,
    notification_id: inboxId,
  });
  if (!error) void refreshNotificationInbox(userId);
}

export { newInboxId };
