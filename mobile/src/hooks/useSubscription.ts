import { useCallback, useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { fetchSubscription } from '@/lib/billing';
import { isEntitled, type SubscriptionRow } from '@/lib/billingHelpers';
import { billingReady } from '@/lib/billingConfig';
import { errorText, isAbortError } from '@/lib/errors';
import { createSubscriptionStore, type SubscriptionSnapshot } from '@/lib/subscriptionFetch';
import { useAuth } from './useAuth';

/**
 * One subscription row for every mounted reader.
 *
 * Settings home and a Settings section are both mounted, and each used to
 * keep its own copy. A refresh in the section (Unlock Discord early) then
 * left the home tile on the old plan. The row lives in lib/subscriptionStore,
 * so one fetch serves every reader and a refresh updates all of them.
 *
 * The cache is the user id, not "signed in". A fetch that finishes after
 * sign-out is dropped, and the next account still loads its own row.
 */
const listeners = new Set<(s: SubscriptionSnapshot<SubscriptionRow>) => void>();
let foregroundBound = false;

const store = createSubscriptionStore<SubscriptionRow>({
  fetchRow: () => fetchSubscription() as Promise<SubscriptionRow | null>,
  billingOn: billingReady,
  isAbort: isAbortError,
  errorText,
  onChange: (next) => listeners.forEach((fn) => fn(next)),
});

function bindForegroundRefresh() {
  if (foregroundBound) return;
  foregroundBound = true;
  AppState.addEventListener('change', (next) => {
    const id = store.currentUserId();
    if (next !== 'active' || !id) return;
    void store.load(id, true);
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
  // A signed-in session can render one frame before `user` is on it. Treating
  // that as signed-out would clear the row and bump the generation.
  const userPending = signedIn && !user?.id;
  const userId = userPending ? null : signedIn ? (user?.id ?? null) : null;
  const [snap, setSnap] = useState<SubscriptionSnapshot<SubscriptionRow>>(store.get());

  useEffect(() => {
    bindForegroundRefresh();
    const listener = (next: SubscriptionSnapshot<SubscriptionRow>) => setSnap(next);
    listeners.add(listener);
    setSnap(store.get());
    return () => {
      listeners.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (authStatus === 'loading' || userPending) return;
    void store.load(userId);
  }, [authStatus, userId, userPending]);

  const refresh = useCallback(() => store.load(userId, true), [userId]);
  const entitled = !enabled ? true : isEntitled(snap.subscription);

  return {
    subscription: snap.subscription,
    entitled,
    loading: enabled ? snap.loading : false,
    error: snap.error,
    refresh,
  };
}
