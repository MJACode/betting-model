import { PLANS, TRIAL_DAYS, type Plan, type PlanKey } from './billingConfig';

/**
 * Pure billing helpers — no React, no react-native, no Supabase, so
 * scripts/verify_billing.ts can import them. Same split as authHelpers.ts.
 */

/** Stripe subscription statuses that grant access. */
const ENTITLING_STATUSES = new Set(['trialing', 'active']);

export interface SubscriptionRow {
  status: string;
  plan: string | null;
  current_period_end: string | null;
  trial_end: string | null;
  cancel_at_period_end: boolean;
}

/**
 * Does this subscription grant access right now?
 *
 * Both halves matter. `past_due` and `canceled` obviously don't entitle, but an
 * `active` row whose period has already ended doesn't either — that happens
 * when a webhook is missed or delayed, and trusting status alone would hand out
 * free access indefinitely.
 *
 * A null period end is treated as entitling: Stripe always sets one on a real
 * subscription, so null means we wrote the row before the webhook filled it in,
 * and locking a just-paid user out is the worse failure.
 */
export function isEntitled(
  sub: SubscriptionRow | null | undefined,
  now: Date = new Date(),
): boolean {
  if (!sub) return false;
  if (!ENTITLING_STATUSES.has(sub.status)) return false;
  if (!sub.current_period_end) return true;
  const end = Date.parse(sub.current_period_end);
  if (Number.isNaN(end)) return true;
  return end > now.getTime();
}

/** Effective monthly cost of a plan. */
export function perMonth(plan: Plan): number {
  return plan.price / plan.months;
}

/**
 * Percent saved versus paying monthly, rounded to a whole number.
 *
 * Can be NEGATIVE, and deliberately is: the weekly plan costs about 44% MORE
 * per month than the monthly one, and the honest number says so. The paywall
 * shows the badge only when this is positive, so a worse-value plan simply
 * carries no badge rather than a fabricated one.
 */
export function savingsPct(plan: Plan, monthly: Plan): number {
  if (plan.key === monthly.key) return 0;
  const full = monthly.price * plan.months;
  if (full <= 0) return 0;
  return Math.round(((full - plan.price) / full) * 100);
}

/** "$29.99" / "$199.99" — no trailing cents games, these are real prices. */
export function formatPrice(dollars: number): string {
  return `$${dollars.toFixed(2)}`;
}

/** "$16.67/mo" for the per-month line under a multi-month plan. */
export function formatPerMonth(plan: Plan): string {
  return `${formatPrice(perMonth(plan))}/mo`;
}

/** The monthly plan, used as the comparison baseline. */
export function monthlyPlan(): Plan {
  const m = PLANS.find((p) => p.key === 'monthly');
  if (!m) throw new Error('No monthly plan configured');
  return m;
}

/** Whole days left in a trial; 0 once it's over or if there isn't one. */
export function trialDaysLeft(
  sub: SubscriptionRow | null | undefined,
  now: Date = new Date(),
): number {
  if (!sub?.trial_end || sub.status !== 'trialing') return 0;
  const end = Date.parse(sub.trial_end);
  if (Number.isNaN(end)) return 0;
  const ms = end - now.getTime();
  if (ms <= 0) return 0;
  return Math.ceil(ms / 86_400_000);
}

/**
 * One line describing the subscription for the Settings card. Deliberately
 * states the cancellation date when one is pending — a user who cancelled
 * should never be left wondering whether they still have access.
 */
export function describeSubscription(
  sub: SubscriptionRow | null | undefined,
  now: Date = new Date(),
): string {
  if (!sub || !isEntitled(sub, now)) {
    if (sub?.status === 'past_due') return 'Payment failed — update your card to keep access.';
    if (sub?.status === 'canceled') return 'Your subscription has ended.';
    return 'No active subscription.';
  }

  const planName = PLANS.find((p) => p.key === sub.plan)?.name ?? 'Subscription';
  const days = trialDaysLeft(sub, now);
  if (days > 0) {
    return `${planName} — free trial, ${days} day${days === 1 ? '' : 's'} left.`;
  }

  const end = sub.current_period_end ? new Date(sub.current_period_end) : null;
  const when = end
    ? end.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
    : null;

  if (sub.cancel_at_period_end) {
    return when ? `${planName} — ends ${when}.` : `${planName} — cancels at period end.`;
  }
  return when ? `${planName} — renews ${when}.` : `${planName} — active.`;
}

/** Marketing line for the paywall header. */
export function trialCopy(): string {
  return `${TRIAL_DAYS}-day free trial, then your plan. Cancel anytime.`;
}

/**
 * The auto-renewal disclosure App Review expects on the paywall, worded for
 * the selected plan. A plan with no trial must not claim one — that is a
 * rejection under 3.1.2, and it is also just untrue.
 */
export function renewalDisclosure(plan: Plan): string {
  const price = formatPrice(plan.price);
  const term = plan.key === 'weekly' ? 'week' : plan.key === 'annual' ? 'year' : 'month';
  const base =
    `${price} per ${term}, automatically renewed until cancelled. ` +
    'Cancel anytime in your App Store account settings.';
  return plan.trialDays > 0
    ? `${plan.trialDays}-day free trial, then ${base}`
    : base;
}

export function isPlanKey(value: string): value is PlanKey {
  return PLANS.some((p) => p.key === value);
}
