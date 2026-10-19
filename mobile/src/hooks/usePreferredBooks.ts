import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

import { getDeviceId } from '@/hooks/useDeviceId';
import { BETTABLE_BOOKS, type BookKey } from '@/lib/markets';
import { supabase } from '@/lib/supabase';

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
 *   3. THE PICK BOARDS AND THE PICK DETAIL (Matt, 2026-10-19: "if someone
 *      doesn't have that Sportsbook in their state we shouldn't show it").
 *      The card shows the best price at THEIR books, with the edge and return
 *      worked out at that price, and "Not offered at your books" when none
 *      of theirs has the bet (lib/myBooks.ts).
 *
 * It does NOT reach the models. Every pick is still decided, staked and
 * graded at the best bettable price (§6), and the record and every published
 * surface stay there. The set changes what this member SEES, nothing else.
 *
 * NEW MEMBERS START WITH EVERY BOOK (Matt, 2026-10-19): the value is in
 * shopping every book, so onboarding opens with all of them checked and the
 * member unchecks the ones they cannot use. `chosen` is false until they have
 * confirmed a set once, which is what brings the onboarding step back up for
 * a member who installed before it existed.
 *
 * STORED IN SUPABASE (`member_books_get` / `member_books_set`, migration
 * member_sportsbooks_2026_10_19.sql), under the install and, when signed in,
 * under the member, so it follows them to a new phone. AsyncStorage is a
 * cache of that row (CLAUDE.md §1b): it answers first so the board does not
 * flash, and the server answer wins when it lands. A member who chose on
 * this phone before the table existed has that choice pushed up once.
 *
 * THE SET IS NEVER EMPTY. Clearing the last book would blank every price
 * with no way to read why, so the last one cannot be unchecked and a stored
 * empty set loads as every book.
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
/** Every book: the default until the member chooses (Matt, 2026-10-19). */
const DEFAULT_BOOKS: BookKey[] = BETTABLE_BOOKS;

interface State {
  books: BookKey[];
  /** The member has confirmed a set at least once (here or on another device). */
  chosen: boolean;
  /** The server has answered this launch (or failed to). Until then a
   *  not-chosen local cache may still be overruled by another device. */
  checked: boolean;
}

const listeners = new Set<(s: State) => void>();
let cached: State | null = null;
let serverSynced = false;

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

function publish(next: State) {
  cached = next;
  listeners.forEach((fn) => fn(next));
}

async function loadLocal(): Promise<State> {
  if (cached) return cached;
  try {
    const raw = await AsyncStorage.getItem(STORAGE_KEY);
    if (raw != null) {
      cached = { books: normalize(JSON.parse(raw)), chosen: true, checked: false };
      return cached;
    }
    // First run since multi-select shipped: carry the single book forward.
    const legacy = await AsyncStorage.getItem(LEGACY_KEY);
    cached = isBookKey(legacy)
      ? { books: [legacy], chosen: true, checked: false }
      : { books: DEFAULT_BOOKS, chosen: false, checked: false };
  } catch {
    cached = { books: DEFAULT_BOOKS, chosen: false, checked: false };
  }
  return cached;
}

async function writeServer(books: BookKey[]): Promise<void> {
  const deviceId = await getDeviceId();
  const { error } = await supabase.rpc('member_books_set', {
    p_device_id: deviceId,
    p_books: books,
  });
  if (error) throw error;
}

/** Once per launch: the server row wins; a local-only choice is pushed up. */
async function syncServer(): Promise<void> {
  if (serverSynced) return;
  serverSynced = true;
  try {
    const local = await loadLocal();
    const deviceId = await getDeviceId();
    const { data, error } = await supabase.rpc('member_books_get', { p_device_id: deviceId });
    if (error) throw error;
    if (Array.isArray(data) && data.length > 0) {
      const books = normalize(data);
      publish({ books, chosen: true, checked: true });
      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(books));
      return;
    }
    if (local.chosen) await writeServer(local.books);
    publish({ ...(cached ?? local), checked: true });
  } catch (err) {
    // Offline or the migration has not landed: the local cache stands, and
    // the next launch tries again.
    serverSynced = false;
    publish({ ...(cached ?? { books: DEFAULT_BOOKS, chosen: false }), checked: true });
    console.warn('[preferredBooks] server sync failed', err);
  }
}

async function save(v: BookKey[]) {
  const books = normalize(v);
  publish({ books, chosen: true, checked: true });
  try {
    await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(books));
  } catch (err) {
    console.warn('[preferredBooks] save failed', err);
  }
  try {
    await writeServer(books);
  } catch (err) {
    console.warn('[preferredBooks] server save failed', err);
  }
}

export function usePreferredBooks() {
  const [state, setState] = useState<State>(cached ?? { books: DEFAULT_BOOKS, chosen: false, checked: false });
  // False until storage has answered. Every consumer that renders a book name
  // or hands off must gate on it: without it the default shows for a frame —
  // and a tap in that window opened the wrong book (UX review, 2026-09-04).
  const [ready, setReady] = useState<boolean>(cached != null);

  useEffect(() => {
    let mounted = true;
    loadLocal().then((s) => {
      if (!mounted) return;
      setState(s);
      setReady(true);
      void syncServer();
    });
    const listener = (s: State) => setState(s);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const setBooks = useCallback((v: BookKey[]) => {
    save(v).catch((err) => console.warn('[preferredBooks] set failed', err));
  }, []);

  // `needsChoice`: the onboarding step should ask. Only once the server has
  // answered, so a member who chose on another phone is not asked again.
  const needsChoice = ready && state.checked && !state.chosen;
  return { books: state.books, chosen: state.chosen, needsChoice, setBooks, ready };
}
