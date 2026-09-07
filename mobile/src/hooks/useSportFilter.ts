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
export type Sport = 'MLB' | 'WNBA' | 'NBA' | 'NFL' | 'NCAAF' | 'UFC' | 'GOLF' | 'NHL';

export const SPORTS: Sport[] = ['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF', 'UFC', 'GOLF', 'NHL'];

const STORAGE_KEY = 'sportFilter.selected';
const DEFAULT_SPORT: Sport = 'MLB';

const listeners = new Set<(s: Sport) => void>();
let cached: Sport | null = null;

async function load(): Promise<Sport> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    // Validate against SPORTS, never a hand-written list. This was six literals
    // that omitted NFL and NCAAF, so selecting either was silently reverted to
    // MLB on the next cold start — in September, the two sports in season. A
    // list that has to be edited alongside SPORTS is a list that will drift
    // again the next time a sport is added.
    const stored = SPORTS.includes(raw as Sport) ? (raw as Sport) : DEFAULT_SPORT;
    // RE-CHECK `cached` AFTER THE AWAIT, not just before it. A writer can land
    // while this getItem is in flight — setSportForVisit does exactly that when a
    // push deep-links to a sport-scoped board — and an unconditional assignment
    // here silently reverts it. The screens mount as children of
    // NavigationContainer, so their load() is always still outstanding when the
    // push router runs, which makes this the normal ordering rather than a
    // rare race: the user taps an NCAAF live push and lands on MLB.
    cached = cached ?? stored;
  } catch {
    cached = cached ?? DEFAULT_SPORT;
  }
  return cached;
}

/**
 * Set the sport from OUTSIDE React — the push router does this before
 * navigating to a sport-scoped board, and it runs from a notification callback
 * with no component around it. Same module store the hook drives, so every
 * mounted `useSportFilter` re-renders through the listener set.
 *
 * DELIBERATELY NOT PERSISTED. A notification is a visit, not a preference: one
 * NCAAF live push should not leave an MLB regular on NCAAF for good, on a
 * screen they will next open with no memory of the tap that changed it. The
 * user's own taps on the SportToggle still persist, because those are the
 * preference. `cached` is set so a screen mounting after this reads the new
 * sport, and listeners fire so the mounted ones re-render.
 */
export function setSportForVisit(v: Sport): void {
  cached = v;
  listeners.forEach((fn) => fn(v));
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
