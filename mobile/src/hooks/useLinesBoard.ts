import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';

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
  const dateRef = useRef(date);
  const loadGen = useRef(0);

  const load = useCallback(async () => {
    const day = todayET();
    const gen = ++loadGen.current;
    setLoading(true);
    setError(null);
    try {
      const gs = await fetchGamesForLinesBoard(day);
      const rows = await fetchLinesBoardOdds(gs.map((g) => g.game_id));
      // A newer load started while this one was out. Its games belong to a
      // different moment; writing them would put the old slate back.
      if (gen !== loadGen.current) return;
      dateRef.current = day;
      setDate(day);
      setGames(gs);
      setOdds(rows);
      setLoaded(true);
    } catch (e: unknown) {
      if (gen !== loadGen.current) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (gen === loadGen.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    void load();
  }, [enabled, load]);

  // A board left open past midnight ET would keep yesterday's slate: the
  // fetch above runs when the segment opens, not when the calendar day
  // changes. The tick and the foreground resume both notice the new ET date
  // and reload once. The same day does not refetch.
  useEffect(() => {
    if (!enabled) return;
    const roll = () => {
      const day = todayET();
      // dateRef stays on the slate on screen until that day's fetch succeeds.
      // Moving it here would title yesterday's games with today's weekday, and
      // a failed fetch would never tick again.
      if (day === dateRef.current) return;
      void load();
    };
    const id = setInterval(roll, 60_000);
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') roll();
    });
    return () => {
      clearInterval(id);
      sub.remove();
    };
  }, [enabled, load]);

  return { games, odds, loading, loaded, error, date, refresh: load };
}
