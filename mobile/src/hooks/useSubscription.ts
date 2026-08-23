import { useCallback, useEffect, useState } from 'react';

import { fetchSubscription } from '@/lib/billing';
import { isEntitled, type SubscriptionRow } from '@/lib/billingHelpers';
import { billingReady } from '@/lib/billingConfig';
import { useAuth } from './useAuth';

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

  const [subscription, setSubscription] = useState<SubscriptionRow | null>(null);
  const [loading, setLoading] = useState<boolean>(enabled);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!enabled || !signedIn) {
      setSubscription(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const row = await fetchSubscription();
      setSubscription((row as SubscriptionRow | null) ?? null);
      setError(null);
    } catch (e) {
      // Keep the previous row — see the note above about not paywalling on a blip.
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [enabled, signedIn]);

  useEffect(() => {
    if (authStatus === 'loading') return;
    void load();
  }, [load, authStatus]);

  const entitled = !enabled ? true : isEntitled(subscription);

  return { subscription, entitled, loading, error, refresh: load };
}
