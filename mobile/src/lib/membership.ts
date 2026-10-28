/**
 * Free / trial / paid, decided on the client from the subscription row.
 *
 * `entitled` is an Apple trial or paid plan — that unlocks the app.
 * `discordPaid` does not. A Whop membership is Discord-only.
 * A receipt that arrives before the webhook has no status yet, so it unlocks
 * the app and does not unlock Discord.
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
  now?: Date;
}): MembershipTier {
  if (!input.billingOn) return 'open';
  const now = input.now ?? new Date();
  const sub = input.subscription;
  if (sub && isEntitled(sub, now) && sub.status === 'trialing') return 'trial';
  if (sub && isEntitled(sub, now) && sub.status === 'active') return 'paid';
  // Entitled, but the row has not landed. Do not treat that as paid.
  if (input.entitled) return 'trial';
  return 'free';
}

/** Record stays open. Everything else waits for a trial or a paid plan. */
export function contentLocked(tier: MembershipTier): boolean {
  return tier === 'free';
}
