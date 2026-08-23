import * as WebBrowser from 'expo-web-browser';

import { supabase } from './supabase';
import {
  BILLING_RAIL,
  BILLING_RETURN_URL,
  billingReady,
  type PlanKey,
} from './billingConfig';
import { openIapManagement, purchasePlan, restoreIapPurchases } from './iap';

/**
 * Billing API (mobile side) — the rail dispatcher.
 *
 * Two rails, selected by `BILLING_RAIL` (billingConfig.ts):
 *
 *   'iap'    — DEFAULT. App Store / Play Billing via RevenueCat. Chosen because
 *              every mainstream card processor restricts the sports-picks
 *              category (Stripe: restricted; Lemon Squeezy: prohibited) while
 *              the app stores have no objection. 15% fee, zero deplatforming
 *              risk, native purchase sheet. Requires an EAS rebuild — see the
 *              OTA note in lib/iap.ts.
 *   'stripe' — Checkout in a browser. 0% Apple commission in the US today
 *              (Epic injunction; Apple filed 2026-08-13 to charge 5–15%), but
 *              gated on Stripe granting written approval for the category.
 *              Kept built and dark as the fallback.
 *
 * Either way, entitlement is granted server-side (stripe-webhook or
 * revenuecat-webhook → the subscriptions table); the app never writes it.
 */

export { isEntitled, type SubscriptionRow } from './billingHelpers';

export class BillingDisabledError extends Error {
  constructor() {
    super('Billing is not enabled in this build.');
    this.name = 'BillingDisabledError';
  }
}

function assertBillingReady(): void {
  if (!billingReady()) throw new BillingDisabledError();
}

export interface CheckoutResult {
  outcome: 'completed' | 'dismissed';
  /**
   * True only when the rail can confirm entitlement synchronously (IAP returns
   * receipt-validated CustomerInfo). Stripe always reports false here — its
   * entitlement lands via webhook, so the caller re-reads the subscription.
   */
  entitledNow: boolean;
}

/**
 * Start a purchase for a plan.
 *
 * IAP: native store sheet, resolves with the receipt-validated result.
 * Stripe: opens Checkout in a browser; resolving does NOT mean payment
 * happened — the webhook decides, so the caller should refresh regardless.
 */
export async function startCheckout(
  plan: PlanKey,
  userId: string,
): Promise<CheckoutResult> {
  assertBillingReady();

  if (BILLING_RAIL === 'iap') {
    const result = await purchasePlan(plan, userId);
    return {
      outcome: result.outcome === 'purchased' ? 'completed' : 'dismissed',
      entitledNow: result.entitled,
    };
  }

  const { data, error } = await supabase.functions.invoke('stripe-checkout', {
    body: { plan },
  });
  if (error) throw new Error(billingErrorMessage(error));

  const payload = data as { url?: string; error?: string } | null;
  if (payload?.error) throw new Error(payload.error);
  if (!payload?.url) throw new Error('Could not start checkout.');

  // Deliberately openBrowserAsync, not openAuthSessionAsync: the auth-session
  // API suppresses shared cookies, which breaks Stripe's saved-card / Link
  // autofill. The webhook grants access, so we don't depend on the return.
  const result = await WebBrowser.openBrowserAsync(payload.url, {
    dismissButtonStyle: 'close',
  });
  return {
    outcome: result.type === 'opened' ? 'completed' : 'dismissed',
    entitledNow: false,
  };
}

/**
 * Open subscription management: the OS subscription screen for IAP (the only
 * place an IAP subscription can be cancelled), the Stripe portal otherwise.
 */
export async function openManageSubscription(userId: string | null): Promise<void> {
  assertBillingReady();

  if (BILLING_RAIL === 'iap') {
    await openIapManagement(userId);
    return;
  }

  const { data, error } = await supabase.functions.invoke('stripe-portal', {});
  if (error) throw new Error(billingErrorMessage(error));

  const payload = data as { url?: string; error?: string } | null;
  if (payload?.error) throw new Error(payload.error);
  if (!payload?.url) throw new Error('Could not open billing.');

  await WebBrowser.openBrowserAsync(payload.url);
}

/**
 * Restore purchases after a reinstall or on a new device. IAP-only concept
 * (App Review requires the button); on the Stripe rail entitlement follows the
 * signed-in account automatically, so there's nothing to restore.
 */
export async function restorePurchases(userId: string): Promise<boolean> {
  assertBillingReady();
  if (BILLING_RAIL !== 'iap') return false;
  return restoreIapPurchases(userId);
}

/** Read the signed-in user's subscription row. Null when there isn't one. */
export async function fetchSubscription() {
  if (!billingReady()) return null;
  const { data, error } = await supabase
    .from('subscriptions')
    .select('status, plan, current_period_end, trial_end, cancel_at_period_end')
    .maybeSingle();
  // RLS scopes this to the caller's own row; no user id filter needed, and
  // adding one from the client would be theatre rather than security.
  if (error) throw error;
  return data as
    | {
        status: string;
        plan: string | null;
        current_period_end: string | null;
        trial_end: string | null;
        cancel_at_period_end: boolean;
      }
    | null;
}

export function billingErrorMessage(err: unknown): string {
  const raw =
    err instanceof Error
      ? err.message
      : typeof err === 'string'
        ? err
        : 'Something went wrong. Please try again.';
  const lower = raw.toLowerCase();
  if (lower.includes('not signed in')) return 'Sign in first to subscribe.';
  if (lower.includes('already have an active subscription')) {
    return "You're already subscribed.";
  }
  if (lower.includes('no billing account')) {
    return 'No billing account yet — subscribe first.';
  }
  if (lower.includes('not available in the store')) {
    return 'That plan is not available in the store yet. Try again shortly.';
  }
  if (lower.includes('does not include in-app purchases')) {
    return 'Update to the latest app version to subscribe.';
  }
  if (lower.includes('network') || lower.includes('fetch failed')) {
    return 'No connection. Check your network and try again.';
  }
  return raw;
}

export { BILLING_RETURN_URL };
