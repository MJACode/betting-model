/**
 * The stake a tracked pick is scored at on the Performance tab.
 *
 * Default, "As posted": the stake the Record tab, Yesterday and Discord book
 * (postedPickUnits, published_pick_unit_profit / _risked). Each pick is staked
 * to win 1u, or its own stake_units, at the price it was decided at, risk is
 * capped at 3u, and a pick with no price counts as that stake to win the
 * same. So a tracked pick shows the same units as the Record tab (mike,
 * 2026-11-03: "everything must be units").
 *
 * "My stakes" is the member's own override: the amount they type is what the
 * bet risks, at the same decided price. A bet they have not set stays as
 * posted. With no price it pays even money, the way the posted stake counts
 * an unpriced pick, never profit_flat's invented −110.
 *
 * Amounts are at the 100-is-1u scale (lib/format FLAT_UNIT), the scale the
 * custom stakes are stored at (hooks/useStakeSettings).
 */
import { decisionOdds } from './decisionPrice';
import { FLAT_UNIT } from './format';
import { decimalOdds, stakeFor } from './thresholds';
import type { TrackedStake, TrackedStakeFor } from './trackedPerformance';
import type { StakeMode } from '@/hooks/useStakeSettings';
import type { Pick } from '@/types';

/** The posted stake: the same price math as postedPickUnits, the pick's own
 *  stake_units included. */
export function postedTrackedStake(p: Pick): TrackedStake {
  const s = stakeFor(p.kelly_fraction, decisionOdds(p), p.stake_units);
  return { risk: s.risk * FLAT_UNIT, win: s.win * FLAT_UNIT, custom: false };
}

/** A member's own stake, risked at the decided price; even money with no price. */
export function customTrackedStake(p: Pick, amount: number): TrackedStake {
  const risk = Number.isFinite(amount) && amount >= 0 ? amount : 0;
  const dec = decimalOdds(decisionOdds(p));
  const win = dec != null && dec > 1 ? risk * (dec - 1) : risk;
  return { risk, win, custom: true };
}

/** The stake function for a stake mode and the member's saved stakes. */
export function trackedStakeFor(
  mode: StakeMode,
  customStakes: Record<string, number>,
): TrackedStakeFor {
  if (mode !== 'custom') return postedTrackedStake;
  return (p) => {
    const own = customStakes[String(p.pick_id)];
    return own == null ? postedTrackedStake(p) : customTrackedStake(p, own);
  };
}
