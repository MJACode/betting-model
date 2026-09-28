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
 * so it is not counted; a mid-run null (a snapshot with no price or no line
 * for the side) is a gap in the feed, not a move to "N/A" and back, so it
 * carries the run's value and joins the run; and every row has a unique
 * `key`, because two snapshots can share a timestamp.
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
  const runs: Array<HistoryPoint & { count: number }> = [];
  for (const p of points) {
    const last = runs[runs.length - 1];
    // A null mid-run is a gap in the feed, not a change to "N/A": it carries
    // the run's value (and so joins the run).
    const line = p.line == null && last ? last.line : p.line;
    const price = p.price == null && last ? last.price : p.price;
    if (last && last.line === line && last.price === price) last.count += 1;
    else runs.push({ ...p, line, price, count: 1 });
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
