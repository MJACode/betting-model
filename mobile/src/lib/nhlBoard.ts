/**
 * Words and the shots line for the NHL Players board.
 *
 * The averages caption and the add-to-betslip sheet say the same sentence.
 * A half-point line of 2.5 is "3 or more shots". The sheet does not switch
 * to "Over 2.5" for that bet.
 */

/** The line the most players are posted at. A tie keeps the lower line. */
export function mostCommonPostedLine(
  rows: readonly { player_name?: string | null; line: number | string | null }[],
): number | null {
  const players = new Map<number, Set<string>>();
  for (const r of rows) {
    const n = typeof r.line === 'number' ? r.line : Number(r.line);
    if (!Number.isFinite(n)) continue;
    const name = (r.player_name ?? '').trim().toLowerCase();
    if (!name) continue;
    const set = players.get(n) ?? new Set<string>();
    set.add(name);
    players.set(n, set);
  }
  let best: number | null = null;
  let count = 0;
  for (const [line, names] of players) {
    if (names.size > count || (names.size === count && best != null && line < best)) {
      best = line;
      count = names.size;
    }
  }
  return best;
}

/**
 * Ruler stop for a half-point line in At Least. selectionFor(n).line is
 * n − 0.5, so a posted 1.5 is stop 2 ("2 or more").
 */
export function stopForPostedLine(line: number): number {
  return line + 0.5;
}

/**
 * One sentence for the caption under the chips and for the sheet.
 *
 * Anytime goal scorer is priced only at 0.5 (measured 2026-10-17:
 * `player_goal_scorer_anytime`, game_date from 2026-10-01, one line,
 * 691 players). A ruler stop past 1 is not that bet, so it gets no caption.
 */
export function nhlBetCaption(line: number, statKey: string): string | null {
  if (statKey === 'goals') {
    if (line !== 0.5) return null;
    return 'Anytime goal scorer: 1 or more goals';
  }
  // A whole number is not "line + 0.5 or more". 2 is not "2.5 or more shots".
  const n = nhlPlainCount(line, 'over');
  if (n == null) return null;
  const noun =
    statKey === 'shots' ? 'shots'
    : statKey === 'points' ? 'points'
    : statKey === 'assists' ? 'assists'
    : statKey;
  return `${n} or more ${noun}`;
}

/**
 * The whole-number count behind a half-point line, when that count is at least 1.
 *
 * 2.5 over is 3. 1.5 under is 1. A whole number is not that sentence
 * ("Over 2" is not "2.5 or more"), and Under 0.5 is 0, which is not "or fewer".
 */
export function nhlPlainCount(line: number, side: 'over' | 'under'): number | null {
  if (!Number.isFinite(line)) return null;
  const doubled = Math.round(line * 2);
  if (Math.abs(line * 2 - doubled) > 1e-6 || doubled % 2 === 0) return null;
  const count = side === 'under' ? (doubled - 1) / 2 : (doubled + 1) / 2;
  if (count < 1) return null;
  return count;
}

/** The off-line pill caption. The board says "3 or more", so the pill does too. */
export function nhlOffLineCount(line: number, side: 'over' | 'under'): string | null {
  const count = nhlPlainCount(line, side);
  if (count == null) return null;
  const how = side === 'under' ? 'or fewer' : 'or more';
  return `${count} ${how}`;
}

/**
 * Move the Shots ruler onto the posted line once per NHL visit.
 *
 * A later refetch, and a return to the Shots chip, leave the number the
 * user already has. `appliedSport` is the sport this visit already opened.
 */
export function shouldOpenShotsLine(
  sport: string,
  statKey: string | null,
  postedLine: number | null,
  appliedSport: string | null,
): boolean {
  return sport === 'NHL' && statKey === 'shots' && postedLine != null && appliedSport !== sport;
}

/** Codes that mean the skater average cannot be read yet, and nothing else.
 *
 * 42501: player_window_totals_nhl is SECURITY INVOKER and nhl_skater_game_log
 * has RLS on with no policy and no anon SELECT, so the call is permission
 * denied until #962. PGRST202 and 42883: the function is not in the schema
 * until this migration runs. A timeout, a missing table, or a permission
 * sentence with a different code stays a real error.
 */
const NHL_SKATER_READ_MISSING = new Set(['42501', 'PGRST202', '42883']);

export function nhlSkaterReadMissing(error: unknown): boolean {
  if (error == null || typeof error !== 'object') return false;
  const code = (error as { code?: unknown }).code;
  return typeof code === 'string' && NHL_SKATER_READ_MISSING.has(code);
}

/** Section title above priced names the log did not rank. */
export function nhlLineOnlyTitle(logEmpty: boolean): string {
  return logEmpty ? 'Lines are up.' : 'Has a line';
}

/**
 * Empty-board sentence when the ranked list is empty. A missing line is not
 * "no data for the last 10 games".
 */
export function nhlEmptyBoardText(hasLines: boolean, statLabel: string): string | null {
  if (hasLines) return null;
  return `No ${statLabel} lines posted yet.`;
}
