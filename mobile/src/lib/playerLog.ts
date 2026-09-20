/**
 * Per-player game-log plumbing shared by every sport's player detail screen.
 *
 * The player detail view (hit rate at a line, rolling averages, recent games)
 * used to be MLB-only: it read `player_game_log` directly and drew its stat
 * chips from the MLB prop-model registry. Each sport keeps its own log table
 * with its own columns, so this module is the one place that knows how to turn
 * any of them into a common row shape and which stats each can offer.
 *
 * Stat definitions come from the SAME `statCatalog` the Stats-tab leaderboard
 * uses, so a player's detail screen can never offer a stat the leaderboard
 * ranks differently (or vice versa).
 */
import type { Sport } from '@/hooks/useSportFilter';
import {
  statForPropModel,
  statsForSport,
  statValue,
  type StatDef,
  type StatGroup,
} from './statCatalog';
import type { PlayerType } from '@/types';

/** Sports with a per-game player log — the ones that can show player detail. */
export type PlayerLogSport = 'MLB' | 'WNBA' | 'NBA' | 'NFL' | 'NCAAF';

const LOG_SPORTS = new Set<Sport>(['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF']);

/** The two football leagues share a log shape (and a weekly cadence). */
const FOOTBALL = new Set<PlayerLogSport>(['NFL', 'NCAAF']);

/**
 * Whether a sport has per-player game logs, and therefore a player detail
 * screen. UFC (fight-level, no per-game stat log), NHL (team + goalie only)
 * and Golf (v1 has no player leaderboard) do not.
 */
export function supportsPlayerDetail(sport: Sport): sport is PlayerLogSport {
  return LOG_SPORTS.has(sport);
}

/** One normalized game from any sport's player log, newest-first when listed. */
export interface PlayerLogEntry {
  player_id: string;
  player_name: string;
  team: string | null;
  game_id: string;
  game_date: string;
  season: number;
  /** MLB only — decides which stat chips apply. */
  player_type?: PlayerType | null;
  /** NFL only — CFBD's box score names participants, not positions. */
  pos?: string | null;
  opponent?: string | null;
  week?: number | null;
  /** Every sport's stat columns, plus the derived ones added below. */
  [key: string]: number | string | null | undefined;
}

// ── Table + column config ───────────────────────────────────────────────────
// Column lists are explicit (not `*`) so a new column on a log table can never
// silently widen what the phone downloads.

const MLB_COLUMNS =
  'player_id, player_name, team, player_type, game_id, game_date, season, ' +
  'innings_pitched, pitches, p_strikeouts, p_walks, p_hits_allowed, p_earned_runs, ' +
  'p_home_runs, at_bats, hits, doubles, triples, home_runs, rbi, runs, walks, ' +
  'strikeouts, stolen_bases, total_bases, batting_order';

const BASKETBALL_COLUMNS =
  'player_id, player_name, team, game_id, game_date, season, minutes, is_starter, ' +
  'points, rebounds, assists, steals, blocks, turnovers, fg3_made';

const NFL_COLUMNS =
  'player_id, player_name, pos, team, opponent, game_id, game_date, season, week, ' +
  'season_type, completions, attempts, passing_yards, passing_tds, interceptions, ' +
  'carries, rushing_yards, rushing_tds, receptions, targets, receiving_yards, ' +
  'receiving_tds, def_sacks, def_interceptions';

// CFBD reports no targets and no position, so the NCAAF list is the NFL one
// minus those two, plus the defensive counts college box scores carry.
const NCAAF_COLUMNS =
  'player_id, player_name, team, opponent, game_id, game_date, season, week, ' +
  'season_type, completions, attempts, passing_yards, passing_tds, interceptions, ' +
  'carries, rushing_yards, rushing_tds, receptions, receiving_yards, ' +
  'receiving_tds, def_tackles, def_solo, def_sacks, def_tfl, def_pd, ' +
  'def_interceptions';

export const LOG_TABLE: Record<PlayerLogSport, string> = {
  MLB: 'player_game_log',
  WNBA: 'wnba_player_game_log',
  NBA: 'nba_player_game_log',
  NFL: 'nfl_player_game_log',
  NCAAF: 'ncaaf_player_game_log',
};

export const LOG_COLUMNS: Record<PlayerLogSport, string> = {
  MLB: MLB_COLUMNS,
  WNBA: BASKETBALL_COLUMNS,
  NBA: BASKETBALL_COLUMNS,
  NFL: NFL_COLUMNS,
  NCAAF: NCAAF_COLUMNS,
};

/**
 * How many games back to load. MLB and basketball play near-daily, so 50 rows
 * is a few months; NFL plays weekly, so 25 rows is already a season and a half
 * and anything more would stretch the "recent form" read past usefulness.
 */
export function logFetchLimit(sport: PlayerLogSport): number {
  return FOOTBALL.has(sport) ? 25 : 50;
}

// ── Derived stats ───────────────────────────────────────────────────────────

/**
 * Adds the columns the leaderboard views compute in SQL but the raw log tables
 * do not store, so a stat chip resolves the same way on both surfaces:
 *   basketball  threes = fg3_made, pra = points + rebounds + assists
 *   NFL         rush_rec_tds = rushing_tds + receiving_tds
 *   MLB pitcher outs — see `outs` note in `chipsForPlayer` below
 * Missing inputs stay missing rather than becoming 0: a null stat must read as
 * "no data" (excluded from the hit rate), never as a game with zero of it.
 */
export function normalizeLogRow(sport: PlayerLogSport, raw: Record<string, unknown>): PlayerLogEntry {
  const row = { ...raw } as PlayerLogEntry;
  if (sport === 'WNBA' || sport === 'NBA') {
    row.threes = num(raw.fg3_made);
    row.pra = sum(raw.points, raw.rebounds, raw.assists);
  } else if (FOOTBALL.has(sport)) {
    row.rush_rec_tds = sum(raw.rushing_tds, raw.receiving_tds);
  } else if (sport === 'MLB') {
    row.outs = ipToOuts(raw.innings_pitched);
  }
  return row;
}

function num(v: unknown): number | null {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Sum of parts, or null when every part is missing (see normalizeLogRow). */
function sum(...parts: unknown[]): number | null {
  let total = 0;
  let seen = false;
  for (const p of parts) {
    const n = num(p);
    if (n == null) continue;
    total += n;
    seen = true;
  }
  return seen ? total : null;
}

/**
 * Baseball innings-pitched notation → outs. 5.2 means five and TWO THIRDS
 * innings, not 5.2 innings, so it cannot be compared against a line as a plain
 * decimal — the detail screen offers outs instead.
 */
export function ipToOuts(ip: unknown): number | null {
  const n = num(ip);
  if (n == null) return null;
  const whole = Math.floor(n);
  const frac = Math.round((n - whole) * 10);
  return whole * 3 + frac;
}

// ── Stat chips ──────────────────────────────────────────────────────────────

/** Detail-screen replacement for the MLB "Innings" leaderboard stat. */
const OUTS_STAT: StatDef = {
  key: 'outs' as StatDef['key'],
  label: 'Outs',
  sport: 'MLB',
  group: 'Pitching',
  playerType: 'pitcher',
  defaultLine: 16.5,
};

/**
 * The stats a player's detail screen can chart, from the shared catalog.
 *
 * Two sport-specific adjustments:
 *  - MLB chips are split by player type, the way the leaderboard splits them.
 *  - MLB pitching swaps "Innings" for "Outs". The leaderboard SUMS innings so
 *    the notation quirk averages out there, but the detail screen compares a
 *    single game against a line, where 5.2 IP >= 5.5 is false and wrong.
 */
export function chipsForPlayer(sport: PlayerLogSport, playerType?: PlayerType | null): StatDef[] {
  const all = statsForSport(sport);
  if (sport !== 'MLB') return all;
  const type = playerType ?? 'batter';
  return all
    .filter((s) => s.playerType === type)
    .map((s) => (s.key === 'innings_pitched' ? OUTS_STAT : s));
}

/** The stat a player's detail screen opens on. */
export function defaultChipForPlayer(
  sport: PlayerLogSport,
  playerType?: PlayerType | null,
): StatDef | null {
  return chipsForPlayer(sport, playerType)[0] ?? null;
}

/** Ordered stat groups present in a chip list, in the order the chips run. */
export function groupsOfChips(chips: StatDef[]): StatGroup[] {
  const seen: StatGroup[] = [];
  for (const c of chips) {
    if (!seen.includes(c.group)) seen.push(c.group);
  }
  return seen;
}

// ── Which groups a player can actually fill ─────────────────────────────────
//
// Lamar Jackson's screen offered a Defense tab: Sacks 0.00 on every window, a
// 0% badge in alarm red, ten charted zeroes (Matt, 2026-09-19). Nothing was
// broken. `nfl_player_game_log` stores 0, never NULL, for a stat a position
// does not produce — measured 2026-09-19, all 175,542 rows carry a value for
// def_sacks — so the tab had ten real games to chart and charted them. It is
// still a control that leads nowhere, and the same shape ran the other way: a
// linebacker got Passing, Rushing and Receiving, all zeroes.
//
// So the screen asks what this player has actually PRODUCED: the log decides,
// and the position is the safety net under it. The log is the stronger of the
// two because it is the same evidence the chart draws — a tab is offered when
// there is something in it, in either league, including the NCAAF logs that
// carry no position at all. The position map exists for the player with
// nothing on file yet, where "no tabs" and "every tab" are both wrong answers.

const NFL_DEFENSIVE_POSITIONS = new Set([
  'CB', 'DB', 'DE', 'DL', 'DT', 'FS', 'ILB', 'LB', 'MLB', 'NT', 'OLB', 'S', 'SAF',
]);

// Offense and special teams. A kicker or a long snapper produces none of these
// either, but the tabs they get are the ones their side of the ball can fill —
// never Defense.
const NFL_NON_DEFENSIVE_POSITIONS = new Set([
  'C', 'FB', 'G', 'K', 'LS', 'OL', 'OT', 'P', 'QB', 'RB', 'TE', 'WR',
]);

const DEFENSIVE_GROUPS: StatGroup[] = ['Defense'];
const NON_DEFENSIVE_GROUPS: StatGroup[] = ['Passing', 'Rushing', 'Receiving'];

/**
 * The groups a football position is expected to fill. Empty for a position we
 * do not recognise and for NCAAF (no position in the box score) — the log is
 * then the only evidence, which is the conservative way round: an unknown
 * position hides nothing on its own.
 */
export function positionGroups(pos: string | null | undefined): StatGroup[] {
  if (!pos) return [];
  const p = pos.toUpperCase();
  if (NFL_DEFENSIVE_POSITIONS.has(p)) return DEFENSIVE_GROUPS;
  if (NFL_NON_DEFENSIVE_POSITIONS.has(p)) return NON_DEFENSIVE_GROUPS;
  return [];
}

/** The player's position from their log, newest game that names one. */
function positionOf(games: PlayerLogEntry[]): string | null {
  for (const g of games) {
    if (g.pos) return String(g.pos);
  }
  return null;
}

/**
 * The chips a loaded player's screen should actually offer: the groups they
 * have put a real number in inside the loaded window, with their position as
 * the safety net. Whole groups are kept or dropped together — a Passing tab
 * still lists Pass TDs for a quarterback who has none this month.
 *
 * "A real number" is non-NULL and non-zero, because the NFL log stores 0 where
 * NCAAF stores NULL and a tab of ten zeroes is the thing being fixed. A
 * quarterback who ran a jet sweep keeps his Rushing tab; a linebacker who
 * caught a lateral gets a Receiving one, because he did.
 *
 * Three fallbacks, each one wider than the last:
 *  - no games loaded yet -> every chip, so the tab row does not shrink to a
 *    guess and then grow back;
 *  - nothing but zeroes on file (an inactive month, a rookie's debut) -> the
 *    position's own groups, which is how a benched quarterback still gets
 *    Passing rather than Defense;
 *  - position unknown too (NCAAF, where CFBD names no position) -> every chip,
 *    rather than a screen with no tabs at all.
 */
export function chipsForLoadedPlayer(chips: StatDef[], games: PlayerLogEntry[]): StatDef[] {
  if (games.length === 0) return chips;
  const filled = filledChipCounts(chips, games);
  const played = new Set<StatGroup>();
  for (const c of chips) {
    if ((filled.get(chipKey(c)) ?? 0) > 0) played.add(c.group);
  }
  const allowed = played.size > 0 ? played : new Set<StatGroup>(positionGroups(positionOf(games)));
  const kept = chips.filter((c) => allowed.has(c.group));
  return kept.length > 0 ? kept : chips;
}

/**
 * The chip a caller asked this screen to open on, resolved against the
 * player's own chip list.
 *
 * The board (and a prop pick) hands the stat over as two loose strings on the
 * route rather than a StatDef, because a route param is serialised into
 * navigation state and restored from it — the same reason `matchupGrade`
 * travels as a string. The group is what disambiguates: football shares stat
 * keys across groups, so `receiving_tds` alone is ambiguous where
 * `Receiving:receiving_tds` is not. A key with no group still resolves, to the
 * first group holding it, so an older build's params keep working.
 *
 * The MLB innings→outs swap (chipsForPlayer) is applied here too: the board
 * sums innings, the detail screen charts outs, and they are one stat to a
 * reader tapping a pitcher's row.
 */
export function requestedChip(
  chips: StatDef[],
  statKey?: string | null,
  statGroup?: string | null,
): StatDef | null {
  if (!statKey) return null;
  const key = statKey === 'innings_pitched' ? String(OUTS_STAT.key) : statKey;
  const matches = chips.filter((c) => String(c.key) === key);
  if (matches.length === 0) return null;
  if (statGroup) {
    const inGroup = matches.find((c) => c.group === statGroup);
    if (inGroup) return inGroup;
  }
  return matches[0] ?? null;
}

/**
 * `chipsForLoadedPlayer` with the ASKED-FOR stat kept, whatever the log says.
 *
 * The two rules pull opposite ways and both are right. A tab the player has
 * never filled is a control that leads nowhere — unless the reader has just
 * tapped that very stat, in which case "he has not scored in ten games" is the
 * answer they came for, and silently rehoming them on Receptions is the bug
 * this fixes. So the filter still decides everything else and ONE chip is
 * exempt from it.
 *
 * One CHIP, not its group (UX review, 2026-09-20): readmitting the group would
 * hand a touchdown-less receiver a Rushing tab holding Rush Yards, Rush TDs
 * and Carries as well, all flat zero — the three controls 2026-09-19 removed,
 * smuggled back in by the exemption. A one-chip tab reads honestly, and it is
 * the only chip in the tab anyone asked for.
 */
export function chipsWithRequested(
  all: StatDef[],
  kept: StatDef[],
  requested: StatDef | null,
): StatDef[] {
  if (!requested) return kept;
  const key = chipKey(requested);
  if (kept.some((c) => chipKey(c) === key)) return kept;
  const keptKeys = new Set(kept.map(chipKey));
  return all.filter((c) => keptKeys.has(chipKey(c)) || chipKey(c) === key);
}

/** A chip's identity: two sports share stat keys, and football shares them across groups. */
export function chipKey(c: StatDef): string {
  return `${c.group}:${String(c.key)}`;
}

/**
 * How many of the loaded games each chip has a real number in — non-NULL and
 * non-zero. Chips missing from the map stay tappable: a running back with no
 * receiving touchdown in twenty-five games can still be bet to score one, so
 * the chip is offered; it is only never the chip a tab OPENS on.
 */
export function filledChipCounts(chips: StatDef[], games: PlayerLogEntry[]): Map<string, number> {
  const counts = new Map<string, number>();
  for (const c of chips) {
    let n = 0;
    for (const g of games) {
      const v = logStatValue(g, c);
      if (v != null && v !== 0) n += 1;
    }
    if (n > 0) counts.set(chipKey(c), n);
  }
  return counts;
}

/**
 * The chip a screen (or one of its tabs) should open on: within a group, the
 * stat this player fills most often; across groups, the most-filled chip of
 * the group they fill most overall. Ties go to catalog order, and a player who
 * fills nothing gets the first chip there is.
 *
 * Not simply "the first filled chip", because first is catalog order and
 * catalog order is a position's: a receiver's chips run Rushing before
 * Receiving, and Rush+Rec TDs sits in the Rushing group, so one receiving
 * touchdown would open a tight end on the Rushing tab. Measured 2026-09-19:
 * 82 of 252 wide receivers and 75 of 146 tight ends with a game since 2025
 * hold their Rushing tab on that chip alone, every other chip in it flat zero.
 * Weighing the whole group settles it on one game as well as on twenty-five.
 */
export function openingChip(
  chips: StatDef[],
  filled: Map<string, number>,
  group?: StatGroup | null,
): StatDef | null {
  const inGroup = group ? chips.filter((c) => c.group === group) : chips;
  if (inGroup.length === 0) return null;
  const weight = new Map<StatGroup, number>();
  for (const c of inGroup) {
    weight.set(c.group, (weight.get(c.group) ?? 0) + (filled.get(chipKey(c)) ?? 0));
  }
  let best: StatDef | null = null;
  let bestScore = 0;
  let bestGroupWeight = 0;
  for (const c of inGroup) {
    const n = filled.get(chipKey(c)) ?? 0;
    if (n === 0) continue;
    const w = weight.get(c.group) ?? 0;
    if (w > bestGroupWeight || (w === bestGroupWeight && n > bestScore)) {
      best = c;
      bestScore = n;
      bestGroupWeight = w;
    }
  }
  return best ?? inGroup[0] ?? null;
}

// ── Line stepper ────────────────────────────────────────────────────────────

/**
 * How much one tap of the +/- stepper moves the line. Counting stats step by
 * one; yardage steps in the increments books actually hang lines at, so
 * walking a passing-yards line from 225 to 250 is one tap, not twenty-five.
 */
export function lineStepFor(def: StatDef | null): number {
  const base = def?.defaultLine ?? 0.5;
  if (base >= 100) return 25;
  if (base >= 40) return 5;
  return 1;
}

/** Snaps the auto-picked line (the median) onto the stepper's grid, never below one step. */
export function roundLineToStep(median: number, step: number): number {
  return Math.max(step, Math.round(median / step) * step);
}

// ── Reading a stat off a row ────────────────────────────────────────────────

/**
 * A game's value for a stat, or null when the log has no value for it. Numbers
 * arriving as strings (Postgres NUMERIC — NFL yardage, sacks) are coerced, the
 * same as the leaderboard does via statValue.
 */
export function logStatValue(row: PlayerLogEntry, def: StatDef | null): number | null {
  if (!def) return null;
  const raw = row[def.key as string];
  if (raw == null) return null;
  return statValue(row, def);
}

// ── Windows ─────────────────────────────────────────────────────────────────

/** 'all' = every game loaded (see logFetchLimit), shown with its own count. */
export type GameWindow = number | 'all';

export interface WindowOption {
  value: GameWindow;
  label: string;
}

/**
 * Deliberately NOT labelled "Season": the screen loads a player's last N games,
 * which for a mid-season MLB or NBA player is less than a season and for an NFL
 * player spans more than one. "All" plus the game count states what it is.
 */
export function windowOptionsFor(sport: PlayerLogSport): WindowOption[] {
  const spans = FOOTBALL.has(sport) ? [3, 5, 10] : [5, 10, 20];
  return [...spans.map((n) => ({ value: n as GameWindow, label: `L${n}` })), { value: 'all' as GameWindow, label: 'All' }];
}

// ── Display helpers ─────────────────────────────────────────────────────────

/** The line under the player's name: team, plus position where a sport has one. */
export function playerSubtitle(
  sport: PlayerLogSport,
  team: string | null,
  row: PlayerLogEntry | undefined,
  playerType?: PlayerType | null,
): string {
  const parts: string[] = [team ?? '—'];
  if (sport === 'MLB') parts.push(playerType === 'pitcher' ? 'Pitcher' : 'Batter');
  else if (sport === 'NFL' && row?.pos) parts.push(String(row.pos));
  return parts.join(' · ');
}

/**
 * The context line under a recent-game date — the volume behind the stat, which
 * is what tells you whether a quiet game was a bad game or a short one.
 */
export function gameContextLine(sport: PlayerLogSport, row: PlayerLogEntry): string {
  const team = row.team ?? '—';
  if (FOOTBALL.has(sport)) {
    const opp = row.opponent ? `vs ${row.opponent}` : null;
    const wk = row.week != null ? `Wk ${row.week}` : null;
    return [team, opp, wk].filter(Boolean).join(' · ');
  }
  if (sport === 'WNBA' || sport === 'NBA') {
    const min = num(row.minutes);
    return `${team} · ${min == null ? '—' : min.toFixed(0)} min`;
  }
  const isPitcher = row.player_type === 'pitcher';
  const vol = isPitcher ? `${row.innings_pitched ?? '—'} IP` : `${row.at_bats ?? '—'} AB`;
  return `${team} · ${vol}`;
}

/**
 * The stat a prop pick's player detail should open on, with the same
 * Innings→Outs swap the chip list makes (see chipsForPlayer).
 */
export function detailStatForPropModel(modelId: string): StatDef | null {
  const def = statForPropModel(modelId);
  if (!def) return null;
  return def.key === 'innings_pitched' ? OUTS_STAT : def;
}
