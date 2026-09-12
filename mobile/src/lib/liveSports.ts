/**
 * WHICH SPORTS HAVE AN IN-PLAY MODEL AT ALL.
 *
 * Mirror of the live lanes in the Python registry: `config.LIVE_MODELS` (MLB +
 * NCAAF) and the separate NFL in-play worker (`nfl/live_model`, whose ids live
 * in `nfl/live_model/config.MODEL_IDS`). PINNED BY
 * tests/test_mobile_live_segment.py, which fails until this set equals those
 * two sources — the same mechanism lib/thresholds.ts uses, for the same reason:
 * a comment asking the next session to remember is not a guard.
 *
 * WHY THE APP NEEDS IT. The Live Signals board is always on screen for every
 * sport (matt, 2026-09-12), so an empty board has two completely different
 * meanings and the copy has to tell them apart: for MLB it means no in-play
 * edge right now, and for NBA it means we do not run an in-play model for that
 * sport at all. One empty state for both reads as a broken board on half the
 * sports in the app.
 *
 * ADD A SPORT HERE WHEN ITS LIVE LANE SHIPS — the test will tell you.
 */

/** Sports with at least one in-play model writing `is_live` picks. */
export const LIVE_MODEL_SPORTS: ReadonlySet<string> = new Set(['MLB', 'NCAAF', 'NFL']);

/** Does this sport have an in-play model at all? */
export function hasLiveModel(sport: string): boolean {
  return LIVE_MODEL_SPORTS.has(sport);
}

/** "MLB, NCAAF and NFL" — for copy that names the live lanes. */
export function liveModelSportsSentence(): string {
  const s = [...LIVE_MODEL_SPORTS];
  if (s.length <= 1) return s.join('');
  return `${s.slice(0, -1).join(', ')} and ${s[s.length - 1]}`;
}
