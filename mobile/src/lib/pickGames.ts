/**
 * The games a board's picks name that its by-date games read did not return.
 *
 * A board reads picks and games for the same date, and pairs them by
 * game_id. A game's row can move to another date after its pick was
 * written: NCAAB Washington @ Utah was bet on 2026-11-15 and its row moved
 * to 2026-12-05 when the game was postponed. The card then had no game, so
 * it lost its team and matchup and headlined a bare "ML".
 *
 * Measured 2026-11-15: at most 2 such games a day over the month before.
 * So the extra read is small, and no read is made on a day with none.
 */
import type { GameRow } from '../types';

/** The distinct game ids the picks name that `gameById` does not hold. */
export function missingGameIds(
  picks: readonly { game_id: string | null | undefined }[],
  gameById: ReadonlyMap<string, GameRow>,
): string[] {
  const out = new Set<string>();
  for (const p of picks) {
    const id = p.game_id;
    if (id && !gameById.has(id)) out.add(id);
  }
  return Array.from(out);
}

/**
 * Adds the missing games to `gameById`, asked for by id through `readByIds`.
 * Enrichment only: a failed read leaves those cards as they were and is
 * returned, so the caller can report it (fetchPicksForDate's
 * onEnrichmentError); null when nothing failed.
 */
export async function fillMissingGames(
  picks: readonly { game_id: string | null | undefined }[],
  gameById: Map<string, GameRow>,
  readByIds: (ids: string[]) => PromiseLike<{ data: unknown; error: unknown }>,
): Promise<unknown> {
  const missing = missingGameIds(picks, gameById);
  if (missing.length === 0) return null;
  let res: { data: unknown; error: unknown };
  try {
    res = await readByIds(missing);
  } catch (e) {
    return e ?? new Error('games read failed');
  }
  if (res.error) return res.error;
  if (!Array.isArray(res.data)) return null;
  for (const g of res.data as GameRow[]) {
    if (g && typeof g.game_id === 'string') gameById.set(g.game_id, g);
  }
  return null;
}
