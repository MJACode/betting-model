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
/** Basketball: guard / forward / center (Matt, 2026-10-05). */
export type BasketballGroup = 'G' | 'F' | 'C';
export type PositionGroup = NflPositionGroup | MlbGroup | BasketballGroup;

/** Sports whose card reads its group from `player_positions`. */
export type RosterSport = 'NBA' | 'WNBA' | 'NCAAF';

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

/** The card's group for a NBA / WNBA / NCAAF player, from `player_positions.pos_group`. */
export function rosterGroup(sport: RosterSport, posGroup: string | null | undefined): PositionGroup | null {
  if (!posGroup) return null;
  const g = posGroup.toUpperCase();
  if (sport === 'NCAAF') return (['QB', 'RB', 'WR', 'TE', 'DL', 'LB', 'DB'] as const).find((x) => x === g) ?? null;
  return (['G', 'F', 'C'] as const).find((x) => x === g) ?? null;
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
  G: 'Guards',
  F: 'Forwards',
  C: 'Centers',
};

/** Mid-sentence form: abbreviations keep their capitals ("WRs", never
 *  "wrs" — VoiceOver spells that out), words go lower case (UX review,
 *  2026-10-06). */
const GROUP_PROSE: Record<PositionGroup, string> = {
  QB: 'QBs', RB: 'RBs', WR: 'WRs', TE: 'TEs',
  DL: 'defensive linemen', LB: 'linebackers', DB: 'defensive backs',
  TOP: '1–3 hitters', MID: '4–6 hitters', BOT: '7–9 hitters', SP: 'starting pitchers',
  G: 'guards', F: 'forwards', C: 'centers',
};

export function groupProse(g: PositionGroup): string {
  return GROUP_PROSE[g];
}

/** Short form for captions: "6 of 10 WR games", "Avg hits per 1–3 hitter". */
const GROUP_SHORT: Record<PositionGroup, string> = {
  QB: 'QB', RB: 'RB', WR: 'WR', TE: 'TE', DL: 'DL', LB: 'LB', DB: 'DB',
  TOP: '1–3 hitter',
  MID: '4–6 hitter',
  BOT: '7–9 hitter',
  SP: 'starter',
  G: 'guard',
  F: 'forward',
  C: 'center',
};

/** What the opponent IS to this group, for the rank caption. */
const OPPONENT_NOUN: Record<PositionGroup, string> = {
  QB: 'defenses', RB: 'defenses', WR: 'defenses', TE: 'defenses',
  DL: 'offenses', LB: 'offenses', DB: 'offenses',
  TOP: 'pitching staffs', MID: 'pitching staffs', BOT: 'pitching staffs',
  SP: 'lineups',
  G: 'defenses', F: 'defenses', C: 'defenses',
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
  G: '15+ minutes',
  F: '15+ minutes',
  C: '15+ minutes',
};

/**
 * NCAAF's role cut where it differs from the NFL's. The college log has no
 * targets column (CFBD box scores do not carry it), so a receiver's role is
 * seen only through a catch. Mirrors add_position_vs_opponent_bball_ncaaf.sql;
 * pinned by tests/test_position_vs_opponent.py.
 */
const NCAAF_ROLE_CUT: Partial<Record<PositionGroup, string>> = {
  RB: '6+ carries and catches',
  WR: '1+ catch',
  TE: '1+ catch',
  DL: '2+ tackles or sacks',
  LB: '2+ tackles or sacks',
  DB: '2+ tackles or sacks',
};

/** The footnote under the list: the cut, in a sentence the reader did not
 *  already know (UX review, 2026-10-06 — "a start batting 1st–3rd" restated
 *  the title). */
export function footnoteText(g: PositionGroup, sport?: string): string {
  switch (g) {
    case 'TOP':
    case 'MID':
    case 'BOT':
      return `Counts lineup starters in that spot only; pinch hitters and late subs don't count.`;
    case 'SP':
      return `Counts starts only; relief outings don't count.`;
    default: {
      const base = `Counts ${GROUP_PROSE[g]} with ${roleCutText(g, sport)} in the game.`;
      // Said out loud: a 0-catch college game cannot be seen as a role.
      return sport === 'NCAAF' && (g === 'WR' || g === 'TE')
        ? `${base} College box scores carry no targets, so a game with no catch can't be counted.`
        : base;
    }
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
  G: 'a guard',
  F: 'a forward',
  C: 'a center',
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

export function roleCutText(g: PositionGroup, sport?: string): string {
  return (sport === 'NCAAF' && NCAAF_ROLE_CUT[g]) || ROLE_CUT[g];
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

/**
 * The season label in progress for the roster sports (CLAUDE.md §4):
 *   NBA    ENDING year — from October the label is next year's (2026-27 = 2027).
 *   WNBA   year of play — January to April show the season just finished.
 *   NCAAF  starting year, like the NFL — January and February are last year's.
 */
export function rosterSeasonInProgress(sport: RosterSport, todayIso: string): number {
  const year = Number(todayIso.slice(0, 4));
  const month = Number(todayIso.slice(5, 7));
  if (sport === 'NBA') return month >= 10 ? year + 1 : year;
  if (sport === 'WNBA') return month <= 4 ? year - 1 : year;
  return month <= 2 ? year - 1 : year;
}

export type SeasonChoice = 'this' | 'last';

/** Player and opponent, so a reused card can tell a new subject from a
 *  refresh of the same one. NUL is not in a player id or an opponent abbrev. */
export function seasonSubjectKey(playerId: string | null, opponent: string): string {
  return `${playerId ?? ''}\0${opponent}`;
}

export interface SeasonChoiceInput {
  subjectKey: string;
  seenKey: string | null;
  /** The once-only auto-open has already run for this subject. */
  decided: boolean;
  /** The reader tapped This season / Last season for this player. */
  readerPicked: boolean;
  choice: SeasonChoice;
  loading: boolean;
  rows: { player_id: string; season: number | string }[];
  playerId: string | null;
  seasonThis: number;
  /**
   * True when this sport has a final game in `seasonThis`. False when the
   * season has not started. null while that read has not landed — do not
   * decide yet. A scheduled-but-unplayed slate is not started: measured
   * 2026-10-06, NBA season 2027 had 46 games and 0 finals.
   */
  seasonStarted: boolean | null;
}

export interface SeasonChoiceNext {
  seenKey: string;
  decided: boolean;
  readerPicked: boolean;
  choice: SeasonChoice;
  subjectChanged: boolean;
}

/**
 * Open on last season only when this season has no final game for the sport
 * yet (it has not started) and last season has games against this opponent.
 * A first meeting after the season has started stays on this season, so the
 * card shows the empty state. Once per player + opponent. A different player
 * or opponent starts that decision again. A season the reader tapped for
 * this same player is left alone, including when the opponent changes.
 * `seasonStarted === null` does not decide: deciding before that read lands
 * is how a mid-season first meeting locked onto last season.
 */
export function nextSeasonChoice(state: SeasonChoiceInput): SeasonChoiceNext {
  const playerId = state.playerId ?? '';
  let decided = state.decided;
  let readerPicked = state.readerPicked;
  let choice = state.choice;
  const subjectChanged = state.seenKey !== state.subjectKey;
  if (subjectChanged) {
    const prevPlayer = state.seenKey == null ? null : state.seenKey.split('\0')[0];
    const samePlayer = prevPlayer !== null && prevPlayer === playerId;
    decided = false;
    if (!(samePlayer && readerPicked)) {
      choice = 'this';
      readerPicked = false;
    }
  }
  if (readerPicked || decided || state.loading || state.rows.length === 0 || state.seasonStarted == null) {
    return { seenKey: state.subjectKey, decided, readerPicked, choice, subjectChanged };
  }
  const others = state.rows.filter((r) => !state.playerId || r.player_id !== state.playerId);
  const hasThis = others.some((r) => Number(r.season) === state.seasonThis);
  const hasLast = others.some((r) => Number(r.season) === state.seasonThis - 1);
  if (state.seasonStarted === false && !hasThis && hasLast) choice = 'last';
  return { seenKey: state.subjectKey, decided: true, readerPicked, choice, subjectChanged };
}

/** True when some other player at this position has a row in either season
 *  the card loaded. The page's own player does not count. */
export function hasOtherPositionGames(
  rows: readonly { player_id: string }[],
  playerId: string | null,
): boolean {
  return rows.some((r) => !playerId || r.player_id !== playerId);
}

/**
 * The empty-state line. "this season yet" is a first meeting: last season
 * has games against this opponent and this one does not. An opponent with
 * no row in either season is named once, for both seasons, with the same
 * opponent string the title and the tooltip already use — the games
 * display name ("Samford"), not an uppercased feed token. The This season
 * / Last season chips still open the year-stamped line. Last season keeps
 * the "in our data" hedge (the 2025 MLB log is missing every ARI, CWS, OAK
 * and WSH game, measured 2026-10-06).
 */
export function emptySeasonMessage(opts: {
  short: string;
  opponent: string;
  choice: SeasonChoice;
  seasonThis: number;
  hasAnySeason: boolean;
}): string {
  if (opts.choice === 'last') {
    return `No ${opts.short} games vs ${opts.opponent} in our ${opts.seasonThis - 1} data.`;
  }
  if (!opts.hasAnySeason) {
    const opponentDisplay = opts.opponent;
    return `No ${opts.short} games vs ${opponentDisplay} this season or last.`;
  }
  return `No ${opts.short} games vs ${opts.opponent} this season yet.`;
}

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

/** MLB groups show a per-player summary instead of every game (Matt,
 *  2026-10-06: "Sure in summary" — ~440 player-games a season vs one team). */
export function isMlbGroup(g: PositionGroup): g is MlbGroup {
  return g === 'TOP' || g === 'MID' || g === 'BOT' || g === 'SP';
}

export interface PlayerSummary {
  playerId: string;
  playerName: string;
  /** His team in his most recent game against this opponent. */
  team: string;
  games: number;
  /** Games that cleared the page's line, the same isHit as the list rows. */
  hits: number;
  avg: number;
  lastDate: string;
}

/**
 * One row per player: how often each cleared the page's line against this
 * opponent, most games first (the steadiest evidence on top), then by hit
 * rate, then by name so the order is stable.
 */
export function playerSummaries(entries: readonly PositionVsOpponentEntry[]): PlayerSummary[] {
  const by = new Map<string, PlayerSummary & { sum: number }>();
  for (const e of entries) {
    const cur = by.get(e.playerId);
    if (!cur) {
      by.set(e.playerId, {
        playerId: e.playerId, playerName: e.playerName, team: e.team,
        games: 1, hits: e.hit ? 1 : 0, avg: e.value, sum: e.value, lastDate: e.date,
      });
      continue;
    }
    cur.games += 1;
    cur.hits += e.hit ? 1 : 0;
    cur.sum += e.value;
    if (e.date > cur.lastDate) {
      cur.lastDate = e.date;
      cur.team = e.team;
      cur.playerName = e.playerName;
    }
  }
  return [...by.values()]
    .map(({ sum, ...p }) => ({ ...p, avg: sum / p.games }))
    .sort(
      (a, b) =>
        b.games - a.games ||
        b.hits / b.games - a.hits / a.games ||
        a.playerName.localeCompare(b.playerName),
    );
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
