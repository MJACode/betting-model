import { useCallback, useEffect, useState } from 'react';
import { fetchOpeningSignalsForDate } from '@/lib/queries';
import { todayET } from '@/lib/format';
import type { GameRow, OpeningSignalRow } from '@/types';

/**
 * Today's locked opening signals + the games to enrich them. Mirrors
 * useTodayPicks. Drives the Signals "Dropped" sub-tab: a signal that's no
 * longer live still has its opening snapshot here, so it never disappears.
 */
export function useOpeningSignals(date?: string) {
  const target = date ?? todayET();
  const [rows, setRows] = useState<OpeningSignalRow[]>([]);
  const [gameById, setGameById] = useState<Map<string, GameRow>>(new Map());
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchOpeningSignalsForDate(target);
      setRows(res.rows);
      setGameById(res.gameById);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [target]);

  useEffect(() => {
    void load();
  }, [load]);

  return { rows, gameById, loading, error, refresh: load, date: target };
}
