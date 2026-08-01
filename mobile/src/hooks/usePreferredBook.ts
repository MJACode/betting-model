import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { LINE_SHOP_BOOKS, MODEL_BOOK, type BookKey } from '@/lib/markets';

/**
 * The user's sportsbook.
 *
 * Picks are always MODELED against DraftKings — this preference only changes
 * which book's price we SHOW, so a user who bets at FanDuel sees the number
 * they'll actually get. The edge/probability on every card still comes from the
 * DraftKings line the model scored against.
 *
 * Defaults to DraftKings so nothing changes until the user opts in. Persisted to
 * AsyncStorage and shared across screens via a module-level store + listeners
 * (same pattern as useSportFilter / useKellySettings).
 */
export type { BookKey };

export const BOOKS: BookKey[] = LINE_SHOP_BOOKS;

const STORAGE_KEY = 'preferredBook.selected';
const DEFAULT_BOOK: BookKey = MODEL_BOOK;

const listeners = new Set<(b: BookKey) => void>();
let cached: BookKey | null = null;

function isBookKey(v: unknown): v is BookKey {
  return typeof v === 'string' && (LINE_SHOP_BOOKS as string[]).includes(v);
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

  /** True when the user bets somewhere other than the book we model against. */
  const isNonModelBook = book !== MODEL_BOOK;

  return { book, setBook, ready, isNonModelBook };
}
