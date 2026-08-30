import { useCallback } from 'react';

import { billingReady } from '@/lib/billingConfig';
import { discordLinkReady } from '@/lib/discordConfig';
import type { AccessRow, AccessSource } from '@/lib/discord';
import { useAccess } from './useAccess';
import { useSubscription } from './useSubscription';

/**
 * THE GATE. One question — "can this person see paid signals?" — answered once,
 * so no screen has to remember that a Discord membership counts too.
 *
 * Use this, not `useSubscription().entitled`, anywhere access is being decided.
 * `useSubscription` still exists and is still correct, but it only knows about
 * the `subscriptions` table: a member who paid through Whop has no row there,
 * and gating on it alone would charge them twice for the thing they already
 * bought. That is the exact failure this hook exists to prevent, and it is why
 * the Settings subscription card is the only remaining caller of the narrower
 * hook — it is describing the app subscription specifically, not deciding
 * access.
 *
 * The database is the arbiter (`public.my_access()` ORs both sources). The
 * receipt-validated client signal from a just-completed purchase is folded in
 * on top, so a user who has paid this second is not staring at a lock while
 * the RevenueCat webhook is still in flight.
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
