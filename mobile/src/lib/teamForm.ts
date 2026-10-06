/**
 * Scoring unit on the pick-detail form strip.
 *
 * The strip used to print "R" for every sport. That is runs, and it is right
 * for baseball only. NFL and NCAAF averages are points (a college total near
 * 48 was showing as "48.0 R"); hockey is goals. The games row under the
 * average already says "G", so goals are not abbreviated the same way.
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
