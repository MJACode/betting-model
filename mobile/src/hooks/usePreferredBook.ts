import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { BETTABLE_BOOKS, MODEL_BOOK, type BookKey } from '@/lib/markets';

/**
 * The member's own sportsbook. TWO readers, and the difference between them is
 * deliberate (Matt, 2026-09-04 — this scope has been reversed twice in three
 * days, so read all of it before narrowing it again):
 *
 *   1. THE STATS BOARD'S LINE, with NO fallback. Their book or nothing: a
 *      player FanDuel has not priced shows no line, because a DraftKings price
 *      standing in under a FanDuel heading is a number they cannot get.
 *   2. WHERE THE BETSLIP HANDS OFF — the bet button on the builder and on each
 *      saved parlay — WITH a DraftKings fallback (`handoffBookFor`). Here the
 *      fallback is the honest move: "Bet on FanDuel" must never open a slip
 *      FanDuel cannot price, and the button says so when it happens.
 *
 * It does NOT reach pricing. Picks, Signals, the pick detail and every parlay
 * are priced, staked and graded at DraftKings — the book the models score
 * against (§6) — and list every book's line best price first. A member cannot
 * switch that, and no board marks one chip as "theirs".
 *
 * Defaults to DraftKings so nothing changes until the user opts in. Persisted to
 * AsyncStorage and shared across screens via a module-level store + listeners
 * (same pattern as useSportFilter / useKellySettings).
 *
 * Only BETTABLE books are selectable (2026-09-03): a "your sportsbook" that
 * cannot be bet from the US — Pinnacle, Bovada — is a price the member cannot
 * take, the same defect docs/best_line.md §2 measured server-side. A stored
 * preference for one of those falls back to DraftKings on load.
 */
export type { BookKey };

export const BOOKS: BookKey[] = BETTABLE_BOOKS;

const STORAGE_KEY = 'preferredBook.selected';
const DEFAULT_BOOK: BookKey = MODEL_BOOK;

const listeners = new Set<(b: BookKey) => void>();
let cached: BookKey | null = null;

function isBookKey(v: unknown): v is BookKey {
  return typeof v === 'string' && (BETTABLE_BOOKS as string[]).includes(v);
}

async function load(): Promise<BookKey> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    // A book we no longer carry (or junk) falls back to DK rather than leaving
    // the app selecting a book we can never show a price for.
    cached = isBookKey(raw) ? raw : DEFAULT_BOOK;
  } catch {
    cached = DEFAULT_BOOK;
  }
  return cached;
}

async function save(v: BookKey) {
  cached = v;
  listeners.forEach((fn) => fn(v));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, v);
  } catch (err) {
    console.warn('[preferredBook] save failed', err);
  }
}

export function usePreferredBook() {
  const [book, setBookState] = useState<BookKey>(cached ?? DEFAULT_BOOK);
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((b) => {
      if (!mounted) return;
      setBookState(b);
      setReady(true);
    });
    const listener = (b: BookKey) => setBookState(b);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setBook = useCallback((v: BookKey) => {
    save(v).catch((err) => console.warn('[preferredBook] set failed', err));
  }, []);

  return { book, setBook, ready };
}
