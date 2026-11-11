/**
 * One shared read of today's board.
 *
 * useTodayPicks is mounted from the betslip bar (App.tsx, outside the
 * navigator) and from Picks at the same time, and again from Stats and the
 * model screens. Each mount used to start the whole seven-sport read: picks,
 * games, DraftKings odds, and the all-books line shop. Callers of one date
 * share a single in-flight request. A finished read is reused until
 * `loadTodayBoard(date, true)` — pull-to-refresh and any other `refresh()`.
 * A refresh that arrives while a read is running does not start a second
 * one; it asks for exactly one follow-up when the current read settles.
 *
 * A finished read is reused for TODAY_PICKS_STALE_MS. A model page or
 * Player Stats opened later than that starts one new read, and every other
 * mount of the same date hears it. Inside the window, hopping screens does
 * not start another seven-sport read. Returning to the app does the same
 * check. Set the constant to Infinity for foreground-only: a mount never
 * expires the read, and coming back to the app is what reads again.
 *
 * No React and no native module, so the dedupe can be run under node.
 */

/**
 * How old a finished read may be before the next mount, or the next return
 * to the app, starts another one.
 *
 * 5 minutes for now. Matt is choosing among 5 minutes, 15 minutes, and
 * foreground-only. Set this to `Infinity` for foreground-only: a mount keeps
 * the read for the whole session, and AppState 'active' is what starts the
 * next read. Pull-to-refresh always reads, whatever this is.
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

/** Tests the Infinity (foreground-only) switch. Pass null to use the constant. */
export function setTodayPicksStaleMsForTests(ms: number | null): void {
  staleMsOverride = ms;
}

/**
 * AppState 'active'. A finite age re-reads only when the cached read is
 * older than TODAY_PICKS_STALE_MS. Infinity re-reads on every return: that
 * is the foreground-only setting, and concurrent callers still share one flight.
 */
export function loadTodayBoardOnForeground(date: string): Promise<void> {
  if (!Number.isFinite(staleMs())) return loadTodayBoard(date, false, true);
  return loadTodayBoard(date, false, false);
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
export async function loadTodayBoard(date: string, force = false, bypassAge = false): Promise<void> {
  const slot = slotFor(date);
  if (slot.inFlight) {
    if (force) slot.again = true;
    return slot.inFlight;
  }
  if (!force && !bypassAge && readIsFresh(slot)) return;
  if (!reader) throw new Error('today board reader is not installed');

  const read = reader;
  let resolveFlight: () => void = () => {};
  const flight = new Promise<void>((resolve) => {
    resolveFlight = resolve;
  });
  slot.inFlight = flight;
  slot.again = false;
  slot.value = { ...slot.value, loading: true, error: null };
  publish(slot);

  try {
    for (;;) {
      slot.again = false;
      let result: TodayBoardRead<unknown>;
      try {
        result = await read(date);
      } catch (e: unknown) {
        result = {
          data: [],
          pausedData: [],
          loaded: false,
          error: e instanceof Error ? e.message : 'Something went wrong',
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
      } else {
        slot.value = { ...slot.value, error: result.error, loading: true };
      }
      if (!slot.again) break;
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
  nowMs = () => Date.now();
  staleMsOverride = null;
}
