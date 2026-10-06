/**
 * Pick Detail card order, after the reasoning card.
 *
 * `timing` is master's context that used to sit above the bet: PickTiming,
 * SharpScore, the "why no edge" note, then LineMovement.
 * `bet` is where to bet, the started line, every book, the betslip, then Track.
 * `after` is the rest: public splits, CLV, the injury flag, weather, the
 * football matchup, prop context, the UFC tape, and the trend strips.
 *
 * NFL and NCAAF put the bet and Track first. Every other sport keeps master's
 * order: timing, then the bet, then the rest.
 */
export const MASTER_DETAIL_BLOCKS = ['timing', 'bet', 'after'] as const;
export const FOOTBALL_DETAIL_BLOCKS = ['bet', 'timing', 'after'] as const;

export type DetailBlock = (typeof MASTER_DETAIL_BLOCKS)[number];

export function pickDetailBlockOrder(sport: string | null | undefined): readonly DetailBlock[] {
  if (sport === 'NFL' || sport === 'NCAAF') return FOOTBALL_DETAIL_BLOCKS;
  return MASTER_DETAIL_BLOCKS;
}
