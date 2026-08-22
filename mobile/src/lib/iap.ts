import { Linking, Platform } from 'react-native';

import {
  REVENUECAT_ANDROID_KEY,
  REVENUECAT_IOS_KEY,
  billingReady,
  type PlanKey,
} from './billingConfig';
import {
  customerInfoEntitled,
  fallbackManagementUrl,
  packageForPlan,
  type MinimalCustomerInfo,
  type MinimalPackage,
} from './iapHelpers';

/**
 * In-app purchases via RevenueCat (App Store / Play Billing).
 *
 * ============================================================================
 * OTA SAFETY — read before touching the imports.
 * ============================================================================
 * `react-native-purchases` is a NATIVE module. A statically-imported native
 * module crashes ON LAUNCH on any installed binary built before the module was
 * added (the session-73 / session-122 lesson). This file therefore loads the
 * SDK ONLY through `loadPurchases()` — a dynamic require, called inside
 * functions that are themselves gated on `billingReady()` (false in
 * production). Never add `import Purchases from 'react-native-purchases'` at
 * the top of this or any file; `import type` is fine (erased at compile time).
 *
 * Activating IAP therefore requires an EAS REBUILD (unlike the Stripe path,
 * which is pure JS) — and app.json's `version` must be bumped with that build
 * so OTA bundles for the new runtime never reach old binaries. Runbook:
 * docs/BILLING.md.
 *
 * Identity: the RevenueCat app user id IS the Supabase auth user id, set at
 * configure time. That's what lets the revenuecat-webhook function map events
 * straight onto the subscriptions table with no alias bookkeeping — and it's
 * why purchases require sign-in.
 */

/** Minimal surface of the SDK we call; structural so nothing imports the package. */
interface PurchasesSDK {
  configure(opts: { apiKey: string; appUserID?: string | null }): void;
  logIn(appUserID: string): Promise<{ customerInfo: MinimalCustomerInfo }>;
  getOfferings(): Promise<{
    current: { availablePackages: MinimalPackage[] } | null;
  }>;
  purchasePackage(pkg: MinimalPackage): Promise<{ customerInfo: MinimalCustomerInfo }>;
  restorePurchases(): Promise<MinimalCustomerInfo>;
  getCustomerInfo(): Promise<MinimalCustomerInfo>;
}

let sdk: PurchasesSDK | null = null;
let configuredFor: string | null = null;

/**
 * Load the native SDK, or explain why we can't. The require is the ONLY place
 * the package name appears as a value — see the OTA note above.
 */
function loadPurchases(): PurchasesSDK {
  if (sdk) return sdk;
  let mod: unknown;
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    mod = require('react-native-purchases');
  } catch {
    throw new Error(
      'This build does not include in-app purchases. Update to the latest app version.',
    );
  }
  const resolved = (mod as { default?: PurchasesSDK }).default ?? (mod as PurchasesSDK);
  if (typeof resolved?.configure !== 'function') {
    throw new Error(
      'This build does not include in-app purchases. Update to the latest app version.',
    );
  }
  sdk = resolved;
  return resolved;
}

function apiKey(): string {
  const key = Platform.OS === 'android' ? REVENUECAT_ANDROID_KEY : REVENUECAT_IOS_KEY;
  if (!key) {
    throw new Error(
      `RevenueCat ${Platform.OS} API key is not set (EXPO_PUBLIC_REVENUECAT_*_KEY).`,
    );
  }
  return key;
}

/** Configure once per process; switch identity if a different user signs in. */
async function ensureConfigured(userId: string): Promise<PurchasesSDK> {
  const purchases = loadPurchases();
  if (configuredFor == null) {
    purchases.configure({ apiKey: apiKey(), appUserID: userId });
    configuredFor = userId;
  } else if (configuredFor !== userId) {
    await purchases.logIn(userId);
    configuredFor = userId;
  }
  return purchases;
}

/** Localized store prices for the paywall, keyed by plan. Best-effort. */
export async function fetchLocalizedPrices(
  userId: string,
): Promise<Partial<Record<PlanKey, string>>> {
  if (!billingReady()) return {};
  const purchases = await ensureConfigured(userId);
  const offerings = await purchases.getOfferings();
  const packages = offerings.current?.availablePackages ?? [];
  const out: Partial<Record<PlanKey, string>> = {};
  for (const key of ['monthly', 'semiannual', 'annual'] as const) {
    const pkg = packageForPlan(packages, key);
    if (pkg) out[key] = pkg.product.priceString;
  }
  return out;
}

export interface IapPurchaseResult {
  outcome: 'purchased' | 'cancelled';
  /** Receipt-validated entitlement, usable immediately (webhook lags seconds). */
  entitled: boolean;
}

/** Run the native purchase sheet for a plan. */
export async function purchasePlan(
  plan: PlanKey,
  userId: string,
): Promise<IapPurchaseResult> {
  if (!billingReady()) {
    throw new Error('Billing is not enabled in this build.');
  }
  const purchases = await ensureConfigured(userId);
  const offerings = await purchases.getOfferings();
  const pkg = packageForPlan(offerings.current?.availablePackages ?? [], plan);
  if (!pkg) {
    throw new Error('That plan is not available in the store yet.');
  }
  try {
    const { customerInfo } = await purchases.purchasePackage(pkg);
    return { outcome: 'purchased', entitled: customerInfoEntitled(customerInfo) };
  } catch (e) {
    // RevenueCat marks a user-dismissed sheet explicitly — that's a normal
    // outcome, not an error.
    if ((e as { userCancelled?: boolean })?.userCancelled) {
      return { outcome: 'cancelled', entitled: false };
    }
    throw e;
  }
}

/**
 * Restore purchases — an App Review requirement for any app selling IAP, and
 * the recovery path after a reinstall or a new phone.
 */
export async function restoreIapPurchases(userId: string): Promise<boolean> {
  if (!billingReady()) return false;
  const purchases = await ensureConfigured(userId);
  const info = await purchases.restorePurchases();
  return customerInfoEntitled(info);
}

/**
 * Open the OS-level subscription management screen (the only place an IAP
 * subscription can actually be cancelled — we can't do it for them).
 */
export async function openIapManagement(userId: string | null): Promise<void> {
  let url: string | null = null;
  if (userId) {
    try {
      const purchases = await ensureConfigured(userId);
      const info = await purchases.getCustomerInfo();
      url = info.managementURL ?? null;
    } catch {
      // Fall through to the platform default.
    }
  }
  await Linking.openURL(url ?? fallbackManagementUrl(Platform.OS));
}
