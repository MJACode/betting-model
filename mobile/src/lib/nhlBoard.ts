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

/** One sentence for the caption under the chips and for the sheet. */
export function nhlBetCaption(line: number, statKey: string): string {
  const n = line + 0.5;
  if (statKey === 'goals') return `Anytime goal scorer: ${n} or more goals`;
  const noun =
    statKey === 'shots' ? 'shots'
    : statKey === 'points' ? 'points'
    : statKey === 'assists' ? 'assists'
    : statKey;
  return `${n} or more ${noun}`;
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
