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
  /** "3:50 PM ET", or "3:50:12 PM ET" when another row shares its minute. */
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

function stamp(at: string, seconds: boolean): string {
  const d = new Date(at);
  if (Number.isNaN(d.getTime())) return '—';
  return `${(seconds ? secondFmt : minuteFmt).format(d)} ET`;
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
  const minutes = runs.map((r) => stamp(r.at, false));
  const clash = new Set(minutes.filter((m, i) => minutes.indexOf(m) !== i));
  return runs.map((r, i) => ({
    ...r,
    opening: i === 0,
    key: `${r.at}#${i}`,
    label: clash.has(minutes[i]) ? stamp(r.at, true) : minutes[i],
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
    return `${head} · some intermediate moves aren't listed`;
  }
  const head =
    r.shownChanges < r.changes
      ? `Last ${r.shownChanges} of ${r.changes} changes`
      : r.hidden > 0
        ? `${noun(r.changes)} · opening not shown`
        : noun(r.changes);
  return `${head} · ${snapshots} snapshots`;
}

/** Right-hand side of the headline. After the start, that number is the close. */
export function movementHeadline(lock: string, end: string, atClose: boolean): string {
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
 * A gap row the bisect did not pin is an upper bound, so it says "by 3:10 PM ET".
 */
export function historyTimeLabel(
  label: string,
  opts: { atCloseLast: boolean; bounded: boolean },
): string {
  if (opts.atCloseLast) return 'Close';
  if (opts.bounded) return `by ${label}`;
  return label;
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
   * game's commence_time. Live reads leave it unset.
   */
  lte?: string;
}

/**
 * What one history read is allowed to see.
 *
 * `until` is commence_time for a pregame pick: every probe, including the
 * latest page, is `snapshot_at <= commence_time`. `from` is the lock time
 * for a live pick, which may read past the start.
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
 * Pregame picks never read a row after the start. The worker keeps writing
 * odds after commence_time, mostly still tagged snapshot_type 'open', so the
 * cap is the timestamp.
 *
 * A live pick — `is_live`, or created at/after the start — reads from its
 * lock and may continue past the start.
 */
export function lineHistoryWindow(input: {
  commenceTime: string | null | undefined;
  createdAt: string | null | undefined;
  isLive?: boolean | null;
}): LineHistoryWindow {
  const start = input.commenceTime ?? '';
  const kick = Date.parse(start);
  if (!start || Number.isNaN(kick)) {
    // No start time on the game or the pick, so this read is not capped.
    return {};
  }
  const created = input.createdAt ?? '';
  const locked = Date.parse(created);
  const live = input.isLive === true || (Number.isFinite(locked) && locked >= kick);
  if (live) {
    if (!Number.isFinite(locked)) return {};
    return { from: created };
  }
  return { until: start };
}

/**
 * Instants strictly between `startIso` and `endIso`. `buckets` counts the
 * whole span, so the result length is `buckets - 2`.
 */
export function historyBucketInstants(startIso: string, endIso: string, buckets: number): string[] {
  const start = Date.parse(startIso);
  const end = Date.parse(endIso);
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
  if (bounds?.from && (!gte || Date.parse(bounds.from) > Date.parse(gte))) {
    gte = bounds.from;
  }
  const lte = bounds?.until ?? probe.lte;
  if (gte === probe.gte && lte === probe.lte) return probe;
  return { ...probe, gte, lte };
}

function quoteKey(row: { snapshot_at: string }): string {
  const { snapshot_at: _at, ...rest } = row;
  return JSON.stringify(rest);
}

interface ChangeGap<T> {
  leftAt: string;
  right: T;
  span: number;
}

function changeGaps<T extends { snapshot_at: string }>(rows: T[]): ChangeGap<T>[] {
  const out: ChangeGap<T>[] = [];
  for (let i = 1; i < rows.length; i++) {
    if (quoteKey(rows[i - 1]) === quoteKey(rows[i])) continue;
    const span = Date.parse(rows[i].snapshot_at) - Date.parse(rows[i - 1].snapshot_at);
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
): Promise<{ row: T; tight: boolean }> {
  const key = quoteKey(right);
  let lo = Date.parse(leftAt);
  let hi = Date.parse(right.snapshot_at);
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
    const t = Date.parse(row.snapshot_at);
    if (!Number.isFinite(t) || t <= lo) break;
    if (quoteKey(row) === key) {
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
 */
export async function sampleOpenToNow<T extends { snapshot_at: string }>(
  read: (probe: HistoryProbe) => Promise<T[]>,
  bounds?: LineHistoryWindow,
): Promise<SampledSeries<T>> {
  const bounded = (probe: HistoryProbe) => read(applyBounds(probe, bounds));
  const [latestDesc, openRows] = await Promise.all([
    bounded({ ascending: false, limit: LINE_HISTORY_PAGE }),
    bounded({ ascending: true, limit: 1 }),
  ]);
  const latest = latestDesc.slice().reverse();
  if (latest.length < LINE_HISTORY_PAGE) return { rows: latest, moveByAt: [] };

  const open = openRows[0];
  const pageStart = latest[0]?.snapshot_at;
  if (!open?.snapshot_at || !pageStart || Date.parse(open.snapshot_at) >= Date.parse(pageStart)) {
    return { rows: latest, moveByAt: [] };
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
  head.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));

  const gaps = changeGaps(head);
  const prev = head[head.length - 1];
  const first = latest[0];
  if (prev && first && quoteKey(prev) !== quoteKey(first)) {
    const span = Date.parse(first.snapshot_at) - Date.parse(prev.snapshot_at);
    if (span > MOVE_TIGHT_MS) gaps.push({ leftAt: prev.snapshot_at, right: first, span });
  }
  gaps.sort((a, b) => b.span - a.span);
  const slots = Math.floor(LINE_HISTORY_BISECT_CAP / LINE_HISTORY_BISECT_STEPS);
  const chosen = gaps.slice(0, slots);
  const skipped = gaps.slice(slots);

  const refined = await Promise.all(
    chosen.map((gap) => refineChange(bounded, gap.leftAt, gap.right)),
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
  const rows = [...headOut, ...tail];
  rows.sort((a, b) => Date.parse(a.snapshot_at) - Date.parse(b.snapshot_at));
  return { rows, moveByAt };
}
