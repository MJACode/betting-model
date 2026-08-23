import { formatPrice } from './billingHelpers';
import type { Plan, PlanKey } from './billingConfig';

/**
 * Pure IAP helpers — no react-native, no react-native-purchases imports (the
 * types below are structural on purpose), so scripts/verify_billing.ts can load
 * them. Same split as authHelpers / billingHelpers.
 */

/**
 * The RevenueCat entitlement identifier. Must match the entitlement created in
 * the RevenueCat dashboard exactly — see docs/BILLING.md.
 */
export const REVENUECAT_ENTITLEMENT_ID = 'signals';

/** The slice of a RevenueCat package the helpers actually read. */
export interface MinimalPackage {
  /** RevenueCat package type: MONTHLY | SIX_MONTH | ANNUAL | CUSTOM | … */
  packageType: string;
  product: {
    /** Store product id, e.g. com.mja.bettingpicks.sub.annual */
    identifier: string;
    /** Localized display price from the store, e.g. "$199.99". */
    priceString: string;
  };
}

/** The slice of RevenueCat CustomerInfo the helpers read. */
export interface MinimalCustomerInfo {
  entitlements: { active: Record<string, unknown> };
  managementURL?: string | null;
}

const PACKAGE_TYPE_TO_PLAN: Record<string, PlanKey> = {
  MONTHLY: 'monthly',
  SIX_MONTH: 'semiannual',
  ANNUAL: 'annual',
};

export function planForPackageType(packageType: string): PlanKey | null {
  return PACKAGE_TYPE_TO_PLAN[packageType] ?? null;
}

/**
 * Fallback mapping from a store product id to a plan, for products attached as
 * CUSTOM packages or arriving via webhook without package context.
 *
 * ORDER MATTERS: the six-month markers must be checked before 'month', because
 * ids like "six_month" and "6month" contain the substring 'month' and would
 * otherwise resolve to the monthly plan. The RevenueCat webhook carries the
 * same heuristic — keep the two in sync.
 */
export function planForProductId(productId: string): PlanKey | null {
  const id = productId.toLowerCase();
  if (/annual|year/.test(id)) return 'annual';
  if (/six|semi|6mo|6_mo|halfyear|half_year/.test(id)) return 'semiannual';
  if (/month/.test(id)) return 'monthly';
  return null;
}

/** Find the store package for one of our plans; packageType first, then id. */
export function packageForPlan(
  packages: readonly MinimalPackage[],
  key: PlanKey,
): MinimalPackage | null {
  const byType = packages.find((p) => planForPackageType(p.packageType) === key);
  if (byType) return byType;
  return packages.find((p) => planForProductId(p.product.identifier) === key) ?? null;
}

/**
 * What the paywall shows for a plan's price: the store's localized string when
 * we have it (it is what the user will actually be charged), else the config
 * price. The config numbers must match App Store Connect or the fallback lies.
 */
export function displayPrice(plan: Plan, localized?: string | null): string {
  return localized && localized.trim() !== '' ? localized : formatPrice(plan.price);
}

/**
 * Client-side entitlement read from RevenueCat's receipt-validated
 * CustomerInfo. Used as the immediate signal right after a purchase or
 * restore, while the webhook → subscriptions-table write (the durable truth)
 * is still in flight.
 */
export function customerInfoEntitled(info: MinimalCustomerInfo | null | undefined): boolean {
  if (!info) return false;
  return Boolean(info.entitlements?.active?.[REVENUECAT_ENTITLEMENT_ID]);
}

/** Where "manage subscription" goes when RevenueCat has no managementURL. */
export function fallbackManagementUrl(platform: string): string {
  return platform === 'android'
    ? 'https://play.google.com/store/account/subscriptions'
    : 'https://apps.apple.com/account/subscriptions';
}
