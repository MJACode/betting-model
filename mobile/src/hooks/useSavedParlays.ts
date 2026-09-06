import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { toSavedParlay, updateSavedParlay, type ParlayLeg, type SavedParlay } from '@/lib/parlay';

/**
 * Saved parlays — self-contained snapshots the user keeps to revisit and bet
 * later. Persisted to AsyncStorage and shared across screens via a module-level
 * store + listeners (same pattern as useParlaySlip / useKellySettings). Newest
 * first. Snapshots are denormalized (see SavedParlay) so they survive today's
 * picks changing.
 */

const STORAGE_KEY = 'savedParlays.v1';

const listeners = new Set<(items: SavedParlay[]) => void>();
let cached: SavedParlay[] | null = null;

function sanitize(raw: unknown): SavedParlay[] {
  if (!Array.isArray(raw)) return [];
  const out: SavedParlay[] = [];
  for (const v of raw) {
    if (
      v &&
      typeof v === 'object' &&
      typeof (v as SavedParlay).id === 'string' &&
      Array.isArray((v as SavedParlay).legs)
    ) {
      out.push(v as SavedParlay);
    }
  }
  return out;
}

async function load(): Promise<SavedParlay[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    cached = raw ? sanitize(JSON.parse(raw)) : [];
  } catch {
    cached = [];
  }
  return cached;
}

async function persist(items: SavedParlay[]) {
  cached = items;
  listeners.forEach((fn) => fn(items));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  } catch (err) {
    console.warn('[savedParlays] save failed', err);
  }
}

export function useSavedParlays() {
  const [items, setItems] = useState<SavedParlay[]>(cached ?? []);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((v) => {
      if (!mounted) return;
      setItems(v);
      setReady(true);
    });
    const listener = (v: SavedParlay[]) => setItems(v);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const save = useCallback((legs: ParlayLeg[], sport: string): SavedParlay => {
    const parlay = toSavedParlay(legs, sport);
    const cur = cached ?? [];
    persist([parlay, ...cur]).catch((err) => console.warn('[savedParlays] save failed', err));
    return parlay;
  }, []);

  /**
   * Write an edited leg set back over an existing save — the other half of
   * "Edit in builder". Without it the builder's only verb was INSERT, so
   * editing a saved parlay left the original standing beside its replacement.
   * The save keeps its id, its created time and its place in the list; only
   * the legs (and `updatedAt`) change. Returns null when the id is gone —
   * deleted from the list while the builder was open — and the caller inserts
   * instead, so an edit can never be silently dropped.
   */
  const update = useCallback((id: string, legs: ParlayLeg[], sport: string): SavedParlay | null => {
    const cur = cached ?? [];
    const idx = cur.findIndex((p) => p.id === id);
    if (idx < 0) return null;
    const next = updateSavedParlay(cur[idx], legs, sport);
    const items = [...cur];
    items[idx] = next;
    persist(items).catch((err) => console.warn('[savedParlays] update failed', err));
    return next;
  }, []);

  const remove = useCallback((id: string) => {
    const cur = cached ?? [];
    persist(cur.filter((p) => p.id !== id)).catch((err) =>
      console.warn('[savedParlays] remove failed', err),
    );
  }, []);

  /** Re-insert a previously-removed parlay (Undo), restoring newest-first order. */
  const restore = useCallback((parlay: SavedParlay) => {
    const cur = cached ?? [];
    if (cur.some((p) => p.id === parlay.id)) return; // already present
    const next = [...cur, parlay].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
    persist(next).catch((err) => console.warn('[savedParlays] restore failed', err));
  }, []);

  const clear = useCallback(() => {
    persist([]).catch((err) => console.warn('[savedParlays] clear failed', err));
  }, []);

  return { items, count: items.length, ready, save, update, remove, restore, clear };
}
