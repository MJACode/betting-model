/**
 * The Betting tab's filters: period, games window and side (Matt, 2026-11-13,
 * from the EVAnalytics layout he uses: "pick what you want to see by
 * quarter/half/full game, then filter full season / last 10/5/3, also
 * home-away").
 *
 * The rows come from `team_period_results`, one per team, game and period,
 * written by the worker (data/ingestors/team_period_results.py). Each row
 * carries the line the period was graded against (DraftKings' last pre-tip
 * number, else the median of the other books) and its ATS and over/under
 * result, plus both teams' rest days. This file counts them; it never grades.
 *
 * THE WINDOW. "Last N" is the team's last N games WITH A LINE for that
 * market, after the side filter: Last 5 + Home is the last five home games
 * that had a spread (for ATS) or a total (for O/U). A game whose period had no
 * line yet cannot count toward an ATS record, and counting it would make
 * "Last 5" print 3 results. Last N reaches back into last season early on, as
 * every NBA last-N read does (Matt, 2026-10-23). "Season" is this season only.
 *
 * Percentages are wins over decided games (w / (w + l)), pushes left out,
 * the same formula team_stats_board_compute uses, so Full + Season + Both
 * prints the same ATS% the board printed before.
 *
 * Pure: verified offline by `npx tsx scripts/verify_team_period_splits.ts`.
 */
import type { Sport } from '@/hooks/useSportFilter';
import type { TeamStatsRow } from '@/types';
import type { TeamStatDef } from '@/lib/teamStatCatalog';

export type PeriodKey = 'FG' | 'H1' | 'Q1' | 'Q2' | 'Q3' | 'Q4';
export type GamesWindow = 'season' | 10 | 5 | 3;
export type SideFilter = 'both' | 'home' | 'away';

export interface PeriodFilter {
  period: PeriodKey;
  games: GamesWindow;
  side: SideFilter;
}

export const DEFAULT_PERIOD_FILTER: PeriodFilter = { period: 'FG', games: 'season', side: 'both' };

export const PERIOD_OPTIONS: { key: PeriodKey; label: string; spoken: string }[] = [
  { key: 'FG', label: 'Full', spoken: 'Full game' },
  { key: 'H1', label: '1H', spoken: 'First half' },
  { key: 'Q1', label: '1Q', spoken: 'First quarter' },
  { key: 'Q2', label: '2Q', spoken: 'Second quarter' },
  { key: 'Q3', label: '3Q', spoken: 'Third quarter' },
  { key: 'Q4', label: '4Q', spoken: 'Fourth quarter' },
];

export const GAMES_OPTIONS: { key: GamesWindow; label: string; spoken: string }[] = [
  { key: 'season', label: 'Season', spoken: 'Full season' },
  { key: 10, label: 'Last 10', spoken: 'Last 10 games' },
  { key: 5, label: 'Last 5', spoken: 'Last 5 games' },
  { key: 3, label: 'Last 3', spoken: 'Last 3 games' },
];

export const SIDE_OPTIONS: { key: SideFilter; label: string; spoken: string }[] = [
  { key: 'both', label: 'Both', spoken: 'Home and away' },
  { key: 'home', label: 'Home', spoken: 'Home games' },
  { key: 'away', label: 'Away', spoken: 'Away games' },
];

/** Sports whose Betting tab has the filters. NCAAB (halves) is next (Matt, 2026-11-13). */
const PERIOD_SPORTS = new Set<Sport>(['NBA']);
export function supportsPeriodFilters(sport: Sport): boolean {
  return PERIOD_SPORTS.has(sport);
}

/** Stats the Side filter replaces on a sport that has it: one Home/Away split
 *  per stat was the old way to ask the same question. */
export const SIDE_REPLACED_KEYS = new Set<string>(['ats_home_pct', 'ats_away_pct']);

/** One row of `team_period_results`, the columns the board reads. */
export interface TeamPeriodRow {
  team: string;
  season: number;
  game_id: string;
  game_date: string;
  is_home: boolean;
  spread: number | string | null;
  total_line: number | string | null;
  ats: 'W' | 'L' | 'P' | null;
  ou: 'O' | 'U' | 'P' | null;
  rest_days: number | null;
  opp_rest_days: number | null;
}

/** The record columns this file adds to a board row, for the splits whose
 *  record the season board never returned. */
export interface PeriodRecordCols {
  fav_w: number; fav_l: number; fav_p: number;
  dog_w: number; dog_l: number; dog_p: number;
  ra_w: number; ra_l: number; ra_p: number;
  sr_w: number; sr_l: number; sr_p: number;
}
export type PeriodBoardRow = TeamStatsRow & PeriodRecordCols;

/** Record + sample keys per Betting stat, so every one prints "W-L-P · %". */
const RECORD_KEYS: Record<string, { w: string; l: string; p: string }> = {
  ats_pct: { w: 'ats_w', l: 'ats_l', p: 'ats_p' },
  over_pct: { w: 'ou_o', l: 'ou_u', p: 'ou_p' },
  fav_ats_pct: { w: 'fav_w', l: 'fav_l', p: 'fav_p' },
  dog_ats_pct: { w: 'dog_w', l: 'dog_l', p: 'dog_p' },
  rest_adv_ats_pct: { w: 'ra_w', l: 'ra_l', p: 'ra_p' },
  short_rest_ats_pct: { w: 'sr_w', l: 'sr_l', p: 'sr_p' },
};

/** The stat as the filtered board reads it: its record and sample point at the
 *  columns `applyPeriodSplits` fills. Stats without one are returned unchanged.
 *
 *  The small-sample rule (under 10 games: untinted, ranked below, marked) is a
 *  SEASON rule. Under Last 10/5/3 the member chose the window, every row would
 *  carry the mark and none would be coloured (UX review, 2026-11-13), so the
 *  def drops its sample there and the board ranks and colours the window as is. */
export function periodStatDef(def: TeamStatDef, f: PeriodFilter = DEFAULT_PERIOD_FILTER): TeamStatDef {
  const k = RECORD_KEYS[String(def.key)];
  if (!k) return def;
  const w = k.w as keyof TeamStatsRow;
  const l = k.l as keyof TeamStatsRow;
  const p = k.p as keyof TeamStatsRow;
  return { ...def, record: { w, l, p }, sample: f.games === 'season' ? [w, l, p] : undefined };
}

function num(v: number | string | null): number | null {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

function pct(w: number, l: number): number | null {
  return w + l > 0 ? Math.round((w / (w + l)) * 1000) / 1000 : null;
}

/** Newest first, the order "last N" reads. */
function newestFirst(a: TeamPeriodRow, b: TeamPeriodRow): number {
  if (a.game_date !== b.game_date) return a.game_date < b.game_date ? 1 : -1;
  return a.game_id < b.game_id ? 1 : a.game_id > b.game_id ? -1 : 0;
}

/** The games one team's record counts, for one market, under the filter. */
export function windowGames(
  rows: TeamPeriodRow[],
  f: PeriodFilter,
  season: number,
  market: 'ats' | 'ou',
): TeamPeriodRow[] {
  const graded = rows
    .filter((r) => (f.side === 'both' ? true : f.side === 'home' ? r.is_home : !r.is_home))
    .filter((r) => (market === 'ats' ? r.ats != null : r.ou != null))
    .filter((r) => (f.games === 'season' ? r.season === season : r.season <= season))
    .sort(newestFirst);
  return f.games === 'season' ? graded : graded.slice(0, f.games);
}

function tally(rows: TeamPeriodRow[]): { w: number; l: number; p: number } {
  let w = 0, l = 0, p = 0;
  for (const r of rows) {
    if (r.ats === 'W') w++;
    else if (r.ats === 'L') l++;
    else if (r.ats === 'P') p++;
  }
  return { w, l, p };
}

/**
 * The board's rows with every Betting number recounted under the filter.
 * Efficiency and Record columns pass through untouched. A team with no period
 * rows gets zero records and no percentages ("—"), never last season's.
 * NBA short rest is the second night of a back-to-back (rest_days <= 1), the
 * board's own rule; a rest edge is more days off than the opponent.
 */
export function applyPeriodSplits(
  board: TeamStatsRow[],
  periodRows: TeamPeriodRow[],
  f: PeriodFilter,
  season: number,
): PeriodBoardRow[] {
  const byTeam = new Map<string, TeamPeriodRow[]>();
  for (const r of periodRows) {
    const list = byTeam.get(r.team);
    if (list) list.push(r);
    else byTeam.set(r.team, [r]);
  }
  return board.map((row) => {
    const mine = byTeam.get(row.team) ?? [];
    const ats = windowGames(mine, f, season, 'ats');
    const ou = windowGames(mine, f, season, 'ou');
    const a = tally(ats);
    let o = 0, u = 0, op = 0;
    for (const r of ou) {
      if (r.ou === 'O') o++;
      else if (r.ou === 'U') u++;
      else if (r.ou === 'P') op++;
    }
    const fav = tally(ats.filter((r) => (num(r.spread) ?? 0) < 0));
    const dog = tally(ats.filter((r) => (num(r.spread) ?? 0) > 0));
    const ra = tally(ats.filter((r) => r.rest_days != null && r.opp_rest_days != null && r.rest_days > r.opp_rest_days));
    const sr = tally(ats.filter((r) => r.rest_days != null && r.rest_days <= 1));
    return {
      ...row,
      ats_w: a.w, ats_l: a.l, ats_p: a.p, ats_pct: pct(a.w, a.l),
      ou_o: o, ou_u: u, ou_p: op, over_pct: pct(o, u),
      fav_w: fav.w, fav_l: fav.l, fav_p: fav.p, fav_ats_pct: pct(fav.w, fav.l),
      dog_w: dog.w, dog_l: dog.l, dog_p: dog.p, dog_ats_pct: pct(dog.w, dog.l),
      ra_w: ra.w, ra_l: ra.l, ra_p: ra.p, rest_adv_ats_pct: pct(ra.w, ra.l),
      rest_adv_games: ra.w + ra.l + ra.p,
      sr_w: sr.w, sr_l: sr.l, sr_p: sr.p, short_rest_ats_pct: pct(sr.w, sr.l),
      short_rest_games: sr.w + sr.l + sr.p,
    };
  });
}

/** "Full · Season · Both" in words, for the column header and VoiceOver. */
export function periodFilterSpoken(f: PeriodFilter): string {
  const p = PERIOD_OPTIONS.find((o) => o.key === f.period)?.spoken ?? '';
  const g = GAMES_OPTIONS.find((o) => o.key === f.games)?.spoken ?? '';
  const s = SIDE_OPTIONS.find((o) => o.key === f.side)?.spoken ?? '';
  return `${p}, ${g.toLowerCase()}, ${s.toLowerCase()}`;
}

/** Short header label: "1Q · L5 · Home"; the defaults are left out. */
export function periodFilterShort(f: PeriodFilter): string {
  const parts: string[] = [];
  if (f.period !== 'FG') parts.push(PERIOD_OPTIONS.find((o) => o.key === f.period)?.label ?? '');
  if (f.games !== 'season') parts.push(`L${f.games}`);
  if (f.side !== 'both') parts.push(f.side === 'home' ? 'Home' : 'Away');
  return parts.join(' · ');
}

/** True when the filter is the board's own season view. */
export function isDefaultPeriodFilter(f: PeriodFilter): boolean {
  return f.period === 'FG' && f.games === 'season' && f.side === 'both';
}
