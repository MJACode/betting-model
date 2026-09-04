import { useEffect, useState } from 'react';
import { fetchModelFullOutcomePicks, type FullOutcomePickRow } from '@/lib/queries';

/**
 * Per-pick history behind a built-in model's full-outcome record — every scored
 * pick (BET + dead-zone NONE + AVOID) that clears the CURRENT thresholds, graded
 * from final results. Row-for-row the same set v_model_full_outcome_picks, bounded to the published window,
 * aggregates, so the list always reconciles with the displayed record.
 *
 * Failure-tolerant: any fetch error leaves rows empty so the model detail
 * screen falls back to its settled-BET-pick history instead of blanking.
 * Models not covered by the view (UFC/NHL/NBA/golf) simply return zero rows.
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
