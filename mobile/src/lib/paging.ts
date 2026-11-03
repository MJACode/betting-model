/**
 * Drain a PostgREST read that can exceed the server's row cap.
 *
 * SUPABASE CAPS EVERY RESPONSE AT max-rows (1,000 on this project: no
 * `pgrst.db_max_rows` override on the `authenticator` role, so the platform
 * default applies), WHATEVER `.limit()` ASKS FOR. The cap is silent — no
 * error, no header the client reads — so a `.limit(20000)` over a 1,912-row
 * day returned the first 1,000 rows and the Stats board printed a DraftKings
 * line for the games that happened to sort first and a dash for the rest
 * (2026-09-04, 4:59pm: Harper priced, Betts / Perez / Santana blank while
 * DraftKings had posted all four since the early morning).
 *
 * `page` builds the query for one window; the caller adds its filters and a
 * DETERMINISTIC order, because PostgREST range paging without one can repeat
 * or skip rows between windows. Advances by what actually came back and stops
 * only on an empty page — the same rule as fetchSettledPicks, for the same
 * reason: treating a short page as the end is the truncation this exists to
 * remove.
 */
export const PAGE_ROWS = 1000;
const MAX_PAGES = 100;

/**
 * A page that hits the database's statement timeout (57014) is asked for once
 * more before the read fails. The first read of the day runs on a cold cache:
 * on 2026-10-31 the Stats board's first NBA page timed out at 15:35:43 and
 * 15:37:10 UTC (anon's limit is 3s, the read took 3.6s cold) and the same
 * request succeeded right after. Only a timeout is retried, and only once per
 * read (not per page), so a real failure still reaches the error state and a
 * slow read cannot double its wait on every page.
 */
export function isStatementTimeout(error: unknown): boolean {
  if (error == null || typeof error !== 'object') return false;
  const o = error as Record<string, unknown>;
  if (o.code === '57014') return true;
  return typeof o.message === 'string' && /statement timeout/i.test(o.message);
}

export async function fetchAllPages<T>(
  page: (from: number, to: number) => PromiseLike<{ data: unknown[] | null; error: unknown }>,
  /** A row's identity, when the caller has one. The refresh pass writes between
   *  pages, and a key inserted mid-drain shifts every later offset by one, so
   *  the row at the seam comes back twice; with a key the repeat is dropped. */
  keyOf?: (row: T) => string,
): Promise<T[]> {
  const out: T[] = [];
  const seen = keyOf ? new Set<string>() : null;
  let from = 0;
  let retried = false;
  for (let i = 0; i < MAX_PAGES; i++) {
    let { data, error } = await page(from, from + PAGE_ROWS - 1);
    if (error && !retried && isStatementTimeout(error)) {
      retried = true;
      ({ data, error } = await page(from, from + PAGE_ROWS - 1));
    }
    if (error) throw error;
    const rows = (data ?? []) as T[];
    if (rows.length === 0) break;
    for (const row of rows) {
      if (seen && keyOf) {
        const k = keyOf(row);
        if (seen.has(k)) continue;
        seen.add(k);
      }
      out.push(row);
    }
    from += rows.length;
  }
  return out;
}
