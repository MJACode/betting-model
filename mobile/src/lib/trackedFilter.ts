/**
 * "Have I placed this yet?" — the TRACKED cut on the Picks board.
 *
 * Matt, 2026-11-21, from the NCAAB Signals filter sheet: *"Add a filter here
 * to show bets that have not been placed, so we should go off of the track
 * indicator."* The Track button on each card (useTrackedBets.isTracked) is
 * the member's own record of what they bet, so this cut reads exactly that —
 * the chip and the card's "Tracking" state can never disagree.
 *
 * One choice of three, not a multi-select: "Not tracked + Tracked" is just
 * All. ALL IS THE DEFAULT and the cut is NOT PERSISTED, so a stored
 * "Not tracked" can never silently hide tomorrow's board.
 */

export type TrackedCut = 'all' | 'untracked' | 'tracked';

export const TRACKED_CUTS: TrackedCut[] = ['all', 'untracked', 'tracked'];

export const TRACKED_CUT_LABEL: Record<TrackedCut, string> = {
  all: 'All',
  untracked: 'Not tracked',
  tracked: 'Tracked',
};

export interface TrackedCutOption {
  cut: TrackedCut;
  label: string;
  /** Picks on the board this chip would show. */
  count: number;
}

/** The three chips with their counts, from each pick's tracked state. */
export function trackedCutOptionsFor(trackedStates: Iterable<boolean>): TrackedCutOption[] {
  let tracked = 0;
  let total = 0;
  for (const t of trackedStates) {
    total += 1;
    if (t) tracked += 1;
  }
  const counts: Record<TrackedCut, number> = {
    all: total,
    untracked: total - tracked,
    tracked,
  };
  return TRACKED_CUTS.map((cut) => ({ cut, label: TRACKED_CUT_LABEL[cut], count: counts[cut] }));
}

/** Does a pick with this tracked state pass the cut? */
export function passesTrackedCut(cut: TrackedCut, isTracked: boolean): boolean {
  if (cut === 'untracked') return !isTracked;
  if (cut === 'tracked') return isTracked;
  return true;
}
