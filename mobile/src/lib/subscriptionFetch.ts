/**
 * Whether a subscription fetch may still be published.
 *
 * The read is async. Sign-out, or a switch to another account, can land
 * first. A late row for the old account must not be stored, and must not
 * count as the read for the new account.
 */
export interface SubscriptionFetchTicket {
  generation: number;
  userId: string | null;
}

export function subscriptionFetchStillCurrent(
  started: SubscriptionFetchTicket,
  now: SubscriptionFetchTicket,
): boolean {
  return started.generation === now.generation && started.userId === now.userId;
}
