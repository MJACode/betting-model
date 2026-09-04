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

export async function fetchAllPages<T>(
  page: (from: number, to: number) => PromiseLike<{ data: unknown[] | null; error: unknown }>,
): Promise<T[]> {
  const out: T[] = [];
  let from = 0;
  for (let i = 0; i < MAX_PAGES; i++) {
    const { data, error } = await page(from, from + PAGE_ROWS - 1);
    if (error) throw error;
    const rows = (data ?? []) as T[];
    if (rows.length === 0) break;
    out.push(...rows);
    from += rows.length;
  }
  return out;
}
