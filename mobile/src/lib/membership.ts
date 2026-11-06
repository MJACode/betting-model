/**
 * Free / trial / paid, decided on the client from the subscription row.
 *
 * `entitled` unlocks the app: a RevenueCat trial or paid plan, a comped
 * grant, or an app_review grant. `discordPaid` (Whop) does not.
 * A receipt that arrives before the webhook has no status yet, so it unlocks
 * the app and does not unlock Discord. `comped` does unlock Discord.
 *
 * Pure: no React, no react-native. verify_billing.ts imports this.
 */

import { isEntitled, type SubscriptionRow } from './billingHelpers';

export type MembershipTier = 'open' | 'free' | 'trial' | 'paid';

export function membershipTier(input: {
  /** False while billing is dark — the app stays open. */
  billingOn: boolean;
  entitled: boolean;
  subscription: SubscriptionRow | null | undefined;
  /** Matched Whop membership. It does not change this tier. */
  discordPaid?: boolean;
  /** Active comped grant. Unlocks Discord. An app_review grant does not. */
  comped?: boolean;
  now?: Date;
}): MembershipTier {
  if (!input.billingOn) return 'open';
  const now = input.now ?? new Date();
  const sub = input.subscription;
  // Comped is paid for Discord even when a trial row is also present.
  if (input.comped) return 'paid';
  if (sub && isEntitled(sub, now) && sub.status === 'trialing') return 'trial';
  if (sub && isEntitled(sub, now) && sub.status === 'active') return 'paid';
  // Entitled, but the row has not landed. Do not treat that as paid.
  if (input.entitled) return 'trial';
  return 'free';
}

/**
 * App premium. RevenueCat signals (the subscriptions row, or CustomerInfo
 * while the webhook is in flight) OR the parsed my_access entitled flag,
 * which already includes an active comped or app_review grant and already
 * rejects a Whop-only row. Pass the parsed flag, not the raw RPC boolean.
 */
export function isAppPremium(input: {
  accessEntitled: boolean;
  subscription?: SubscriptionRow | null;
  rcSignals?: boolean;
  now?: Date;
}): boolean {
  return (
    input.accessEntitled ||
    isEntitled(input.subscription, input.now) ||
    input.rcSignals === true
  );
}

/** Record stays open. Everything else waits for a trial or a paid plan. */
export function contentLocked(tier: MembershipTier): boolean {
  return tier === 'free';
}
