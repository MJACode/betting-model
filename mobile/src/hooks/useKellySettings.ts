import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Global Kelly-sizing knobs.
 *
 * `multiplier` scales the server-side recommendation. The Python scorer
 * already applies tenth-Kelly (0.10), so `multiplier = 1.0` matches today's
 * behavior. 2.5 ~ quarter-Kelly, 5.0 ~ half-Kelly, 10.0 ~ full Kelly.
 *
 * `cap` is an optional max fraction of bankroll per bet. null = no cap.
 * The old hard 5% cap has been removed — the user is responsible for sizing.
 */
const MULTIPLIER_KEY = 'kelly.multiplier';
const CAP_KEY = 'kelly.cap';

export const MULTIPLIER_DEFAULT = 1.0;
export const MULTIPLIER_MIN = 0.25;
export const MULTIPLIER_MAX = 10.0;
export const MULTIPLIER_STEP = 0.25;

export const CAP_MIN = 0.005;
export const CAP_MAX = 1.0;

interface KellyState {
  multiplier: number;
  cap: number | null;
}

const listeners = new Set<(s: KellyState) => void>();
let cached: KellyState | null = null;

async function load(): Promise<KellyState> {
  if (cached) return cached;
  try {
    const [mRaw, cRaw] = await Promise.all([
      AsyncStorage.getItem(MULTIPLIER_KEY),
      AsyncStorage.getItem(CAP_KEY),
    ]);
    const m = mRaw != null ? parseFloat(mRaw) : NaN;
    const c = cRaw != null ? parseFloat(cRaw) : NaN;
    cached = {
      multiplier: Number.isFinite(m) && m > 0 ? m : MULTIPLIER_DEFAULT,
      cap: Number.isFinite(c) && c > 0 ? c : null,
    };
  } catch {
    cached = { multiplier: MULTIPLIER_DEFAULT, cap: null };
  }
  return cached;
}

async function saveMultiplier(v: number) {
  const next: KellyState = { ...(cached ?? { multiplier: MULTIPLIER_DEFAULT, cap: null }), multiplier: v };
  cached = next;
  await AsyncStorage.setItem(MULTIPLIER_KEY, String(v));
  listeners.forEach((fn) => fn(next));
}

async function saveCap(v: number | null) {
  const next: KellyState = { ...(cached ?? { multiplier: MULTIPLIER_DEFAULT, cap: null }), cap: v };
  cached = next;
  if (v == null) {
    await AsyncStorage.removeItem(CAP_KEY);
  } else {
    await AsyncStorage.setItem(CAP_KEY, String(v));
  }
  listeners.forEach((fn) => fn(next));
}

export function useKellySettings() {
  const [state, setState] = useState<KellyState>(
    cached ?? { multiplier: MULTIPLIER_DEFAULT, cap: null },
  );
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((s) => {
      if (!mounted) return;
      setState({ ...s });
      setReady(true);
    });
    const listener = (s: KellyState) => setState({ ...s });
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setMultiplier = useCallback((v: number) => {
    saveMultiplier(v).catch((err) => console.warn('[kelly] save multiplier failed', err));
  }, []);

  const setCap = useCallback((v: number | null) => {
    saveCap(v).catch((err) => console.warn('[kelly] save cap failed', err));
  }, []);

  return {
    multiplier: state.multiplier,
    cap: state.cap,
    setMultiplier,
    setCap,
    ready,
  };
}
