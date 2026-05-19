import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

const KEY = 'bankroll';
const DEFAULT = 1000;

const listeners = new Set<(v: number) => void>();
let cached: number | null = null;

async function load(): Promise<number> {
  if (cached != null) return cached;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    cached = raw ? parseFloat(raw) : DEFAULT;
  } catch {
    cached = DEFAULT;
  }
  return cached ?? DEFAULT;
}

async function save(value: number) {
  cached = value;
  await AsyncStorage.setItem(KEY, String(value));
  listeners.forEach((fn) => fn(value));
}

export function useBankroll() {
  const [value, setValue] = useState<number>(cached ?? DEFAULT);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setValue(v);
      setReady(true);
    });
    const listener = (v: number) => setValue(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setBankroll = useCallback((v: number) => {
    save(v).catch((err) => console.warn('[bankroll] save failed', err));
  }, []);

  return { bankroll: value, setBankroll, ready };
}
