import { useCallback, useEffect, useState } from 'react';

import { fetchSubscription } from '@/lib/billing';
import { isEntitled, type SubscriptionRow } from '@/lib/billingHelpers';
import { billingReady } from '@/lib/billingConfig';
import { errorText, isAbortError } from '@/lib/errors';
import { useAuth } from './useAuth';

/**
 * One subscription row for every mounted reader.
 *
 * Settings home and a Settings section are both mounted, and each used to
 * keep its own copy. A refresh in the section (Unlock Discord early) then
 * left the home tile on the old plan. The row lives here, like useAccess,
 * so one fetch serves every reader and a refresh updates all of them.
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
/** The signed-in flag the last successful read was for. null = never read. */
let loadedFor: boolean | null = null;
let inFlight: Promise<void> | null = null;

function publish(next: Partial<SubscriptionSnapshot>) {
  snapshot = { ...snapshot, ...next };
  listeners.forEach((fn) => fn(snapshot));
}

async function loadSubscription(signedIn: boolean, force = false): Promise<void> {
  if (!billingReady() || !signedIn) {
    loadedFor = signedIn;
    publish({ subscription: null, loading: false, error: null });
    return;
  }
  if (inFlight) {
    await inFlight;
    if (!force) return;
  }
  if (!force && loadedFor === signedIn) return;
  // Claim the slot before the first await so a second reader joins this read.
  let finish!: () => void;
  const run = new Promise<void>((resolve) => {
    finish = resolve;
  });
  inFlight = run;
  publish({ loading: true });
  try {
    const row = await fetchSubscription();
    loadedFor = signedIn;
    publish({
      subscription: (row as SubscriptionRow | null) ?? null,
      error: null,
      loading: false,
    });
  } catch (e) {
    // Keep the previous row — a blip must not drop a paying member.
    if (!isAbortError(e)) publish({ error: errorText(e), loading: false });
    else publish({ loading: false });
  } finally {
    if (inFlight === run) inFlight = null;
    finish();
  }
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
  const { signedIn, status: authStatus } = useAuth();
  const enabled = billingReady();
  const [snap, setSnap] = useState<SubscriptionSnapshot>(snapshot);

  useEffect(() => {
    const listener = (next: SubscriptionSnapshot) => setSnap(next);
    listeners.add(listener);
    setSnap(snapshot);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (authStatus === 'loading') return;
    void loadSubscription(signedIn);
  }, [authStatus, signedIn]);

  const refresh = useCallback(() => loadSubscription(signedIn, true), [signedIn]);
  const entitled = !enabled ? true : isEntitled(snap.subscription);

  return {
    subscription: snap.subscription,
    entitled,
    loading: enabled ? snap.loading : false,
    error: snap.error,
    refresh,
  };
}
