// useLivePicks — the in-play board's data source.
//
// Mirrors the useTodayPicks shape so the same PickCard list renders it.
//
// TWO VARIANTS, AND THE SPLIT IS NOT A PREFERENCE.
//
// `useLivePicks` polls while its SCREEN is focused and stops on blur (battery +
// cost), which is what a board wants. It cannot be used everywhere, because
// useFocusEffect calls useNavigation(), and that THROWS ("Couldn't find a
// navigation object") when neither NavigationContext nor
// NavigationContainerRefContext is in scope.
//
// BetslipBar is mounted at the app root as a SIBLING of <NavigationContainer>
// (App.tsx) — deliberately, so one bar covers the tabs and pushed screens
// alike — so every hook on its path is outside both contexts. useResolvedSlip
// is on that path and reads live picks so a live betslip leg can resolve.
// Calling the focus-aware variant there crashed on render for any user with
// something in their slip, on every screen (UX review, 2026-09-06). So that
// caller uses `useLivePicksUnfocused`, which runs a plain effect for its
// lifetime — the same thing useTodayPicks already does, for the same reason.
//
// The CADENCE is a parameter because live picks stopped being their own tab on
// 2026-09-06 and became a segment on the Picks screen, so the fetch runs
// whenever Picks is open — most of a session. A flat 30s poll would have been a
// permanent background cost to show a segment that is empty ~81% of the clock
// (measured: 175 live BETs over 25 of the last 31 days, ~5.3h of board
// occupancy per active day). The screen polls fast only while the user is
// actually LOOKING at the live segment.

import { useCallback, useEffect, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { fetchLivePicks } from '@/lib/queries';
import { errorText } from '@/lib/errors';
import { todayET } from '@/lib/format';
import type { EnrichedPick } from '@/types';

/** Looking at the live board: the book's own number moves faster than this. */
export const LIVE_POLL_MS = 30_000;
/** Somewhere else in the app: enough to notice a game going in-play. */
export const LIVE_IDLE_POLL_MS = 120_000;

export type LivePicksState = {
  data: EnrichedPick[];
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  date: string;
};

/** State + the poll body. Mounted by exactly one of the two hooks below. */
function useLivePicksCore(pollMs: number) {
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
    // Pull-to-refresh reads `loading` to decide whether to spin. Without this
    // the control snapped straight back and the board looked inert.
    setLoading(true);
    try {
      setError(null);
      const picks = await fetchLivePicks(target);
      setData(picks);
    } catch (e) {
      // errorText, not err.message: raw Postgres ("canceling statement due to
      // statement timeout") is not a sentence to hand a bettor, and this string
      // now renders on the home screen rather than a tab nobody opened.
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, []);

  // Re-created when pollMs changes (the user switched into or out of the live
  // segment), which restarts the interval at the new cadence.
  const startPolling = useCallback(() => {
    void refresh();
    timerRef.current = setInterval(() => void refresh(), pollMs);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      timerRef.current = null;
    };
  }, [refresh, pollMs]);

  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    [],
  );

  return { data, loading, error, refresh, date, startPolling };
}

/**
 * For a SCREEN, inside the navigator: polls while focused, stops on blur.
 */
export function useLivePicks(options?: { pollMs?: number }): LivePicksState {
  const { startPolling, ...state } = useLivePicksCore(options?.pollMs ?? LIVE_POLL_MS);
  useFocusEffect(startPolling);
  return state;
}

/**
 * For an app-root consumer mounted OUTSIDE NavigationContainer: polls for its
 * own lifetime. Never call useLivePicks there — see the header.
 */
export function useLivePicksUnfocused(options?: { pollMs?: number }): LivePicksState {
  const { startPolling, ...state } = useLivePicksCore(
    options?.pollMs ?? LIVE_IDLE_POLL_MS,
  );
  useEffect(startPolling, [startPolling]);
  return state;
}
