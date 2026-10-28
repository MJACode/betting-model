import { useCallback } from 'react';

import { billingReady } from '@/lib/billingConfig';
import { discordLinkReady } from '@/lib/discordConfig';
import type { AccessRow, AccessSource } from '@/lib/discord';
import { useAccess } from './useAccess';
import { useSubscription } from './useSubscription';

/**
 * THE GATE. One question — "can this person see paid signals?" — answered once.
 *
 * The database is the arbiter. `public.my_access().entitled` is the Apple
 * subscription (trialing/active, period open). A Whop membership is
 * `discord_access` and does not unlock the app, so this hook does not OR it in.
 * The receipt-validated client signal from a just-completed purchase is folded
 * in on top, so a user who has paid this second is not staring at a lock while
 * the RevenueCat webhook is still in flight.
 *
 * Use this, not a screen-local read of `discord_access`, to decide access.
 * `useSubscription` still describes the App Store row. The Settings
 * subscription card is that description, not a second gate.
 */
export interface UseEntitlement {
  /** Can this user see paid signals? */
  entitled: boolean;
  /** Where it comes from — drives the copy, never the decision. */
  source: AccessSource;
  access: AccessRow;
  loading: boolean;
  /** Re-read after checkout, a link, or a pull-to-refresh. */
  refresh: () => Promise<void>;
}

export function useEntitlement(): UseEntitlement {
  const { access, entitled: accessEntitled, loading, refresh } = useAccess();
  const { subscription, entitled: subEntitled, refresh: refreshSub } =
    useSubscription();

  const gated = billingReady() || discordLinkReady();

  const refreshBoth = useCallback(async () => {
    await Promise.all([refresh(), refreshSub()]);
  }, [refresh, refreshSub]);

  // Both hooks return true when their own feature is dark, so an unconditional
  // OR would be wrong the moment one flag is on and the other is off. The gate
  // is open only when NOTHING gates.
  if (!gated) {
    return {
      entitled: true,
      source: 'none',
      access,
      loading: false,
      refresh: refreshBoth,
    };
  }

  // `subEntitled` covers the window between a completed purchase and the
  // webhook landing — the subscription row is readable by the user themselves
  // before my_access() has anything to report.
  const entitled = accessEntitled || (billingReady() && subEntitled);
  const source: AccessSource =
    access.source !== 'none'
      ? access.source
      : subscription && subEntitled
        ? 'app'
        : 'none';

  return { entitled, source, access, loading, refresh: refreshBoth };
}
