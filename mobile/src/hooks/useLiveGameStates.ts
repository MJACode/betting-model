// useLiveGameStates — freshest in-play state (score, inning, outs, bases) for a
// day's games, so cards can show "2–0 · T5" next to the LIVE badge.
//
// Reads v_live_game_state_latest, which the live poller feeds every ~15s while
// games are in progress. Polls while the screen is focused and stops on blur.
// MLB only — that's the poller's coverage; other sports get no row and the
// cards fall back to the plain LIVE badge.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { reconcileLiveSnapshots } from '@/lib/format';
import { fetchLiveGameStates } from '@/lib/queries';
import type { LiveGameStateRow } from '@/types';

const POLL_INTERVAL_MS = 30_000;

/**
 * `dates` is one ET date, or the live-slate window from liveSlateDatesET(). The
 * Picks screen passes the window, because a game that kicked off late still
 * carries yesterday's game_date after midnight ET — and its score and clock
 * would otherwise stop updating exactly when the game is most live.
 */
export function useLiveGameStates(dates: string | string[]) {
  const [rows, setRows] = useState<LiveGameStateRow[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  // Keyed on the VALUE, not the array identity: a caller that builds the list
  // inline would otherwise tear down and restart the poll on every render.
  const key = Array.isArray(dates) ? dates.join(',') : dates;

  const refresh = useCallback(async () => {
    try {
      setRows(await fetchLiveGameStates(key.split(',')));
    } catch {
      // Enrichment only — a failure must never blank the board. Keep the last
      // known state; a stale row is dropped by the freshness filter below.
    }
  }, [key]);

  useFocusEffect(
    useCallback(() => {
      void refresh();
      timerRef.current = setInterval(() => void refresh(), POLL_INTERVAL_MS);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
      };
    }, [refresh]),
  );

  // Re-evaluate freshness whenever new rows land (and on each poll tick, since
  // every tick sets state), so a dead poller decays out of the UI on its own.
  const byGame = useMemo(() => reconcileLiveSnapshots(rows, Date.now()), [rows]);

  return { byGame, refresh };
}

/**
 * Single-game variant for the detail screen — same view, one fetch, no polling
 * loop beyond the standard interval.
 */
export function useLiveGameState(date: string | null, gameId: string | null) {
  const [row, setRow] = useState<LiveGameStateRow | null>(null);

  const refresh = useCallback(async () => {
    if (!date || !gameId) {
      setRow(null);
      return;
    }
    try {
      // Reconcile over the whole slate, not just this game — the "poller is
      // alive but this game went quiet" signal needs the other games for
      // context, and the detail screen must agree with the card.
      const all = await fetchLiveGameStates(date);
      setRow(reconcileLiveSnapshots(all, Date.now()).get(gameId) ?? null);
    } catch {
      // Enrichment only.
    }
  }, [date, gameId]);

  useEffect(() => {
    void refresh();
    const timer = setInterval(() => void refresh(), POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [refresh]);

  return row;
}
