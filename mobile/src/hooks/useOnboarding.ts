import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * First-run onboarding flag. Drives the one-time expectations walkthrough that
 * sets an honest ROI band, explains variance / cold streaks, and frames
 * "no-pick days" and responsible-gambling limits BEFORE the user starts betting
 * — the single biggest defense against the hype→cold-streak→1-star churn that
 * sinks tout/AI-picks apps. Re-runnable from Settings.
 *
 * Module-store + AsyncStorage, same pattern as useSportFilter.
 */
const STORAGE_KEY = 'onboarding.seen.v1';

const listeners = new Set<(seen: boolean) => void>();
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

async function persist(seen: boolean) {
  cached = seen;
  listeners.forEach((fn) => fn(seen));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, seen ? '1' : '0');
  } catch (err) {
    console.warn('[onboarding] save failed', err);
  }
}

export function useOnboarding() {
  const [seen, setSeen] = useState<boolean>(cached ?? true); // assume seen until loaded (no flash)
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setSeen(v);
      setReady(true);
    });
    const listener = (v: boolean) => setSeen(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const markSeen = useCallback(() => {
    void persist(true);
  }, []);
  const replay = useCallback(() => {
    void persist(false);
  }, []);

  return { seen, ready, markSeen, replay };
}
