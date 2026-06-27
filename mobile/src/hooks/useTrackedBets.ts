import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';

import { getDeviceId } from './useDeviceId';
import { trackBet, untrackBet } from '@/lib/queries';
import type { Pick } from '@/types';

/**
 * Track-a-bet state.
 *
 * The user taps the Track icon on a (game-level) bet to be notified when the DK
 * line moves big before game time. The "tracked" icon state lives on-device
 * (AsyncStorage set of pick_ids, shared via a module store + listeners — same
 * pattern as useParlaySlip / useSportFilter), so the UI is instant and needs no
 * server read. Tapping also writes/deletes a `tracked_bets` row (keyed by this
 * device's id) that the pipeline's line-change notifier watches.
 *
 * Picks lock now (game markets at 7am), so pick_id is stable for the day — safe
 * to key on. The DB write is best-effort: the local set is the source of truth
 * for the icon, and a failed write just means no alert (logged, not surfaced).
 */
const STORAGE_KEY = 'trackedBets.pickIds.v1';

const listeners = new Set<(ids: number[]) => void>();
let cached: number[] | null = null;

function sanitize(raw: unknown): number[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<number>();
  const out: number[] = [];
  for (const v of raw) {
    if (typeof v === 'number' && Number.isFinite(v) && !seen.has(v)) {
      seen.add(v);
      out.push(v);
    }
  }
  return out;
}

async function load(): Promise<number[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw ? sanitize(JSON.parse(raw)) : [];
  } catch {
    cached = [];
  }
  return cached;
}

async function persist(ids: number[]) {
  cached = ids;
  listeners.forEach((fn) => fn(ids));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch (err) {
    console.warn('[trackedBets] save failed', err);
  }
}

export function useTrackedBets() {
  const [ids, setIds] = useState<number[]>(cached ?? []);

  useEffect(() => {
    let mounted = true;
    listeners.add(setIds);
    if (cached == null) {
      void load().then((loaded) => {
        if (mounted) setIds(loaded);
      });
    }
    return () => {
      mounted = false;
      listeners.delete(setIds);
    };
  }, []);

  const isTracked = (pickId: number) => ids.includes(pickId);

  /** Start tracking — optimistic local add, best-effort DB write. */
  const track = (pick: Pick) => {
    if (ids.includes(pick.pick_id)) return;
    void persist([...ids, pick.pick_id]);
    void getDeviceId()
      .then((deviceId) => trackBet(deviceId, pick))
      .catch((err) => console.warn('[trackedBets] trackBet failed', err));
  };

  const untrack = (pickId: number) => {
    if (!ids.includes(pickId)) return;
    void persist(ids.filter((id) => id !== pickId));
    void getDeviceId()
      .then((deviceId) => untrackBet(deviceId, pickId))
      .catch((err) => console.warn('[trackedBets] untrackBet failed', err));
  };

  const toggle = (pick: Pick) => (isTracked(pick.pick_id) ? untrack(pick.pick_id) : track(pick));

  return { ids, count: ids.length, isTracked, track, untrack, toggle };
}
