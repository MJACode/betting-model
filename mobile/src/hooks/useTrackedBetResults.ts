import { useCallback, useEffect, useMemo, useState } from 'react';

import { useTrackedBets } from './useTrackedBets';
import { fetchPicksByIds } from '@/lib/queries';
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
 */
export function useTrackedBetResults() {
  const { ids, untrack } = useTrackedBets();
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

  const { rows, summary } = useMemo(
    () => computeTrackedResults(ids, picks),
    [ids, picks],
  );

  return {
    /** Graded tracked bets — open first, then settled newest-first. */
    rows,
    summary,
    loading,
    refresh: load,
    untrack,
    trackedCount: ids.length,
  };
}

export type { TrackedBetRow, TrackedBetSummary };
