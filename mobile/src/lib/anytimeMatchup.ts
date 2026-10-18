/**
 * Stats > NFL > Anytime TD matchup column (Designer Option A).
 *
 * The A–F grade stays on every other board. This one answers "how easy is
 * the defense for this position?" with five bars, a tier word, and a rank
 * line ("3rd easiest", or "3rd toughest" when that end is nearer). Rank 1
 * allows the most touchdowns to the position.
 *
 * Tiers, over 32 teams: 1–6 Great, 7–13 Good, 14–19 Average, 20–26 Tough,
 * 27–32 Very tough.
 * The server blends last season until a defense has played
 * BLEND_UNTIL_TEAM_GAMES this season (the same 8 the SQL comments name).
 *
 * Visible strings live in ATD_COPY so the screen and the verifier share one
 * list. Matt signs that list off; do not paraphrase it in the component.
 */
import { nflPositionGroup, type NflPositionGroup } from './positionVsOpponent';

/** Must match the `< 8` / `>= 8` cuts in position_defense_ranks_nfl. */
export const BLEND_UNTIL_TEAM_GAMES = 8;

/** Metrics move under the name once Dynamic Type is above the default.
 *  MATCHUP plus its arrow fills the 66pt column at scale 1 and clips as
 *  soon as the type grows, so the stack starts at the first step above 1.
 *  A phone-width cutoff stacked every phone at the default size. */
export const ATD_STACK_FONT_SCALE = 1;

/** The board's column widths. Hit % 40, Matchup 66, Best price 62. */
export const ATD_HIT_W = 40;
export const ATD_MATCHUP_W = 66;
export const ATD_ODDS_W = 62;

/** Stable order for the groups a board actually has rows for. */
const GROUP_ORDER: readonly NflPositionGroup[] = ['QB', 'RB', 'WR', 'TE', 'DL', 'LB', 'DB'];

export type MatchupTier = 'Great' | 'Good' | 'Average' | 'Tough' | 'Very tough';

/** Best (easiest) first. The index is the order a floor compares. */
export const TIER_ORDER: readonly MatchupTier[] = [
  'Great', 'Good', 'Average', 'Tough', 'Very tough',
];

/** Floors a person can set. Very tough includes everyone, so it is not a chip. */
export const TIER_FLOORS: readonly MatchupTier[] = ['Great', 'Good', 'Average', 'Tough'];

/** The chip and the pill. "Tough" alone hides that the floor includes Great. */
export function tierFloorLabel(tier: MatchupTier): string {
  return `${tier} or easier`;
}

/** Large text: one left-aligned line. "Great · 5th easiest". */
export function stackedMatchupLine(tier: MatchupTier, line: string): string {
  return `${tier} · ${line}`;
}

/** Position groups present on the rows, in GROUP_ORDER. An unmapped pos adds nothing. */
export function groupsUsedByBoard(positions: Iterable<string | null | undefined>): NflPositionGroup[] {
  const found = new Set<NflPositionGroup>();
  for (const pos of positions) {
    const group = nflPositionGroup(pos);
    if (group) found.add(group);
  }
  return GROUP_ORDER.filter((g) => found.has(g));
}

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
    + 'Counted: touchdowns that defense has allowed to this position, per player-game. Rank 1 allows the most. Ties share a rank, and the next rank skips.\n\n'
    + 'The line counts from the nearer end. 1st easiest allows the most. 1st toughest allows the fewest.\n\n'
    + 'Five bars in the compact column. Great is five filled, Very tough is one. At larger text the tier and the rank are one line.\n\n'
    + 'Tiers: 1st–6th Great, 7th–13th Good, 14th–19th Average, 20th–26th Tough, 27th–32nd Very tough.\n\n'
    + 'This season’s games, once a defense has played 8. Before that, this season and last are combined. A short sample can move the rank. One note on the board says when that blend is on.\n\n'
    + 'A dash is not an average. The reason sits under it in the compact column, and beside it at larger text: No game, Bye, Not playing, No rank, or No position.\n\n'
    + 'Tap the Matchup header to sort. Ties go to the higher hit rate, then the better price.',
  explainHint: 'Opens what this matchup means.',
  partialNote: 'Some defense ranks didn’t load. Those matchups say Unavailable.',
  filterTitle: 'Matchup',
  filterSubtitle:
    'How easy the defense is for this position. A tier includes every easier tier.',
  filterAny: 'Any',
  includeUnranked: 'Include matchups we can’t rank',
  unavailableNote: 'Defense ranks didn’t load. Ranked matchups say Unavailable.',
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
  { max: 6, tier: 'Great', bars: 5 },
  { max: 13, tier: 'Good', bars: 4 },
  { max: 19, tier: 'Average', bars: 3 },
  { max: 26, tier: 'Tough', bars: 2 },
  { max: 32, tier: 'Very tough', bars: 1 },
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

/**
 * Count from the nearer end of the ranked defenses. Rank 3 of 32 is
 * "3rd easiest". Rank 30 of 32 is "3rd toughest". A tie (equal distance)
 * stays on the easy end. Missing team count uses 32.
 */
export function rankLine(rank: number, teamsRanked?: number | null): string {
  const listed = teamsRanked != null && teamsRanked >= rank ? teamsRanked : Math.max(rank, 32);
  const fromTough = listed - rank + 1;
  if (rank <= fromTough) return `${ordinal(rank)} easiest`;
  return `${ordinal(fromTough)} toughest`;
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

export function matchupSpoken(tier: MatchupTier, line: string, group: NflPositionGroup | null): string {
  const who = group ? `, ${GROUP_SPOKEN[group]}` : '';
  return `Matchup, ${tier}, ${line}${who}.`;
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

function gapView(reason: GapReason): AnytimeMatchupView {
  return {
    kind: 'gap',
    reason,
    label: ATD_COPY.gaps[reason],
    spoken: ATD_COPY.gapSpoken[reason],
  };
}

export function buildAnytimeMatchup(args: {
  status: 'loading' | 'error' | 'ok';
  placement: MatchupPlacement;
  rank: DefenseRank | null;
}): AnytimeMatchupView {
  // A bye, a missing game, a known absence, or no position does not need a
  // rank. Those stay labeled when the fetch is still running or has failed.
  const structural = gapReason(args.placement, false);
  if (structural && structural !== 'too_early') return gapView(structural);
  if (args.status === 'loading') return { kind: 'loading' };
  if (args.status === 'error') return { kind: 'unavailable' };
  const group = nflPositionGroup(args.placement.pos);
  const ranked = args.rank?.rank != null && group != null;
  const gap = gapReason(args.placement, ranked);
  if (gap) return gapView(gap);
  const hit = tierForRank(args.rank!.rank);
  if (!hit || !group || args.rank!.rank == null) return gapView('too_early');
  const line = rankLine(args.rank!.rank, args.rank!.teamsRanked);
  return {
    kind: 'rank',
    tier: hit.tier,
    bars: hit.bars,
    rank: args.rank!.rank,
    line,
    spoken: matchupSpoken(hit.tier, line, group),
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
