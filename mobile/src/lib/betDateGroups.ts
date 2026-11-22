/**
 * The Performance tab's bet lists, grouped by bet date (Matt, 2026-11-21:
 * "make the bet list collapsible by bet dates and a see all option").
 *
 * Dates run newest first; inside a date the list keeps the order it was given
 * (the tracked list's own order: open first, then settled newest first). The
 * two newest dates start open and the rest folded; the list shows the newest
 * seven dates until "See all". A day holding an OPEN bet always shows and
 * starts open, however old: before the grouping every open bet sat at the top
 * of the list, and those are the bets a member is still sweating (UX review,
 * 2026-11-21). A member's own tap on a header always wins.
 *
 * Pure on purpose: no imports, so a node test loads it with type stripping
 * (mobile/scripts/verify_bet_date_groups.ts).
 */

export interface DateGroup<T> {
  /** ET calendar day, YYYY-MM-DD. */
  date: string;
  items: T[];
}

/** How many of the newest dates start open. */
export const DEFAULT_OPEN_DATES = 2;
/** How many dates show before "See all". */
export const DEFAULT_VISIBLE_DATES = 7;

export function groupByDate<T>(items: readonly T[], dateOf: (t: T) => string): DateGroup<T>[] {
  const by = new Map<string, T[]>();
  for (const it of items) {
    const d = dateOf(it);
    const list = by.get(d);
    if (list) list.push(it);
    else by.set(d, [it]);
  }
  return [...by.entries()]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([date, list]) => ({ date, items: list }));
}

/**
 * The dates on screen: the newest DEFAULT_VISIBLE_DATES plus any older day
 * with an open bet, or all of them after "See all".
 */
export function visibleDateGroups<T>(
  groups: DateGroup<T>[],
  showAll: boolean,
  hasOpen: (g: DateGroup<T>) => boolean = () => false,
): DateGroup<T>[] {
  if (showAll) return groups;
  return groups.filter((g, i) => i < DEFAULT_VISIBLE_DATES || hasOpen(g));
}

/** Open by the member's own tap if there is one, else if newest or holding an open bet. */
export function isDateOpen(
  date: string,
  index: number,
  taps: Readonly<Record<string, boolean>>,
  hasOpen = false,
): boolean {
  const tapped = taps[date];
  return tapped ?? (index < DEFAULT_OPEN_DATES || hasOpen);
}

export interface DateSummary {
  /** Won less lost, at the list's own scale (100-is-1u). */
  net: number;
  wins: number;
  losses: number;
  pushes: number;
  open: number;
  /** Anything settled to a result (won, lost or push). */
  settled: number;
  /** No action or not graded: in the day's bet count, not in its record. */
  other: number;
}

/** One date's line: units and W-L over its won and lost bets; open counted apart. */
export function summarizeDate<T>(
  items: readonly T[],
  statusOf: (t: T) => string,
  profitOf: (t: T) => number,
): DateSummary {
  let net = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let open = 0;
  let other = 0;
  for (const it of items) {
    const s = statusOf(it);
    if (s === 'won') {
      wins++;
      net += profitOf(it);
    } else if (s === 'lost') {
      losses++;
      net += profitOf(it);
    } else if (s === 'push') pushes++;
    else if (s === 'open') open++;
    else other++;
  }
  return { net: Math.round(net * 100) / 100, wins, losses, pushes, open, settled: wins + losses + pushes, other };
}
