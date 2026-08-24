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
export type PlayerLogSport = 'MLB' | 'WNBA' | 'NBA' | 'NFL';

const LOG_SPORTS = new Set<Sport>(['MLB', 'WNBA', 'NBA', 'NFL']);

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
  /** NFL only. */
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

export const LOG_TABLE: Record<PlayerLogSport, string> = {
  MLB: 'player_game_log',
  WNBA: 'wnba_player_game_log',
  NBA: 'nba_player_game_log',
  NFL: 'nfl_player_game_log',
};

export const LOG_COLUMNS: Record<PlayerLogSport, string> = {
  MLB: MLB_COLUMNS,
  WNBA: BASKETBALL_COLUMNS,
  NBA: BASKETBALL_COLUMNS,
  NFL: NFL_COLUMNS,
};

/**
 * How many games back to load. MLB and basketball play near-daily, so 50 rows
 * is a few months; NFL plays weekly, so 25 rows is already a season and a half
 * and anything more would stretch the "recent form" read past usefulness.
 */
export function logFetchLimit(sport: PlayerLogSport): number {
  return sport === 'NFL' ? 25 : 50;
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
  } else if (sport === 'NFL') {
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

/** Ordered stat groups present in a sport's chip set (NFL is the only multi-group one). */
export function chipGroupsFor(sport: PlayerLogSport, playerType?: PlayerType | null): StatGroup[] {
  const seen: StatGroup[] = [];
  for (const c of chipsForPlayer(sport, playerType)) {
    if (!seen.includes(c.group)) seen.push(c.group);
  }
  return seen;
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
  const spans = sport === 'NFL' ? [3, 5, 10] : [5, 10, 20];
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
  if (sport === 'NFL') {
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
