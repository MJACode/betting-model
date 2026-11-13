/**
 * What to do when a Stripe webhook names a different subscription than the
 * row we already stored.
 *
 * The row's status is not enough. A missed `customer.subscription.deleted`
 * leaves the row saying `active` after Stripe has already canceled that id.
 * Cancelling the incoming subscription in that case would kill the
 * customer's real replacement. The caller has to read the stored id from
 * Stripe first and pass that snapshot in.
 */

export interface StoredSubscriptionRow {
  stripe_subscription_id?: string | null;
  status?: string | null;
}

export interface IncomingSubscription {
  id: string;
  status?: string | null;
}

/** Stripe's current view of the id on the row. Null means Stripe has no such subscription. */
export interface StripeSubscriptionSnapshot {
  id: string;
  status?: string | null;
}

export type SecondSubAction = "apply" | "ignore" | "cancel_incoming";

export function isLiveSubscriptionStatus(status: string | null | undefined): boolean {
  return status === "trialing" || status === "active";
}

export function secondSubscriptionAction(
  existing: StoredSubscriptionRow | null | undefined,
  incoming: IncomingSubscription,
  storedInStripe: StripeSubscriptionSnapshot | null,
): SecondSubAction {
  const storedId = existing?.stripe_subscription_id ?? null;
  if (!storedId || storedId === incoming.id) return "apply";
  if (!isLiveSubscriptionStatus(existing?.status)) return "apply";
  const storedStillLive =
    storedInStripe != null &&
    storedInStripe.id === storedId &&
    isLiveSubscriptionStatus(storedInStripe.status);
  if (!storedStillLive) return "apply";
  if (isLiveSubscriptionStatus(incoming.status)) return "cancel_incoming";
  return "ignore";
}
