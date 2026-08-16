import { useCallback, useEffect, useState } from 'react';
import {
  fetchPicksForDate,
  fetchUpcomingUfcPicks,
  fetchUpcomingGolfPicks,
  fetchUpcomingNflPicks,
} from '@/lib/queries';
import { addDays, isGameOver, todayET } from '@/lib/format';
import type { EnrichedPick } from '@/types';

/** Mirrors config.UFC_SCORE_AHEAD_DAYS — how far ahead UFC fights are scored. */
const UFC_AHEAD_DAYS = 7;
/** Mirrors config.GOLF_SCORE_AHEAD_DAYS — how far ahead tournaments are scored. */
const GOLF_AHEAD_DAYS = 7;
/** The Thursday wind card prices games through Monday night — 5 days covers it. */
const NFL_AHEAD_DAYS = 5;

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
      const [rows, ufcRows, golfRows, nflRows] = await Promise.all([
        fetchPicksForDate(target),
        fetchUpcomingUfcPicks(target, addDays(target, UFC_AHEAD_DAYS)).catch(
          () => [] as EnrichedPick[],
        ),
        fetchUpcomingGolfPicks(target, addDays(target, GOLF_AHEAD_DAYS)).catch(
          () => [] as EnrichedPick[],
        ),
        fetchUpcomingNflPicks(target, addDays(target, NFL_AHEAD_DAYS)).catch(
          () => [] as EnrichedPick[],
        ),
      ]);
      // Drop games that have already finished — once a game ends it shouldn't
      // linger on the board for the rest of the day.
      const all = [...rows, ...ufcRows, ...golfRows, ...nflRows].filter(
        (d) => !isGameOver(d.game, d.pick.sport),
      );
      setData(all);
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
