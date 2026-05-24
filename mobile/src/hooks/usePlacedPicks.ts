import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

const KEY = 'placedOverrides';

/**
 * AsyncStorage-backed map of pick_id -> boolean.
 *
 * Default: every pick is NOT placed. The user must explicitly mark each pick
 * they're actually betting. Only picks marked `true` here count toward
 * Performance ROI, the calendar, and per-day P&L.
 */
type OverrideMap = Record<string, boolean>;

const listeners = new Set<(m: OverrideMap) => void>();
let cached: OverrideMap | null = null;

async function load(): Promise<OverrideMap> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    cached = raw ? (JSON.parse(raw) as OverrideMap) : {};
  } catch {
    cached = {};
  }
  return cached;
}

async function save(map: OverrideMap) {
  cached = map;
  await AsyncStorage.setItem(KEY, JSON.stringify(map));
  listeners.forEach((fn) => fn(map));
}

export function isPlaced(
  pickId: number,
  _signalType: string,
  overrides: OverrideMap,
): boolean {
  return overrides[String(pickId)] === true;
}

export function usePlacedPicks() {
  const [overrides, setOverrides] = useState<OverrideMap>(cached ?? {});
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((m) => {
      if (!mounted) return;
      setOverrides({ ...m });
      setReady(true);
    });
    const listener = (m: OverrideMap) => setOverrides({ ...m });
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const togglePlaced = useCallback(
    (pickId: number, _signalType: string) => {
      const map = { ...(cached ?? {}) };
      const key = String(pickId);
      if (map[key]) {
        delete map[key];
      } else {
        map[key] = true;
      }
      save(map).catch((err) => console.warn('[placed] save failed', err));
    },
    [],
  );

  const reset = useCallback(() => {
    save({}).catch((err) => console.warn('[placed] reset failed', err));
  }, []);

  return { overrides, isPlaced, togglePlaced, reset, ready };
}

/** Count of picks the user has marked as placed. */
export function placedCount(overrides: OverrideMap): number {
  let n = 0;
  for (const v of Object.values(overrides)) if (v) n++;
  return n;
}
