/**
 * The Stats tab's position row (Matt-approved Designer handoff, 2026-09-25,
 * Option A).
 *
 * Getting from Passing to Receiving used to take three taps (open the group
 * dropdown, pick a group, pick a chip), and the dropdown sat at the head of
 * the chips as if it were one of them. Now one always-visible segmented row
 * replaces Players | Teams: the football boards read QB / RB / WR/TE / DEF /
 * Teams, MLB reads Hitters / Pitchers / Teams, and every other sport keeps
 * what it had.
 *
 * A segment ONLY decides which chips are visible. Every chip is an existing
 * STAT_CATALOG entry, addressed by its `group:key` (chipKey), so the stat a
 * chip reads and the market it is priced in do not move. A spec'd chip the
 * catalog does not carry for a sport (NCAAF has no Targets: CFBD's box score
 * does not report them) is left out, never invented.
 *
 * Pure on purpose — `scripts/verify_stat_segments.ts` pins it without React.
 */
import type { Sport } from '@/hooks/useSportFilter';
import type { SeasonTotalsRow } from '@/types';
import { STAT_CATALOG, type StatDef, type StatGroup } from './statCatalog';
import { supportsTeamBoard } from './teamStatCatalog';
import { NFL_DEFENSIVE_POSITIONS } from './playerLog';

export type StatSegment =
  | 'players'
  | 'qb' | 'rb' | 'wrte' | 'def'
  | 'hitters' | 'pitchers'
  | 'teams';

/** One chip in a segment: a catalog entry, by its group and column key. */
interface ChipRef {
  group: StatGroup;
  key: keyof SeasonTotalsRow;
}

/** Every catalog chip in one group, in catalog order. */
const WHOLE_GROUP = (group: StatGroup) => ({ wholeGroup: group }) as const;
type ChipSpec = ChipRef | ReturnType<typeof WHOLE_GROUP>;

/**
 * The football segments, in the order the chips are shown. The RB and WR/TE
 * Anytime TD chips are the SAME column under two groups (the catalog lists it
 * in Rushing and in Receiving), so each segment points at the group its
 * other chips come from.
 */
const FOOTBALL_CHIPS: Record<'qb' | 'rb' | 'wrte' | 'def', ChipSpec[]> = {
  qb: [WHOLE_GROUP('Passing'), { group: 'Rushing', key: 'rushing_yards' }],
  rb: [
    { group: 'Rushing', key: 'rushing_yards' },
    { group: 'Rushing', key: 'carries' },
    { group: 'Rushing', key: 'rush_rec_tds' },
    { group: 'Receiving', key: 'receptions' },
    { group: 'Receiving', key: 'receiving_yards' },
  ],
  wrte: [
    { group: 'Receiving', key: 'receptions' },
    { group: 'Receiving', key: 'receiving_yards' },
    { group: 'Receiving', key: 'targets' },
    { group: 'Receiving', key: 'rush_rec_tds' },
  ],
  def: [WHOLE_GROUP('Defense')],
};

const FOOTBALL_SEGMENTS: StatSegment[] = ['qb', 'rb', 'wrte', 'def'];
const MLB_SEGMENTS: StatSegment[] = ['hitters', 'pitchers'];

/**
 * The row for a sport, left to right. Teams rides at the end wherever the
 * sport has a team board, exactly as the old Players | Teams toggle did —
 * so UFC and golf get no row at all (SegmentTabs renders nothing under two
 * items) and the NHL keeps Players | Teams.
 */
export function segmentsForSport(sport: Sport): StatSegment[] {
  const players: StatSegment[] =
    sport === 'NFL' || sport === 'NCAAF' ? FOOTBALL_SEGMENTS
    : sport === 'MLB' ? MLB_SEGMENTS
    : ['players'];
  return supportsTeamBoard(sport) ? [...players, 'teams'] : players;
}

/** The segment a sport opens on — the one its default stat lives in. */
export function defaultSegmentFor(sport: Sport): StatSegment {
  return segmentsForSport(sport).find((s) => s !== 'teams') ?? 'players';
}

/**
 * Compact labels. The NFL row is five tabs — QB / RB / WR/TE / DEF / Teams,
 * WR/TE being one — and at 393pt each gets 78.6pt; the widest label is about
 * 45pt at font.size.body semibold (verify_stat_segments.ts does the sum).
 */
export function segmentLabel(seg: StatSegment): string {
  switch (seg) {
    case 'players': return 'Players';
    case 'qb': return 'QB';
    case 'rb': return 'RB';
    case 'wrte': return 'WR/TE';
    case 'def': return 'DEF';
    case 'hitters': return 'Hitters';
    case 'pitchers': return 'Pitchers';
    case 'teams': return 'Teams';
  }
}

/** What VoiceOver says — "W R slash T E" is not a word anyone uses. */
export function segmentAccessibilityLabel(seg: StatSegment): string {
  switch (seg) {
    case 'qb': return 'Quarterbacks';
    case 'rb': return 'Running backs';
    case 'wrte': return 'Receivers and tight ends';
    case 'def': return 'Defense';
    default: return segmentLabel(seg);
  }
}

function specFor(sport: Sport, seg: StatSegment): ChipSpec[] {
  if (sport === 'NFL' || sport === 'NCAAF') {
    return seg === 'qb' || seg === 'rb' || seg === 'wrte' || seg === 'def' ? FOOTBALL_CHIPS[seg] : [];
  }
  if (sport === 'MLB') {
    return seg === 'hitters' ? [WHOLE_GROUP('Batting')]
      : seg === 'pitchers' ? [WHOLE_GROUP('Pitching')]
      : [];
  }
  return seg === 'players'
    ? [...new Set(STAT_CATALOG.filter((d) => d.sport === sport).map((d) => d.group))].map(WHOLE_GROUP)
    : [];
}

function resolve(sport: Sport, seg: StatSegment): { chips: StatDef[]; missing: ChipRef[] } {
  const chips: StatDef[] = [];
  const missing: ChipRef[] = [];
  for (const spec of specFor(sport, seg)) {
    if ('wholeGroup' in spec) {
      chips.push(...STAT_CATALOG.filter((d) => d.sport === sport && d.group === spec.wholeGroup));
      continue;
    }
    const def = STAT_CATALOG.find(
      (d) => d.sport === sport && d.group === spec.group && d.key === spec.key,
    );
    if (def) chips.push(def);
    else missing.push(spec);
  }
  return { chips, missing };
}

/** The chips a segment shows, in display order. Teams (its own board) has none. */
export function chipsForSegment(sport: Sport, seg: StatSegment): StatDef[] {
  return resolve(sport, seg).chips;
}

/** Spec'd chips the sport's catalog does not carry — left out, and listed. */
export function omittedChips(sport: Sport, seg: StatSegment): string[] {
  return resolve(sport, seg).missing.map((c) => `${c.group}:${String(c.key)}`);
}

/**
 * Rule 5: switching segment keeps the selected stat when the new segment
 * has it, else lands on the segment's first chip.
 *
 * "Has it" is the same chip first, then the same COLUMN: Anytime TD is one
 * stat filed under Rushing for RB and under Receiving for WR/TE, and a user
 * on it who taps WR/TE is still asking about Anytime TD. Keys are unique
 * within a sport's catalog apart from that one shared column.
 */
export function statForSegment(
  sport: Sport,
  seg: StatSegment,
  current: StatDef | null,
): StatDef | null {
  const chips = chipsForSegment(sport, seg);
  if (current) {
    const same =
      chips.find((c) => c.group === current.group && c.key === current.key) ??
      chips.find((c) => c.key === current.key);
    if (same) return same;
  }
  return chips[0] ?? null;
}

/**
 * Real positions, as nflverse writes them into `nfl_player_game_log.pos`.
 * Measured 2026-09-25 (read-only, seasons 2025–2026): 25 codes, none NULL —
 * pinned in scripts/verify_stat_segments.ts, which fails if a code maps to
 * neither a segment nor the excluded set below.
 *
 * DEF is the ONE defensive set the app has: it is `NFL_DEFENSIVE_POSITIONS`
 * from playerLog.ts (the player page's Defense-tab rule), not a copy of it.
 */
const NFL_POSITIONS: Record<'qb' | 'rb' | 'wrte' | 'def', ReadonlySet<string>> = {
  qb: new Set(['QB']),
  rb: new Set(['RB', 'FB']),
  wrte: new Set(['WR', 'TE']),
  def: NFL_DEFENSIVE_POSITIONS,
};

/**
 * Known positions that belong to NO segment: kickers, punters, long snappers
 * and the offensive line. A kicker is not a receiver because he once caught a
 * fake. Named on purpose — this is the only way a row with a position drops
 * out of every segment; an unknown or missing position passes (below).
 */
export const NFL_EXCLUDED_POSITIONS: ReadonlySet<string> = new Set([
  'K', 'P', 'LS',
  'C', 'G', 'OG', 'T', 'OT', 'OL',
]);

const NFL_SEGMENT_POSITIONS: ReadonlySet<string> = new Set(
  Object.values(NFL_POSITIONS).flatMap((set) => [...set]),
);

/** Every position code this module knows, segment or excluded — for the verify script. */
export function knownNflPositions(): { segment: ReadonlySet<string>; excluded: ReadonlySet<string> } {
  return { segment: NFL_SEGMENT_POSITIONS, excluded: NFL_EXCLUDED_POSITIONS };
}

/**
 * The positions a segment admits, or null when the board must not filter by
 * position at all.
 *
 * Only the NFL, and only on a read that returns `pos` — the Averages board
 * (player_window_totals_nfl) and the last-N Hit Rate board
 * (player_recent_games_nfl). The Season and H2H Hit Rate reads
 * (player_{season,h2h}_stat_values_nfl) return no position, and NCAAF has
 * none anywhere (CFBD's box score names participants, not positions), so
 * there the segment scopes the chips and nothing else — and says so
 * (positionFallbackNote). A position is never inferred from a stat line.
 */
export function positionsForSegment(
  sport: Sport,
  seg: StatSegment,
  readCarriesPosition: boolean,
): ReadonlySet<string> | null {
  if (sport !== 'NFL' || !readCarriesPosition) return null;
  return isPositionSegment(seg) ? NFL_POSITIONS[seg] : null;
}

/** Does the board's current NFL read carry a position per row? */
export function readCarriesPosition(
  sport: Sport,
  mode: 'hitRate' | 'totals',
  window: number | 'season' | 'h2h',
): boolean {
  return sport === 'NFL' && (mode === 'totals' || typeof window === 'number');
}

/**
 * Does a row belong on this segment's board?
 *
 * - no filter: everyone;
 * - a known segment position: only its own segment;
 * - a known non-skill position (NFL_EXCLUDED_POSITIONS): no segment;
 * - no position, or one this module has never seen: EVERY segment. An
 *   unknown is not evidence against the player, and dropping him silently
 *   is the failure this rule replaced (Reviewer, #830).
 */
export function matchesPosition(
  pos: unknown,
  allowed: ReadonlySet<string> | null,
): boolean {
  if (!allowed) return true;
  if (typeof pos !== 'string') return true;
  const p = pos.trim().toUpperCase();
  if (!p) return true;
  if (NFL_EXCLUDED_POSITIONS.has(p)) return false;
  if (!NFL_SEGMENT_POSITIONS.has(p)) return true;
  return allowed.has(p);
}

export function isPositionSegment(seg: StatSegment): seg is 'qb' | 'rb' | 'wrte' | 'def' {
  return seg === 'qb' || seg === 'rb' || seg === 'wrte' || seg === 'def';
}

/**
 * The caption under the chips when a football position segment is on but the
 * board cannot filter by position (Designer, #830 review; copy is Designer's
 * with the real windows named). Null — and so zero height — everywhere else:
 * Teams, the NFL reads that do filter, and every non-football sport.
 */
export function positionFallbackNote(
  sport: Sport,
  seg: StatSegment,
  boardMode: 'players' | 'teams',
  positions: ReadonlySet<string> | null,
): string | null {
  if (boardMode !== 'players' || positions !== null || !isPositionSegment(seg)) return null;
  if (sport === 'NCAAF') return "All positions: college box scores don't list positions.";
  if (sport === 'NFL') {
    return "All positions: Season and H2H don't carry positions yet. Recent-game windows and Averages filter by position.";
  }
  return null;
}

/** The segment's players as a plural noun, for sentences — the VoiceOver
 *  label, lower-cased. "No … and …" reads as both-at-once, so the WR/TE pair
 *  becomes "or"; "No defense with Tackles" does not parse, so DEF says
 *  "defensive players". */
export function segmentPositionNoun(seg: StatSegment): string {
  if (seg === 'def') return 'defensive players';
  return segmentAccessibilityLabel(seg).toLowerCase().replace(' and ', ' or ');
}

/**
 * Did the position cut, and only it, empty the board? Compare the list just
 * before the cut with the list just after it — never with the final list: on
 * Hit Rates the band runs after the cut, and a band that empties a board the
 * position left non-empty must not say "Try another position" (Reviewer,
 * #830). `filterOn` is false while no position set applies.
 */
export function emptiedByPosition(filterOn: boolean, beforeCut: number, afterCut: number): boolean {
  return filterOn && afterCut === 0 && beforeCut > 0;
}

/**
 * The empty board when the POSITION filter emptied a list that had rows
 * before it — the data is fine, the position simply has nobody on this stat
 * (Designer, #830 review). e.g. "No receivers or tight ends with Targets in
 * the last 10 games. Try another position."
 */
export function positionEmptyText(
  seg: StatSegment,
  statLabel: string,
  window: number | 'season' | 'h2h',
): string {
  const when =
    window === 'season' ? 'this season'
    : window === 'h2h' ? 'against their next opponent'
    : `in the last ${window} games`;
  return `No ${segmentPositionNoun(seg)} with ${statLabel} ${when}. Try another position.`;
}
