/**
 * Stats > NFL > Anytime TD matchup column (Designer Option A).
 *
 * The A–F grade stays on every other board. This one answers "how easy is
 * the defense for this position?" with five bars, a tier word, and a rank
 * line ("3rd easiest"). Rank 1 allows the most touchdowns to the position.
 *
 * Tiers, over 32 teams: 1–6, 7–13, 14–19, 20–26, 27–32.
 * The server blends last season until a defense has played
 * BLEND_UNTIL_TEAM_GAMES this season (the same 8 the SQL comments name).
 *
 * Visible strings live in ATD_COPY so the screen and the verifier share one
 * list. Matt signs that list off; do not paraphrase it in the component.
 */
import { nflPositionGroup, type NflPositionGroup } from './positionVsOpponent';

/** Must match the `< 8` / `>= 8` cuts in position_defense_ranks_nfl. */
export const BLEND_UNTIL_TEAM_GAMES = 8;

/** Metrics move under the name at this Dynamic Type scale, before a fixed
 *  column clips the price (the board's own note: about 1.3). */
export const ATD_STACK_FONT_SCALE = 1.3;

/** And on a phone narrower than this: Hit 56 + Matchup 96 + Best 72 leave
 *  the name about 67pt on a 375pt screen, which clips the opponent. */
export const ATD_STACK_BELOW_WIDTH = 430;

export const ATD_HIT_W = 56;
export const ATD_MATCHUP_W = 96;
export const ATD_ODDS_W = 72;

export const ATD_POS_GROUPS: readonly NflPositionGroup[] = [
  'QB', 'RB', 'WR', 'TE', 'DL', 'LB', 'DB',
];

export type MatchupTier = 'Easiest' | 'Easy' | 'Average' | 'Tough' | 'Toughest';

/** Best (easiest) first. The index is the order a floor compares. */
export const TIER_ORDER: readonly MatchupTier[] = [
  'Easiest', 'Easy', 'Average', 'Tough', 'Toughest',
];

/** Floors a person can set. Toughest includes everyone, so it is not a chip. */
export const TIER_FLOORS: readonly MatchupTier[] = ['Easiest', 'Easy', 'Average', 'Tough'];

export type GapReason = 'no_game' | 'bye' | 'not_playing' | 'too_early' | 'no_position';

export type MatchupSort = 'easiest' | 'toughest';

/** One defense from position_defense_ranks_nfl, keyed by group and team. */
export interface DefenseRank {
  defense: string;
  avgAllowed: number | null;
  playerGames: number;
  seasonTeamGames: number;
  windowTeamGames: number;
  blended: boolean;
  /** 1 = most allowed = easiest. Null when the server could not rank. */
  rank: number | null;
  teamsRanked: number;
}

export const ATD_COPY = {
  header: 'MATCHUP',
  hitHeader: 'HIT %',
  priceHeader: 'BEST',
  earlySeason:
    'Some defenses still include last season, until they have played 8 games.',
  totalHeader: 'TD',
  loadingLabel: 'Loading',
  unavailableLabel: 'Unavailable',
  infoTitle: 'Matchup',
  infoBody:
    'How easy this week’s defense is for the player’s position.\n\n'
    + 'Five bars. Easiest is five filled, Toughest is one. The line under the word is the rank: 1st easiest allows the most touchdowns to that position, 32nd the fewest.\n\n'
    + 'Tiers: 1st–6th Easiest, 7th–13th Easy, 14th–19th Average, 20th–26th Tough, 27th–32nd Toughest.\n\n'
    + 'This season’s games, once a defense has played 8. Before that, this season and last are combined. One note on the board says when that blend is on.\n\n'
    + 'A dash is not an average. The reason sits under it: No game, Bye, Not playing, No rank, or No position.\n\n'
    + 'Tap Matchup to sort. Ties go to the higher hit rate, then the better price.',
  filterTitle: 'Matchup',
  filterSubtitle:
    'How easy the defense is for this position. A tier includes every easier tier.',
  filterAny: 'Any',
  includeUnranked: 'Include matchups we can’t rank',
  unavailableNote: 'Defense ranks didn’t load, so matchups are blank.',
  gaps: {
    no_game: 'No game',
    bye: 'Bye',
    not_playing: 'Not playing',
    too_early: 'No rank',
    no_position: 'No position',
  } as Record<GapReason, string>,
  gapSpoken: {
    no_game: 'Matchup, no opponent.',
    bye: 'Matchup, bye week.',
    not_playing: 'Matchup, not playing.',
    too_early: 'Matchup, no rank.',
    no_position: 'Matchup, no position.',
  } as Record<GapReason, string>,
  loadingSpoken: 'Matchup, loading.',
  unavailableSpoken: 'Matchup unavailable.',
  sortEasiest: 'Matchup, sorted easiest first.',
  sortToughest: 'Matchup, sorted toughest first.',
  sortOff: 'Matchup, not sorted. Sorts easiest first.',
  sortHint: 'Changes the matchup sort.',
} as const;

const TIER_BANDS: readonly { max: number; tier: MatchupTier; bars: number }[] = [
  { max: 6, tier: 'Easiest', bars: 5 },
  { max: 13, tier: 'Easy', bars: 4 },
  { max: 19, tier: 'Average', bars: 3 },
  { max: 26, tier: 'Tough', bars: 2 },
  { max: 32, tier: 'Toughest', bars: 1 },
];

export function ordinal(n: number): string {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return `${n}th`;
  switch (n % 10) {
    case 1: return `${n}st`;
    case 2: return `${n}nd`;
    case 3: return `${n}rd`;
    default: return `${n}th`;
  }
}

export function tierForRank(rank: number | null | undefined): { tier: MatchupTier; bars: number } | null {
  if (rank == null || !Number.isFinite(rank) || rank < 1) return null;
  const band = TIER_BANDS.find((b) => rank <= b.max) ?? TIER_BANDS[TIER_BANDS.length - 1];
  return { tier: band.tier, bars: band.bars };
}

export function rankLine(rank: number): string {
  return `${ordinal(rank)} easiest`;
}

/** Spoken group, full words. Abbreviations in the cell would be spelled out. */
const GROUP_SPOKEN: Record<NflPositionGroup, string> = {
  QB: 'quarterbacks',
  RB: 'running backs',
  WR: 'wide receivers',
  TE: 'tight ends',
  DL: 'defensive linemen',
  LB: 'linebackers',
  DB: 'defensive backs',
};

export function matchupSpoken(tier: MatchupTier, rank: number, bars: number, group: NflPositionGroup | null): string {
  const who = group ? `, ${GROUP_SPOKEN[group]}` : '';
  return `Matchup, ${tier}, ${rankLine(rank)}, ${bars} of 5 bars${who}.`;
}

export function meetsTierFloor(
  tier: MatchupTier | null | undefined,
  floor: MatchupTier | null,
  includeUnranked = true,
): boolean {
  if (!floor) return true;
  if (!tier) return includeUnranked;
  return TIER_ORDER.indexOf(tier) <= TIER_ORDER.indexOf(floor);
}

export interface AnytimeSortRow {
  rank: number | null;
  /** Higher is better. Hit rate on that board; the average in Averages mode. */
  primary: number;
  /** American odds. Higher is a better price. Null sorts last. */
  price: number | null;
}

/**
 * Easiest-first puts rank 1 at the top. Unranked rows stay last either way.
 * A shared rank falls through to the higher primary, then the better price.
 */
export function compareAnytimeRows(a: AnytimeSortRow, b: AnytimeSortRow, order: MatchupSort): number {
  const aU = a.rank == null;
  const bU = b.rank == null;
  if (aU !== bU) return aU ? 1 : -1;
  if (a.rank != null && b.rank != null && a.rank !== b.rank) {
    return order === 'easiest' ? a.rank - b.rank : b.rank - a.rank;
  }
  if (a.primary !== b.primary) return b.primary - a.primary;
  const aP = a.price == null;
  const bP = b.price == null;
  if (aP !== bP) return aP ? 1 : -1;
  if (a.price != null && b.price != null && a.price !== b.price) return b.price - a.price;
  return 0;
}

export function nextMatchupSort(current: MatchupSort | null): MatchupSort | null {
  if (current == null) return 'easiest';
  if (current === 'easiest') return 'toughest';
  return null;
}

export interface MatchupPlacement {
  pos?: string | null;
  team?: string | null;
  opponent?: string | null;
  /** The league has at least one game in the loaded window. */
  leagueHasGames: boolean;
  /** This player's team has a game in that window. */
  teamHasGame: boolean;
  /** Set only when a feed says he is out. Absent is not a guess. */
  inactive?: boolean | null;
}

/**
 * Why the cell is a dash, or null when a rank can be drawn.
 * Bye and a missing game win over "no position": the week is the reason
 * there is nothing to rank. Not playing wins when we actually know it.
 */
export function gapReason(p: MatchupPlacement, ranked: boolean): GapReason | null {
  if (p.inactive) return 'not_playing';
  const hasOpponent = !!p.opponent && p.teamHasGame;
  if (!hasOpponent) {
    if (p.team && p.leagueHasGames && !p.teamHasGame) return 'bye';
    return 'no_game';
  }
  if (!nflPositionGroup(p.pos)) return 'no_position';
  if (!ranked) return 'too_early';
  return null;
}

export type AnytimeMatchupView =
  | { kind: 'loading' }
  | { kind: 'unavailable' }
  | { kind: 'gap'; reason: GapReason; label: string; spoken: string }
  | {
      kind: 'rank';
      tier: MatchupTier;
      bars: number;
      rank: number;
      line: string;
      spoken: string;
      group: NflPositionGroup;
    };

export function buildAnytimeMatchup(args: {
  status: 'loading' | 'error' | 'ok';
  placement: MatchupPlacement;
  rank: DefenseRank | null;
}): AnytimeMatchupView {
  if (args.status === 'loading') return { kind: 'loading' };
  if (args.status === 'error') return { kind: 'unavailable' };
  const group = nflPositionGroup(args.placement.pos);
  const ranked = args.rank?.rank != null && group != null;
  const gap = gapReason(args.placement, ranked);
  if (gap) {
    return {
      kind: 'gap',
      reason: gap,
      label: ATD_COPY.gaps[gap],
      spoken: ATD_COPY.gapSpoken[gap],
    };
  }
  const hit = tierForRank(args.rank!.rank);
  if (!hit || !group || args.rank!.rank == null) {
    return {
      kind: 'gap',
      reason: 'too_early',
      label: ATD_COPY.gaps.too_early,
      spoken: ATD_COPY.gapSpoken.too_early,
    };
  }
  return {
    kind: 'rank',
    tier: hit.tier,
    bars: hit.bars,
    rank: args.rank!.rank,
    line: rankLine(args.rank!.rank),
    spoken: matchupSpoken(hit.tier, args.rank!.rank, hit.bars, group),
    group,
  };
}

/** A dash whose reason we already know, without pretending a defense was ranked. */
export function namedGap(reason: GapReason): AnytimeMatchupView {
  return {
    kind: 'gap',
    reason,
    label: ATD_COPY.gaps[reason],
    spoken: ATD_COPY.gapSpoken[reason],
  };
}

export function defenseKey(group: string, defense: string): string {
  return `${group.toUpperCase()}|${defense.toUpperCase()}`;
}

/** True when any defense in the index is still on the blended window. */
export function anyBlended(ranks: Iterable<DefenseRank>): boolean {
  for (const r of ranks) if (r.blended) return true;
  return false;
}

export function isAnytimeTdBoard(sport: string, statKey: string | null | undefined): boolean {
  return sport === 'NFL' && statKey === 'rush_rec_tds';
}
