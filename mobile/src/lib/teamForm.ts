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

/**
 * Visible names of the five team columns.
 *
 * The fifth column's own name (`teamFifthColumnLabel`) can repeat column 4:
 * 20 cross-season games are L20 and L20, and 12 are L20 beside L12. When that
 * name is already on an earlier column, the fifth column says All. Column 4
 * takes the real count when it has 1–19 games and that count is not already
 * L3, L5 or L10. A season column stays L20: those games are this season, and
 * the note says Season uses them.
 */
export function teamStripLabels(
  counts: { l3: number; l5: number; l10: number; l20: number; l25: number },
  seasonGames?: number | null,
): { l3: string; l5: string; l10: string; l20: string; fifth: string } {
  const fifthRaw = teamFifthColumnLabel(counts.l25, seasonGames);
  const seasonCol = fifthRaw === 'Season';
  let l20 = 'L20';
  if (!seasonCol && counts.l20 > 0 && counts.l20 < TEAM_WINDOW_SIZE.l20) {
    const candidate = `L${counts.l20}`;
    if (candidate !== 'L3' && candidate !== 'L5' && candidate !== 'L10') l20 = candidate;
  }
  const used = new Set(['L3', 'L5', 'L10', l20]);
  const fifth = used.has(fifthRaw) ? 'All' : fifthRaw;
  return { l3: 'L3', l5: 'L5', l10: 'L10', l20, fifth };
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
 * already names every column. The names are the ones on the strip. When the
 * window also reaches an earlier season, "so far" would sit next to "This
 * season: N games" and contradict it, so that case says "available". An
 * unknown season says neither: "so far" would claim a season we don't have.
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
  const labels = teamStripLabels(counts, seasonGames);
  const columns = [
    { label: labels.l3, games: counts.l3, size: TEAM_WINDOW_SIZE.l3 },
    { label: labels.l5, games: counts.l5, size: TEAM_WINDOW_SIZE.l5 },
    { label: labels.l10, games: counts.l10, size: TEAM_WINDOW_SIZE.l10 },
    { label: labels.l20, games: counts.l20, size: TEAM_WINDOW_SIZE.l20 },
    { label: labels.fifth, games: counts.l25, size: TEAM_WINDOW_SIZE.season },
  ];
  const gamesWord = n === 1 ? 'game' : 'games';
  const those = n === 1 ? 'that 1' : `those ${n}`;
  const knownSeason = seasonGames != null;
  const crossSeason = knownSeason && counts.l25 > seasonGames;
  const how = !knownSeason ? '' : crossSeason ? ' available' : ' so far';
  if (labels.fifth === 'All') {
    const sharing = columns.filter((c) => c.games === n);
    const other = sharing.find((c) => c.label !== 'All');
    if (sharing.length === 2 && other != null) {
      return `Only ${n} ${gamesWord}${how}. ${other.label} and All use ${those}.`;
    }
    const earlier = columns.filter((c) => c.games < n);
    if (earlier.length === 0) {
      return `Only ${n} ${gamesWord}${how}. Every column uses ${those}.`;
    }
    const lastFull = earlier[earlier.length - 1];
    return `Only ${n} ${gamesWord}${how}. Every column after ${lastFull.label} uses ${those}.`;
  }
  const short = columns.filter((c) => n < c.size);
  if (short.length === 0) return null;
  const span = columnSpan(short.map((c) => c.label));
  const use = short.length === 1 ? 'uses' : 'all use';
  return `Only ${n} ${gamesWord}${how}. ${span} ${use} ${those}.`;
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
  const labels = teamStripLabels(counts, seasonGames);
  const fifth = labels.fifth;
  const windows = [
    { label: labels.l3, games: counts.l3 },
    { label: labels.l5, games: counts.l5 },
    { label: labels.l10, games: counts.l10 },
    { label: labels.l20, games: counts.l20 },
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
    named === 'All'
      ? 'All games'
      : named === 'Season'
        ? 'Season'
        : `Last ${spokenN} ${spokenN === 1 ? 'game' : 'games'}`;
  // The count stays in the spoken label. The visible cell does not print it.
  // All already means every game in hand, so it does not add "only N played".
  if (named !== 'All' && opts.games > 0 && opts.games < (named === 'Season' ? n : spokenN)) {
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
