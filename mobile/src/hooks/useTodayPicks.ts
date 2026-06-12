import { useCallback, useEffect, useState } from 'react';
import { fetchPicksForDate, fetchUpcomingUfcPicks } from '@/lib/queries';
import { addDays, todayET } from '@/lib/format';
import type { EnrichedPick } from '@/types';

/** Mirrors config.UFC_SCORE_AHEAD_DAYS — how far ahead UFC fights are scored. */
const UFC_AHEAD_DAYS = 7;

export function useTodayPicks(date?: string) {
  const target = date ?? todayET();
  const [data, setData] = useState<EnrichedPick[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      // Today's picks (all sports) + the upcoming UFC card. UFC events are
      // weekly, so the UFC tab shows the next card's picks ahead of fight day.
      // The UFC fetch is enrichment — don't fail the whole feed on it.
      const [rows, ufcRows] = await Promise.all([
        fetchPicksForDate(target),
        fetchUpcomingUfcPicks(target, addDays(target, UFC_AHEAD_DAYS)).catch(
          () => [] as EnrichedPick[],
        ),
      ]);
      setData([...rows, ...ufcRows]);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [target]);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, loading, error, refresh: load, date: target };
}
