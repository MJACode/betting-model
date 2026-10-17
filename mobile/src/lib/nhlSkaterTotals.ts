/**
 * NHL skater leaderboard rows, summed on the phone from `nhl_skater_stats`.
 *
 * There is no season-totals view and no window RPC the app may call: those
 * are the unapplied game-log grants (#962). The table is one row per skater
 * per game (measured 2026-10-16: columns goals, assists, points,
 * shots_on_goal; 0 rows). The board still wants one row per player, so this
 * is the sum the other sports' `player_window_totals_*` functions do in SQL.
 *
 * A team filter is applied AFTER the window, on the player's newest team.
 * Filtering the per-game read by team would drop a traded player's games for
 * the other club and keep someone who has already left tonight's team.
 */
import type { SeasonTotalsRow } from '@/types';

/** One game from nhl_skater_stats. Integers can arrive as strings. */
export interface NhlSkaterGame {
  player_id: string | null;
  player_name: string | null;
  team: string | null;
  position?: string | null;
  season: number;
  game_date: string;
  game_id: string | null;
  goals: number | string | null;
  assists: number | string | null;
  points: number | string | null;
  shots_on_goal: number | string | null;
}

/**
 * Season labels to try, newest first.
 *
 * NHL labels a season by the year it ENDS (CLAUDE.md §4). The Stats screen
 * passes the calendar year. In October 2026 that is 2026, and the season in
 * progress is 2027, so the ending year is tried first and the calendar year
 * is the fallback (last season, and the right label from January on).
 */
export function nhlSeasonCandidates(calendarYear: number): number[] {
  return [calendarYear + 1, calendarYear];
}

function num(v: number | string | null | undefined): number {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string') {
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

function playerKey(g: NhlSkaterGame): string {
  const id = (g.player_id ?? '').trim();
  if (id) return id;
  const name = (g.player_name ?? '').trim();
  return name ? `name:${name.toLowerCase()}` : '';
}

/** Newest game first. Date is ISO, so a string compare is the order. */
function newerFirst(a: NhlSkaterGame, b: NhlSkaterGame): number {
  if (a.game_date !== b.game_date) return a.game_date < b.game_date ? 1 : -1;
  const ag = a.game_id ?? '';
  const bg = b.game_id ?? '';
  if (ag === bg) return 0;
  return ag < bg ? 1 : -1;
}

/**
 * One SeasonTotalsRow per skater: the sum of his last `window` games, or of
 * the whole season when `window` is null. `teams` keeps skaters whose newest
 * game in that window was for one of those teams.
 */
export function aggregateNhlSkaterTotals(
  games: readonly NhlSkaterGame[],
  season: number,
  window: number | null,
  teams?: readonly string[] | null,
): SeasonTotalsRow[] {
  const byPlayer = new Map<string, NhlSkaterGame[]>();
  for (const g of games) {
    const key = playerKey(g);
    if (!key) continue;
    const list = byPlayer.get(key);
    if (list) list.push(g);
    else byPlayer.set(key, [g]);
  }
  const teamSet = teams && teams.length > 0 ? new Set(teams) : null;
  const out: SeasonTotalsRow[] = [];
  for (const [key, list] of byPlayer) {
    const ordered = [...list].sort(newerFirst);
    const windowed = window == null ? ordered : ordered.slice(0, Math.max(0, window));
    if (windowed.length === 0) continue;
    const latest = windowed[0]!;
    const team = latest.team ?? null;
    if (teamSet && (team == null || !teamSet.has(team))) continue;
    const id = (latest.player_id ?? '').trim();
    out.push({
      player_id: id || key,
      player_name: (latest.player_name ?? '').trim(),
      team,
      season,
      games_played: windowed.length,
      pos: latest.position ?? null,
      goals: windowed.reduce((s, g) => s + num(g.goals), 0),
      assists: windowed.reduce((s, g) => s + num(g.assists), 0),
      points: windowed.reduce((s, g) => s + num(g.points), 0),
      shots_on_goal: windowed.reduce((s, g) => s + num(g.shots_on_goal), 0),
    });
  }
  out.sort((a, b) => a.player_id.localeCompare(b.player_id));
  return out;
}
