import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';
import * as Notifications from 'expo-notifications';

import { getDeviceId } from '@/hooks/useDeviceId';
import {
  fetchInbox,
  fetchInboxUnreadCount,
  markInboxAllRead,
  markInboxRead,
} from '@/lib/notificationInbox';
import {
  unreadOf,
  withAllRead,
  withRead,
  type InboxItem,
} from '@/lib/notificationInboxHelpers';

/**
 * Inbox state, in one module store so the header bell on every tab and the
 * inbox screen cannot disagree: whichever refreshes last updates both. Memory
 * only; the server is the record of what is read.
 */
const listeners = new Set<() => void>();

let items: InboxItem[] = [];
let unread = 0;
let loaded = false;

function emit() {
  listeners.forEach((fn) => fn());
}

function setItems(next: InboxItem[]) {
  items = next;
  unread = unreadOf(next);
  loaded = true;
  emit();
}

/** The bell's count. A failed poll keeps the badge the reader is looking at. */
export async function refreshInboxUnread(): Promise<number> {
  try {
    const n = await fetchInboxUnreadCount(await getDeviceId());
    if (n !== unread) {
      unread = n;
      emit();
    }
    return n;
  } catch {
    return unread;
  }
}

/**
 * Clear one. Optimistic: the row un-bolds at once, and a failed write is
 * corrected by the next refresh rather than flashing back.
 */
export async function markNotificationRead(id: number): Promise<void> {
  const known = items.find((i) => i.id === id);
  if (known && !known.is_read) {
    setItems(withRead(items, id));
  } else if (!known && unread > 0) {
    // Tapped from the lock screen before the inbox was ever loaded.
    unread -= 1;
    emit();
  }
  try {
    await markInboxRead(await getDeviceId(), id);
  } catch (err) {
    console.warn('[inbox] mark read failed', err);
  }
  void refreshInboxUnread();
}

/** Drop the in-memory copy (account deletion). */
export function clearInboxForAccountDeletion(): void {
  items = [];
  unread = 0;
  loaded = false;
  emit();
}

function useStore() {
  const [, bump] = useState(0);
  useEffect(() => {
    const listener = () => bump((n) => n + 1);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);
}

/**
 * The bell's count. Refreshes on mount, whenever the app comes to the
 * foreground, and when a push arrives while the app is open, so a missed
 * notification shows on the badge without a pull-to-refresh.
 */
export function useInboxUnread(): number {
  useStore();
  useEffect(() => {
    void refreshInboxUnread();
    const appSub = AppState.addEventListener('change', (s) => {
      if (s === 'active') void refreshInboxUnread();
    });
    let pushSub: Notifications.Subscription | undefined;
    try {
      // The worker writes the inbox row before it sends, so the row is there
      // by the time the push lands.
      pushSub = Notifications.addNotificationReceivedListener(() => {
        void refreshInboxUnread();
      });
    } catch {
      // A build without expo-notifications: the badge still refreshes on focus.
    }
    return () => {
      appSub.remove();
      pushSub?.remove();
    };
  }, []);
  return unread;
}

export function useNotificationInbox() {
  useStore();
  const [loading, setLoading] = useState(!loaded);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await fetchInbox(await getDeviceId()));
      setError(null);
    } catch (err) {
      console.warn('[inbox] load failed', err);
      setError('Couldn’t load your notifications. Pull to try again.');
    } finally {
      setLoading(false);
    }
  }, []);

  const markAllRead = useCallback(async () => {
    const before = items;
    setItems(withAllRead(items));
    try {
      await markInboxAllRead(await getDeviceId());
      return true;
    } catch (err) {
      console.warn('[inbox] read all failed', err);
      setItems(before);
      return false;
    }
  }, []);

  return {
    items,
    unread,
    loaded,
    loading,
    error,
    refresh,
    markRead: markNotificationRead,
    markAllRead,
  };
}
