import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Push-notification opt-in flag. Mirrors the useOnboarding pattern
 * (module-store + AsyncStorage + cross-component listeners).
 *
 * When enabled, usePushNotifications requests permission and registers
 * the Expo push token. When disabled, the token row is marked
 * enabled=false so the backend stops sending.
 */
const STORAGE_KEY = 'push.optIn.v1';

const listeners = new Set<(v: boolean) => void>();
let cached: boolean | null = null;

async function load(): Promise<boolean> {
  if (cached != null) return cached;
  try {
    cached = (await AsyncStorage.getItem(STORAGE_KEY)) === '1';
  } catch {
    cached = false;
  }
  return cached;
}

async function persist(enabled: boolean) {
  cached = enabled;
  listeners.forEach((fn) => fn(enabled));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, enabled ? '1' : '0');
  } catch (err) {
    console.warn('[pushOptIn] save failed', err);
  }
}

export function usePushOptIn() {
  const [enabled, setEnabled] = useState<boolean>(cached ?? false);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setEnabled(v);
      setReady(true);
    });
    const listener = (v: boolean) => setEnabled(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setOptIn = useCallback((v: boolean) => {
    void persist(v);
  }, []);

  return { enabled, ready, setOptIn };
}
