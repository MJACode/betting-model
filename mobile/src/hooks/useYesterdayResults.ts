import { useCallback, useEffect, useState } from 'react';

import { fetchSettledPicks } from '@/lib/queries';
import { addDays, todayET } from '@/lib/format';
import { computeDailyResults, EMPTY_DAILY, type DailyResults } from '@/lib/dailyResults';

/**
 * Loads yesterday's (ET) settled picks and aggregates them into overall +
 * per-sport + per-model records for the daily recap modal. Single-day query —
 * cheap enough to run on app launch (drives the once/day auto-pop gate).
 */
export function useYesterdayResults() {
  const date = addDays(todayET(), -1);
  const [results, setResults] = useState<DailyResults>(() => ({
    date,
    overall: EMPTY_DAILY,
    sports: [],
  }));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const settled = await fetchSettledPicks(date, date);
      setResults(computeDailyResults(date, settled));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    void load();
  }, [load]);

  return { date, results, loading, error, refresh: load };
}
