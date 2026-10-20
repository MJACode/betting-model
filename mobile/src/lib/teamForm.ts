/**
 * The unit of a team's scoring average on a form strip, by sport.
 *
 * The strip under a game pick shows each team's win rate and its average
 * score over its last games. That average is runs in baseball, goals in
 * hockey and points everywhere else; until 2026-10-17 it read "R" for every
 * sport, so an NBA total showed "112.4 R". Hockey says "GF" (goals for), not
 * "G": the same cell already counts games as "5 G".
 */
export function teamScoreUnit(sport: string | null | undefined): string {
  switch ((sport ?? '').toUpperCase()) {
    case 'MLB':
      return 'R';
    case 'NHL':
      return 'GF';
    case 'NBA':
    case 'WNBA':
    case 'NFL':
    case 'NCAAF':
      return 'PTS';
    default:
      // A sport with no team form strip today (UFC, golf): the old label.
      return 'R';
  }
}
