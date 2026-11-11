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
 * A finished read is reused for TODAY_BOARD_MAX_AGE_MS. A model page or
 * Player Stats opened later than that starts one new read, and every other
 * mount of the same date hears it. Inside the window, hopping screens does
 * not start another seven-sport read. 5 minutes is the review's pick
 * (2026-11-11): long enough that a launch burst stays one read, short enough
 * that an evening visit is not still showing noon. Change the constant to
 * move that line.
 *
 * No React and no native module, so the dedupe can be run under node.
 */

/** How long a finished read satisfies a mount that did not ask to refresh. */
export const TODAY_BOARD_MAX_AGE_MS = 5 * 60 * 1000;

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

/** Tests move the clock instead of waiting out TODAY_BOARD_MAX_AGE_MS. */
export function setTodayBoardClockForTests(fn: () => number): void {
  nowMs = fn;
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
  const fresh = slot.value.loaded && nowMs() - slot.fetchedAt < TODAY_BOARD_MAX_AGE_MS;
  if (!force && fresh) return;
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
}
