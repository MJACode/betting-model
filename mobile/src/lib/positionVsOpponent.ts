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
 * NFL groups by position (the log carries `pos`). MLB groups batters by
 * lineup spot — 1-3, 4-6, 7-9 — and pitchers as starters (Matt, 2026-10-05:
 * "line up spot and starter"). NBA, WNBA and NCAAF need a position ingest
 * first and return null here until it lands.
 */
import { computeHitRate, isHit, type HitDirection } from '@/lib/hitRate';
import type { PositionVsOpponentRow } from '@/types';

export type NflPositionGroup = 'QB' | 'RB' | 'WR' | 'TE' | 'DL' | 'LB' | 'DB';
/** MLB: batters by lineup spot, pitchers as the game's starter. Mirrors the
 *  CASE in add_position_vs_opponent_mlb.sql. */
export type MlbGroup = 'TOP' | 'MID' | 'BOT' | 'SP';
export type PositionGroup = NflPositionGroup | MlbGroup;

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

/**
 * The MLB group for a player: a starting pitcher is SP (a reliever has no
 * card), a batter is bucketed by his lineup spot — tonight's posted slot when
 * the lineup is out, else the spot he last started in.
 */
export function mlbGroup(args: {
  playerType: 'batter' | 'pitcher' | null | undefined;
  /** Tonight's posted slot, when the lineup is out. */
  lineupSlot: number | null | undefined;
  /** The log, newest first. */
  games: ReadonlyArray<Record<string, unknown>>;
}): MlbGroup | null {
  if (args.playerType === 'pitcher') {
    // player_game_log.is_starter is a boolean column; PostgREST sends it as
    // JSON true/false. His most recent outing decides: a starter who made one
    // relief appearance last time out has no card until he starts again.
    const s = args.games[0]?.is_starter;
    return s === true || s === 'true' || s === 1 ? 'SP' : null;
  }
  let slot = args.lineupSlot ?? null;
  if (slot == null) {
    for (const g of args.games) {
      const b = Number(g.batting_order);
      if (g.batting_order != null && Number.isFinite(b)) {
        slot = b;
        break;
      }
    }
  }
  if (slot == null || slot < 1 || slot > 9) return null;
  return slot <= 3 ? 'TOP' : slot <= 6 ? 'MID' : 'BOT';
}

/** Plural for the title: "WRs vs ATL", "Defensive backs vs ATL". */
const GROUP_PLURAL: Record<PositionGroup, string> = {
  QB: 'QBs',
  RB: 'RBs',
  WR: 'WRs',
  TE: 'TEs',
  DL: 'Defensive linemen',
  LB: 'Linebackers',
  DB: 'Defensive backs',
  TOP: '1–3 hitters',
  MID: '4–6 hitters',
  BOT: '7–9 hitters',
  SP: 'Starting pitchers',
};

/** Short form for captions: "6 of 10 WR games", "Avg hits per 1–3 hitter". */
const GROUP_SHORT: Record<PositionGroup, string> = {
  QB: 'QB', RB: 'RB', WR: 'WR', TE: 'TE', DL: 'DL', LB: 'LB', DB: 'DB',
  TOP: '1–3 hitter',
  MID: '4–6 hitter',
  BOT: '7–9 hitter',
  SP: 'starter',
};

/** What the opponent IS to this group, for the rank caption. */
const OPPONENT_NOUN: Record<PositionGroup, string> = {
  QB: 'defenses', RB: 'defenses', WR: 'defenses', TE: 'defenses',
  DL: 'offenses', LB: 'offenses', DB: 'offenses',
  TOP: 'pitching staffs', MID: 'pitching staffs', BOT: 'pitching staffs',
  SP: 'lineups',
};

/** The role cut, in words, for the card's footnote. Same numbers as the SQL. */
const ROLE_CUT: Record<PositionGroup, string> = {
  QB: '10+ pass attempts',
  RB: '6+ carries and targets',
  WR: '3+ targets',
  TE: '2+ targets',
  DL: '2+ tackles, sacks or QB hits',
  LB: '2+ tackles, sacks or QB hits',
  DB: '2+ tackles, sacks or QB hits',
  TOP: 'starting the game batting 1st–3rd',
  MID: 'starting the game batting 4th–6th',
  BOT: 'starting the game batting 7th–9th',
  SP: 'starting the game',
};

/** The footnote under the list: the cut, in a sentence the reader did not
 *  already know (UX review, 2026-10-06 — "a start batting 1st–3rd" restated
 *  the title). */
export function footnoteText(g: PositionGroup): string {
  switch (g) {
    case 'TOP':
    case 'MID':
    case 'BOT':
      return `Counts lineup starters in that spot only; pinch hitters and late subs don't count.`;
    case 'SP':
      return `Counts starts only; relief outings don't count.`;
    default:
      return `Counts ${GROUP_PLURAL[g].toLowerCase()} with ${ROLE_CUT[g]} in the game.`;
  }
}

/** How the rank reads: a lineup does not "allow" a pitcher's strikeouts. */
export function rankPhrase(g: PositionGroup): string {
  return g === 'SP' ? '1st = the most per opposing starter' : '1st = allows the most';
}

/** With its article, for prose: "an RB", "a WR", "a defensive back". */
const GROUP_SINGULAR: Record<PositionGroup, string> = {
  QB: 'a QB',
  RB: 'an RB',
  WR: 'a WR',
  TE: 'a TE',
  DL: 'a defensive lineman',
  LB: 'a linebacker',
  DB: 'a defensive back',
  TOP: 'a 1–3 hitter',
  MID: 'a 4–6 hitter',
  BOT: 'a 7–9 hitter',
  SP: 'a starting pitcher',
};

export function groupShort(g: PositionGroup): string {
  return GROUP_SHORT[g];
}

export function opponentNoun(g: PositionGroup): string {
  return OPPONENT_NOUN[g];
}

export function groupSingular(g: PositionGroup): string {
  return GROUP_SINGULAR[g];
}

export function groupPlural(g: PositionGroup): string {
  return GROUP_PLURAL[g];
}

export function roleCutText(g: PositionGroup): string {
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

/**
 * The MLB season label in progress — the YEAR OF PLAY (CLAUDE.md §4). January
 * and February have no games, so they show the season just finished.
 */
export function mlbSeasonInProgress(todayIso: string): number {
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
  /** NFL week, when the log carries it. */
  week: number | null;
  /** MLB batting spot that game ("2"), or 'SP'; the NFL position otherwise. */
  pos: string | null;
  gameId: string;
  /** 1 or 2 when this player has two games on this date (an MLB
   *  doubleheader: 192 same-day pairs in the 2026 log, measured 2026-10-06);
   *  null otherwise. */
  gameOfDay: number | null;
  value: number;
  hit: boolean;
}

export interface PositionVsOpponent {
  opponent: string;
  group: PositionGroup;
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
    group: PositionGroup;
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
      week: r.week == null ? null : Number(r.week),
      pos: r.pos ?? null,
      gameId: r.game_id,
      gameOfDay: null,
      value: v,
      hit: isHit(v, opts.line, opts.side),
    });
  }
  // Newest game first; inside one game, the bigger number first so the
  // defence's worst day reads at the top of its group.
  entries.sort((a, b) => (a.date === b.date ? b.value - a.value : a.date < b.date ? 1 : -1));
  // Doubleheaders: number a player's two games on one date by game id, so
  // two rows with the same name and date say which game each was.
  const sameDay = new Map<string, PositionVsOpponentEntry[]>();
  for (const e of entries) {
    const k = `${e.playerId}:${e.date}`;
    sameDay.set(k, [...(sameDay.get(k) ?? []), e]);
  }
  for (const list of sameDay.values()) {
    if (list.length < 2) continue;
    [...list].sort((a, b) => (a.gameId < b.gameId ? -1 : 1)).forEach((e, i) => (e.gameOfDay = i + 1));
  }
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
