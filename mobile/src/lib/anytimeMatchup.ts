/**
 * Stats > NFL > Anytime TD matchup column.
 *
 * Five bars, filled from the left. Rank 1 allows the most touchdowns to the
 * position. Over 32 teams: 1–6 fills 5, 7–13 fills 4, 14–19 fills 3,
 * 20–26 fills 2, 27–32 fills 1. The count is the strength. No tier word and
 * no "Nth easiest" on the row (Matt, 2026-10-28, Option A).
 *
 * The server blends last season until a defense has played
 * BLEND_UNTIL_TEAM_GAMES this season (the same 8 the SQL comments name).
 *
 * Visible strings live in ATD_COPY so the screen and the verifier share one
 * list. Matt signs that list off; do not paraphrase it in the component.
 */
import {
  matchupStrengthFloorSpoken,
  matchupStrengthSpoken,
  type MatchupStrength,
} from './matchup';
import { nflPositionGroup, type NflPositionGroup } from './positionVsOpponent';
import { FONT_SIZE_MICRO } from './typeScale';

/** Must match the `< 8` / `>= 8` cuts in position_defense_ranks_nfl. */
export const BLEND_UNTIL_TEAM_GAMES = 8;

/** The row stacks at this Dynamic Type scale and above. Below it, MATCHUP
 *  shrinks to the 66pt column instead of stacking the row. A phone-width
 *  cutoff stacked every phone at the default size. */
export const ATD_STACK_FONT_SCALE = 1.3;

/** "MATCHUP" at FONT_SIZE_MICRO semibold, letterSpacing 0. Measured in Inter. */
export const ATD_MATCHUP_WORD_W = 57;
/** The sort arrow beside the header word. */
export const ATD_HEADER_ARROW_W = 9;

/**
 * Font size for the MATCHUP header. Dynamic Type multiplies the result, so
 * this cancels the part of the scale that would push the word and the arrow
 * out of `columnPt`. At scale 1.3 the row stacks and the column stops being
 * the limit.
 */
export function matchupHeaderFontSize(
  fontScale: number,
  columnPt = ATD_MATCHUP_W,
  base = FONT_SIZE_MICRO,
): number {
  const scale = Number.isFinite(fontScale) && fontScale > 0 ? fontScale : 1;
  const room = columnPt - ATD_HEADER_ARROW_W;
  const natural = ATD_MATCHUP_WORD_W * scale;
  const size = Number.isFinite(base) && base > 0 ? base : FONT_SIZE_MICRO;
  if (room <= 0 || natural <= room) return size;
  return size * (room / natural);
}

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

/** Floors a person can set. One bar includes everyone, so it is not a chip. */
export const TIER_FLOORS: readonly MatchupTier[] = ['Great', 'Good', 'Average', 'Tough'];

/** Bars that tier fills. The name is the stored floor; the chip draws this count. */
export function tierBars(tier: MatchupTier): MatchupStrength {
  return (5 - TIER_ORDER.indexOf(tier)) as MatchupStrength;
}

/** The chip and the pill. "strength 4 or more" — the floor includes every stronger bar. */
export function tierFloorSpoken(tier: MatchupTier): string {
  return matchupStrengthFloorSpoken(tierBars(tier));
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
    + 'Five bars, filled from the left. The count is the strength. Five filled is ranks 1–6. Four is 7–13. Three is 14–19. Two is 20–26. One is 27–32.\n\n'
    + 'This season’s games, once a defense has played 8. Before that, this season and last are combined. A short sample can move the rank. One note on the board says when that blend is on.\n\n'
    + 'There is no bar when the defense cannot be ranked. Bye, No game, Not playing, and No position name the reason. A dash means no rank.\n\n'
    + 'Tap the Matchup header to sort. Ties go to the higher hit rate, then the better price.',
  explainHint: 'Opens what this matchup means.',
  partialNote: 'Some defense ranks didn’t load. Those matchups say Unavailable.',
  filterTitle: 'Matchup',
  filterSubtitle:
    'Five bars for this position. The floor keeps that strength and every stronger spot.',
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
  sortEasiest: 'Matchup, sorted strongest first.',
  sortToughest: 'Matchup, sorted weakest first.',
  sortOff: 'Matchup, not sorted. Sorts strongest first.',
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
 * 1 plus how many peers allow strictly fewer. SQL `rank()` gives every member
 * of a tie the easiest number, so `teamsRanked - rank + 1` counts those peers
 * as if they were tougher. Six defenses at zero, all rank 27 of 32, have
 * nobody strictly below them: this returns 1.
 */
export function toughEndRank(rank: number, peers: Iterable<{ rank: number | null }>): number {
  let fewer = 0;
  for (const peer of peers) {
    if (peer.rank != null && peer.rank > rank) fewer += 1;
  }
  return fewer + 1;
}

/** Defenses in one position group. Keys are `defenseKey(group, team)`. */
export function ranksInGroup(ranks: Iterable<[string, DefenseRank]>, group: string): DefenseRank[] {
  const prefix = `${group.toUpperCase()}|`;
  const out: DefenseRank[] = [];
  for (const [key, row] of ranks) {
    if (key.startsWith(prefix)) out.push(row);
  }
  return out;
}

/**
 * Count from the nearer end of the ranked defenses. Not rendered: the row is
 * bars, and VoiceOver says the filled count. Kept so the nearer-end count
 * still has one definition.
 *
 * Rank 3 of 32 is "3rd easiest". Rank 30 of 32 is "3rd toughest". A tie at
 * equal distance stays on the easy end. Missing team count uses 32.
 *
 * `fromToughEnd` is `toughEndRank` for the position group. Omit it and a
 * unique rank keeps `teamsRanked - rank + 1`. A tie at rank 1 stays
 * "1st easiest" either way.
 */
export function rankLine(
  rank: number,
  teamsRanked?: number | null,
  fromToughEnd?: number | null,
): string {
  const listed = teamsRanked != null && teamsRanked >= rank ? teamsRanked : Math.max(rank, 32);
  const fromFormula = listed - rank + 1;
  const fromTough =
    fromToughEnd != null && Number.isFinite(fromToughEnd) && fromToughEnd >= 1
      ? fromToughEnd
      : fromFormula;
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

export function matchupSpoken(bars: number, group: NflPositionGroup | null): string {
  const who = group ? `, ${GROUP_SPOKEN[group]}` : '';
  const n = Math.min(5, Math.max(1, Math.round(bars))) as MatchupStrength;
  return `${matchupStrengthSpoken(n)}${who}.`;
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
  return {
    kind: 'rank',
    tier: hit.tier,
    bars: hit.bars,
    rank: args.rank!.rank,
    spoken: matchupSpoken(hit.bars, group),
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
