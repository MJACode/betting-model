import { useCallback, useEffect, useState } from 'react';

import { getDeviceId } from '@/hooks/useDeviceId';
import { useAuth } from '@/hooks/useAuth';
import {
  fetchFeedbackMessages,
  fetchFeedbackThreads,
  fetchFeedbackUnreadCount,
  markFeedbackRead,
  submitFeedback,
} from '@/lib/feedback';
import {
  sortThreads,
  unreadTotal,
  type FeedbackCategory,
  type FeedbackMessage,
  type FeedbackThread,
} from '@/lib/feedbackHelpers';

/**
 * In-app feedback state.
 *
 * Threads and the unread count live in a module store so the Settings badge and
 * the Feedback screen can't disagree: whichever one refreshes last updates both.
 * The store is memory-only (not persisted) — feedback is server state, and a
 * stale cached copy of a conversation is worse than a spinner.
 */
const listeners = new Set<() => void>();

let threads: FeedbackThread[] = [];
let unread = 0;
let loaded = false;

function emit() {
  listeners.forEach((fn) => fn());
}

function setThreads(next: FeedbackThread[]) {
  threads = sortThreads(next);
  unread = unreadTotal(threads);
  loaded = true;
  emit();
}

/** Cheap scalar refresh for the Settings badge — no thread payload. */
export async function refreshFeedbackUnread(): Promise<number> {
  try {
    const deviceId = await getDeviceId();
    const n = await fetchFeedbackUnreadCount(deviceId);
    if (n !== unread) {
      unread = n;
      emit();
    }
    return n;
  } catch {
    // A failed poll must never blank a badge the user is looking at.
    return unread;
  }
}

export function useFeedback() {
  const [, bump] = useState(0);
  const [loading, setLoading] = useState(!loaded);
  const [error, setError] = useState<string | null>(null);
  const { user } = useAuth();

  useEffect(() => {
    const listener = () => bump((n) => n + 1);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const deviceId = await getDeviceId();
      setThreads(await fetchFeedbackThreads(deviceId));
      setError(null);
    } catch (err) {
      console.warn('[feedback] load failed', err);
      setError('load');
    } finally {
      setLoading(false);
    }
  }, []);

  /** Post a message. Returns the thread id so a new conversation can be opened. */
  const submit = useCallback(
    async (message: string, category: FeedbackCategory, threadId?: number | null) => {
      const deviceId = await getDeviceId();
      const id = await submitFeedback({
        deviceId,
        message,
        category,
        threadId: threadId ?? null,
        userId: user?.id ?? null,
      });
      // Re-read rather than patching locally: the server owns subject
      // derivation, status and timestamps.
      try {
        setThreads(await fetchFeedbackThreads(deviceId));
      } catch {
        /* the message is sent; a failed refresh is cosmetic */
      }
      return id;
    },
    [user?.id],
  );

  const markRead = useCallback(async (threadId: number) => {
    try {
      const deviceId = await getDeviceId();
      await markFeedbackRead(deviceId, threadId);
      setThreads(await fetchFeedbackThreads(deviceId));
    } catch (err) {
      console.warn('[feedback] mark read failed', err);
    }
  }, []);

  const loadMessages = useCallback(async (threadId: number): Promise<FeedbackMessage[]> => {
    const deviceId = await getDeviceId();
    return fetchFeedbackMessages(deviceId, threadId);
  }, []);

  return { threads, unread, loading, error, loaded, refresh, submit, markRead, loadMessages };
}

/** Badge-only consumer (Settings). Refreshes the scalar on mount. */
export function useFeedbackUnread() {
  const [, bump] = useState(0);

  useEffect(() => {
    const listener = () => bump((n) => n + 1);
    listeners.add(listener);
    void refreshFeedbackUnread();
    return () => {
      listeners.delete(listener);
    };
  }, []);

  return unread;
}
