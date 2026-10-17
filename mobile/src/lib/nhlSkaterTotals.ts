/**
 * Which NHL season label to ask `player_window_totals_nhl` for.
 *
 * nhl_skater_game_log.season is the year the season ENDS (CLAUDE.md §4).
 * Measured 2026-10-17: season 2027 holds the games from 2026-09-29 on.
 * The Stats screen passes the calendar year. In October that is 2026, so
 * the ending year is tried first and the calendar year is last season.
 * From January through June the ending year is the calendar year, and
 * next year's label has no games.
 */
export function nhlSeasonCandidates(calendarYear: number, month: number): number[] {
  if (month >= 1 && month <= 6) return [calendarYear];
  return [calendarYear + 1, calendarYear];
}
