/**
 * Loads one byom_backtest call. No screen. `season` null is the current
 * NFL season. The rows are results, not a recommended stake.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { splitLoadError } from '@/lib/errors';
import { fetchByomBacktest, type ByomBacktestRow, type ByomFilters } from '@/lib/byom';

export function useByomBacktest(season: number | null, filters?: ByomFilters) {
  const [rows, setRows] = useState<ByomBacktestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [noAccess, setNoAccess] = useState(false);
  const filterKey = JSON.stringify(filters ?? {});
  // A response lands only when no newer load has started.
  const seq = useRef(0);

  const load = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    setNoAccess(false);
    try {
      const parsed = JSON.parse(filterKey) as ByomFilters;
      const next = await fetchByomBacktest(season, parsed);
      if (seq.current !== id) return;
      setRows(next);
      setNoAccess(false);
    } catch (e: unknown) {
      if (seq.current !== id) return;
      const split = splitLoadError(e);
      if (split.noAccess) setRows([]);
      setNoAccess(split.noAccess);
      setError(split.error);
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [season, filterKey]);

  useEffect(() => {
    void load();
  }, [load]);

  return { rows, loading, error, noAccess, reload: load };
}
