import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';

import { getDeviceId } from './useDeviceId';
import { trackBet, untrackBet } from '@/lib/queries';
import type { Pick } from '@/types';

/**
 * Track-a-bet state.
 *
 * Two kinds of tracked bet, kept in separate on-device stores (module store +
 * listeners, same pattern as useParlaySlip / useSportFilter — instant UI, no
 * server read):
 *
 *  1. Pre-game / prop / settled picks — keyed on `pick_id`. Picks lock (game
 *     markets at 6am, props at first signal), so pick_id is stable for the day.
 *     Tapping also writes a `tracked_bets` row (device-scoped) that the
 *     pipeline's line-change notifier watches. Graded on the Performance tab by
 *     hydrating those pick_ids.
 *
 *  2. LIVE (in-play) picks — keyed on a STABLE composite key
 *     `game_id|model_id|pick_side`, NOT pick_id. Live picks are delete+rescored
 *     every pass, so their pick_id churns; keying on the proposition survives
 *     that. We store a light snapshot so the Performance tab can render + grade
 *     the row from the model's settled live pick for that side, even though the
 *     exact pick row it saw at tap time is long gone. No `tracked_bets` DB write
 *     for live picks — the line-change notifier is game-level pre-game only and
 *     would ignore them.
 */
const STORAGE_KEY = 'trackedBets.pickIds.v1';
const LIVE_STORAGE_KEY = 'trackedBets.live.v1';

/** Stable identity for a live pick: proposition, not the churning pick_id. */
export function liveTrackKey(pick: Pick): string {
  return `${pick.game_id}|${pick.model_id}|${pick.pick_side}`;
}

/** Light snapshot persisted when a live bet is tracked (the pick row churns). */
export interface LiveTrackSnapshot {
  key: string;
  game_id: string;
  model_id: string;
  pick_side: string;
  pick_label: string;
  sport: string;
  game_date: string;
  dk_odds: number | null;
  scored_line: number | null;
  tracked_at: string;
}

function snapshotFromPick(pick: Pick): LiveTrackSnapshot {
  return {
    key: liveTrackKey(pick),
    game_id: pick.game_id,
    model_id: pick.model_id,
    pick_side: pick.pick_side,
    pick_label: pick.pick_label,
    sport: pick.sport,
    game_date: pick.game_date,
    dk_odds: pick.dk_odds,
    scored_line: pick.scored_line,
    tracked_at: new Date().toISOString(),
  };
}

// ── pick_id store (non-live) ──────────────────────────────────────────────────
const idListeners = new Set<(ids: number[]) => void>();
let idCache: number[] | null = null;

function sanitizeIds(raw: unknown): number[] {
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

async function loadIds(): Promise<number[]> {
  if (idCache) return idCache;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    idCache = raw ? sanitizeIds(JSON.parse(raw)) : [];
  } catch {
    idCache = [];
  }
  return idCache;
}

async function persistIds(ids: number[]) {
  idCache = ids;
  idListeners.forEach((fn) => fn(ids));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch (err) {
    console.warn('[trackedBets] save failed', err);
  }
}

// ── live snapshot store ───────────────────────────────────────────────────────
const liveListeners = new Set<(snaps: LiveTrackSnapshot[]) => void>();
let liveCache: LiveTrackSnapshot[] | null = null;

function sanitizeLive(raw: unknown): LiveTrackSnapshot[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: LiveTrackSnapshot[] = [];
  for (const v of raw) {
    if (
      v &&
      typeof v === 'object' &&
      typeof (v as LiveTrackSnapshot).key === 'string' &&
      typeof (v as LiveTrackSnapshot).game_id === 'string' &&
      !seen.has((v as LiveTrackSnapshot).key)
    ) {
      seen.add((v as LiveTrackSnapshot).key);
      out.push(v as LiveTrackSnapshot);
    }
  }
  return out;
}

async function loadLive(): Promise<LiveTrackSnapshot[]> {
  if (liveCache) return liveCache;
  try {
    const raw = await AsyncStorage.getItem(LIVE_STORAGE_KEY);
    liveCache = raw ? sanitizeLive(JSON.parse(raw)) : [];
  } catch {
    liveCache = [];
  }
  return liveCache;
}

async function persistLive(snaps: LiveTrackSnapshot[]) {
  liveCache = snaps;
  liveListeners.forEach((fn) => fn(snaps));
  try {
    await AsyncStorage.setItem(LIVE_STORAGE_KEY, JSON.stringify(snaps));
  } catch (err) {
    console.warn('[trackedBets] live save failed', err);
  }
}

export function useTrackedBets() {
  const [ids, setIds] = useState<number[]>(idCache ?? []);
  const [liveSnapshots, setLiveSnapshots] = useState<LiveTrackSnapshot[]>(liveCache ?? []);

  useEffect(() => {
    let mounted = true;
    idListeners.add(setIds);
    liveListeners.add(setLiveSnapshots);
    if (idCache == null) {
      void loadIds().then((loaded) => {
        if (mounted) setIds(loaded);
      });
    }
    if (liveCache == null) {
      void loadLive().then((loaded) => {
        if (mounted) setLiveSnapshots(loaded);
      });
    }
    return () => {
      mounted = false;
      idListeners.delete(setIds);
      liveListeners.delete(setLiveSnapshots);
    };
  }, []);

  const isTracked = (pick: Pick): boolean =>
    pick.is_live
      ? liveSnapshots.some((s) => s.key === liveTrackKey(pick))
      : ids.includes(pick.pick_id);

  /** Start tracking. Live → local snapshot only; else → local + DB row. */
  const track = (pick: Pick) => {
    if (pick.is_live) {
      const key = liveTrackKey(pick);
      if (liveSnapshots.some((s) => s.key === key)) return;
      void persistLive([...liveSnapshots, snapshotFromPick(pick)]);
      return;
    }
    if (ids.includes(pick.pick_id)) return;
    void persistIds([...ids, pick.pick_id]);
    void getDeviceId()
      .then((deviceId) => trackBet(deviceId, pick))
      .catch((err) => console.warn('[trackedBets] trackBet failed', err));
  };

  const untrack = (pickId: number) => {
    if (!ids.includes(pickId)) return;
    void persistIds(ids.filter((id) => id !== pickId));
    void getDeviceId()
      .then((deviceId) => untrackBet(deviceId, pickId))
      .catch((err) => console.warn('[trackedBets] untrackBet failed', err));
  };

  const untrackLiveKey = (key: string) => {
    if (!liveSnapshots.some((s) => s.key === key)) return;
    void persistLive(liveSnapshots.filter((s) => s.key !== key));
  };

  /** Untrack from a pick object (branches live vs pick_id). */
  const untrackPick = (pick: Pick) => {
    if (pick.is_live) untrackLiveKey(liveTrackKey(pick));
    else untrack(pick.pick_id);
  };

  const toggle = (pick: Pick) => (isTracked(pick) ? untrackPick(pick) : track(pick));

  return {
    ids,
    liveSnapshots,
    count: ids.length + liveSnapshots.length,
    isTracked,
    track,
    untrack,
    untrackLiveKey,
    untrackPick,
    toggle,
  };
}
