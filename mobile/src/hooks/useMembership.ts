import { billingReady } from '@/lib/billingConfig';
import { isEntitled } from '@/lib/billingHelpers';
import { confirmedTrial } from '@/lib/discordJoin';
import { contentLocked, membershipTier, type MembershipTier } from '@/lib/membership';
import { useEntitlement } from './useEntitlement';
import { useSubscription } from './useSubscription';

/**
 * One read of free / trial / paid for the screens that gate on it.
 *
 * While the row is still loading, `hold` is true and nothing is locked yet —
 * a subscriber must not flash the free shell on a cold start. Discord stays
 * locked until the resolved tier is paid.
 */
export function useMembership() {
  const { entitled, loading: accessLoading, access, refresh: refreshAccess } = useEntitlement();
  const { subscription, loading: subLoading, refresh: refreshSub } = useSubscription();
  const billingOn = billingReady();
  const comped = access.source === 'comped';
  const resolved = !billingOn || entitled || (!accessLoading && !subLoading);
  const tier: MembershipTier = membershipTier({
    billingOn,
    entitled: resolved ? entitled : false,
    subscription,
    discordPaid: access.discord_access,
    comped,
  });

  return {
    tier,
    resolved,
    hold: billingOn && !resolved,
    contentLocked: resolved && contentLocked(tier),
    discordPaid: resolved && tier === 'paid',
    /**
     * A loaded `trialing` row whose period is still open. Not the fallback
     * tier: entitled-with-no-row is also reported as `trial`.
     */
    trialConfirmed: confirmedTrial({
      subLoading,
      status: subscription?.status,
      periodEntitled: isEntitled(subscription),
    }),
    subscription,
    entitled: resolved ? entitled : false,
    access,
    refresh: () => Promise.all([refreshAccess(), refreshSub()]).then(() => undefined),
  };
}
