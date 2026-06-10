import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Global parlay "slip" — the user's manual selections.
 *
 * Holds an ORDERED list of pick_ids the user tapped "Add to play" on (from the
 * Stats tab, the pick cards, or the pick detail screen). The Parlay tab's
 * "Build your own" mode resolves these ids against today's live picks and
 * packages them into one parlay. Persisted to AsyncStorage and shared across
 * screens via a module-level store + listeners (same pattern as useSportFilter
 * / useKellySettings). Custom hand-entered legs are NOT stored here — they live
 * in the Parlay screen's session state, same as auto mode.
 */

const STORAGE_KEY = 'parlaySlip.pickIds.v1';

const listeners = new Set<(ids: number[]) => void>();
let cached: number[] | null = null;

function sanitize(raw: unknown): number[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<number>();
  const out: number[] = [];
  for (const v of raw) {
    const n = typeof v === 'number' ? v : Number(v);
    if (Number.isFinite(n) && !seen.has(n)) {
      seen.add(n);
      out.push(n);
    }
  }
  return out;
}

async function load(): Promise<number[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw ? sanitize(JSON.parse(raw)) : [];
  } catch {
    cached = [];
  }
  return cached;
}

async function save(ids: number[]) {
  cached = ids;
  listeners.forEach((fn) => fn(ids));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch (err) {
    console.warn('[parlaySlip] save failed', err);
  }
}

export function useParlaySlip() {
  const [ids, setIds] = useState<number[]>(cached ?? []);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setIds(v);
      setReady(true);
    });
    const listener = (v: number[]) => setIds(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const has = useCallback((id: number) => (cached ?? ids).includes(id), [ids]);

  const add = useCallback((id: number) => {
    const cur = cached ?? [];
    if (cur.includes(id)) return;
    save([...cur, id]).catch((err) => console.warn('[parlaySlip] add failed', err));
  }, []);

  const remove = useCallback((id: number) => {
    const cur = cached ?? [];
    if (!cur.includes(id)) return;
    save(cur.filter((x) => x !== id)).catch((err) => console.warn('[parlaySlip] remove failed', err));
  }, []);

  const toggle = useCallback((id: number) => {
    const cur = cached ?? [];
    const next = cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id];
    save(next).catch((err) => console.warn('[parlaySlip] toggle failed', err));
  }, []);

  const clear = useCallback(() => {
    save([]).catch((err) => console.warn('[parlaySlip] clear failed', err));
  }, []);

  return { ids, count: ids.length, ready, has, add, remove, toggle, clear };
}
