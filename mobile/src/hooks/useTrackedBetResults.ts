import { useCallback, useEffect, useMemo, useState } from 'react';

import { useTrackedBets } from './useTrackedBets';
import { useStakeSettings, FLAT_STAKE, type StakeMode } from './useStakeSettings';
import { useBankroll } from './useBankroll';
import { useKellySettings } from './useKellySettings';
import { fetchPicksByIds } from '@/lib/queries';
import { recommendedBet } from '@/lib/thresholds';
import {
  computeTrackedResults,
  type TrackedBetRow,
  type TrackedBetSummary,
} from '@/lib/trackedPerformance';
import type { Pick } from '@/types';

/**
 * Scores the user's tracked bets for the Performance tab.
 *
 * Tracked state is the on-device pick_id set (useTrackedBets); results come
 * from the picks table, which the pipeline settles every morning. Fetch is
 * failure-tolerant — a network error keeps the last-known rows so the card
 * degrades instead of vanishing.
 *
 * The stake each bet is scored at comes from useStakeSettings: $100 flat
 * (default), the pick's Kelly-sized bet (kelly_fraction x bankroll x the
 * user's Kelly knobs — the "Bet $X" the card showed), or a per-bet custom
 * amount (defaults to $100 until edited).
 */
export function useTrackedBetResults() {
  const { ids, untrack } = useTrackedBets();
  const stakes = useStakeSettings();
  const { bankroll } = useBankroll();
  const { multiplier, cap } = useKellySettings();
  const [picks, setPicks] = useState<Pick[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (ids.length === 0) {
      setPicks([]);
      return;
    }
    setLoading(true);
    try {
      setPicks(await fetchPicksByIds(ids));
    } catch (err) {
      console.warn('[trackedBetResults] fetch failed', err);
    } finally {
      setLoading(false);
    }
  }, [ids]);

  useEffect(() => {
    void load();
  }, [load]);

  const stakeFor = useCallback(
    (p: Pick): number => {
      if (stakes.mode === 'kelly') {
        return recommendedBet(Number(p.kelly_fraction ?? 0), bankroll, { multiplier, cap });
      }
      if (stakes.mode === 'custom') {
        return stakes.customStakes[String(p.pick_id)] ?? FLAT_STAKE;
      }
      return FLAT_STAKE;
    },
    [stakes.mode, stakes.customStakes, bankroll, multiplier, cap],
  );

  const { rows, summary } = useMemo(
    () => computeTrackedResults(ids, picks, stakeFor),
    [ids, picks, stakeFor],
  );

  return {
    /** Graded tracked bets — open first, then settled newest-first. */
    rows,
    summary,
    loading,
    refresh: load,
    untrack,
    trackedCount: ids.length,
    /** Stake sizing controls (Performance tab selector). */
    stakeMode: stakes.mode,
    setStakeMode: stakes.setMode,
    setCustomStake: stakes.setCustomStake,
    bankroll,
  };
}

export type { TrackedBetRow, TrackedBetSummary, StakeMode };
