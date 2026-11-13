/**
 * Who holds the App Subscriber Discord role.
 *
 * Trial app access stays (status `trialing` still entitles the app). The
 * paid Discord role does not: only an `active` row whose period has not
 * ended. A null period end grants, matching subscriptionEntitles — a row
 * written before the webhook filled the date in must not lock out someone
 * who just paid.
 */
export function subscriptionGrantsDiscordRole(
  row: { status?: string | null; current_period_end?: string | null } | null | undefined,
  now: number = Date.now(),
): boolean {
  if (row?.status !== "active") return false;
  if (!row.current_period_end) return true;
  const end = Date.parse(row.current_period_end);
  if (Number.isNaN(end)) return true;
  return end > now;
}
