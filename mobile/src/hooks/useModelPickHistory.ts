import { useEffect, useState } from 'react';
import { fetchModelFullOutcomePicks, type FullOutcomePickRow } from '@/lib/queries';

/**
 * Every scored pick (BET + dead-zone NONE + AVOID) that clears the CURRENT
 * thresholds, graded from final results. That is the sweep population, not
 * the published record. The model detail screen does not use this hook; it
 * lists posted settled bets so its count matches the Record.
 *
 * Failure-tolerant: any fetch error leaves rows empty. Models the view does
 * not grade (UFC/NHL/NBA) return zero rows.
 */
export function useModelPickHistory(modelId: string) {
  const [rows, setRows] = useState<FullOutcomePickRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchModelFullOutcomePicks(modelId)
      .then((r) => {
        if (!cancelled) setRows(r);
      })
      .catch(() => {
        if (!cancelled) setRows([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [modelId]);

  return { rows, loading };
}
