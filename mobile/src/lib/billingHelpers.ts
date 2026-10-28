import {
  DEFAULT_PLAN_KEY,
  EARLY_UNLOCK_PRODUCT_IDS,
  PLANS,
  STORE_PRODUCT_IDS,
  TRIAL_DAYS,
  type Plan,
  type PlanKey,
} from './billingConfig';

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
 * Can be NEGATIVE, and deliberately is: the weekly plan costs about 73% MORE
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

/** "$24.99" / "$149.99" — no trailing cents games, these are real prices. */
export function formatPrice(dollars: number): string {
  return `$${dollars.toFixed(2)}`;
}

/** "$12.50/mo" for the per-month line under a multi-month plan. */
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

/**
 * Shown when Unlock Discord early would purchase the intro product the user
 * is already trialing. StoreKit does not end a trial by buying that same id.
 */
export const SAME_PLAN_PURCHASE_MESSAGE =
  'Ending the trial would buy the same App Store product you are already trialing. That purchase was refused.';

/** Shown when the convert would change tier or open a second subscription. */
export const TIER_SWITCH_MESSAGE =
  'Ending the trial would switch you to a different plan or start a second subscription. That purchase was refused.';

export interface EarlyUnlockTarget {
  ok: true;
  plan: PlanKey;
  productId: string;
  /** The intro id already on the trial. The convert purchase must not be this. */
  replacesProductId: string;
}

export interface EarlyUnlockRefusal {
  ok: false;
  reason: string;
}

/** Same marker order as planForProductId. annual before week before month. */
function tierOfProductId(productId: string): PlanKey | null {
  const id = productId.toLowerCase();
  if (/annual|year/.test(id)) return 'annual';
  if (/week|wk/.test(id)) return 'weekly';
  if (/month/.test(id)) return 'monthly';
  return null;
}

/**
 * The product Unlock Discord early purchases.
 *
 * A monthly trial converts by buying `…premium.monthly.notrial`. An annual
 * trial buys `…premium.annual.notrial`. Those ids have no introductory offer
 * and must share a subscription group with the trial id, so the store
 * replaces that subscription. Weekly is refused: it is a different tier, and
 * weekly has no trial to end. The intro id itself is also refused.
 */
export function earlyUnlockTarget(trialingPlan: PlanKey): EarlyUnlockTarget | EarlyUnlockRefusal {
  const replacesProductId = STORE_PRODUCT_IDS[trialingPlan];
  const productId = EARLY_UNLOCK_PRODUCT_IDS[trialingPlan];
  if (!productId || trialingPlan === 'weekly') {
    return { ok: false, reason: TIER_SWITCH_MESSAGE };
  }
  if (productId === replacesProductId || productId === STORE_PRODUCT_IDS.weekly) {
    return { ok: false, reason: productId === replacesProductId ? SAME_PLAN_PURCHASE_MESSAGE : TIER_SWITCH_MESSAGE };
  }
  if (tierOfProductId(productId) !== trialingPlan) {
    return { ok: false, reason: TIER_SWITCH_MESSAGE };
  }
  return { ok: true, plan: trialingPlan, productId, replacesProductId };
}

/** Charge line on Unlock Discord early. Same tier, that tier's price. */
export function earlyUnlockLine(trialingPlan: PlanKey): string {
  const target = earlyUnlockTarget(trialingPlan);
  if (!target.ok) {
    return 'This trial cannot be ended by switching plans. No invite is shown until a paid plan is active.';
  }
  const convert = planForKey(target.plan);
  return `Ends the ${convert.name} trial. ${formatPrice(convert.price)} today. No invite is shown until that plan is active.`;
}

function planForKey(key: PlanKey): Plan {
  const plan = PLANS.find((p) => p.key === key);
  if (!plan) throw new Error(`Unknown plan: ${key}`);
  return plan;
}

/** The plan the paywall selects on open. */
export function defaultPlan(): Plan {
  return PLANS.find((p) => p.key === DEFAULT_PLAN_KEY) ?? PLANS[0];
}

/**
 * Primary paywall button. Weekly has no trial, so it must not offer one.
 */
export function paywallCta(plan: Plan): string {
  return plan.trialDays > 0 ? `Start ${plan.trialDays}-day free trial` : 'Subscribe';
}

/**
 * Header under the title. Depends on the SELECTED plan: the old global
 * `trialCopy()` promised a 7-day trial while Weekly, which has none, was
 * selected.
 */
export function paywallSubtitle(plan: Plan): string {
  if (plan.trialDays <= 0) return 'Charged today. Cancel anytime.';
  return `${TRIAL_DAYS}-day free trial on Monthly and Annual. Cancel anytime.`;
}

/** Annual per-week equivalent. 149.99/52 = $2.88. Null for the other plans. */
export function formatPerWeek(plan: Plan): string | null {
  if (plan.key !== 'annual') return null;
  return `${formatPrice(plan.price / 52)}/wk`;
}

/** Right-hand price caption on a plan row. */
export function planPriceCaption(plan: Plan): string {
  if (plan.key === 'annual') return `per year · ${formatPerWeek(plan)}`;
  if (plan.key === 'monthly') return 'per month';
  return 'per week';
}

/** Left-hand trial caption on a plan row. */
export function planTrialLine(plan: Plan): string {
  return plan.trialDays > 0 ? `${plan.trialDays}-day free trial` : 'No free trial';
}

export interface PlanStatusCopy {
  badge: 'Free' | 'Trial' | 'Premium';
  line: string;
}

const STATUS_MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** UTC, so a status line does not depend on the phone's timezone. */
function formatStatusDate(iso: string | null, withYear: boolean): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return null;
  const day = `${STATUS_MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
  return withYear ? `${day}, ${d.getUTCFullYear()}` : day;
}

/**
 * Settings plan row. Free, "Free trial ends DATE", or "Annual · renews DATE".
 * A Whop membership does not change this row. The app plan is the Apple
 * subscription.
 */
export function planStatusCopy(
  sub: SubscriptionRow | null | undefined,
  _opts: { discordPaid?: boolean } = {},
  now: Date = new Date(),
): PlanStatusCopy {
  if (sub && isEntitled(sub, now) && sub.status === 'trialing') {
    const when = formatStatusDate(sub.trial_end ?? sub.current_period_end, false);
    return { badge: 'Trial', line: when ? `Free trial ends ${when}` : 'Free trial' };
  }
  if (sub && isEntitled(sub, now) && sub.status === 'active') {
    const planName = PLANS.find((p) => p.key === sub.plan)?.name ?? 'Premium';
    const when = formatStatusDate(sub.current_period_end, true);
    if (sub.cancel_at_period_end) {
      return {
        badge: 'Premium',
        line: when ? `${planName} · ends ${when}` : `${planName} · cancels at period end`,
      };
    }
    return { badge: 'Premium', line: when ? `${planName} · renews ${when}` : planName };
  }
  return { badge: 'Free', line: 'Free plan' };
}

/**
 * The auto-renewal disclosure App Review expects on the paywall, worded for
 * the selected plan. A plan with no trial must not offer one — that is a
 * rejection under 3.1.2, and it is also just untrue. Weekly says there is
 * no free trial and that the charge is today.
 */
export function renewalDisclosure(plan: Plan): string {
  const price = formatPrice(plan.price);
  const term = plan.key === 'weekly' ? 'week' : plan.key === 'annual' ? 'year' : 'month';
  const cancel = 'Cancel anytime in your App Store account settings.';
  if (plan.trialDays <= 0) {
    return `${price} per ${term}, charged today. No free trial. Renews every ${term} until you cancel. ${cancel}`;
  }
  return `${plan.trialDays}-day free trial, then ${price} per ${term}. Renews every ${term} until you cancel. ${cancel}`;
}

export function isPlanKey(value: string): value is PlanKey {
  return PLANS.some((p) => p.key === value);
}
