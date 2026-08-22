/**
 * Subscription plans + the billing feature flag.
 *
 * ============================================================================
 * BILLING IS BUILT BUT NOT ACTIVE. `BILLING_ENABLED` is the kill switch.
 * ============================================================================
 *
 * While it is `false` no paywall renders, no plan is offered, and nothing is
 * gated — the app behaves exactly as it does today, with every signal visible.
 *
 * Billing DEPENDS ON AUTH. A subscription belongs to an account, not a device:
 * a device UUID is lost on reinstall, can't be recovered by the user, and can't
 * follow them to a second phone. So `AUTH_ENABLED` must be true before
 * `BILLING_ENABLED` does anything useful — `billingReady()` enforces that
 * rather than leaving it to be discovered in production.
 *
 * Activation runbook: mobile/docs/BILLING.md
 */

import { AUTH_ENABLED } from './authConfig';

/** Master switch for the paywall. Overridable via EXPO_PUBLIC_BILLING_ENABLED. */
export const BILLING_ENABLED: boolean =
  (process.env.EXPO_PUBLIC_BILLING_ENABLED ?? 'false').toLowerCase() === 'true';

/** Billing is only meaningful once users can have accounts. */
export function billingReady(): boolean {
  return BILLING_ENABLED && AUTH_ENABLED;
}

export type PlanKey = 'monthly' | 'semiannual' | 'annual';

export interface Plan {
  key: PlanKey;
  /** Shown on the plan card. */
  name: string;
  /** Total charged per term, in dollars. Must match the Stripe Price exactly. */
  price: number;
  /** Billing term in months — drives the per-month math. */
  months: number;
  /** Short line under the name. */
  blurb: string;
  /** Marketing badge, e.g. "Best value". */
  badge?: string;
}

/**
 * The ladder. These numbers are DISPLAY ONLY — Stripe is the source of truth
 * for what's actually charged, and the price id is chosen server-side in the
 * stripe-checkout function so a client can't check out against a price of its
 * own choosing. If you change a price in Stripe, change it here too or the
 * paywall will quote a number the user isn't charged.
 */
export const PLANS: readonly Plan[] = [
  {
    key: 'monthly',
    name: 'Monthly',
    price: 29.99,
    months: 1,
    blurb: 'Cancel anytime.',
  },
  {
    key: 'semiannual',
    name: 'Season Pass',
    price: 129.99,
    months: 6,
    blurb: 'Six months — covers a full season.',
    badge: 'Most popular',
  },
  {
    key: 'annual',
    name: 'Annual',
    price: 199.99,
    months: 12,
    blurb: 'Every sport, all year.',
    badge: 'Best value',
  },
] as const;

/** Free-trial length in days. Must match STRIPE_TRIAL_DAYS on the server. */
export const TRIAL_DAYS = 7;

/** Where Stripe Checkout sends the browser back to. */
export const BILLING_RETURN_URL = 'signalbase://billing-return';

export function planFor(key: PlanKey): Plan {
  const plan = PLANS.find((p) => p.key === key);
  if (!plan) throw new Error(`Unknown plan: ${key}`);
  return plan;
}
