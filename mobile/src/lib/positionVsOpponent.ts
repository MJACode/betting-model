/**
 * "WRs vs ATL" — how other players at the player's position have done against
 * the team he plays next (Matt, 2026-10-05).
 *
 * The server (position_vs_opponent_nfl) returns one row per QUALIFYING
 * player-game against that defence — "real role only", the cut is in the
 * migration and named on the card — each carrying the defence's league rank for
 * that season. Everything that depends on the page's line (the hit rate, each
 * row's ✓/✗) is computed here, so moving the ruler never refetches.
 *
 * Phase 1 is NFL only: it is the one log with both `pos` and `opponent` on
 * every row. MLB (lineup spot / starter) and NBA, WNBA, NCAAF (position ingest
 * first) are the next two phases, and return null here until they land.
 */
import { computeHitRate, isHit, type HitDirection } from '@/lib/hitRate';
import type { PositionVsOpponentRow } from '@/types';

export type NflPositionGroup = 'QB' | 'RB' | 'WR' | 'TE' | 'DL' | 'LB' | 'DB';

/** Mirrors the CASE in the migration — the two must agree or the card asks
 *  for a group the server never fills. Pinned by
 *  tests/test_position_vs_opponent.py. */
const NFL_GROUP_OF: Record<string, NflPositionGroup> = {
  QB: 'QB',
  RB: 'RB', FB: 'RB',
  WR: 'WR',
  TE: 'TE',
  DE: 'DL', DT: 'DL', NT: 'DL', DL: 'DL',
  LB: 'LB', ILB: 'LB', OLB: 'LB', MLB: 'LB',
  CB: 'DB', S: 'DB', FS: 'DB', SS: 'DB', SAF: 'DB', DB: 'DB',
};

/** Linemen, kickers and long snappers have no group: the card does not show. */
export function nflPositionGroup(pos: string | null | undefined): NflPositionGroup | null {
  if (!pos) return null;
  return NFL_GROUP_OF[pos.toUpperCase()] ?? null;
}

/** Plural for the title: "WRs vs ATL", "Defensive backs vs ATL". */
const GROUP_PLURAL: Record<NflPositionGroup, string> = {
  QB: 'QBs',
  RB: 'RBs',
  WR: 'WRs',
  TE: 'TEs',
  DL: 'Defensive linemen',
  LB: 'Linebackers',
  DB: 'Defensive backs',
};

/** The role cut, in words, for the card's footnote. Same numbers as the SQL. */
const ROLE_CUT: Record<NflPositionGroup, string> = {
  QB: '10+ pass attempts',
  RB: '6+ carries and targets',
  WR: '3+ targets',
  TE: '2+ targets',
  DL: '2+ tackles, sacks or QB hits',
  LB: '2+ tackles, sacks or QB hits',
  DB: '2+ tackles, sacks or QB hits',
};

export function groupPlural(g: NflPositionGroup): string {
  return GROUP_PLURAL[g];
}

export function roleCutText(g: NflPositionGroup): string {
  return ROLE_CUT[g];
}

/**
 * The NFL season label in progress on `todayIso` — the STARTING year
 * (2025 = the season that ends in Feb 2026; measured on production: 2025 REG
 * runs 2025-09 → 2026-01-04, POST to 2026-02-08). January and February belong
 * to the previous label; from March on, the coming season's.
 */
export function nflSeasonInProgress(todayIso: string): number {
  const year = Number(todayIso.slice(0, 4));
  const month = Number(todayIso.slice(5, 7));
  return month <= 2 ? year - 1 : year;
}

export type SeasonChoice = 'this' | 'last';

export interface PositionVsOpponentEntry {
  playerId: string;
  playerName: string;
  team: string;
  date: string;
  value: number;
  hit: boolean;
}

export interface PositionVsOpponent {
  opponent: string;
  group: NflPositionGroup;
  season: number;
  /** Newest first. */
  entries: PositionVsOpponentEntry[];
  hits: number;
  total: number;
  /** null when there is nothing to rate. */
  hitRate: number | null;
  /** The defence's average per qualifying player-game, and its league rank
   *  (1 = allows the most). null when the defence has no qualifying game. */
  avgAllowed: number | null;
  rankMostAllowed: number | null;
  teamsRanked: number | null;
}

/**
 * The card's numbers for one season, off the rows the RPC returned.
 *
 * The player himself is dropped: the card is about OTHER players at his
 * position. (A player traded mid-season can have faced this defence.)
 */
export function positionVsOpponent(
  rows: readonly PositionVsOpponentRow[],
  opts: {
    opponent: string;
    group: NflPositionGroup;
    season: number;
    excludePlayerId: string | null;
    line: number;
    side: HitDirection;
  },
): PositionVsOpponent {
  const inSeason = rows.filter((r) => Number(r.season) === opts.season);
  // Rank fields are the defence's, repeated on every row of the season; read
  // them before excluding the player so a defence that has only faced HIM
  // still gets its rank.
  const head = inSeason[0];
  const entries: PositionVsOpponentEntry[] = [];
  for (const r of inSeason) {
    if (opts.excludePlayerId && r.player_id === opts.excludePlayerId) continue;
    const v = Number(r.value);
    if (!Number.isFinite(v)) continue;
    entries.push({
      playerId: r.player_id,
      playerName: r.player_name,
      team: r.team,
      date: r.game_date,
      value: v,
      hit: isHit(v, opts.line, opts.side),
    });
  }
  // Newest game first; inside one game, the bigger number first so the
  // defence's worst day reads at the top of its group.
  entries.sort((a, b) => (a.date === b.date ? b.value - a.value : a.date < b.date ? 1 : -1));
  const { hits, total, pct } = computeHitRate(entries.map((e) => e.value), opts.line, opts.side);
  return {
    opponent: opts.opponent,
    group: opts.group,
    season: opts.season,
    entries,
    hits,
    total,
    hitRate: total ? pct : null,
    avgAllowed: head ? Number(head.avg_allowed) : null,
    rankMostAllowed: head ? Number(head.rank_most_allowed) : null,
    teamsRanked: head ? Number(head.teams_ranked) : null,
  };
}
