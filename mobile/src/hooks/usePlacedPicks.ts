import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';
import type { Pick, SignalType } from '@/types';

/**
 * AsyncStorage-backed map of pick_id -> PlacedBet.
 *
 * Default: every pick is NOT placed. The user must explicitly mark each pick
 * they're actually betting. Only picks present here count toward Performance
 * ROI, the calendar, and per-day P&L.
 *
 * Each entry stores the user's stake (defaults to the Kelly recommendation
 * at toggle-on time, user-editable thereafter) plus a snapshot of the pick
 * so the My Bets view still renders if the server pick is later removed.
 */
export interface PlacedBetSnapshot {
  pickLabel: string;
  modelId: string;
  signalType: SignalType;
  gameId: string;
  gameDate: string;
  dkOdds: number | null;
  kellyFraction: number;
}

export interface PlacedBet {
  amount: number;        // user-editable dollars; 0 = "tracking, no stake"
  placedAt: number;      // ms epoch at first toggle-on
  updatedAt: number;
  snapshot: PlacedBetSnapshot | null; // null for legacy migrated entries
}

export type PlacedMap = Record<string, PlacedBet>;

const KEY = 'placedBets.v2';
const LEGACY_KEY = 'placedOverrides';

const listeners = new Set<(m: PlacedMap) => void>();
let cached: PlacedMap | null = null;

async function migrateLegacy(): Promise<PlacedMap> {
  try {
    const raw = await AsyncStorage.getItem(LEGACY_KEY);
    if (!raw) return {};
    const legacy = JSON.parse(raw) as Record<string, boolean>;
    const now = Date.now();
    const out: PlacedMap = {};
    for (const [id, on] of Object.entries(legacy)) {
      if (on === true) {
        out[id] = { amount: 0, placedAt: now, updatedAt: now, snapshot: null };
      }
    }
    return out;
  } catch {
    return {};
  }
}

async function load(): Promise<PlacedMap> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (raw) {
      cached = JSON.parse(raw) as PlacedMap;
      return cached;
    }
    const migrated = await migrateLegacy();
    cached = migrated;
    if (Object.keys(migrated).length > 0) {
      await AsyncStorage.setItem(KEY, JSON.stringify(migrated));
    }
  } catch {
    cached = {};
  }
  return cached;
}

async function save(map: PlacedMap) {
  cached = map;
  await AsyncStorage.setItem(KEY, JSON.stringify(map));
  listeners.forEach((fn) => fn(map));
}

function snapshotOf(pick: Pick): PlacedBetSnapshot {
  return {
    pickLabel: pick.pick_label,
    modelId: pick.model_id,
    signalType: pick.signal_type,
    gameId: pick.game_id,
    gameDate: pick.game_date,
    dkOdds: pick.dk_odds,
    kellyFraction: pick.kelly_fraction,
  };
}

/**
 * Whether a pick is being tracked. The second arg used to be `signal_type`
 * for legacy callers; it is ignored — tracking is purely set-membership now.
 */
export function isPlaced(
  pickId: number,
  _signalType: unknown,
  overrides: PlacedMap,
): boolean {
  return Object.prototype.hasOwnProperty.call(overrides, String(pickId));
}

export function usePlacedPicks() {
  const [overrides, setOverrides] = useState<PlacedMap>(cached ?? {});
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((m) => {
      if (!mounted) return;
      setOverrides({ ...m });
      setReady(true);
    });
    const listener = (m: PlacedMap) => setOverrides({ ...m });
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const togglePlaced = useCallback(
    (pickId: number, pick: Pick, defaultAmount: number) => {
      const map = { ...(cached ?? {}) };
      const key = String(pickId);
      if (map[key]) {
        delete map[key];
      } else {
        const now = Date.now();
        map[key] = {
          amount: defaultAmount,
          placedAt: now,
          updatedAt: now,
          snapshot: snapshotOf(pick),
        };
      }
      save(map).catch((err) => console.warn('[placed] save failed', err));
    },
    [],
  );

  const setBetAmount = useCallback((pickId: number, amount: number) => {
    const map = { ...(cached ?? {}) };
    const key = String(pickId);
    const existing = map[key];
    if (!existing) return;
    const safe = Number.isFinite(amount) && amount >= 0 ? amount : 0;
    map[key] = { ...existing, amount: safe, updatedAt: Date.now() };
    save(map).catch((err) => console.warn('[placed] save amount failed', err));
  }, []);

  const getPlacedBet = useCallback((pickId: number): PlacedBet | undefined => {
    return (cached ?? {})[String(pickId)];
  }, []);

  const reset = useCallback(() => {
    save({}).catch((err) => console.warn('[placed] reset failed', err));
    AsyncStorage.removeItem(LEGACY_KEY).catch(() => {});
  }, []);

  return { overrides, isPlaced, togglePlaced, setBetAmount, getPlacedBet, reset, ready };
}

/** Count of picks the user has marked as placed. */
export function placedCount(overrides: PlacedMap): number {
  return Object.keys(overrides).length;
}
