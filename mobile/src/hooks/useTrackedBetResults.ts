import { useCallback, useEffect, useMemo, useState } from 'react';

import { useTrackedBets, type LiveTrackSnapshot } from './useTrackedBets';
import { useStakeSettings, type StakeMode } from './useStakeSettings';
import { fetchPicksByIds, fetchLivePicksForGames, fetchGamesByIds } from '@/lib/queries';
import {
  computeTrackedResults,
  sortTrackedRows,
  mergeTrackedSummaries,
  type TrackedBetRow,
  type TrackedBetSummary,
} from '@/lib/trackedPerformance';
import { computeLiveTrackedResults } from '@/lib/liveTracked';
import { trackedStakeFor } from '@/lib/trackedStake';
import type { Pick } from '@/types';

/**
 * Scores the user's tracked bets for the Performance tab.
 *
 * Two sources, merged:
 *   - pre-game / prop / settled picks — hydrated by pick_id (useTrackedBets.ids),
 *     graded from the picks table (settled every morning).
 *   - LIVE picks — tracked by stable proposition key (useTrackedBets.liveSnapshots);
 *     their pick_id churns, so we resolve the live picks for their games and grade
 *     the model's settled pick for that side (computeLiveTrackedResults).
 *
 * Fetch is failure-tolerant — a network error keeps the last-known rows so the
 * card degrades instead of vanishing.
 *
 * Stake per bet comes from useStakeSettings through lib/trackedStake: the
 * posted stake by default, so a tracked pick shows the Record tab's units, or
 * the member's own stake on the bets they set ("My stakes").
 */
export function useTrackedBetResults() {
  const { ids, liveSnapshots, untrackPick } = useTrackedBets();
  const stakes = useStakeSettings();
  const [picks, setPicks] = useState<Pick[]>([]);
  const [livePicks, setLivePicks] = useState<Pick[]>([]);
  const [finalGameIds, setFinalGameIds] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);

  const liveGameIds = useMemo(
    () => Array.from(new Set(liveSnapshots.map((s) => s.game_id))),
    [liveSnapshots],
  );
  const liveGameKey = liveGameIds.join(',');

  const load = useCallback(async () => {
    if (ids.length === 0 && liveGameIds.length === 0) {
      setPicks([]);
      setLivePicks([]);
      setFinalGameIds(new Set());
      return;
    }
    setLoading(true);
    try {
      const [byId, live, games] = await Promise.all([
        ids.length ? fetchPicksByIds(ids) : Promise.resolve<Pick[]>([]),
        liveGameIds.length ? fetchLivePicksForGames(liveGameIds) : Promise.resolve<Pick[]>([]),
        liveGameIds.length ? fetchGamesByIds(liveGameIds) : Promise.resolve([]),
      ]);
      setPicks(byId);
      setLivePicks(live);
      setFinalGameIds(new Set(games.filter((g) => g.home_score != null).map((g) => g.game_id)));
    } catch (err) {
      console.warn('[trackedBetResults] fetch failed', err);
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ids, liveGameKey]);

  useEffect(() => {
    void load();
  }, [load]);

  const stakeFor = useMemo(
    () => trackedStakeFor(stakes.mode, stakes.customStakes),
    [stakes.mode, stakes.customStakes],
  );

  const { rows, summary } = useMemo(() => {
    const nonLive = computeTrackedResults(ids, picks, stakeFor);
    const live = computeLiveTrackedResults(
      liveSnapshots,
      livePicks,
      (id) => finalGameIds.has(id),
      stakeFor,
    );
    return {
      rows: sortTrackedRows([...nonLive.rows, ...live.rows]),
      summary: mergeTrackedSummaries(nonLive.summary, live.summary),
    };
  }, [ids, picks, liveSnapshots, livePicks, finalGameIds, stakeFor]);

  return {
    /** Graded tracked bets — open first, then settled newest-first. */
    rows,
    summary,
    loading,
    refresh: load,
    /** Untrack from a pick (branches live vs pick_id). */
    untrackPick,
    trackedCount: ids.length + liveSnapshots.length,
    /** Stake sizing controls (Performance tab selector). */
    stakeMode: stakes.mode,
    setStakeMode: stakes.setMode,
    setCustomStake: stakes.setCustomStake,
  };
}

export type { TrackedBetRow, TrackedBetSummary, StakeMode, LiveTrackSnapshot };
