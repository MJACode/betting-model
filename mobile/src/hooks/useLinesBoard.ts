import { useCallback, useEffect, useState } from 'react';

import { todayET } from '@/lib/format';
import { errorText, isAbortError } from '@/lib/errors';
import { fetchGamesForLinesBoard, fetchLinesBoardOdds } from '@/lib/queries';
import type { GameRow, OddsByBookRow } from '@/types';

/**
 * Today's NHL and NBA games and every book's latest line for them.
 *
 * Fetches only while the Lines segment is open. The read is paged and
 * narrowed in fetchLinesBoardOdds — a full MLB Saturday is the read this
 * board must not make.
 */
export function useLinesBoard(enabled: boolean) {
  const [games, setGames] = useState<GameRow[]>([]);
  const [odds, setOdds] = useState<OddsByBookRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [date, setDate] = useState(todayET);

  const load = useCallback(async () => {
    const day = todayET();
    setDate(day);
    setLoading(true);
    setError(null);
    try {
      const gs = await fetchGamesForLinesBoard(day);
      const rows = await fetchLinesBoardOdds(gs.map((g) => g.game_id));
      setGames(gs);
      setOdds(rows);
      setLoaded(true);
    } catch (e: unknown) {
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    void load();
  }, [enabled, load]);

  return { games, odds, loading, loaded, error, date, refresh: load };
}
