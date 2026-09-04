import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { BETTABLE_BOOKS, MODEL_BOOK, type BookKey } from '@/lib/markets';

/**
 * The member's own sportsbooks — a SET, not one book (Matt, 2026-09-04, with a
 * competitor's leaderboard beside ours: "give them the option to place on any
 * Sportsbook we have odds for and it tells them if the bet is available
 * there"). Selecting DraftKings and FanDuel means the Stats board prints
 * whichever of the two pays more on each line, badged with the book that won.
 *
 * TWO readers, and the difference between them is deliberate — this scope has
 * been reversed twice in three days, so read all of it before narrowing it:
 *
 *   1. THE STATS BOARD'S LINE, with NO fallback outside the set. Their books or
 *      nothing: a player none of them has priced shows no line, because a
 *      DraftKings price under a FanDuel heading is a number they cannot get.
 *   2. WHERE THE BETSLIP HANDS OFF — the bet button on the builder and on each
 *      saved parlay — WITH a DraftKings fallback (`handoffBookFor`). Here the
 *      fallback is the honest move: "Bet on FanDuel" must never open a slip
 *      FanDuel cannot price, and the button says so when it happens. The "Open
 *      with" row beside it still lists EVERY book we price, selected or not,
 *      with its coverage, so the set narrows the default and never the options.
 *
 * It does NOT reach pricing. Picks, Signals, the pick detail and every parlay
 * are priced, staked and graded at DraftKings — the book the models score
 * against (§6). A member cannot switch that.
 *
 * THE SET IS NEVER EMPTY. Clearing the last book would blank the Stats column
 * with no way to read why, so the last one cannot be unchecked and a stored
 * empty set loads as DraftKings.
 *
 * Only BETTABLE books are selectable (2026-09-03): a book that cannot be bet
 * from the US — Pinnacle, Bovada — is a price the member cannot take, the same
 * defect docs/best_line.md §2 measured server-side. Stored keys we no longer
 * carry are dropped on load.
 *
 * Migrates the single-book key this replaced (`preferredBook.selected`), so a
 * member who chose FanDuel keeps FanDuel as their one selected book.
 */
export type { BookKey };

export const BOOKS: BookKey[] = BETTABLE_BOOKS;

const STORAGE_KEY = 'preferredBooks.selected';
/** The v1 single-book key, read once to migrate and then left alone. */
const LEGACY_KEY = 'preferredBook.selected';
const DEFAULT_BOOKS: BookKey[] = [MODEL_BOOK];

const listeners = new Set<(b: BookKey[]) => void>();
let cached: BookKey[] | null = null;

function isBookKey(v: unknown): v is BookKey {
  return typeof v === 'string' && (BETTABLE_BOOKS as string[]).includes(v);
}

/** Selection order is never trusted for display — always BETTABLE_BOOKS order,
 *  so the picker and every caption read the same left to right. */
function normalize(keys: unknown): BookKey[] {
  const set = new Set(Array.isArray(keys) ? keys.filter(isBookKey) : []);
  const out = BETTABLE_BOOKS.filter((b) => set.has(b));
  return out.length > 0 ? out : DEFAULT_BOOKS;
}

async function load(): Promise<BookKey[]> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (raw != null) {
      cached = normalize(JSON.parse(raw));
      return cached;
    }
    // First run since multi-select shipped: carry the single book forward.
    const legacy = await AsyncStorage.getItem(LEGACY_KEY);
    cached = isBookKey(legacy) ? [legacy] : DEFAULT_BOOKS;
  } catch {
    cached = DEFAULT_BOOKS;
  }
  return cached;
}

async function save(v: BookKey[]) {
  const next = normalize(v);
  cached = next;
  listeners.forEach((fn) => fn(next));
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch (err) {
    console.warn('[preferredBooks] save failed', err);
  }
}

export function usePreferredBooks() {
  const [books, setBooksState] = useState<BookKey[]>(cached ?? DEFAULT_BOOKS);
  // False until storage has answered. Every consumer that renders a book name
  // or hands off must gate on it: the seeded default is DraftKings, so without
  // it a FanDuel member sees DK for a frame — and a tap in that window opened
  // the wrong book (UX review, 2026-09-04).
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    load().then((b) => {
      if (!mounted) return;
      setBooksState(b);
      setReady(true);
    });
    const listener = (b: BookKey[]) => setBooksState(b);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setBooks = useCallback((v: BookKey[]) => {
    save(v).catch((err) => console.warn('[preferredBooks] set failed', err));
  }, []);

  return { books, setBooks, ready };
}
