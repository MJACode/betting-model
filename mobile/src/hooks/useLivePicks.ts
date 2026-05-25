// useLivePicks — Phase 5 scaffolding for the Live tab.
//
// Polls Supabase every POLL_INTERVAL_MS while the screen is focused.
// Stops polling on blur (battery + cost). Mirrors the useTodayPicks shape
// so LiveScreen can render with the existing PickCard component.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { fetchLivePicks } from '@/lib/queries';
import type { EnrichedPick } from '@/types';

const POLL_INTERVAL_MS = 30_000;

function todayInET(): string {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
  return fmt.format(new Date());
}

export function useLivePicks() {
  const [data, setData] = useState<EnrichedPick[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [date] = useState<string>(todayInET());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setError(null);
      const picks = await fetchLivePicks(date);
      setData(picks);
    } catch (err: any) {
      setError(err?.message ?? 'Failed to load live picks');
    } finally {
      setLoading(false);
    }
  }, [date]);

  // Start/stop polling on focus/blur.
  useFocusEffect(
    useCallback(() => {
      refresh();
      timerRef.current = setInterval(refresh, POLL_INTERVAL_MS);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
      };
    }, [refresh])
  );

  return { data, loading, error, refresh, date };
}
