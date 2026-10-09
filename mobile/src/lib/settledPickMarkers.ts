/**
 * Markers that reach rows the settled-pick cache already holds.
 *
 * The cache (settledPickCache) re-downloads only the trailing
 * REFRESH_WINDOW_DAYS and keeps every older row exactly as it was first
 * fetched. A marker can land on a row long after that. The second copy of one
 * bet under another game id is marked condition_status = DUPLICATE only once
 * both copies have settled and someone has written the migration (mike,
 * 2026-10-09: "Count each fight once"). A phone that cached the row before
 * then would keep counting both copies in the model screen's bet history and
 * CLV, and in custom-model backtests, while the header above them (the
 * published view) counts one.
 *
 * So every load also reads the condition_status of every pick since the record
 * start that has one (118 rows on 2026-10-09, about 25ms on the server), and
 * this copies the server's value onto the cached rows. That list is complete
 * for the range, so a cached row missing from it has no marker on the server
 * and goes back to null, which is what a rolled-back marking looks like.
 *
 * Pure (no React Native imports) so it runs under node in the test suite.
 */
import type { SettledPick } from '@/types';

export interface SettledPickMarker {
  pick_id: number;
  condition_status: string | null;
}

/**
 * The cached rows with the server's condition_status on every row dated
 * `since` or later. `markers` is null when the read failed: the rows come back
 * unchanged, never cleared, and the next load tries again.
 */
export function applySettledMarkers(
  rows: SettledPick[],
  markers: SettledPickMarker[] | null,
  since: string,
): SettledPick[] {
  if (markers == null) return rows;
  const byId = new Map<number, string | null>();
  for (const m of markers) byId.set(Number(m.pick_id), m.condition_status ?? null);
  return rows.map((r) => {
    if (r.game_date < since) return r;
    const server = byId.get(Number(r.pick_id)) ?? null;
    return (r.condition_status ?? null) === server ? r : { ...r, condition_status: server };
  });
}
