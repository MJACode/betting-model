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

export type BillingRail = 'iap' | 'stripe';

/**
 * Which payment rail the paywall uses.
 *
 * DEFAULT IS IAP (App Store / Play Billing via RevenueCat), decided 2026-08-22:
 * Stripe lists "sports forecasting or odds making" as a restricted business
 * (default outcome: decline or account closure), and the other mainstream card
 * processors carry the same category rules — Lemon Squeezy prohibits gambling
 * outright, Paddle's AUP is equivalent. Apple/Google have no such objection
 * (the picks-app category is full of precedents), charge 15% at this revenue
 * size, and can't freeze funds mid-season. The Stripe path stays built and
 * dark as the fallback if written approval ever arrives and the ~12pp fee gap
 * becomes worth the platform risk.
 *
 * Env-overridable so a build can flip rails without a code change.
 */
export const BILLING_RAIL: BillingRail =
  (process.env.EXPO_PUBLIC_BILLING_RAIL ?? 'iap').toLowerCase() === 'stripe'
    ? 'stripe'
    : 'iap';

/**
 * RevenueCat PUBLIC SDK keys (safe to embed — they can only be used to make
 * purchases, not read the account). Per-platform; from RevenueCat → Project
 * Settings → API keys. Empty until activation.
 */
export const REVENUECAT_IOS_KEY = process.env.EXPO_PUBLIC_REVENUECAT_IOS_KEY ?? '';
export const REVENUECAT_ANDROID_KEY =
  process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_KEY ?? '';

/** Billing is only meaningful once users can have accounts. */
export function billingReady(): boolean {
  return BILLING_ENABLED && AUTH_ENABLED;
}

export type PlanKey = 'weekly' | 'monthly' | 'annual';

export interface Plan {
  key: PlanKey;
  /** Shown on the plan card. */
  name: string;
  /** Total charged per term, in dollars. Must match the store product exactly. */
  price: number;
  /**
   * Billing term in months — drives the per-month math. Weekly is 1/4.345 of a
   * month (52 weeks / 12), not 1/4: a "monthly equivalent" built on four weeks
   * understates a weekly plan's real cost by 8%, which is the direction that
   * flatters us and would be a false comparison on the paywall.
   */
  months: number;
  /** Short line under the name. */
  blurb: string;
  /** Marketing badge, e.g. "Best value". */
  badge?: string;
  /**
   * Free-trial length for THIS plan. Weekly gets none on purpose: a 7-day
   * trial on a 7-day term is a free week that renews into another free week
   * for anyone willing to cancel and resubscribe.
   */
  trialDays: number;
}

/**
 * The ladder — Weekly / Monthly / Annual, set 2026-08-30 to mirror the layout
 * Matt asked for.
 *
 * These numbers are DISPLAY ONLY. The store (App Store Connect) is the source
 * of truth for what is actually charged, and the paywall prefers the store's
 * own localized price string whenever it can fetch one; these are the fallback
 * for the moment before that arrives. If you change a price in App Store
 * Connect, change it here too or the fallback quotes a number the user is not
 * charged.
 */
export const PLANS: readonly Plan[] = [
  {
    key: 'weekly',
    name: 'Weekly',
    price: 9.99,
    months: 12 / 52,
    blurb: 'Try it for a week.',
    trialDays: 0,
  },
  {
    key: 'monthly',
    name: 'Monthly',
    price: 29.99,
    months: 1,
    blurb: 'Cancel anytime.',
    badge: 'Most popular',
    trialDays: 7,
  },
  {
    key: 'annual',
    name: 'Annual',
    price: 199.99,
    months: 12,
    blurb: 'Every sport, all year.',
    badge: 'Best value',
    trialDays: 7,
  },
] as const;

/**
 * Headline free-trial length, used in the paywall's subtitle. Per-plan lengths
 * live on the plans themselves (weekly has none) — this is the longest one
 * offered, which is what the marketing line is about.
 */
export const TRIAL_DAYS = 7;

/** Where Stripe Checkout sends the browser back to. */
export const BILLING_RETURN_URL = 'signalbase://billing-return';

export function planFor(key: PlanKey): Plan {
  const plan = PLANS.find((p) => p.key === key);
  if (!plan) throw new Error(`Unknown plan: ${key}`);
  return plan;
}
