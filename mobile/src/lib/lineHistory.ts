/**
 * Line-movement rows for Pick Detail — usability audit M13 (PR 3).
 *
 * The table used to print the last 8 raw snapshots: on a busy market that was
 * eight rows stamped "3:50 PM ET" alternating −105 / −115, which is noise, not
 * a story. Now a row is a CHANGE: consecutive snapshots at the same line and
 * price collapse into the first of the run, and two rows that would print the
 * same minute get seconds so the order is readable. Pure (Intl only).
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
    if (last && last.line === p.line && last.price === p.price) last.count += 1;
    else runs.push({ ...p, count: 1 });
  }
  const minutes = runs.map((r) => stamp(r.at, false));
  const clash = new Set(minutes.filter((m, i) => minutes.indexOf(m) !== i));
  return runs.map((r, i) => ({ ...r, label: clash.has(minutes[i]) ? stamp(r.at, true) : minutes[i] }));
}

/** The last `n` changes, oldest → newest (what the card shows). */
export function recentChanges(points: HistoryPoint[], n = 8): { rows: HistoryRow[]; changes: number } {
  const all = collapseLineHistory(points);
  return { rows: all.slice(-n), changes: all.length };
}
