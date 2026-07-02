import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchDayPicks } from '@/lib/queries';
import { computeDailyResults, emptyDailyResults, type DailyResults } from '@/lib/dailyResults';

/**
 * Loads one day's picks and aggregates them into overall + per-sport +
 * per-model records (plus the individual graded picks) for the daily recap
 * modal. Refetches whenever `date` changes or `reloadToken` bumps — the host
 * bumps the token every time the modal opens so the recap never shows a stale
 * launch-time fetch (settlement lands ~7am ET and the app can sit in memory
 * across days) and a failed fetch gets retried on the next open.
 */
export function useDailyResults(date: string, reloadToken = 0) {
  const [results, setResults] = useState<DailyResults>(() => emptyDailyResults(date));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Monotonic request id — a response only lands if no newer request started
  // (the user can step through days faster than queries resolve).
  const seq = useRef(0);

  const load = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const dayPicks = await fetchDayPicks(date);
      if (seq.current !== id) return;
      setResults(computeDailyResults(date, dayPicks));
    } catch (e: unknown) {
      if (seq.current !== id) return;
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (seq.current === id) setLoading(false);
    }
    // reloadToken is intentionally a dependency: bumping it recreates `load`,
    // which re-fires the effect below even when `date` is unchanged.
  }, [date, reloadToken]);

  useEffect(() => {
    void load();
  }, [load]);

  return { results, loading, error, refresh: load };
}
