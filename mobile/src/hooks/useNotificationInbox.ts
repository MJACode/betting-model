import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';
import * as Notifications from 'expo-notifications';

import { readAuthStatus, readAuthUserId, subscribeAuthUser } from '@/hooks/useAuth';
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
  /** False until notification_inbox_hide_2026_11_26.sql adds deleted_at. The
   *  screen hides its delete controls rather than offer one that fails. */
  canDelete: boolean;
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
  canDelete: false,
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
    emit({
      rows: [],
      muted: new Set(),
      unread: 0,
      loading: false,
      loaded: true,
      error: null,
      userId: null,
      canDelete: false,
    });
    await applyUnreadBadge(0, Notifications);
    return;
  }
  emit({ ...snapshot, loading: true, error: null, userId });
  const since = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
  // "Delete" is a hide: deleted_at is stamped and the row stays (no data is
  // ever deleted). Until the column exists, read the way we always did.
  const readInbox = (withHidden: boolean) =>
    withHidden
      ? supabase
          .from('notification_inbox')
          .select('id, kind, title, body, sport, route, notification_id, sent_at, read_at')
          .eq('user_id', userId)
          .gte('sent_at', since)
          .is('deleted_at', null)
          .order('sent_at', { ascending: false })
      : supabase
          .from('notification_inbox')
          .select('id, kind, title, body, sport, route, notification_id, sent_at, read_at')
          .eq('user_id', userId)
          .gte('sent_at', since)
          .order('sent_at', { ascending: false });
  const [first, prefs] = await Promise.all([
    readInbox(true),
    supabase.from('notification_sport_prefs').select('sport, enabled').eq('user_id', userId),
  ]);
  let inbox = first;
  let canDelete = true;
  if (inbox.error && /deleted_at/i.test(inbox.error.message ?? '')) {
    canDelete = false;
    inbox = await readInbox(false);
  }
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
      canDelete: missing ? false : snapshot.canDelete,
    });
    if (missing) await applyUnreadBadge(0, Notifications);
    return;
  }
  const muted = mutedSports((prefs.data ?? []) as { sport: string; enabled: boolean }[]);
  fetched = (inbox.data ?? []) as InboxRow[];
  const rows = visibleInbox(fetched, muted, new Date());
  const unread = unreadCount(rows);
  emit({ rows, muted, unread, loading: false, loaded: true, error: null, userId, canDelete });
  await applyUnreadBadge(unread, Notifications);
}

export function refreshNotificationInbox(userId?: string | null): Promise<void> {
  // Auth still resolving is not "signed out". Loading as signed out clears
  // the icon badge and then nothing reloads when the session arrives.
  if (readAuthStatus() === 'loading') return Promise.resolve();
  const id = userId === undefined ? readAuthUserId() : userId;
  if (inflight && inflightFor === id) return inflight;
  inflightFor = id;
  inflight = load(id).finally(() => {
    inflight = null;
  });
  return inflight;
}

let watching = false;
/** A tap that arrived before the session was known. Marked once auth resolves. */
let pendingInboxId: string | null = null;

/** One listener set for the process: auth, foreground, and a push arriving. */
function watchInbox(): void {
  if (watching) return;
  watching = true;
  subscribeAuthUser(() => {
    if (pendingInboxId && readAuthStatus() !== 'loading' && readAuthUserId()) {
      const id = pendingInboxId;
      pendingInboxId = null;
      void markReadByInboxId(id);
    }
    void refreshNotificationInbox();
  });
  AppState.addEventListener('change', (next) => {
    if (next === 'active') void refreshNotificationInbox();
  });
  try {
    Notifications.addNotificationReceivedListener(() => {
      void refreshNotificationInbox();
    });
  } catch (err) {
    console.warn('[push] inbox listener unavailable', err);
  }
}

/** The OS tap opened this alert. Mark that inbox row read and refresh the bell. */
export async function markReadByInboxId(inboxId: unknown): Promise<void> {
  if (typeof inboxId !== 'string' || inboxId.length === 0) return;
  if (readAuthStatus() === 'loading') {
    pendingInboxId = inboxId;
    return;
  }
  const userId = readAuthUserId();
  if (!userId) return;
  const readAt = new Date().toISOString();
  const { error } = await supabase
    .from('notification_inbox')
    .update({ read_at: readAt })
    .eq('notification_id', inboxId)
    .eq('user_id', userId);
  await dismissInboxNotifications([inboxId], Notifications);
  if (!error) await refreshNotificationInbox(userId);
}

export function useNotificationInbox(): InboxSnapshot & {
  refresh: () => Promise<void>;
  markRead: (row: InboxRow) => Promise<void>;
  markAllRead: () => Promise<void>;
  dismissVisible: () => Promise<void>;
  deleteRows: (rows: InboxRow[]) => Promise<boolean>;
  setSportEnabled: (sport: string, enabled: boolean) => Promise<void>;
} {
  const [local, setLocal] = useState(snapshot);
  useEffect(() => {
    watchInbox();
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

  /** Hide these rows from the list, the bell and the badge. The row is kept
   *  (deleted_at stamped, read_at too if it was unread). Resolves false and
   *  reloads the list if the write fails, so nothing vanishes that is still
   *  stored as visible. */
  const deleteRows = useCallback(async (targets: InboxRow[]) => {
    const userId = snapshot.userId;
    if (!userId || targets.length === 0 || !snapshot.canDelete) return false;
    const now = new Date().toISOString();
    const ids = new Set(targets.map((r) => r.id));
    fetched = fetched.filter((r) => !ids.has(r.id));
    const rows = visibleInbox(fetched, snapshot.muted, new Date());
    const unread = unreadCount(rows);
    emit({ ...snapshot, rows, unread });
    await applyUnreadBadge(unread, Notifications);
    await dismissInboxNotifications(targets.map((r) => r.notification_id), Notifications);
    const unreadIds = targets.filter((r) => r.read_at == null).map((r) => r.id);
    const readIds = targets.filter((r) => r.read_at != null).map((r) => r.id);
    const writes = [];
    if (unreadIds.length) {
      writes.push(
        supabase
          .from('notification_inbox')
          .update({ deleted_at: now, read_at: now })
          .eq('user_id', userId)
          .in('id', unreadIds),
      );
    }
    if (readIds.length) {
      writes.push(
        supabase
          .from('notification_inbox')
          .update({ deleted_at: now })
          .eq('user_id', userId)
          .in('id', readIds),
      );
    }
    const results = await Promise.all(writes);
    if (results.some((r) => r.error)) {
      void refreshNotificationInbox(userId);
      return false;
    }
    return true;
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

  return { ...local, refresh, markRead, markAllRead, dismissVisible, deleteRows, setSportEnabled };
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
