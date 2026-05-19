import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

const KEY = 'placedOverrides';

/**
 * AsyncStorage-backed map of pick_id -> boolean.
 *
 * Default semantics (not stored): BET signal => placed; AVOID/NONE => not placed.
 * This store contains user OVERRIDES of the default. A pick_id appearing here
 * with `true` means the user explicitly placed it (rare for non-BET picks);
 * a pick_id appearing with `false` means the user explicitly chose not to.
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
  signalType: string,
  overrides: OverrideMap,
): boolean {
  const key = String(pickId);
  if (Object.prototype.hasOwnProperty.call(overrides, key)) {
    return overrides[key]!;
  }
  return signalType === 'BET';
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
    (pickId: number, signalType: string) => {
      const current = isPlaced(pickId, signalType, cached ?? {});
      const next = !current;
      const map = { ...(cached ?? {}) };
      const defaultPlaced = signalType === 'BET';
      if (next === defaultPlaced) {
        delete map[String(pickId)];
      } else {
        map[String(pickId)] = next;
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
