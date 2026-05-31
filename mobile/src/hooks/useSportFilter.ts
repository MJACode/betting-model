import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Global sport selector.
 *
 * Keeps each sport's picks fully separate in the UI: the Picks / Signals / Live
 * screens show ONLY the selected sport, never a mix. Default is MLB so existing
 * behavior is unchanged. Persisted to AsyncStorage and shared across screens via
 * a module-level store + listeners (same pattern as useKellySettings).
 */
export type Sport = 'MLB' | 'WNBA';

export const SPORTS: Sport[] = ['MLB', 'WNBA'];

const STORAGE_KEY = 'sportFilter.selected';
const DEFAULT_SPORT: Sport = 'MLB';

const listeners = new Set<(s: Sport) => void>();
let cached: Sport | null = null;

async function load(): Promise<Sport> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw === 'WNBA' || raw === 'MLB' ? (raw as Sport) : DEFAULT_SPORT;
  } catch {
    cached = DEFAULT_SPORT;
  }
  return cached;
}

async function save(v: Sport) {
  cached = v;
  listeners.forEach((fn) => fn(v));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, v);
  } catch (err) {
    console.warn('[sportFilter] save failed', err);
  }
}

export function useSportFilter() {
  const [sport, setSportState] = useState<Sport>(cached ?? DEFAULT_SPORT);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((s) => {
      if (!mounted) return;
      setSportState(s);
      setReady(true);
    });
    const listener = (s: Sport) => setSportState(s);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setSport = useCallback((v: Sport) => {
    save(v).catch((err) => console.warn('[sportFilter] set failed', err));
  }, []);

  return { sport, setSport, ready };
}
