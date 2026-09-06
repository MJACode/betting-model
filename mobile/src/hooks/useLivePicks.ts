// useLivePicks — the in-play board's data source.
//
// Polls Supabase while the screen is focused and stops on blur (battery +
// cost). Mirrors the useTodayPicks shape so the same PickCard list renders it.
//
// The cadence is a PARAMETER, not a constant, because there are now two callers
// with different needs. Live picks stopped being their own tab on 2026-09-06 and
// became a segment on the Picks screen, so the fetch runs whenever Picks is
// open — most of a session — and a flat 30s poll would have been a permanent
// background cost to show a segment that is empty ~81% of the clock (measured:
// 175 live BETs over 25 of the last 31 days, ~5.3h of board occupancy per active
// day). So the screen polls fast only while the user is actually LOOKING at the
// live segment, and slowly otherwise, which is all that is needed to notice a
// game going in-play. useResolvedSlip polls slower still — it only needs live
// picks to exist so a live betslip leg resolves.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { fetchLivePicks } from '@/lib/queries';
import { todayET } from '@/lib/format';
import type { EnrichedPick } from '@/types';

/** Looking at the live board: the book's own number moves faster than this. */
export const LIVE_POLL_MS = 30_000;
/** Somewhere else in the app: enough to notice a game going in-play. */
export const LIVE_IDLE_POLL_MS = 120_000;

export function useLivePicks(options?: { pollMs?: number }) {
  const pollMs = options?.pollMs ?? LIVE_POLL_MS;
  const [data, setData] = useState<EnrichedPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // The ET date is RECOMPUTED per fetch, never captured. It used to be held in
  // useState, so an app left warm across midnight ET polled yesterday's slate
  // for as long as it stayed in memory — the live board silently stopped being
  // live. `date` here is only what the last fetch used, for display.
  const [date, setDate] = useState<string>(todayET);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    const target = todayET();
    setDate(target);
    try {
      setError(null);
      const picks = await fetchLivePicks(target);
      setData(picks);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load live picks');
    } finally {
      setLoading(false);
    }
  }, []);

  // Start/stop polling on focus/blur. Re-runs when pollMs changes (the user
  // switched into or out of the live segment), which restarts the interval at
  // the new cadence.
  useFocusEffect(
    useCallback(() => {
      void refresh();
      timerRef.current = setInterval(() => void refresh(), pollMs);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
      };
    }, [refresh, pollMs])
  );

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  return { data, loading, error, refresh, date };
}
