// useLiveGameStates — freshest in-play state (score, inning, outs, bases) for a
// day's games, so cards can show "2–0 · T5" next to the LIVE badge.
//
// Reads v_live_game_state_latest, which the live poller feeds every ~15s while
// games are in progress. Polls while the screen is focused and stops on blur.
// MLB only — that's the poller's coverage; other sports get no row and the
// cards fall back to the plain LIVE badge.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { fetchLiveGameStates } from '@/lib/queries';
import type { LiveGameStateRow } from '@/types';

const POLL_INTERVAL_MS = 30_000;

/**
 * Snapshots older than this are dropped rather than displayed. The poller
 * writes every ~15s while a game is live, so a gap this large means it died or
 * the slate ended — better to show a plain LIVE badge than a frozen inning.
 * (The backend scorer uses a tighter 5-minute guard, config.LIVE_STATE_MAX_AGE_SEC;
 * display can tolerate more lag than a bet decision.)
 */
const MAX_AGE_MS = 15 * 60_000;

function isFresh(row: LiveGameStateRow, now: number): boolean {
  const ts = new Date(row.snapshot_at).getTime();
  if (Number.isNaN(ts)) return false;
  return now - ts <= MAX_AGE_MS;
}

export function useLiveGameStates(date: string) {
  const [rows, setRows] = useState<LiveGameStateRow[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const refresh = useCallback(async () => {
    try {
      setRows(await fetchLiveGameStates(date));
    } catch {
      // Enrichment only — a failure must never blank the board. Keep the last
      // known state; a stale row is dropped by the freshness filter below.
    }
  }, [date]);

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
  const byGame = useMemo(() => {
    const now = Date.now();
    const map = new Map<string, LiveGameStateRow>();
    for (const row of rows) {
      if (isFresh(row, now)) map.set(row.game_id, row);
    }
    return map;
  }, [rows]);

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
      const all = await fetchLiveGameStates(date);
      const match = all.find((r) => r.game_id === gameId) ?? null;
      setRow(match && isFresh(match, Date.now()) ? match : null);
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
