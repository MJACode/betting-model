import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Global betslip — the user's manual selections.
 *
 * Holds an ORDERED list of STABLE keys (game_id|model_id|player_id — see
 * slipKeyForPick) the user tapped "Add to betslip" on (from the Stats tab, the
 * pick cards, or the pick detail screen). The Betslip tab's "Your slip" mode
 * resolves these keys against today's live picks and packages them into one
 * parlay. Persisted to AsyncStorage and shared across screens via a module-level
 * store + listeners (same pattern as useSportFilter / useKellySettings). Custom
 * hand-entered legs are NOT stored here — they live in the Parlay screen's
 * session state, same as auto mode.
 *
 * IMPORTANT: the slip stores stable keys, NOT picks.pick_id. The picks table is
 * delete+rescored on every hourly refresh, so pick_id churns — a slip keyed on
 * pick_id would silently go stale within the hour (badge stuck on a count while
 * nothing resolves, new adds rotting on the next refresh). The stable key
 * survives the rescore because the new pick row carries the same
 * game/model/player. v1 stored pick_ids; v2 stores keys, so the old store is
 * abandoned (any stuck v1 count is exactly the bug we're fixing).
 */

const STORAGE_KEY = 'parlaySlip.keys.v2';
const LEGACY_KEY = 'parlaySlip.pickIds.v1';

const listeners = new Set<(keys: string[]) => void>();
let cached: string[] | null = null;

function sanitize(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: string[] = [];
  for (const v of raw) {
    if (typeof v !== 'string' || v.length === 0) continue;
    if (!seen.has(v)) {
      seen.add(v);
      out.push(v);
    }
  }
  return out;
}

async function load(): Promise<string[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw ? sanitize(JSON.parse(raw)) : [];
  } catch {
    cached = [];
  }
  // Drop the abandoned v1 (numeric pick_id) store so its stale count can't
  // resurface. Best-effort — ignore failures.
  AsyncStorage.removeItem(LEGACY_KEY).catch(() => {});
  return cached;
}

async function save(keys: string[]) {
  cached = keys;
  listeners.forEach((fn) => fn(keys));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(keys));
  } catch (err) {
    console.warn('[parlaySlip] save failed', err);
  }
}

export function useParlaySlip() {
  const [keys, setKeys] = useState<string[]>(cached ?? []);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setKeys(v);
      setReady(true);
    });
    const listener = (v: string[]) => setKeys(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const has = useCallback((key: string) => (cached ?? keys).includes(key), [keys]);

  const add = useCallback((key: string) => {
    const cur = cached ?? [];
    if (cur.includes(key)) return;
    save([...cur, key]).catch((err) => console.warn('[parlaySlip] add failed', err));
  }, []);

  const remove = useCallback((key: string) => {
    const cur = cached ?? [];
    if (!cur.includes(key)) return;
    save(cur.filter((x) => x !== key)).catch((err) => console.warn('[parlaySlip] remove failed', err));
  }, []);

  const toggle = useCallback((key: string) => {
    const cur = cached ?? [];
    const next = cur.includes(key) ? cur.filter((x) => x !== key) : [...cur, key];
    save(next).catch((err) => console.warn('[parlaySlip] toggle failed', err));
  }, []);

  const clear = useCallback(() => {
    save([]).catch((err) => console.warn('[parlaySlip] clear failed', err));
  }, []);

  return { keys, count: keys.length, ready, has, add, remove, toggle, clear };
}
