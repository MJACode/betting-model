/**
 * Scoring unit on the pick-detail form strip.
 *
 * The strip used to print "R" for every sport. That is runs, and it is right
 * for baseball only. NFL and NCAAF averages are points (a college total near
 * 48 was showing as "48.0 R"); hockey is goals. A short fetch is named once
 * under the strip, not as a count inside the cell.
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

/** How many games each team-strip column asks for. The fifth column is not always 25. */
export const TEAM_WINDOW_SIZE: Record<string, number> = {
  l3: 3,
  l5: 5,
  l10: 10,
  l20: 20,
  season: 25,
};

/**
 * Visible name of the fifth team column.
 *
 * Season when the games shown are the whole current season (fewer than 25,
 * and every one of them is this season). L25 when the column is the last 25,
 * which may reach an earlier season. A shorter list that already does is
 * the last N games, not Season and not L25. Zero games is not a last-25 window.
 */
export function teamFifthColumnLabel(games: number, seasonGames?: number | null): string {
  if (games >= TEAM_WINDOW_SIZE.season) return 'L25';
  if (games > 0 && seasonGames != null && games > seasonGames) return `L${games}`;
  if (games > 0 && seasonGames == null) return `L${games}`;
  return 'Season';
}

/** "L5–Season", or a list when the last label is not a wider window than the first. */
function columnSpan(labels: string[]): string {
  if (labels.length <= 1) return labels[0] ?? '';
  const last = labels[labels.length - 1];
  const lastN = /^L(\d+)$/.exec(last);
  const firstN = /^L(\d+)$/.exec(labels[0]);
  const wider =
    last === 'Season' ||
    last === 'L25' ||
    (lastN != null && firstN != null && Number(lastN[1]) > Number(firstN[1]));
  if (wider) return `${labels[0]}–${last}`;
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels.slice(0, -1).join(', ')} and ${last}`;
}

/**
 * One line under the strip when the fetch is shorter than a column.
 * The count used to sit in the cell, and at large text "4 games" ran into
 * the next column. Zero is a missing fetch, not "0 games". A full 25
 * already names every column. The last name is the fifth column's own
 * label, so a season is not called L25. When the window also reaches an
 * earlier season, "so far" would sit next to "This season: N games" and
 * contradict it, so that case says "available".
 */
export function teamShortWindowNote(
  counts: {
    l3: number;
    l5: number;
    l10: number;
    l20: number;
    l25: number;
  },
  seasonGames?: number | null,
): string | null {
  const n = Math.max(counts.l3, counts.l5, counts.l10, counts.l20, counts.l25);
  if (n <= 0 || n >= TEAM_WINDOW_SIZE.season) return null;
  const fifth = teamFifthColumnLabel(counts.l25, seasonGames);
  const windows = [
    { label: 'L3', size: TEAM_WINDOW_SIZE.l3 },
    { label: 'L5', size: TEAM_WINDOW_SIZE.l5 },
    { label: 'L10', size: TEAM_WINDOW_SIZE.l10 },
    { label: 'L20', size: TEAM_WINDOW_SIZE.l20 },
    { label: fifth, size: TEAM_WINDOW_SIZE.season },
  ];
  const short = windows.filter((w) => n < w.size);
  if (short.length === 0) return null;
  const gamesWord = n === 1 ? 'game' : 'games';
  const those = n === 1 ? 'that 1' : `those ${n}`;
  const span = columnSpan(short.map((w) => w.label));
  const use = short.length === 1 ? 'uses' : 'all use';
  const crossSeason = seasonGames != null && counts.l25 > seasonGames;
  const how = crossSeason ? 'available' : 'so far';
  return `Only ${n} ${gamesWord} ${how}. ${span} ${use} ${those}.`;
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
  const fifth = teamFifthColumnLabel(counts.l25, seasonGames);
  const windows = [
    { label: 'L3', games: counts.l3 },
    { label: 'L5', games: counts.l5 },
    { label: 'L10', games: counts.l10 },
    { label: 'L20', games: counts.l20 },
    { label: fifth, games: counts.l25 },
  ];
  const first = windows.find((w) => w.games > seasonGames);
  const label = first?.label ?? fifth;
  const head = `This season: ${seasonGames} ${seasonGames === 1 ? 'game' : 'games'}. `;
  const tail =
    label === fifth ? `${fifth} includes earlier seasons.` : `${label}–${fifth} include earlier seasons.`;
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
  /** Fifth column only. Season is not spoken as "Last 25". */
  columnLabel?: string;
}): string {
  const n = opts.window;
  const named = opts.columnLabel;
  const fromLabel = named != null && /^L(\d+)$/.test(named) ? Number(named.slice(1)) : null;
  const spokenN = fromLabel ?? n;
  let head =
    named === 'Season' ? 'Season' : `Last ${spokenN} ${spokenN === 1 ? 'game' : 'games'}`;
  // The count stays in the spoken label. The visible cell does not print it.
  if (opts.games > 0 && opts.games < (named === 'Season' ? n : spokenN)) {
    head += `, only ${opts.games} played`;
  }
  if (named !== 'Season' && opts.seasonGames != null && opts.games > opts.seasonGames) {
    head += ', including earlier seasons';
  }
  const won =
    opts.winPct != null ? `won ${Math.round(opts.winPct * 100)} percent` : 'win rate not available';
  const avg =
    opts.avg == null
      ? 'average not available'
      : `${opts.avg.toFixed(1)}${opts.spokenUnit ? ` ${opts.spokenUnit}` : ''} a game`;
  return `${head}: ${won}, ${avg}`;
}
