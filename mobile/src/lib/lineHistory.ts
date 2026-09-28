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
 * The table's footer. "Last 8 of 19 changes" only when changes are really cut;
 * when the one row off the top is the OPENING, every change is on screen and
 * "Last 8 of 8 changes" read as a cut that wasn't (Reviewer #847) — it says
 * "8 changes · opening not shown" instead.
 */
export function changesFooter(
  r: { changes: number; shownChanges: number; hidden: number },
  snapshots: number,
): string {
  const noun = (n: number) => `${n} ${n === 1 ? 'change' : 'changes'}`;
  const head =
    r.shownChanges < r.changes
      ? `Last ${r.shownChanges} of ${r.changes} changes`
      : r.hidden > 0
        ? `${noun(r.changes)} · opening not shown`
        : noun(r.changes);
  return `${head} · ${snapshots} snapshots`;
}
