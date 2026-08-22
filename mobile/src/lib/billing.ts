import * as WebBrowser from 'expo-web-browser';

import { supabase } from './supabase';
import {
  BILLING_RETURN_URL,
  billingReady,
  type PlanKey,
} from './billingConfig';

/**
 * Billing API (mobile side).
 *
 * Payment happens in Stripe Checkout, opened in a browser — NOT Apple In-App
 * Purchase. In the US this is allowed with no entitlement and (as of the Epic
 * injunction) no Apple commission; Apple filed on 2026-08-13 to charge 5–15%,
 * so that may change. Outside the US the rules differ and this flow should not
 * be offered — see docs/BILLING.md.
 *
 * Checkout deliberately uses `openBrowserAsync` (SFSafariViewController on iOS)
 * rather than `openAuthSessionAsync`: the auth-session API is scoped to OAuth
 * redirects and suppresses shared cookies, which breaks Stripe's saved-card and
 * Link autofill. The subscription is granted by the stripe-webhook function, so
 * we never rely on the user actually returning to the app.
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

/** What the caller should do after the browser closes. */
export type CheckoutOutcome = 'returned' | 'dismissed';

/**
 * Open Stripe Checkout for a plan.
 *
 * Resolves once the browser closes. It does NOT mean payment succeeded —
 * entitlement arrives via webhook, so the caller should re-read the
 * subscription rather than assume. Returning 'dismissed' just means the user
 * closed the sheet; they may still have paid.
 */
export async function startCheckout(plan: PlanKey): Promise<CheckoutOutcome> {
  assertBillingReady();

  const { data, error } = await supabase.functions.invoke('stripe-checkout', {
    body: { plan },
  });
  if (error) throw new Error(billingErrorMessage(error));

  const payload = data as { url?: string; error?: string } | null;
  if (payload?.error) throw new Error(payload.error);
  if (!payload?.url) throw new Error('Could not start checkout.');

  const result = await WebBrowser.openBrowserAsync(payload.url, {
    dismissButtonStyle: 'close',
  });
  return result.type === 'opened' ? 'returned' : 'dismissed';
}

/** Open the Stripe billing portal (update card, switch plan, cancel). */
export async function openBillingPortal(): Promise<void> {
  assertBillingReady();

  const { data, error } = await supabase.functions.invoke('stripe-portal', {});
  if (error) throw new Error(billingErrorMessage(error));

  const payload = data as { url?: string; error?: string } | null;
  if (payload?.error) throw new Error(payload.error);
  if (!payload?.url) throw new Error('Could not open billing.');

  await WebBrowser.openBrowserAsync(payload.url);
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
  if (lower.includes('network') || lower.includes('fetch failed')) {
    return 'No connection. Check your network and try again.';
  }
  return raw;
}

export { BILLING_RETURN_URL };
