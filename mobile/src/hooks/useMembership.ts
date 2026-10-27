import { billingReady } from '@/lib/billingConfig';
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
  const resolved = !billingOn || entitled || (!accessLoading && !subLoading);
  const tier: MembershipTier = membershipTier({
    billingOn,
    entitled: resolved ? entitled : false,
    subscription,
    discordPaid: access.discord_access,
  });

  return {
    tier,
    resolved,
    hold: billingOn && !resolved,
    contentLocked: resolved && contentLocked(tier),
    discordPaid: resolved && tier === 'paid',
    subscription,
    entitled: resolved ? entitled : false,
    access,
    refresh: () => Promise.all([refreshAccess(), refreshSub()]).then(() => undefined),
  };
}
