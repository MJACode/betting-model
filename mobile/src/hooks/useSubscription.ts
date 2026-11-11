import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { fetchSubscription } from '@/lib/billing';
import { isEntitled, type SubscriptionRow } from '@/lib/billingHelpers';
import { billingReady } from '@/lib/billingConfig';
import { errorText, isAbortError } from '@/lib/errors';
import {
  subscriptionFetchStillCurrent,
  type SubscriptionFetchTicket,
} from '@/lib/subscriptionFetch';
import { useAuth } from './useAuth';

/**
 * One subscription row for every mounted reader.
 *
 * Settings home and a Settings section are both mounted, and each used to
 * keep its own copy. A refresh in the section (Unlock Discord early) then
 * left the home tile on the old plan. The row lives here, like useAccess,
 * so one fetch serves every reader and a refresh updates all of them.
 *
 * The cache is the user id, not "signed in". A fetch that finishes after
 * sign-out is dropped, so the next account is not served the previous row.
 */
interface SubscriptionSnapshot {
  subscription: SubscriptionRow | null;
  loading: boolean;
  error: string | null;
}

const listeners = new Set<(s: SubscriptionSnapshot) => void>();
let snapshot: SubscriptionSnapshot = {
  subscription: null,
  loading: billingReady(),
  error: null,
};
/** User id of the last successful read. undefined = never read. */
let loadedFor: string | null | undefined;
let currentUserId: string | null = null;
let generation = 0;
let inFlight: Promise<void> | null = null;
let foregroundBound = false;

function publish(next: Partial<SubscriptionSnapshot>) {
  snapshot = { ...snapshot, ...next };
  listeners.forEach((fn) => fn(snapshot));
}

function ticketNow(): SubscriptionFetchTicket {
  return { generation, userId: currentUserId };
}

/** Bump the generation when the account changes, before any await. */
function noteUser(userId: string | null) {
  if (userId === currentUserId) return;
  generation += 1;
  currentUserId = userId;
  loadedFor = undefined;
}

async function loadSubscription(userId: string | null, force = false): Promise<void> {
  noteUser(userId);
  if (!billingReady() || !userId) {
    loadedFor = null;
    publish({ subscription: null, loading: false, error: null });
    return;
  }
  const asked = ticketNow();
  if (inFlight) {
    await inFlight;
    if (!subscriptionFetchStillCurrent(asked, ticketNow())) return;
    if (!force) return;
  }
  if (!subscriptionFetchStillCurrent(asked, ticketNow())) return;
  if (!force && loadedFor === userId) return;
  // Claim the slot before the first await so a second reader joins this read.
  let finish!: () => void;
  const run = new Promise<void>((resolve) => {
    finish = resolve;
  });
  inFlight = run;
  const started = ticketNow();
  publish({ loading: true });
  try {
    const row = await fetchSubscription();
    if (!subscriptionFetchStillCurrent(started, ticketNow())) {
      publish({ loading: false });
      return;
    }
    loadedFor = userId;
    publish({
      subscription: (row as SubscriptionRow | null) ?? null,
      error: null,
      loading: false,
    });
  } catch (e) {
    if (!subscriptionFetchStillCurrent(started, ticketNow())) {
      publish({ loading: false });
      return;
    }
    // Keep the previous row — a blip must not drop a paying member.
    if (!isAbortError(e)) publish({ error: errorText(e), loading: false });
    else publish({ loading: false });
  } finally {
    if (inFlight === run) inFlight = null;
    finish();
  }
}

function bindForegroundRefresh() {
  if (foregroundBound) return;
  foregroundBound = true;
  AppState.addEventListener('change', (next) => {
    if (next !== 'active' || !currentUserId) return;
    void loadSubscription(currentUserId, true);
  });
}

/**
 * The signed-in user's subscription + whether they're entitled.
 *
 * Two behaviours worth knowing:
 *
 *  - When billing is off, `entitled` is TRUE. Everything is free today, so the
 *    gate must be open — a flag that's off must never lock users out of what
 *    they already have. This is why callers can use `entitled` unconditionally
 *    without also checking the flag.
 *
 *  - Fetch failures leave `entitled` at its last known value rather than
 *    dropping it to false. A network blip should not paywall a paying user
 *    mid-slate; the server-side check is the real boundary anyway.
 */
export interface UseSubscription {
  subscription: SubscriptionRow | null;
  /** Access to paid features. True whenever billing is disabled. */
  entitled: boolean;
  loading: boolean;
  error: string | null;
  /** Re-read after checkout returns (entitlement lands via webhook). */
  refresh: () => Promise<void>;
}

export function useSubscription(): UseSubscription {
  const { signedIn, status: authStatus, user } = useAuth();
  const enabled = billingReady();
  const userId = signedIn ? (user?.id ?? null) : null;
  const [snap, setSnap] = useState<SubscriptionSnapshot>(snapshot);

  useEffect(() => {
    bindForegroundRefresh();
    const listener = (next: SubscriptionSnapshot) => setSnap(next);
    listeners.add(listener);
    setSnap(snapshot);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (authStatus === 'loading') return;
    void loadSubscription(userId);
  }, [authStatus, userId]);

  const refresh = useCallback(() => loadSubscription(userId, true), [userId]);
  const entitled = !enabled ? true : isEntitled(snap.subscription);

  return {
    subscription: snap.subscription,
    entitled,
    loading: enabled ? snap.loading : false,
    error: snap.error,
    refresh,
  };
}
