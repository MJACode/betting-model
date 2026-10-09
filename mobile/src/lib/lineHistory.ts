/**
 * Line-movement rows for Pick Detail — usability audit M13 (PR 3).
 *
 * The table used to print the last 8 raw snapshots: on a busy market that was
 * eight rows stamped "3:50 PM ET" alternating −105 / −115, which is noise, not
 * a story. Now a row is a CHANGE: consecutive snapshots at the same line and
 * price collapse into the first of the run, and two rows that would print the
 * same minute get seconds so the order is readable. Pure (Intl only).
 *
 * Reviewer (#847): the OPENING row is where the line started, not a change,
 * so it is not counted; a snapshot with NOTHING for the side (every tracked
 * field null) is a gap in the feed, not a move to "N/A" and back, so it joins
 * the run; and every row has a unique `key`, because two snapshots can share
 * a timestamp.
 *
 * Reviewer (#847 approval): a PARTIAL snapshot (line but no price, or price
 * but no line) is unknown, not carried. Carrying each field on its own
 * invented pairs the book never posted — 8.5 @ −110 then 9.0 @ null printed
 * "9.0 @ −110". A partial row neither joins, breaks nor starts a run and is
 * not shown; the next complete snapshot says where the line went. A field no
 * snapshot has (the line on a moneyline, where the card passes null) is not
 * tracked, so it never makes a row partial.
 *
 * Since the pick (2026-10-09): the card used to read the OLDEST 50 snapshots
 * of a market and call the last of them "now" — days before the pick on a busy
 * NFL total, so it said "steady" about a line that had moved. It now shows the
 * book's price when the pick was made (the last snapshot at or before it) and
 * every snapshot after it up to the game's start, newest kept (`sincePick`).
 * The first row is that price, not the opener, so it reads "At pick".
 *
 * Every stamp is parsed (`parseStamp`), never compared as text: about half of
 * player_prop_odds is stamped in Eastern time ("...-04:00", "-05:00" from
 * November), so its text order is hours off its time order.
 */

import { parseStamp } from './format';

/** Snapshots the card holds: the price at the pick plus the newest after it. */
export const HISTORY_ROWS = 50;

export interface HistoryPoint {
  /** ISO timestamp of the snapshot. */
  at: string;
  line: number | null;
  price: number | null;
}

export interface HistoryRow extends HistoryPoint {
  /** How many snapshots this row stands for (the run it collapsed). */
  count: number;
  /** The first row: the price the changes are measured from. Not a change. */
  baseline: boolean;
  /** Unique React key (timestamps can repeat). */
  key: string;
  /**
   * "3:50 PM ET", or "3:50:12 PM ET" when another row shares its minute, or
   * "At pick" for the book's price when the pick was made.
   */
  label: string;
}

const minuteFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  hour: 'numeric',
  minute: '2-digit',
});
const secondFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  hour: 'numeric',
  minute: '2-digit',
  second: '2-digit',
});

/**
 * A stamp's instant in ms, or NaN. Through parseStamp, never the bare Date
 * constructor: Hermes rejects a space for "T" and only promises millisecond
 * fractions.
 */
function instant(at: string | null | undefined): number {
  return at ? parseStamp(at).getTime() : NaN;
}

function stamp(at: string, seconds: boolean): string {
  const d = parseStamp(at);
  if (Number.isNaN(d.getTime())) return '—';
  return `${(seconds ? secondFmt : minuteFmt).format(d)} ET`;
}

/**
 * A 19-character UTC bound ("2026-10-07T18:00:15", the second floored) for a
 * server-side text comparison on odds.snapshot_at. Only the game-line table:
 * every row there is UTC ("…Z", "…+00:00", "….ffffff+00:00", measured
 * 2026-10-09), so its text order is its time order, and a bound with no suffix
 * sorts before every row stamped inside that second, whatever its shape. Never
 * player_prop_odds: Eastern-time rows there compare hours wrong as text.
 */
export function utcSecond(at: string | null | undefined): string | null {
  const t = instant(at);
  return Number.isNaN(t) ? null : new Date(t).toISOString().slice(0, 19);
}

/** The game's start: the earliest of the stamps that parse (games.commence_time, picks.game_time). */
export function gameStartAt(...stamps: Array<string | null | undefined>): string | null {
  const times = stamps.map(instant).filter((t) => !Number.isNaN(t));
  return times.length > 0 ? new Date(Math.min(...times)).toISOString() : null;
}

/**
 * Was the pick made before the game started? A live pick is made after it, so
 * there is no pre-game line since the pick, and the card hides. An unknown
 * start does not hide it.
 */
export function pickedBeforeStart(pickAt: string, startAt: string | null): boolean {
  const pick = instant(pickAt);
  const start = instant(startAt);
  return !Number.isNaN(pick) && (Number.isNaN(start) || pick < start);
}

/** Rows oldest → newest by the instant each was taken; a stamp that does not parse is dropped. */
export function byTime<T extends { snapshot_at: string }>(rows: T[]): T[] {
  return rows
    .map((r, i) => ({ r, i, t: instant(r.snapshot_at) }))
    .filter((x) => !Number.isNaN(x.t))
    .sort((a, b) => a.t - b.t || a.i - b.i)
    .map((x) => x.r);
}

export interface PickWindow<T> {
  /** Oldest → newest, all before the start. */
  rows: T[];
  /**
   * rows[0] is the book's price when the pick was made: the last snapshot at
   * or before it. False when there were too many snapshots since the pick to
   * hold them all (only the newest are kept), or none at or before it.
   */
  fromPick: boolean;
  /** The game has started: the last row is the last price before it, not "now". */
  closed: boolean;
}

/**
 * The book's line from the pick to the game's start. The pick is scored from
 * a snapshot taken a few seconds to about 45 minutes before it, so a window
 * that began AT the pick would be empty for most NHL props; it begins at that
 * snapshot instead. Rows at or after the start are dropped (books keep
 * posting "open" rows after it). Everything since the pick when it fits in
 * `max` with the price at the pick; otherwise the newest `max`.
 */
export function sincePick<T extends { snapshot_at: string }>(
  rows: T[],
  pickAt: string,
  startAt: string | null,
  max = HISTORY_ROWS,
  now = Date.now(),
): PickWindow<T> {
  const start = instant(startAt);
  const closed = !Number.isNaN(start) && now >= start;
  if (!pickedBeforeStart(pickAt, startAt)) return { rows: [], fromPick: false, closed };
  const pick = instant(pickAt);
  const end = Number.isNaN(start) ? Infinity : start;
  const pre = byTime(rows).filter((r) => instant(r.snapshot_at) < end);
  const after = pre.filter((r) => instant(r.snapshot_at) > pick);
  const atPick = pre.filter((r) => instant(r.snapshot_at) <= pick).pop();
  if (atPick && after.length <= max - 1) return { rows: [atPick, ...after], fromPick: true, closed };
  return { rows: after.slice(-max), fromPick: false, closed };
}

/**
 * Collapse runs of the same line + price; returns oldest → newest. With
 * `fromPick` (the first point is the price at the pick) that row reads
 * "At pick".
 */
export function collapseLineHistory(points: HistoryPoint[], fromPick = false): HistoryRow[] {
  const tracksLine = points.some((p) => p.line != null);
  const tracksPrice = points.some((p) => p.price != null);
  const runs: Array<HistoryPoint & { count: number }> = [];
  // The first row is the price at the pick only if the first POINT started it
  // (a partial first point is skipped, and the next row is after the pick).
  let pickRun = false;
  for (let i = 0; i < points.length; i++) {
    const p = points[i];
    const known = [tracksLine ? p.line != null : null, tracksPrice ? p.price != null : null].filter(
      (k): k is boolean => k != null,
    );
    const last = runs[runs.length - 1];
    // Nothing for the side: a gap in the feed. It joins the run (only both
    // null carry); before any run it has nothing to join.
    if (known.every((k) => !k)) {
      if (last) last.count += 1;
      continue;
    }
    // Partial: unknown, never half-carried into a pair (see the header).
    if (!known.every((k) => k)) continue;
    if (last && last.line === p.line && last.price === p.price) last.count += 1;
    else {
      runs.push({ ...p, count: 1 });
      if (i === 0) pickRun = fromPick;
    }
  }
  const minutes = runs.map((r) => stamp(r.at, false));
  const clash = new Set(minutes.filter((m, i) => minutes.indexOf(m) !== i));
  return runs.map((r, i) => ({
    ...r,
    baseline: i === 0,
    key: `${r.at}#${i}`,
    label: i === 0 && pickRun ? 'At pick' : clash.has(minutes[i]) ? stamp(r.at, true) : minutes[i],
  }));
}

/**
 * The last `n` rows, oldest → newest (what the card shows). `changes` counts
 * moves only — the first row is where they are measured from, not one — and
 * `shownChanges` is how many of them are on screen.
 */
export function recentChanges(
  points: HistoryPoint[],
  n = 8,
  fromPick = false,
): { rows: HistoryRow[]; changes: number; shownChanges: number; hidden: number } {
  const all = collapseLineHistory(points, fromPick);
  const rows = all.slice(-n);
  return {
    rows,
    changes: Math.max(0, all.length - 1),
    shownChanges: rows.filter((r) => !r.baseline).length,
    hidden: all.length - rows.length,
  };
}

/**
 * The table's footer. "Last 8 of 19 changes" only when changes are really cut;
 * when the one row off the top is the first row (where the changes are
 * measured from), every change is on screen and "Last 8 of 8 changes" read as
 * a cut that wasn't (Reviewer #847) — it says "8 changes" instead. It used to
 * add "opening not shown"; that row is the price at the pick now, not the
 * opener. `fromPick` (sincePick): the table runs from the pick; otherwise it
 * holds only the newest snapshots, and says so.
 */
export function changesFooter(
  r: { changes: number; shownChanges: number; hidden: number },
  snapshots: number,
  fromPick: boolean,
): string {
  const noun = (n: number) => `${n} ${n === 1 ? 'change' : 'changes'}`;
  const head =
    r.shownChanges < r.changes ? `Last ${r.shownChanges} of ${r.changes} changes` : noun(r.changes);
  return fromPick
    ? `${head} since your pick · ${snapshots} snapshots`
    : `${head} in the newest ${snapshots} snapshots`;
}
