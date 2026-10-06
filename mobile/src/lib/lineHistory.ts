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
 */

export interface HistoryPoint {
  /** ISO timestamp of the snapshot. */
  at: string;
  line: number | null;
  price: number | null;
}

export interface HistoryRow extends HistoryPoint {
  /** How many snapshots this row stands for (the run it collapsed). */
  count: number;
  /** The first row: where the line opened. Not a change. */
  opening: boolean;
  /** Unique React key (timestamps can repeat). */
  key: string;
  /**
   * "8:21 PM", or "8:21:12 PM" when another row shares its minute.
   * The header carries ET. A series that crosses midnight also carries
   * the date: "10/4 8:21 PM".
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
const dayKeyFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
});
const monthDayFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  month: 'numeric',
  day: 'numeric',
});
const spokenDateFmt = new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York',
  month: 'long',
  day: 'numeric',
});

function stamp(at: string, seconds: boolean, withDate: boolean): string {
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return '—';
  const time = (seconds ? secondFmt : minuteFmt).format(d);
  if (!withDate) return time;
  return `${monthDayFmt.format(d)} ${time}`;
}

function etDay(at: string): string {
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return '';
  return dayKeyFmt.format(d);
}

/** Collapse runs of the same line + price; returns oldest → newest. */
export function collapseLineHistory(points: HistoryPoint[]): HistoryRow[] {
  const tracksLine = points.some((p) => p.line != null);
  const tracksPrice = points.some((p) => p.price != null);
  const runs: Array<HistoryPoint & { count: number }> = [];
  for (const p of points) {
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
    else runs.push({ ...p, count: 1 });
  }
  const withDate = new Set(runs.map((r) => etDay(r.at))).size > 1;
  const minutes = runs.map((r) => stamp(r.at, false, withDate));
  const clash = new Set(minutes.filter((m, i) => minutes.indexOf(m) !== i));
  return runs.map((r, i) => ({
    ...r,
    opening: i === 0,
    key: `${r.at}#${i}`,
    label: clash.has(minutes[i]) ? stamp(r.at, true, withDate) : minutes[i],
  }));
}

/**
 * The last `n` rows, oldest → newest (what the card shows). `changes` counts
 * moves only — the opening row is not one — and `shownChanges` is how many of
 * them are on screen.
 */
export function recentChanges(
  points: HistoryPoint[],
  n = 8,
): { rows: HistoryRow[]; changes: number; shownChanges: number; hidden: number } {
  const all = collapseLineHistory(points);
  const rows = all.slice(-n);
  return {
    rows,
    changes: Math.max(0, all.length - 1),
    shownChanges: rows.filter((r) => !r.opening).length,
    hidden: all.length - rows.length,
  };
}

/**
 * How many snapshots one read is allowed to bring back.
 *
 * PostgREST returns at most this many rows and does not say when the table
 * holds more. An oldest-first page of this size is the early line, not the
 * current one: JAX/PHI DraftKings spreads on 2026-10-06 were 3,939 rows, the
 * 50th was still −3 on Oct 2, and the latest was −7.
 */
export const LINE_HISTORY_PAGE = 50;

/**
 * The table's footer. "Last 8 of 19 changes" only when changes are really cut;
 * when the one row off the top is the OPENING, every change is on screen and
 * "Last 8 of 8 changes" read as a cut that wasn't (Reviewer #847) — it says
 * "8 changes · opening not shown" instead.
 *
 * A partial series is the open, a sample of the gap, and the latest page.
 * Quoting that length as the snapshot population says the book only moved
 * as often as we sampled.
 */
export function changesFooter(
  r: { changes: number; shownChanges: number; hidden: number },
  snapshots: number,
  /** The series is the open, a sample of the gap, and the latest page — not every row. */
  partial = false,
): string {
  const noun = (n: number) => `${n} ${n === 1 ? 'change' : 'changes'}`;
  if (partial) {
    // "Of N" is the full count on a complete history. On a sample that N is
    // not the book, so a cut table says how many rows are on screen and that
    // moves in between are missing. The snapshot length is not quoted.
    const head =
      r.shownChanges < r.changes
        ? `Last ${r.shownChanges} ${r.shownChanges === 1 ? 'change' : 'changes'} shown`
        : noun(r.changes);
    return `${head} · brief moves between samples may be missing`;
  }
  const head =
    r.shownChanges < r.changes
      ? `Last ${r.shownChanges} of ${r.changes} changes`
      : r.hidden > 0
        ? `${noun(r.changes)} · opening not shown`
        : noun(r.changes);
  return `${head} · ${snapshots} snapshots`;
}

/**
 * Right-hand side of the headline. After the start, that number is the close.
 * A non-live lock after the stored start shows only the pick's own number:
 * the close is earlier, so the arrow would run backwards.
 */
export function movementHeadline(lock: string, end: string, atClose: boolean, lockOnly = false): string {
  if (lockOnly) return lock;
  return atClose ? `${lock} → ${end} at the close` : `${lock} → ${end}`;
}

export type MovementVerdictKind = 'steady' | 'against' | 'favor' | 'steamed' | 'eased';

/** Verdict under the headline. The against-line names the pick, not the side key. */
export function movementVerdict(opts: {
  kind: MovementVerdictKind;
  atClose: boolean;
  lock?: string;
  end?: string;
  pp?: number | null;
}): string {
  const { kind, atClose } = opts;
  if (kind === 'steady') return atClose ? 'Line steady through the close' : 'Line steady since pick';
  if (kind === 'against') {
    const base = `Line moved ${opts.lock} → ${opts.end} against your pick`;
    return atClose ? `${base} by the close` : base;
  }
  if (kind === 'favor') {
    const base = `Line moved ${opts.lock} → ${opts.end} in your favor`;
    return atClose ? `${base} by the close` : base;
  }
  if (kind === 'steamed') {
    const n = (opts.pp ?? 0).toFixed(1);
    return atClose
      ? `Steamed ${n}pp against you by the close`
      : `Steamed ${n}pp against you since scoring`;
  }
  const abs = Math.abs(opts.pp ?? 0).toFixed(1);
  return atClose
    ? `Moved ${abs}pp in your favor by the close`
    : `Moved ${abs}pp in your favor since scoring`;
}

/**
 * Time cell. The last pregame row is the close once the game has started.
 * A live pick ends on Final only once the game is final. While it is still
 * on, that row is Latest. A gap row the bisect did not pin is an upper
 * bound, so it says "by 8:21 PM" (or "by 10/4 8:21 PM"). ET is the column
 * header, not the cell.
 */
export function historyTimeLabel(
  label: string,
  opts: {
    atCloseLast: boolean;
    atFinalLast?: boolean;
    atLatestLast?: boolean;
    bounded: boolean;
  },
): string {
  if (opts.atFinalLast) return 'Final';
  if (opts.atLatestLast) return 'Latest';
  if (opts.atCloseLast) return 'Close';
  if (opts.bounded) return `by ${label}`;
  return label;
}

/** The sentence under a live pick's headline. Not green, not red. */
export function inPlayMovementLabel(): string {
  return 'In-play prices since your pick';
}

function speakMagnitude(n: number, signed: boolean): string {
  const abs = Math.abs(n);
  const body = String(abs);
  if (n < 0) return `minus ${body}`;
  if (n > 0 && signed) return `plus ${body}`;
  return body;
}

/** "October 4 at 11:33 AM" in Eastern time. Seconds when the cell shows them. */
export function historySpokenWhen(at: string, seconds = false): string {
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return 'time not available';
  const time = (seconds ? secondFmt : minuteFmt).format(d);
  return `${spokenDateFmt.format(d)} at ${time}`;
}

/**
 * One VoiceOver label for a history row. Close, Final and Latest name
 * the row. A pinned minute says when it changed. A "by" cell is an upper
 * bound. A line is "plus" or "minus" only when the cell shows a sign.
 */
export function historyRowAccessibilityLabel(opts: {
  marker: string;
  at: string;
  line: number | null;
  price: number | null;
  showLine: boolean;
  signedLine?: boolean;
}): string {
  const seconds = /\d:\d{2}:\d{2}/.test(opts.marker);
  const spoken = historySpokenWhen(opts.at, seconds);
  const when =
    opts.marker === 'Close' || opts.marker === 'Final' || opts.marker === 'Latest'
      ? opts.marker
      : opts.marker.startsWith('by ')
        ? `No later than ${spoken}`
        : `Changed by ${spoken}`;
  const parts: string[] = [];
  if (opts.showLine) {
    parts.push(opts.line == null ? 'line not available' : `line ${speakMagnitude(opts.line, opts.signedLine === true)}`);
  }
  parts.push(opts.price == null ? 'price not available' : `price ${speakMagnitude(opts.price, true)}`);
  return `${when}: ${parts.join(', ')}`;
}

/** VoiceOver for the headline numbers. Minus is the word, not a hyphen. */
export function movementHeadlineLabel(opts: {
  kind: 'line' | 'price';
  lock: number | null;
  end: number | null;
  atClose: boolean;
  /** Spreads show a sign. Totals and props do not say "plus". */
  signedLine?: boolean;
  /** The pick's own number only. No arrow, no close. */
  lockOnly?: boolean;
}): string {
  const signed = opts.kind === 'price' || opts.signedLine === true;
  const speak = (n: number | null) => (n == null || Number.isNaN(n) ? 'not available' : speakMagnitude(n, signed));
  const noun = opts.kind === 'line' ? 'Line ' : 'Price ';
  if (opts.lockOnly) return `${noun}${speak(opts.lock)}`;
  const tail = opts.atClose ? ' at the close' : '';
  return `${noun}${speak(opts.lock)} to ${speak(opts.end)}${tail}`;
}

/** American price on this card. Minus is U+2212. A missing price is an em dash. */
export function formatHistoryAmerican(odds: number | null | undefined): string {
  if (odds == null || Number.isNaN(Number(odds))) return '—';
  const rounded = Math.round(Number(odds));
  if (rounded > 0) return `+${rounded}`;
  if (rounded < 0) return `\u2212${Math.abs(rounded)}`;
  return '0';
}

/**
 * A line on this card. Spreads always show a sign. A negative uses U+2212.
 * Null is an em dash, not "N/A".
 */
export function formatHistoryLine(line: number | null | undefined, explicitSign: boolean): string {
  if (line == null || Number.isNaN(Number(line))) return '—';
  const n = Number(line);
  const abs = Math.abs(n);
  const body = String(abs);
  if (n < 0) return `\u2212${body}`;
  if (n > 0 && explicitSign) return `+${body}`;
  return body;
}

/**
 * Samples across the span from the open to the start of the latest page,
 * counting the two ends the caller already holds. Interior probes are one
 * row each.
 */
export const LINE_HISTORY_BUCKETS = 12;

export interface HistoryProbe {
  ascending: boolean;
  limit: number;
  /** Inclusive lower bound on snapshot_at. */
  gte?: string;
  /** Exclusive upper bound on snapshot_at. */
  lt?: string;
  /**
   * Inclusive upper bound on snapshot_at. Pregame reads set this to the
   * game's commence_time, written in the series' own text form. Live reads
   * leave it unset.
   */
  lte?: string;
  /**
   * One newest row, no range. That row's suffix is how this series writes
   * snapshot_at. A range on this read would be the wrong offset.
   */
  unbounded?: boolean;
}

/**
 * What one history read is allowed to see.
 *
 * `until` is commence_time for a pregame pick, including one whose lock
 * is after that start. Every probe is `snapshot_at <= commence_time`.
 * `from` is the lock time for a live pick, which may read past the start.
 */
export interface LineHistoryWindow {
  from?: string;
  until?: string;
}

export interface SampledSeries<T> {
  rows: T[];
  /**
   * snapshot_at of gap rows whose time only bounds the move. The card prints
   * those as "by 3:10 PM ET".
   */
  moveByAt: string[];
}

/**
 * Postgres writes timestamps as text, and not all of it is ISO.
 * `created_at` since 2026-09-20 looks like `2026-10-05 01:00:00.123+00`
 * (a space, and `+00` with no minutes). Hermes parses the ECMA-262 form
 * `YYYY-MM-DDTHH:mm:ss.sssZ` or `±HH:MM`, and a space sorts before `T`, so
 * the raw string both fails to parse and compares before every ISO row.
 * Null when the text is not a timestamp.
 */
export function normalizeTimestamp(raw: string | null | undefined): string | null {
  if (raw == null) return null;
  const match = /^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}(?::?\d{2})?)?$/i.exec(
    raw.trim(),
  );
  if (!match) return null;
  const date = match[1];
  const time = match[2];
  const frac = match[3];
  const tz = match[4];
  let fraction = '';
  if (frac) fraction = `.${(frac.slice(1) + '000').slice(0, 3)}`;
  let zone = 'Z';
  if (tz) {
    if (tz.toUpperCase() === 'Z') zone = 'Z';
    else {
      const sign = tz[0] === '-' ? '-' : '+';
      const rest = tz.slice(1).replace(':', '');
      if (!/^\d{2,4}$/.test(rest)) return null;
      const hh = rest.slice(0, 2);
      const mm = (rest.slice(2, 4) || '00').padStart(2, '0');
      zone = `${sign}${hh}:${mm}`;
    }
  }
  const iso = `${date}T${time}${fraction}${zone}`;
  if (Number.isNaN(Date.parse(iso))) return null;
  return iso;
}

function instantMs(raw: string | null | undefined): number {
  const iso = normalizeTimestamp(raw);
  if (!iso) return Number.NaN;
  return Date.parse(iso);
}

/**
 * `snapshot_at` is text, so a bound has to wear the series' own suffix or
 * the comparison is not chronological. `2026-10-04T23:20:05-04:00` sorts
 * before `2026-10-05T00:10:00+00:00` even though it is three hours later.
 * `sampleTs` is one row from the series: same separator, fraction length
 * and offset spelling. Subseconds are dropped when the sample has none.
 */
export function formatBoundLike(sampleTs: string, instant: number | Date): string {
  const ms = typeof instant === 'number' ? instant : instant.getTime();
  if (!Number.isFinite(ms)) return '';
  const match = /^(\d{4}-\d{2}-\d{2})([ T])(\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]\d{2}(?::?\d{2})?)?$/i.exec(
    sampleTs.trim(),
  );
  if (!match) return new Date(ms).toISOString();
  const sep = match[2] === ' ' ? ' ' : 'T';
  const frac = match[4];
  const tz = match[5] ?? 'Z';
  let offsetMin = 0;
  let suffix = 'Z';
  if (tz.toUpperCase() === 'Z') {
    suffix = 'Z';
  } else {
    const sign = tz[0] === '-' ? -1 : 1;
    const rest = tz.slice(1).replace(':', '');
    const hh = Number(rest.slice(0, 2));
    const mm = Number(rest.slice(2, 4) || '0');
    if (!Number.isFinite(hh) || !Number.isFinite(mm)) return new Date(ms).toISOString();
    offsetMin = sign * (hh * 60 + mm);
    suffix = tz;
  }
  const shifted = new Date(ms + offsetMin * 60_000);
  const pad = (n: number) => String(n).padStart(2, '0');
  let fraction = '';
  if (frac) {
    const width = frac.length - 1;
    const digits = `${String(shifted.getUTCMilliseconds()).padStart(3, '0')}000000`;
    fraction = `.${digits.slice(0, width)}`;
  }
  return (
    `${shifted.getUTCFullYear()}-${pad(shifted.getUTCMonth() + 1)}-${pad(shifted.getUTCDate())}` +
    `${sep}${pad(shifted.getUTCHours())}:${pad(shifted.getUTCMinutes())}:${pad(shifted.getUTCSeconds())}` +
    `${fraction}${suffix}`
  );
}

/**
 * Pregame picks never read a row after the start. The worker keeps writing
 * odds after commence_time, mostly still tagged snapshot_type 'open', so the
 * cap is the timestamp.
 *
 * A live pick is `is_live === true` only. It reads from its lock and may
 * continue past the start. Any other pick is pregame and stops at
 * commence_time, even when the lock is later. Close is the latest row at
 * or before that start. A row between the start and the lock is in-play
 * and must not be labelled Close.
 *
 * Both instants come back normalized. An unparseable lock on a live pick
 * is unknown, not a pregame cap: capping it would hide the in-play rows
 * it was written on. An unparseable lock on any other pick still caps
 * at commence_time.
 */
export function lineHistoryWindow(input: {
  commenceTime: string | null | undefined;
  createdAt: string | null | undefined;
  isLive?: boolean | null;
}): LineHistoryWindow {
  const startRaw = input.commenceTime ?? '';
  const start = startRaw ? normalizeTimestamp(startRaw) : null;
  const kick = start ? Date.parse(start) : Number.NaN;
  if (!start || Number.isNaN(kick)) {
    // No start time on the game or the pick, so this read is not capped.
    return {};
  }
  if (input.isLive === true) {
    const createdRaw = input.createdAt ?? '';
    const created = createdRaw ? normalizeTimestamp(createdRaw) : null;
    if (!created || Number.isNaN(Date.parse(created))) {
      // The lock did not parse. Unknown, not pregame.
      return {};
    }
    return { from: created };
  }
  return { until: start };
}

/**
 * Non-live, and the lock is after the stored start. The series still ends
 * on the close, but that close is earlier than the lock, so a green or red
 * verdict would read the move backwards. Caller suppresses the verdict.
 */
export function nonLiveLockAfterStart(input: {
  commenceTime: string | null | undefined;
  createdAt: string | null | undefined;
  isLive?: boolean | null;
}): boolean {
  if (input.isLive === true) return false;
  const startRaw = input.commenceTime ?? '';
  const start = startRaw ? normalizeTimestamp(startRaw) : null;
  const kick = start ? Date.parse(start) : Number.NaN;
  if (!start || Number.isNaN(kick)) return false;
  const createdRaw = input.createdAt ?? '';
  const created = createdRaw ? normalizeTimestamp(createdRaw) : null;
  const locked = created ? Date.parse(created) : Number.NaN;
  return Number.isFinite(locked) && locked > kick;
}

/**
 * Instants strictly between `startIso` and `endIso`. `buckets` counts the
 * whole span, so the result length is `buckets - 2`.
 */
export function historyBucketInstants(startIso: string, endIso: string, buckets: number): string[] {
  const start = instantMs(startIso);
  const end = instantMs(endIso);
  const interior = buckets - 2;
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start || interior < 1) return [];
  const out: string[] = [];
  for (let i = 1; i <= interior; i++) {
    out.push(new Date(start + ((end - start) * i) / (interior + 1)).toISOString());
  }
  return out;
}

/**
 * Halves taken per changed gap. Six steps bring a bucket-width gap (about
 * a tenth of the pregame span) inside a quarter hour. Wider than that, or
 * a gap the cap did not spend queries on, stays an upper bound.
 */
export const LINE_HISTORY_BISECT_STEPS = 6;

/** Hard cap on the extra reads. Four changes get the full step budget. */
export const LINE_HISTORY_BISECT_CAP = 24;

/** A refined time within this of the previous bound is the move, not "by". */
const MOVE_TIGHT_MS = 60_000;

function applyBounds(probe: HistoryProbe, bounds?: LineHistoryWindow): HistoryProbe {
  let gte = probe.gte;
  const fromMs = bounds?.from ? instantMs(bounds.from) : Number.NaN;
  const gteMs = gte ? instantMs(gte) : Number.NaN;
  if (bounds?.from && Number.isFinite(fromMs) && (!gte || !Number.isFinite(gteMs) || fromMs > gteMs)) {
    gte = bounds.from;
  }
  const lte = bounds?.until ?? probe.lte;
  if (gte === probe.gte && lte === probe.lte) return probe;
  return { ...probe, gte, lte };
}

function rowQuote<T extends { snapshot_at: string }>(row: T, quote?: (row: T) => string): string {
  if (quote) return quote(row);
  const { snapshot_at: _at, ...rest } = row;
  return JSON.stringify(rest);
}

interface ChangeGap<T> {
  leftAt: string;
  right: T;
  span: number;
}

function changeGaps<T extends { snapshot_at: string }>(
  rows: T[],
  quote?: (row: T) => string,
): ChangeGap<T>[] {
  const out: ChangeGap<T>[] = [];
  for (let i = 1; i < rows.length; i++) {
    if (rowQuote(rows[i - 1], quote) === rowQuote(rows[i], quote)) continue;
    const span = instantMs(rows[i].snapshot_at) - instantMs(rows[i - 1].snapshot_at);
    if (span > MOVE_TIGHT_MS) out.push({ leftAt: rows[i - 1].snapshot_at, right: rows[i], span });
  }
  return out;
}

/**
 * Earliest snapshot in (leftAt, right] carrying right's quote. Empty halves
 * shrink the window without moving the candidate: no row there means the
 * move is not there. Stops at a minute, or after LINE_HISTORY_BISECT_STEPS.
 */
async function refineChange<T extends { snapshot_at: string }>(
  read: (probe: HistoryProbe) => Promise<T[]>,
  leftAt: string,
  right: T,
  quote?: (row: T) => string,
): Promise<{ row: T; tight: boolean }> {
  const key = rowQuote(right, quote);
  let lo = instantMs(leftAt);
  let hi = instantMs(right.snapshot_at);
  let best = right;
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi - lo <= MOVE_TIGHT_MS) {
    return { row: best, tight: true };
  }
  for (let step = 0; step < LINE_HISTORY_BISECT_STEPS; step++) {
    if (hi - lo <= MOVE_TIGHT_MS) break;
    const midMs = lo + (hi - lo) / 2;
    const row = (await read({
      ascending: true,
      limit: 1,
      gte: new Date(midMs).toISOString(),
      lt: best.snapshot_at,
    }))[0];
    if (!row?.snapshot_at) {
      hi = midMs;
      continue;
    }
    const t = instantMs(row.snapshot_at);
    if (!Number.isFinite(t) || t <= lo) break;
    if (rowQuote(row, quote) === key) {
      best = row;
      hi = t;
    } else {
      lo = t;
    }
  }
  return { row: best, tight: hi - lo <= MOVE_TIGHT_MS };
}

/**
 * Oldest-first snapshots from the open through the latest row the window
 * allows.
 *
 * A history that fits in one page comes back whole (latest page, reversed).
 * A full page has not reached the open, so the open is kept and the gap
 * before that page is sampled. The latest page is kept row for row — two
 * snapshots can share a timestamp — and the series always ends on it.
 *
 * `bounds.until` caps every probe, including that latest page. `bounds.from`
 * starts a live pick at its lock. With neither set, the read is unbounded.
 *
 * The first read is one newest row and no range. Every bound sent after that
 * is formatted like that row, because snapshot_at is text and a UTC cap does
 * not exclude a `-04:00` row. `quote` keys a move on the pick's side. The
 * default is the whole row, so the other side's price is a move.
 */
export async function sampleOpenToNow<T extends { snapshot_at: string }>(
  read: (probe: HistoryProbe) => Promise<T[]>,
  bounds?: LineHistoryWindow,
  quote?: (row: T) => string,
): Promise<SampledSeries<T>> {
  const sample = (await read({ ascending: false, limit: 1, unbounded: true }))[0];
  const sampleTs = sample?.snapshot_at;
  const like = (instant: string | number | undefined): string | undefined => {
    if (instant == null || instant === '') return undefined;
    const ms = typeof instant === 'number' ? instant : instantMs(instant);
    if (!Number.isFinite(ms)) return typeof instant === 'string' ? instant : undefined;
    if (!sampleTs) return new Date(ms).toISOString();
    return formatBoundLike(sampleTs, ms);
  };
  const bounded = (probe: HistoryProbe) => {
    const applied = applyBounds(probe, bounds);
    return read({
      ...applied,
      gte: applied.gte != null ? like(applied.gte) : undefined,
      lt: applied.lt != null ? like(applied.lt) : undefined,
      lte: applied.lte != null ? like(applied.lte) : undefined,
    });
  };
  const [latestDesc, openRows] = await Promise.all([
    bounded({ ascending: false, limit: LINE_HISTORY_PAGE }),
    bounded({ ascending: true, limit: 1 }),
  ]);
  const latest = latestDesc.slice().reverse();
  if (latest.length < LINE_HISTORY_PAGE) {
    return { rows: rowsWithinWindow(latest, bounds), moveByAt: [] };
  }

  const open = openRows[0];
  const pageStart = latest[0]?.snapshot_at;
  if (!open?.snapshot_at || !pageStart || instantMs(open.snapshot_at) >= instantMs(pageStart)) {
    return { rows: rowsWithinWindow(latest, bounds), moveByAt: [] };
  }

  const instants = historyBucketInstants(open.snapshot_at, pageStart, LINE_HISTORY_BUCKETS);
  const probed = await Promise.all(
    instants.map((gte) => bounded({ ascending: true, limit: 1, gte, lt: pageStart })),
  );
  const seen = new Set(latest.map((r) => r.snapshot_at));
  const head: T[] = [];
  for (const row of [open, ...probed.flat()]) {
    if (!row?.snapshot_at || seen.has(row.snapshot_at)) continue;
    seen.add(row.snapshot_at);
    head.push(row);
  }
  head.sort((a, b) => instantMs(a.snapshot_at) - instantMs(b.snapshot_at));

  const gaps = changeGaps(head, quote);
  const prev = head[head.length - 1];
  const first = latest[0];
  if (prev && first && rowQuote(prev, quote) !== rowQuote(first, quote)) {
    const span = instantMs(first.snapshot_at) - instantMs(prev.snapshot_at);
    if (span > MOVE_TIGHT_MS) gaps.push({ leftAt: prev.snapshot_at, right: first, span });
  }
  gaps.sort((a, b) => b.span - a.span);
  const slots = Math.floor(LINE_HISTORY_BISECT_CAP / LINE_HISTORY_BISECT_STEPS);
  const chosen = gaps.slice(0, slots);
  const skipped = gaps.slice(slots);

  const refined = await Promise.all(
    chosen.map((gap) => refineChange(bounded, gap.leftAt, gap.right, quote)),
  );
  const replacements = new Map<string, T>();
  const moveByAt: string[] = [];
  chosen.forEach((gap, i) => {
    const result = refined[i];
    if (result.row.snapshot_at !== gap.right.snapshot_at) {
      replacements.set(gap.right.snapshot_at, result.row);
    }
    if (!result.tight) moveByAt.push(result.row.snapshot_at);
  });
  for (const gap of skipped) moveByAt.push(gap.right.snapshot_at);

  const headSeen = new Set(latest.map((r) => r.snapshot_at));
  const headOut: T[] = [];
  for (const row of head) {
    const next = replacements.get(row.snapshot_at) ?? row;
    if (headSeen.has(next.snapshot_at)) continue;
    headSeen.add(next.snapshot_at);
    headOut.push(next);
  }
  let tail = latest;
  if (first) {
    const junction = replacements.get(first.snapshot_at);
    if (junction && junction.snapshot_at !== first.snapshot_at && !headSeen.has(junction.snapshot_at)) {
      tail = [junction, ...latest];
    }
  }
  const rows = rowsWithinWindow([...headOut, ...tail], bounds);
  rows.sort((a, b) => instantMs(a.snapshot_at) - instantMs(b.snapshot_at));
  const kept = new Set(rows.map((row) => row.snapshot_at));
  return { rows, moveByAt: moveByAt.filter((at) => kept.has(at)) };
}

/**
 * Real-time window on the assembled series. A mixed offset can still satisfy
 * a text cap: `2026-10-04T20:00:00-05:00` is after a 00:10Z start and still
 * sorts before `2026-10-04T20:10:00-04:00`. Those rows never reach the card.
 */
function rowsWithinWindow<T extends { snapshot_at: string }>(rows: T[], bounds?: LineHistoryWindow): T[] {
  if (!bounds?.from && !bounds?.until) return rows;
  const fromMs = bounds.from ? instantMs(bounds.from) : Number.NEGATIVE_INFINITY;
  const untilMs = bounds.until ? instantMs(bounds.until) : Number.POSITIVE_INFINITY;
  return rows.filter((row) => {
    const t = instantMs(row.snapshot_at);
    if (!Number.isFinite(t)) return false;
    return t >= fromMs && t <= untilMs;
  });
}
