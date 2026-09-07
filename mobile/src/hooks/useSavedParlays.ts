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

/**
 * Which saved parlay the betslip is currently an EDIT of — a module store, not
 * screen state, because the Betslip screen is POPPED mid-edit on the commonest
 * gesture there is: "Find players to add" navigates to the tabs (which pops
 * it), and adding a leg pushes a FRESH Betslip. Held in component state the
 * binding died on that trip, so "Edit in builder → add a player → save" filed
 * a duplicate again — the exact bug it was meant to fix (UX review).
 *
 * Cleared when the slip empties or is cleared: a slip with nothing left in it
 * is no longer that parlay, and the next save is a new one.
 */
const editingListeners = new Set<(id: string | null) => void>();
let editingId: string | null = null;

export function setEditingParlayId(id: string | null): void {
  if (editingId === id) return;
  editingId = id;
  editingListeners.forEach((fn) => fn(id));
}

/**
 * Hand-entered custom legs — a module store for the SAME reason editingId is
 * one: the Betslip screen is popped out from under them.
 *
 * They were screen state, so "Find players to add" (which navigates to the
 * tabs, popping this screen) already destroyed every manual leg and the
 * half-typed one with it. A push deep-link to a board does the same thing, and
 * a notification is not a gesture the user can predict — they tap "3 new BET
 * signals" and their hand-built parlay is gone, with no warning and no undo
 * (UX review, 2026-09-06). Session-scoped still: cleared with the slip, and
 * never persisted.
 */
const customListeners = new Set<(legs: ParlayLeg[]) => void>();
let manualCustomLegs: ParlayLeg[] = [];

export function setManualCustomLegs(
  update: ParlayLeg[] | ((prev: ParlayLeg[]) => ParlayLeg[]),
): void {
  manualCustomLegs = typeof update === 'function' ? update(manualCustomLegs) : update;
  customListeners.forEach((fn) => fn(manualCustomLegs));
}

export function useManualCustomLegs(): ParlayLeg[] {
  const [legs, setLegs] = useState<ParlayLeg[]>(manualCustomLegs);
  useEffect(() => {
    const listener = (v: ParlayLeg[]) => setLegs(v);
    customListeners.add(listener);
    setLegs(manualCustomLegs); // a mount after the setter ran still sees them
    return () => {
      customListeners.delete(listener);
    };
  }, []);
  return legs;
}

export function useEditingParlayId(): string | null {
  const [id, setId] = useState<string | null>(editingId);
  useEffect(() => {
    const listener = (v: string | null) => setId(v);
    editingListeners.add(listener);
    setId(editingId); // a mount after the setter ran still sees it
    return () => {
      editingListeners.delete(listener);
    };
  }, []);
  return id;
}

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
