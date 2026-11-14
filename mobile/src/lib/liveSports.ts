/**
 * WHICH SPORTS HAVE AN IN-PLAY MODEL AT ALL.
 *
 * Mirror of the in-play models in the Python registry: `config.LIVE_MODELS`
 * (MLB, NBA, NCAAB, NCAABW, NCAAF and EUROLEAGUE) and the separate NFL in-play worker (`nfl/live_model`, whose ids live
 * in `nfl/live_model/config.MODEL_IDS`). PINNED BY
 * tests/test_mobile_live_segment.py, which fails until this set equals those
 * two sources — the same mechanism lib/thresholds.ts uses, for the same reason:
 * a comment asking the next session to remember is not a guard.
 *
 * WHY THE APP NEEDS IT. The Live Signals board is always on screen for every
 * sport (matt, 2026-09-12), so an empty board has two completely different
 * meanings and the copy has to tell them apart: for MLB it means no in-play
 * edge right now, and for NHL it means we do not run an in-play model for that
 * sport at all. One empty state for both reads as a broken board on half the
 * sports in the app.
 *
 * ADD A SPORT HERE WHEN ITS IN-PLAY MODEL SHIPS — the test will tell you.
 */

import { sportDisplayName } from './loadState';

/** Sports with at least one in-play model writing `is_live` picks. */
// Ordered so the two college basketball codes close the sentence ("... NCAAB
// and NCAABW"): side by side in the middle of a list they read as one word
// typed twice (UX review, 2026-11-11). EUROLEAGUE (2026-11-13) sits before them
// for the same reason.
export const LIVE_MODEL_SPORTS: ReadonlySet<string> = new Set(['MLB', 'NBA', 'NFL', 'NCAAF', 'EUROLEAGUE', 'NCAAB', 'NCAABW']);

/** Does this sport have an in-play model at all? */
export function hasLiveModel(sport: string): boolean {
  return LIVE_MODEL_SPORTS.has(sport);
}

/** "MLB, NBA, NFL, NCAAF, EuroLeague, NCAAB and NCAABW" — for copy that names
 *  the sports with an in-play model, each by its display name. Pass `name` to
 *  say each sport another way: VoiceOver reads them through sportSpokenName, so
 *  it never spells "NCAAB" then "NCAABW". */
export function liveModelSportsSentence(name: (sport: string) => string = sportDisplayName): string {
  const s = [...LIVE_MODEL_SPORTS].map(name);
  if (s.length <= 1) return s.join('');
  return `${s.slice(0, -1).join(', ')} and ${s[s.length - 1]}`;
}

const LIVE_EMPTY_VALID = 'No live signal is a valid answer, not a board that failed to load.';

/**
 * The Live board's empty subtitle for a sport that HAS an in-play model: when
 * the board can fill. NBA says when it checks, because its model does not
 * watch a game continuously: models/nba_live_loop.py reads the books once an
 * hour while a game is in progress (the backtest's own timing), and its one
 * live model, the early spread, decides a game once, in quarters 1-2. No
 * clock minute is named here, so the copy does not go stale if the loop's
 * minute moves.
 */
export function liveEmptySubtitle(sport: string): string {
  if (sport === 'NBA') {
    return (
      'The NBA in-play model checks games in progress once an hour, through the first and second quarters, and ' +
      'bets each game at most once. ' +
      LIVE_EMPTY_VALID
    );
  }
  if (sport === 'NCAAB') {
    // models/ncaab_live_loop.py: games in progress twice an hour, only the
    // biggest edges, and no more than five bets a night (mike, 2026-11-07).
    // tests/test_ncaab_live_config.py pins "twice an hour" and "five" to the
    // loop's cadence and cap.
    return (
      'The NCAAB in-play models check games in progress twice an hour, bet only their biggest edges, ' +
      'and stop after five bets a night. ' +
      LIVE_EMPTY_VALID
    );
  }
  if (sport === 'NCAABW') {
    // models/ncaabw_live_loop.py: one decision a game, during the halftime
    // break, on the full-game total.
    return (
      'The NCAABW in-play model checks each game during its halftime break and bets it at most once, ' +
      'on the full-game total. ' +
      LIVE_EMPTY_VALID
    );
  }
  if (sport === 'EUROLEAGUE') {
    // models/euroleague_live_loop.py: one decision a game, during the halftime
    // break, on the full-game spread.
    return (
      'The EuroLeague in-play model checks each game during its halftime break and bets it at most once, ' +
      'on the full-game spread. ' +
      LIVE_EMPTY_VALID
    );
  }
  return `Live signals appear while a game is in play and the in-play model finds an edge. ${LIVE_EMPTY_VALID}`;
}
