/**
 * The injury index an add needs when the screen in front of the user is not
 * the Stats board. A failed read is an empty index — the same as the board
 * showing no tags — so a missing feed does not block a player we cannot see.
 */
import { fetchInjuryStatus } from '@/lib/queries';
import { buildInjuryIndex, EMPTY_INJURY_INDEX, type InjuryIndex } from '@/lib/injuryStatus';

export async function injuryIndexForSport(sport: string, nowMs = Date.now()): Promise<InjuryIndex> {
  try {
    return buildInjuryIndex(await fetchInjuryStatus(sport), nowMs);
  } catch {
    return EMPTY_INJURY_INDEX;
  }
}
