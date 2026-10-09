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
 *
 * Review of that change (2026-10-09):
 * - When more snapshots follow the pick than the card holds, the price at the
 *   pick is still the first row. The dropped ones sit behind a divider row
 *   ("Earlier changes not shown") that no run crosses, and the footer names
 *   the missing stretch instead of counting changes it cannot see.
 * - `since` counts the snapshots after the pick, so a pick the book has not
 *   re-priced reads "no new price", not "steady".
 * - Labels carry the weekday when the rows cross an Eastern midnight, and the
 *   date too past six days (a weekday repeats after seven). "ET" is in the
 *   column heading, not on every row.
 * - A pick made after the start that is not live (an NHL start moved earlier
 *   at settlement) reads the last pre-game price (`historyFrom`).
 */

import { etDate, formatDayTimeET, parseStamp } from './format';

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
  /**
   * A row the changes are measured from, not a change: the first row, and the
   * first row after a divider (what came before it is not on the card).
   */
  baseline: boolean;
  /**
   * Not a snapshot: snapshots between the price at the pick and the next row
   * were dropped. Its label says so; it has no line or price.
   */
  divider: boolean;
  /** Unique React key (timestamps can repeat). */
  key: string;
  /**
   * Eastern time with no zone (the column heading says ET): "3:50 PM", or
   * "3:50:12 PM" when another row shares its minute; "Sat 3:50 PM" when the
   * rows cross midnight, "Sat 10/3, 3:50 PM" when they span over six days.
   * "At pick" for the pick's own price; the divider's text on a divider.
   */
  label: string;
}

/** The divider row's text. */
export const DIVIDER_LABEL = 'Earlier changes not shown';

const ET = 'America/New_York';
const minuteFmt = new Intl.DateTimeFormat('en-US', { timeZone: ET, hour: 'numeric', minute: '2-digit' });
const secondFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: ET,
  hour: 'numeric',
  minute: '2-digit',
  second: '2-digit',
});
const weekdayFmt = new Intl.DateTimeFormat('en-US', { timeZone: ET, weekday: 'short' });
const monthDayFmt = new Intl.DateTimeFormat('en-US', { timeZone: ET, month: 'numeric', day: 'numeric' });

/**
 * A stamp's instant in ms, or NaN. Through parseStamp, never the bare Date
 * constructor: Hermes rejects a space for "T" and only promises millisecond
 * fractions.
 */
function instant(at: string | null | undefined): number {
  return at ? parseStamp(at).getTime() : NaN;
}

/** How much of the day a row label needs: none, the weekday, or weekday and date. */
type DayPart = 'none' | 'weekday' | 'date';

function stamp(at: string, seconds: boolean, day: DayPart = 'none'): string {
  const d = parseStamp(at);
  if (Number.isNaN(d.getTime())) return '—';
  const time = (seconds ? secondFmt : minuteFmt).format(d);
  if (day === 'none') return time;
  const weekday = weekdayFmt.format(d);
  return day === 'date' ? `${weekday} ${monthDayFmt.format(d)}, ${time}` : `${weekday} ${time}`;
}

/**
 * Rows on one Eastern day need no day. Across midnight they need the weekday;
 * across more than six days the date too, because a weekday repeats after
 * seven (an NFL opener can be locked a week or more before kickoff).
 */
function dayPart(ats: string[]): DayPart {
  const days = [
    ...new Set(
      ats
        .map((a) => parseStamp(a))
        .filter((d) => !Number.isNaN(d.getTime()))
        .map(etDate),
    ),
  ].sort();
  if (days.length < 2) return 'none';
  const first = Date.parse(`${days[0]}T00:00:00Z`);
  const last = Date.parse(`${days[days.length - 1]}T00:00:00Z`);
  return (last - first) / 86400000 > 6 ? 'date' : 'weekday';
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
 * Where the card's window starts: the pick, or the start when the pick was
 * made after it. Null hides the card: a live pick (in-game movement after it
 * is not built), or a pick time that does not parse.
 *
 * Only `is_live` hides it. A pre-game pick can still sit after the start the
 * card computes: an NHL game's start moves about ten minutes earlier when it
 * is settled, which put most NHL moneyline and regulation picks "after the
 * start" and took their card away once the result was in (review,
 * 2026-10-09). Such a pick reads the last price before the start.
 */
export function historyFrom(
  pick: { is_live?: boolean | null; created_at: string },
  startAt: string | null,
): string | null {
  if (pick.is_live === true) return null;
  const t = instant(pick.created_at);
  if (Number.isNaN(t)) return null;
  const s = instant(startAt);
  return new Date(Number.isNaN(s) ? t : Math.min(t, s)).toISOString();
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
   * rows[0] is the book's price when the pick was made: its last snapshot at
   * or before the pick. False when the series holds none (the book first
   * posted after the pick, or a long prop series was capped).
   */
  fromPick: boolean;
  /**
   * Snapshots after the pick were dropped to fit: between rows[0] and rows[1]
   * with `fromPick`, before rows[0] without it.
   */
  gap: boolean;
  /**
   * Snapshots after the pick and before the start that reached the phone,
   * kept or not (the game-line read already stops at the newest 50). Zero
   * with `fromPick`: the book has posted nothing since the pick.
   */
  since: number;
  /** The game has started: the last row is the last price before it, not "now". */
  closed: boolean;
}

/** The last `k` items (none for k <= 0; `slice(-0)` would keep them all). */
function newest<T>(rows: T[], k: number): T[] {
  return k <= 0 ? [] : rows.slice(Math.max(0, rows.length - k));
}

/**
 * The book's line from the pick to the game's start. The pick is scored from
 * a snapshot taken a few seconds to about 45 minutes before it, so a window
 * that began AT the pick would be empty for most NHL props; it begins at that
 * snapshot instead. Rows at or after the start are dropped (books keep
 * posting "open" rows after it). A pick time after the start reads as the
 * start. The price at the pick is always kept; after it, the newest that fit
 * in `max`, and `gap` says whether any were dropped.
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
  const end = Number.isNaN(start) ? Infinity : start;
  const pick = Math.min(instant(pickAt), end);
  if (Number.isNaN(pick)) return { rows: [], fromPick: false, gap: false, since: 0, closed };
  const pre = byTime(rows).filter((r) => instant(r.snapshot_at) < end);
  const after = pre.filter((r) => instant(r.snapshot_at) > pick);
  const atPick = pre.filter((r) => instant(r.snapshot_at) <= pick).pop();
  const kept = newest(after, atPick ? max - 1 : max);
  return {
    rows: atPick ? [atPick, ...kept] : kept,
    fromPick: atPick != null,
    gap: kept.length < after.length,
    since: after.length,
    closed,
  };
}

export interface CollapseOptions {
  /** The first point is the pick's own price: its row reads "At pick". */
  atPick?: boolean;
  /**
   * Snapshots between the first point and the second were dropped: a divider
   * row goes between them, and no run spans it (the same price on both sides
   * says nothing about what happened in between).
   */
  gap?: boolean;
}

/** Collapse runs of the same line + price; returns oldest → newest. */
export function collapseLineHistory(points: HistoryPoint[], opts: CollapseOptions = {}): HistoryRow[] {
  const tracksLine = points.some((p) => p.line != null);
  const tracksPrice = points.some((p) => p.price != null);
  type Run = HistoryPoint & { count: number; baseline: boolean; divider: boolean; atPick: boolean };
  const runs: Run[] = [];
  for (let i = 0; i < points.length; i++) {
    if (i === 1 && opts.gap) {
      runs.push({ at: '', line: null, price: null, count: 0, baseline: false, divider: true, atPick: false });
    }
    const p = points[i];
    const known = [tracksLine ? p.line != null : null, tracksPrice ? p.price != null : null].filter(
      (k): k is boolean => k != null,
    );
    const last = runs[runs.length - 1];
    const open = last && !last.divider ? last : undefined;
    // Nothing for the side: a gap in the feed. It joins the run (only both
    // null carry); before any run, or right after a divider, it has nothing
    // to join.
    if (known.every((k) => !k)) {
      if (open) open.count += 1;
      continue;
    }
    // Partial: unknown, never half-carried into a pair (see the header).
    if (!known.every((k) => k)) continue;
    if (open && open.line === p.line && open.price === p.price) open.count += 1;
    else {
      // The first row is the price at the pick only if the first POINT
      // started it (a partial first point is skipped, and the next row is
      // after the pick).
      runs.push({ ...p, count: 1, baseline: open == null, divider: false, atPick: i === 0 && opts.atPick === true });
    }
  }
  const part = dayPart(runs.filter((r) => !r.divider).map((r) => r.at));
  const minutes = runs.map((r) => (r.divider ? '' : stamp(r.at, false, part)));
  const clash = new Set(minutes.filter((m, i) => m !== '' && minutes.indexOf(m) !== i));
  return runs.map((r, i) => ({
    at: r.at,
    line: r.line,
    price: r.price,
    count: r.count,
    baseline: r.baseline,
    divider: r.divider,
    key: r.divider ? `divider#${i}` : `${r.at}#${i}`,
    label: r.divider
      ? DIVIDER_LABEL
      : r.atPick
        ? 'At pick'
        : clash.has(minutes[i])
          ? stamp(r.at, true, part)
          : minutes[i],
  }));
}

export interface RecentChanges {
  /** The rows on screen, oldest → newest. */
  rows: HistoryRow[];
  /** Moves in the whole series: rows that are neither a baseline nor a divider. */
  changes: number;
  /** How many of them are on screen. */
  shownChanges: number;
  /** Rows above the screen (a divider counts). */
  hidden: number;
  /** The first snapshot row's stamp, on screen or not. */
  firstAt: string | null;
}

/**
 * The last `n` rows, oldest → newest (what the card shows). `changes` counts
 * moves only — the first row is where they are measured from, not one, and
 * neither is the first row after a divider — and `shownChanges` is how many
 * of them are on screen.
 */
export function recentChanges(points: HistoryPoint[], n = 8, opts: CollapseOptions = {}): RecentChanges {
  const all = collapseLineHistory(points, opts);
  const rows = all.slice(-n);
  const isChange = (r: HistoryRow) => !r.baseline && !r.divider;
  return {
    rows,
    changes: all.filter(isChange).length,
    shownChanges: rows.filter(isChange).length,
    hidden: all.length - rows.length,
    firstAt: all.find((r) => !r.divider)?.at ?? null,
  };
}

/**
 * The table's footer. "Last 8 of 19 changes" only when changes are really cut;
 * when the one row off the top is the first row (where the changes are
 * measured from), every change is on screen and "Last 8 of 8 changes" read as
 * a cut that wasn't (Reviewer #847) — it says "8 changes" instead.
 *
 * Never a snapshot count: snapshots are the feed's unit, not the reader's (50
 * of them is 50 minutes at DraftKings). When snapshots after the pick were
 * dropped (`gap`), the change count is not a total, so the footer names the
 * stretch that is missing instead. Without the price at the pick, it says
 * where the table starts.
 */
export function changesFooter(
  r: Pick<RecentChanges, 'rows' | 'changes' | 'shownChanges' | 'hidden' | 'firstAt'>,
  w: { fromPick: boolean; gap: boolean },
): string {
  const noun = (n: number) => `${n} ${n === 1 ? 'change' : 'changes'}`;
  const head =
    r.shownChanges < r.changes ? `Last ${r.shownChanges} of ${r.changes} changes` : noun(r.changes);
  if (!w.fromPick) {
    return r.firstAt
      ? `${head} since ${formatDayTimeET(r.firstAt)}. The price at your pick isn't available.`
      : `The price at your pick isn't available.`;
  }
  if (!w.gap) return `${head} since your pick`;
  // The first row on screen after the price at the pick: everything between
  // the pick and it is missing, whether the cut or the 8-row screen hid it.
  const resume = r.rows.find((x, i) => !x.divider && r.hidden + i > 0);
  return resume
    ? `Changes between your pick and ${formatDayTimeET(resume.at)} not shown`
    : 'Some changes since your pick not shown';
}
