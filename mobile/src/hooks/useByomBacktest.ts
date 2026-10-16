/**
 * Loads one byom_backtest call. No screen. `season` null is the current
 * NFL season. The rows are results, not a recommended stake.
 */

import { useCallback, useEffect, useState } from 'react';

import { errorText, isAbortError } from '@/lib/errors';
import { fetchByomBacktest, type ByomBacktestRow, type ByomFilters } from '@/lib/byom';

export function useByomBacktest(season: number | null, filters?: ByomFilters) {
  const [rows, setRows] = useState<ByomBacktestRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const filterKey = JSON.stringify(filters ?? {});

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const parsed = JSON.parse(filterKey) as ByomFilters;
      const next = await fetchByomBacktest(season, parsed);
      setRows(next);
    } catch (e: unknown) {
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [season, filterKey]);

  useEffect(() => {
    void load();
  }, [load]);

  return { rows, loading, error, reload: load };
}
