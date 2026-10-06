/**
 * Scoring unit on the pick-detail form strip.
 *
 * The strip used to print "R" for every sport. That is runs, and it is right
 * for baseball only. NFL and NCAAF averages are points (a college total near
 * 48 was showing as "48.0 R"); hockey is goals. The short-window count under
 * the average says "games", not "G" — in hockey "G" is goals.
 */
export function teamScoringUnit(sport: string | null | undefined): string {
  switch (sport) {
    case 'MLB':
      return 'R';
    case 'NHL':
      return 'goals';
    case 'NFL':
    case 'NCAAF':
    case 'NBA':
    case 'WNBA':
      return 'pts';
    default:
      return '';
  }
}

/** The same unit, in the words VoiceOver should speak. */
export function teamScoringUnitSpoken(sport: string | null | undefined): string {
  switch (sport) {
    case 'MLB':
      return 'runs';
    case 'NHL':
      return 'goals';
    case 'NFL':
    case 'NCAAF':
    case 'NBA':
    case 'WNBA':
      return 'points';
    default:
      return '';
  }
}

/** How many games each team-strip column asks for. The fifth column is L25. */
export const TEAM_WINDOW_SIZE: Record<string, number> = {
  l3: 3,
  l5: 5,
  l10: 10,
  l20: 20,
  season: 25,
};

/**
 * The games line under a team cell. A full window already says L5 / L25, so
 * the count is only there when the window is short. Zero is a missing fetch,
 * not "0 games".
 */
export function teamGamesRow(games: number, windowSize: number): string | null {
  if (games <= 0 || games >= windowSize) return null;
  return `${games} ${games === 1 ? 'game' : 'games'}`;
}

/** How many of the fetched games belong to the pick's season. Null if we don't know the season. */
export function countThisSeason(
  games: Array<{ season: number | null }>,
  season: number | null | undefined,
): number | null {
  if (season == null) return null;
  return games.filter((g) => g.season === season).length;
}

/**
 * One line under the strip when a column reaches into an earlier season.
 * Names the smallest window that does. Null when every game is this season,
 * or when the season is unknown.
 */
export function teamSeasonNote(
  seasonGames: number | null | undefined,
  counts: { l3: number; l5: number; l10: number; l20: number; l25: number },
): string | null {
  if (seasonGames == null) return null;
  if (!(counts.l25 > seasonGames)) return null;
  if (seasonGames === 0) {
    return 'No games yet this season. Every column is from earlier seasons.';
  }
  const windows = [
    { label: 'L3', games: counts.l3 },
    { label: 'L5', games: counts.l5 },
    { label: 'L10', games: counts.l10 },
    { label: 'L20', games: counts.l20 },
    { label: 'L25', games: counts.l25 },
  ];
  const first = windows.find((w) => w.games > seasonGames);
  const label = first?.label ?? 'L25';
  const head = `This season: ${seasonGames} ${seasonGames === 1 ? 'game' : 'games'}. `;
  const tail =
    label === 'L25' ? 'L25 includes earlier seasons.' : `${label}–L25 include earlier seasons.`;
  return head + tail;
}

/**
 * One VoiceOver label for a team cell. The window name is "Last 5", not the
 * separate "L5" / "40%" / "18.8 pts" / "5 G" pieces.
 */
export function teamCellAccessibilityLabel(opts: {
  window: number;
  games: number;
  winPct: number | null;
  avg: number | null;
  spokenUnit: string;
  seasonGames?: number | null;
}): string {
  const n = opts.window;
  let head = `Last ${n} ${n === 1 ? 'game' : 'games'}`;
  if (opts.games > 0 && opts.games < n) {
    head += `, ${opts.games} ${opts.games === 1 ? 'game' : 'games'} played`;
  }
  if (opts.seasonGames != null && opts.games > opts.seasonGames) {
    head += ', including earlier seasons';
  }
  const won =
    opts.winPct != null ? `won ${Math.round(opts.winPct * 100)} percent` : 'won not available';
  const avg =
    opts.avg == null
      ? 'average not available'
      : `${opts.avg.toFixed(1)}${opts.spokenUnit ? ` ${opts.spokenUnit}` : ''} a game`;
  return `${head}: ${won}, ${avg}`;
}
