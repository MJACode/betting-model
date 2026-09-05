/**
 * Signal counts for the sport toggle's badge.
 *
 * This module used to back the Picks tab's "Movement" board as well; that board
 * was removed on 2026-09-05 (per-pick line movement lives on PickDetail, via
 * LineMovementCard), leaving the cross-sport signal tally as its one job.
 */
import { isUnlockedPreview, passesActionFilter } from './thresholds';
import type { EnrichedPick } from '@/types';

/**
 * How many picks have cleared the bet line, per sport, across the WHOLE board.
 *
 * The boards render one sport at a time (the global sport toggle), so a user
 * parked on their usual sport had no way to see that another sport had bets
 * waiting — during the Sept/Oct MLB-NFL overlap that meant missing NFL
 * entirely. This feeds the toggle's badge. Sports with zero signals are absent
 * from the result rather than present-as-0, so the badge renders only when
 * there is something to act on.
 */
export function signalCountsBySport(all: EnrichedPick[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const d of all) {
    if (!passesActionFilter(d.pick)) continue;
    // Unlocked look-ahead picks (future UFC/golf) are lines, not signals —
    // they must not badge the toggle. Mirrors the Signals sub-tab filter.
    if (isUnlockedPreview(d.pick)) continue;
    counts[d.pick.sport] = (counts[d.pick.sport] ?? 0) + 1;
  }
  return counts;
}
