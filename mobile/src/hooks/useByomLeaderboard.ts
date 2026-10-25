/**
 * The signed-in user's NFL models, each graded by byom_backtest and
 * ranked by units. An empty filter is not graded. A slower response
 * does not replace a newer one. Signed-out does not call the list RPC.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { useAuth } from '@/hooks/useAuth';
import { errorText, isAbortError } from '@/lib/errors';
import {
  fetchByomModels,
  fetchByomScopedBacktest,
  type ByomFilters,
  type ByomModel,
} from '@/lib/byom';
import {
  isWholeSeason,
  rankByUnits,
  recordFromRows,
  showsUnits,
  type ByomRecord,
  type ByomSeasonScope,
} from '@/lib/byomRecord';

export interface ByomLeaderboardRow {
  model: ByomModel;
  record: ByomRecord | null;
  showsUnits: boolean;
  rank: number | null;
  /** Empty filters are the whole season. They are not graded. */
  ungraded: boolean;
}

async function pool<T, R>(items: readonly T[], limit: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let next = 0;
  const workers = Math.min(Math.max(limit, 0), items.length);
  await Promise.all(Array.from({ length: workers }, async () => {
    for (;;) {
      const index = next;
      next += 1;
      if (index >= items.length) return;
      out[index] = await fn(items[index]);
    }
  }));
  return out;
}

export function useByomLeaderboard(sport: string, scope: ByomSeasonScope) {
  const { signedIn, ready } = useAuth();
  const [rows, setRows] = useState<ByomLeaderboardRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seq = useRef(0);
  const seenScope = useRef(scope);
  const enabled = sport === 'NFL' && ready && signedIn;

  const load = useCallback(async () => {
    if (!enabled) {
      seq.current += 1;
      setRows([]);
      setError(null);
      setLoading(false);
      return;
    }
    const id = ++seq.current;
    if (seenScope.current !== scope) {
      seenScope.current = scope;
      setRows([]);
    }
    setLoading(true);
    setError(null);
    try {
      const models = (await fetchByomModels()).filter((model) => model.sport === 'NFL');
      if (seq.current !== id) return;
      const graded = await pool(models, 3, async (model) => {
        if (isWholeSeason(model.filters)) {
          return { model, record: null as ByomRecord | null, ungraded: true };
        }
        const backtest = await fetchByomScopedBacktest(scope, model.filters);
        return { model, record: recordFromRows(backtest), ungraded: false };
      });
      if (seq.current !== id) return;
      const ranked = rankByUnits(graded.map((item) => ({
        id: item.model.model_id,
        name: item.model.name,
        bets: item.record?.bets ?? 0,
        units: item.record?.units ?? null,
        showsUnits: item.record != null && showsUnits(item.model.filters),
        ungraded: item.ungraded,
        model: item.model,
        record: item.record,
      })));
      setRows(ranked.map((item) => ({
        model: item.model,
        record: item.record,
        showsUnits: item.showsUnits,
        rank: item.rank,
        ungraded: item.ungraded,
      })));
    } catch (e: unknown) {
      if (seq.current !== id) return;
      // A failed refresh keeps the rows already on screen. The list
      // banners that failure. A failed first load has nothing to keep.
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [enabled, scope]);

  useEffect(() => {
    void load();
  }, [load]);

  return { rows, loading, error, reload: load, signedIn, authReady: ready };
}

export type { ByomFilters };
