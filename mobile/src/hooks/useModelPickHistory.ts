import { useEffect, useState } from 'react';
import { splitLoadError } from '@/lib/errors';
import { fetchModelFullOutcomePicks, type FullOutcomePickRow } from '@/lib/queries';

/**
 * Every scored pick (BET + dead-zone NONE + AVOID) that clears the CURRENT
 * thresholds, graded from final results. That is the sweep population, not
 * the published record. The model detail screen does not use this hook; it
 * lists posted settled bets so its count matches the Record.
 *
 * A premium-gate refusal leaves rows empty and sets noAccess. Any other
 * fetch error leaves rows empty and sets error, so a screen can show it.
 * Models the view does not grade (UFC/NHL/NBA) return zero rows.
 */
export function useModelPickHistory(modelId: string) {
  const [rows, setRows] = useState<FullOutcomePickRow[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [noAccess, setNoAccess] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNoAccess(false);
    fetchModelFullOutcomePicks(modelId)
      .then((r) => {
        if (cancelled) return;
        setRows(r);
        setNoAccess(false);
        setError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const split = splitLoadError(e);
        setRows([]);
        setNoAccess(split.noAccess);
        setError(split.error);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [modelId]);

  return { rows, loading, error, noAccess };
}
