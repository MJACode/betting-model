/**
 * One shared read of today's board.
 *
 * useTodayPicks is mounted from the betslip bar (App.tsx, outside the
 * navigator) and from Picks at the same time, and again from Stats and the
 * model screens. Each mount used to start the whole seven-sport read: picks,
 * games, DraftKings odds, and the all-books line shop. Callers of one date
 * share a single in-flight request. A refresh that arrives while a read is
 * running does not start a second one; it asks for exactly one follow-up when
 * the current read settles, so the newest read is the one every caller
 * settles on.
 *
 * When the board reloads is not decided here. PicksHomeScreen reloads it
 * (every 10 minutes while its tab is focused, on coming back to the app or
 * the tab, and on pull-to-refresh) through `loadTodayBoard(date, true)`. This
 * file only decides whether a MOUNT may reuse a finished read: it may while
 * the read is younger than TODAY_PICKS_STALE_MS. A model page or Player Stats
 * opened later than that starts one new read, and every other mount of the
 * same date hears it.
 *
 * The error shown on the board is cleared only by a read that succeeds. A
 * failing or cancelled background reload leaves it as it was, so the banner
 * is not unmounted and mounted again every 10 minutes (UX review,
 * 2026-11-12).
 *
 * No React and no native module, so the dedupe can be run under node.
 */

import { errorText, isAbortError } from './errors';

/**
 * How old a finished read may be before the next MOUNT starts another one.
 * Picks' timer, its resume reload and pull-to-refresh read whatever this is.
 *
 * 5 minutes. `Infinity` means a mount never expires the read: only Picks'
 * reloads (and a new Eastern date) read again.
 */
export const TODAY_PICKS_STALE_MS = 5 * 60 * 1000;

export interface TodayBoardPartial {
  whats: string[];
  reason: string;
}

export interface TodayBoardSnapshot<Row> {
  data: Row[];
  pausedData: Row[];
  loading: boolean;
  /** At least one read has succeeded. A failure does not clear it. */
  loaded: boolean;
  error: string | null;
  partial: TodayBoardPartial | null;
}

export interface TodayBoardRead<Row> {
  data: Row[];
  pausedData: Row[];
  /** True only when the read succeeded. A failure must not replace the rows. */
  loaded: boolean;
  error: string | null;
  partial: TodayBoardPartial | null;
}

interface Slot<Row> {
  value: TodayBoardSnapshot<Row>;
  listeners: Set<(value: TodayBoardSnapshot<Row>) => void>;
  inFlight: Promise<void> | null;
  /** A refresh landed during the current read. One follow-up, not one per caller. */
  again: boolean;
  /** When the last successful read finished. 0 until then. */
  fetchedAt: number;
}

const slots = new Map<string, Slot<unknown>>();

/*
 * The Eastern day every UNDATED board is on. Each mount of useTodayPicks keeps
 * its own day, so after midnight ET a mount that never pulls, never returns
 * to the app and never remounts (the betslip bar, while the app stays open)
 * kept yesterday's board after Picks had moved on. Now the first undated
 * mount to move onto a new day moves this, and every undated mount follows
 * (design review, 2026-11-13). It only moves forward. A mount given an
 * explicit date ignores it.
 */
let boardDay: string | null = null;
const dayListeners = new Set<(day: string) => void>();

/** The Eastern day undated boards are on, or null before any has mounted. */
export function todayBoardDay(): string | null {
  return boardDay;
}

/**
 * An undated board is on `day` (it mounted, refreshed, or came back to the
 * app on it). If that is later than the shared day, every other undated
 * board is told to follow. Returns the day undated boards should now show.
 */
export function moveTodayBoardDay(day: string): string {
  if (boardDay != null && day <= boardDay) return boardDay;
  boardDay = day;
  dayListeners.forEach((fn) => fn(day));
  return day;
}

/** Hear the shared day move. Every undated mount listens. */
export function subscribeTodayBoardDay(listener: (day: string) => void): () => void {
  dayListeners.add(listener);
  return () => {
    dayListeners.delete(listener);
  };
}

let reader: ((date: string) => Promise<TodayBoardRead<unknown>>) | null = null;
let nowMs: () => number = () => Date.now();
/** Tests pass Infinity without editing the exported constant. null uses the constant. */
let staleMsOverride: number | null = null;

function staleMs(): number {
  return staleMsOverride ?? TODAY_PICKS_STALE_MS;
}

/** A mount reuses a finished read until it is older than the staleness age.
 *  Infinity never expires a mount. */
function readIsFresh(slot: Slot<unknown>): boolean {
  if (!slot.value.loaded) return false;
  const age = staleMs();
  if (!Number.isFinite(age)) return true;
  return nowMs() - slot.fetchedAt < age;
}

/** True when this date has no successful read inside the staleness age.
 *  Does not create a slot. */
export function todayBoardIsStale(date: string): boolean {
  const slot = slots.get(date) as Slot<unknown> | undefined;
  if (!slot) return true;
  return !readIsFresh(slot);
}

/**
 * Which Eastern date to read.
 *
 * An explicit date stays. A refresh always rolls forward to `today`, so a
 * pull after midnight ET does not re-read the day the screen mounted on.
 * A mount rolls forward only when the day it is holding is older than
 * TODAY_PICKS_STALE_MS. Inside that window it keeps the held day.
 */
export function todayPicksDateKey(opts: {
  explicit?: string;
  held: string;
  today: string;
  heldIsStale: boolean;
  refresh: boolean;
}): string {
  if (opts.explicit != null) return opts.explicit;
  if (opts.refresh) return opts.today;
  if (opts.held !== opts.today && opts.heldIsStale) return opts.today;
  return opts.held;
}

export function emptyTodayBoard<Row>(): TodayBoardSnapshot<Row> {
  return {
    data: [],
    pausedData: [],
    loading: true,
    loaded: false,
    error: null,
    partial: null,
  };
}

function slotFor<Row>(date: string): Slot<Row> {
  let slot = slots.get(date) as Slot<Row> | undefined;
  if (!slot) {
    slot = {
      value: emptyTodayBoard<Row>(),
      listeners: new Set(),
      inFlight: null,
      again: false,
      fetchedAt: 0,
    };
    slots.set(date, slot as Slot<unknown>);
    // A phone left open across midnight was keeping every earlier board.
    // Drop a date nobody is looking at. The slot just created has no
    // listeners yet, so it is excluded. An in-flight read is kept.
    for (const [key, other] of slots) {
      if (key !== date && other.listeners.size === 0 && other.inFlight == null) slots.delete(key);
    }
  }
  return slot;
}

function publish<Row>(slot: Slot<Row>): void {
  const value = slot.value;
  slot.listeners.forEach((fn) => fn(value));
}

/** The hook installs the real reader. Tests install a fake. */
export function setTodayBoardReader<Row>(fn: (date: string) => Promise<TodayBoardRead<Row>>): void {
  reader = fn as (date: string) => Promise<TodayBoardRead<unknown>>;
}

/** Tests move the clock instead of waiting out TODAY_PICKS_STALE_MS. */
export function setTodayBoardClockForTests(fn: () => number): void {
  nowMs = fn;
}

/** Tests the Infinity (a mount never expires) setting. Pass null to use the constant. */
export function setTodayPicksStaleMsForTests(ms: number | null): void {
  staleMsOverride = ms;
}

export function todayBoardSnapshot<Row>(date: string): TodayBoardSnapshot<Row> {
  return slotFor<Row>(date).value;
}

export function subscribeTodayBoard<Row>(
  date: string,
  listener: (value: TodayBoardSnapshot<Row>) => void,
): () => void {
  const slot = slotFor<Row>(date);
  slot.listeners.add(listener);
  return () => {
    slot.listeners.delete(listener);
  };
}

/**
 * `force` is refresh: ignore a finished read. Concurrent callers, forced or
 * not, await the same promise. A force that arrives mid-read schedules one
 * follow-up instead of a parallel read.
 */
export async function loadTodayBoard(date: string, force = false): Promise<void> {
  const slot = slotFor(date);
  if (slot.inFlight) {
    if (force) slot.again = true;
    return slot.inFlight;
  }
  if (!force && readIsFresh(slot)) return;
  if (!reader) throw new Error('today board reader is not installed');

  const read = reader;
  let resolveFlight: () => void = () => {};
  const flight = new Promise<void>((resolve) => {
    resolveFlight = resolve;
  });
  slot.inFlight = flight;
  slot.again = false;
  // `error` is NOT cleared here. A failing background reload would unmount
  // the error banner and mount it again, read out each time by VoiceOver.
  // It clears when a read succeeds (UX review, 2026-11-12).
  slot.value = { ...slot.value, loading: true };
  publish(slot);

  try {
    for (;;) {
      slot.again = false;
      let result: TodayBoardRead<unknown>;
      try {
        result = await read(date);
      } catch (e: unknown) {
        // The same text the hook's own catch gives. A cancel is not a
        // failure: no error, so the shown one stays as it was.
        result = {
          data: [],
          pausedData: [],
          loaded: false,
          error: isAbortError(e) ? null : errorText(e),
          partial: null,
        };
      }
      if (result.loaded) {
        slot.fetchedAt = nowMs();
        slot.value = {
          data: result.data,
          pausedData: result.pausedData,
          partial: result.partial,
          loaded: true,
          error: null,
          loading: true,
        };
      } else if (result.error != null) {
        // A failed read keeps the rows. A cancelled one (error null) leaves
        // the shown error as it was too.
        slot.value = { ...slot.value, error: result.error, loading: true };
      }
      if (!slot.again) break;
      // A refresh arrived during this pass, so one more read follows. Show
      // this pass's rows now rather than holding them for the follow-up:
      // a pull during a background read would otherwise see nothing until
      // two full reads finished. Only a pass that loaded is shown early; a
      // failed one could put up an error the follow-up clears a moment later.
      if (result.loaded) publish(slot);
    }
  } finally {
    // Drop the in-flight marker BEFORE publishing. A listener that refreshes
    // off this update has to start a new read, not set `again` on a flight
    // that is already leaving.
    slot.inFlight = null;
    slot.again = false;
    slot.value = { ...slot.value, loading: false };
    publish(slot);
    resolveFlight();
  }
}

export function resetTodayBoardForTests(): void {
  slots.clear();
  boardDay = null;
  dayListeners.clear();
  nowMs = () => Date.now();
  staleMsOverride = null;
}
