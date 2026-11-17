/**
 * The actual stat or final score beside a Build Your Own Model bet's
 * Won or Lost. Its own file, with only a type import, so a test can run it.
 */
import type { ByomBet } from './byom';

export type ByomActualFields = Pick<ByomBet,
  'market' | 'player_name' | 'actual' | 'home_score' | 'away_score'
  | 'home_team' | 'away_team'>;

// The same keys as ANYTIME_TD_MARKET, DOUBLE_DOUBLE_MARKET and
// TRIPLE_DOUBLE_MARKET in byomRecord.ts (pinned by
// tests/test_byom_bet_actual.py). Repeated here so this file imports nothing.
const ANYTIME_TD = 'player_anytime_td';
const DOUBLE_DOUBLE = 'player_double_double';
const TRIPLE_DOUBLE = 'player_triple_double';

function scoreText(value: number): string {
  // Stats and scores are whole numbers; a stray fraction keeps one place.
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

/**
 * What happened, beside Won or Lost (Matt, 2026-11-17). A prop shows its
 * stat ("Actual: 7"); a game bet shows the final score, away first to
 * match the "away @ home" line. Null when the server sent neither.
 *
 * The server stores a double-double or triple-double as 1 or 0
 * (byom/prop_facts.py), so those read yes or no, never "Actual: 0".
 * Anytime TD is a count of rushing plus receiving touchdowns.
 */
export function byomActualText(bet: ByomActualFields): string | null {
  if (bet.player_name) {
    if (bet.actual == null) return null;
    if (bet.market === DOUBLE_DOUBLE) {
      return `Double-double: ${bet.actual > 0 ? 'yes' : 'no'}`;
    }
    if (bet.market === TRIPLE_DOUBLE) {
      return `Triple-double: ${bet.actual > 0 ? 'yes' : 'no'}`;
    }
    if (bet.market === ANYTIME_TD) {
      return bet.actual > 0 ? `TDs: ${scoreText(bet.actual)}` : 'No TD';
    }
    return `Actual: ${scoreText(bet.actual)}`;
  }
  if (bet.home_score == null || bet.away_score == null) return null;
  return `Final: ${bet.away_team} ${scoreText(bet.away_score)} @ `
    + `${bet.home_team} ${scoreText(bet.home_score)}`;
}
