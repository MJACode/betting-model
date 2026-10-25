/**
 * One scoped byom_backtest read, summed to a record. A null filter
 * does not call: an empty filter is the whole season and is not a
 * model preview. A slower response does not replace a newer one.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { errorText, isAbortError } from '@/lib/errors';
import { fetchByomScopedBacktest, type ByomFilters } from '@/lib/byom';
import { byomFilters } from '@/lib/byomFilters';
import {
  recordFromRows,
  type ByomRecord,
  type ByomSeasonScope,
} from '@/lib/byomRecord';

export function useByomRecord(scope: ByomSeasonScope, filters: ByomFilters | null) {
  const [record, setRecord] = useState<ByomRecord | null>(null);
  const [loading, setLoading] = useState(filters != null);
  const [error, setError] = useState<string | null>(null);
  const filterKey = filters == null ? '' : JSON.stringify(byomFilters(filters));
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (filterKey === '') {
      seq.current += 1;
      setRecord(null);
      setError(null);
      setLoading(false);
      return;
    }
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    setRecord(null);
    try {
      const parsed = JSON.parse(filterKey) as ByomFilters;
      const rows = await fetchByomScopedBacktest(scope, parsed);
      if (seq.current !== id) return;
      setRecord(recordFromRows(rows));
    } catch (e: unknown) {
      if (seq.current !== id) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [scope, filterKey]);

  useEffect(() => {
    void load();
  }, [load]);

  return { record, loading, error, reload: load };
}
