/**
 * What the Stats tab's Teams board shows, per sport.
 *
 * Three groups, in this order, and the order is the point:
 *
 *  1. EFFICIENCY — opponent/pace/park-adjusted process metrics. These are what
 *     the sharp-betting literature actually rates: pace-adjusted ratings in
 *     basketball, EPA and success rate in football, Corsi in hockey, wRC+ and
 *     bullpen ERA in baseball. They lead the board.
 *
 *  2. RECORD — plain win/loss and scoring. Context, not signal.
 *
 *  3. BETTING — ATS, over/under, favorite/dog, home/away and rest splits.
 *     Every competitor ships these and users come looking for them, but the
 *     same literature is blunt that they are DESCRIPTIVE, not predictive: a
 *     team's ATS record regresses to ~.500 as soon as the market prices the
 *     trend in. They are last, and the board states that in one line rather
 *     than presenting them as an edge.
 *
 * Deliberately NOT here:
 *  - NHL expected-goals share (xGF%). The free NHL API does not expose it and
 *    our column is 0% populated, so it would be a column of dashes.
 *  - NFL DVOA / PFF grades. Proprietary and licensed; EPA per play is the
 *    standard free substitute, but that needs play-by-play we do not ingest
 *    for the NFL, so NFL efficiency is yards-per-play based and says so.
 *  - MLB rest splits. Baseball plays daily, so a rest-day cut is noise.
 */
import type { Sport } from '@/hooks/useSportFilter';
import type { TeamStatsRow } from '@/types';

export type TeamStatGroup = 'Efficiency' | 'Record' | 'Betting';

export const TEAM_GROUP_ORDER: TeamStatGroup[] = ['Efficiency', 'Record', 'Betting'];

/** How a value is rendered. `pct3` is a 0..1 rate shown as a percentage. */
export type TeamStatFormat = 'int' | 'dec1' | 'dec2' | 'dec3' | 'pct3';

export interface TeamStatDef {
  key: keyof TeamStatsRow;
  label: string;
  group: TeamStatGroup;
  /** Sports that show this stat. */
  sports: Sport[];
  format: TeamStatFormat;
  /**
   * Which end of the league is good, for the rank tint. `null` means neither
   * (pace is a style, not a virtue) — those render uncoloured.
   */
  better: 'high' | 'low' | null;
  /**
   * Companion win/loss columns, rendered under the value as "67-42".
   * Present on the betting splits so a 60% ATS mark can't hide a 3-2 sample.
   */
  record?: { w: keyof TeamStatsRow; l: keyof TeamStatsRow; p?: keyof TeamStatsRow };
  /** Sample-size column, so a split built on 4 games reads as one. */
  sample?: keyof TeamStatsRow;
  hint?: string;
}

const BALL: Sport[] = ['MLB', 'NBA', 'WNBA', 'NHL', 'NFL', 'NCAAF'];
const HOOPS: Sport[] = ['NBA', 'WNBA'];
/** Sports where a rest-day split is meaningful (MLB plays daily). */
const RESTFUL: Sport[] = ['NBA', 'WNBA', 'NHL', 'NFL', 'NCAAF'];

export const TEAM_STAT_CATALOG: TeamStatDef[] = [
  // ── Efficiency ──────────────────────────────────────────────────────────
  // MLB
  { key: 'wrc_plus', label: 'wRC+', group: 'Efficiency', sports: ['MLB'], format: 'int', better: 'high',
    hint: 'Park- and league-adjusted offense. 100 is average.' },
  { key: 'ops', label: 'OPS', group: 'Efficiency', sports: ['MLB'], format: 'dec3', better: 'high' },
  { key: 'team_era', label: 'Team ERA', group: 'Efficiency', sports: ['MLB'], format: 'dec2', better: 'low' },
  { key: 'bullpen_era', label: 'Bullpen ERA', group: 'Efficiency', sports: ['MLB'], format: 'dec2', better: 'low',
    hint: 'Relief corps only — the half of the staff the market prices least efficiently.' },
  { key: 'team_whip', label: 'WHIP', group: 'Efficiency', sports: ['MLB'], format: 'dec2', better: 'low' },
  // Basketball
  { key: 'net_rating', label: 'Net Rtg', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'high',
    hint: 'Points scored minus allowed per 100 possessions — pace-adjusted margin.' },
  { key: 'off_rating', label: 'Off Rtg', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'high' },
  { key: 'def_rating', label: 'Def Rtg', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'low' },
  { key: 'pace', label: 'Pace', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: null,
    hint: 'Possessions per game. Context for totals — fast is not better, just different.' },
  { key: 'efg_pct', label: 'eFG%', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'high' },
  { key: 'tov_pct', label: 'TOV%', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'low' },
  // NHL
  { key: 'corsi_for_pct', label: 'Corsi%', group: 'Efficiency', sports: ['NHL'], format: 'dec1', better: 'high',
    hint: 'Share of shot attempts. Holds up better than goal differential, which is dominated by shooting and save luck.' },
  { key: 'pp_pct', label: 'PP%', group: 'Efficiency', sports: ['NHL'], format: 'dec1', better: 'high' },
  { key: 'pk_pct', label: 'PK%', group: 'Efficiency', sports: ['NHL'], format: 'dec1', better: 'high' },
  // College football
  { key: 'sp_overall', label: 'SP+', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'high',
    hint: "Bill Connelly's opponent-adjusted rating — the standard public CFB power number." },
  { key: 'epa_off', label: 'EPA/play Off', group: 'Efficiency', sports: ['NCAAF'], format: 'dec3', better: 'high' },
  { key: 'epa_def', label: 'EPA/play Def', group: 'Efficiency', sports: ['NCAAF'], format: 'dec3', better: 'low' },
  { key: 'success_off', label: 'Success% Off', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'high' },
  { key: 'success_def', label: 'Success% Def', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'low' },
  { key: 'explosiveness_off', label: 'Explosiveness', group: 'Efficiency', sports: ['NCAAF'], format: 'dec2', better: 'high' },
  { key: 'havoc_rate', label: 'Havoc%', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'high',
    hint: 'Share of plays with a TFL, forced fumble, interception or pass breakup.' },
  // NFL — yards-based, because we do not ingest NFL play-by-play for EPA.
  { key: 'yards_per_play', label: 'Yards/Play', group: 'Efficiency', sports: ['NFL'], format: 'dec2', better: 'high' },
  { key: 'pass_yards_pg', label: 'Pass Yds/G', group: 'Efficiency', sports: ['NFL'], format: 'dec1', better: 'high' },
  { key: 'rush_yards_pg', label: 'Rush Yds/G', group: 'Efficiency', sports: ['NFL'], format: 'dec1', better: 'high' },
  // Every sport
  { key: 'point_diff_pg', label: 'Margin/G', group: 'Efficiency', sports: BALL, format: 'dec2', better: 'high' },
  { key: 'points_for_pg', label: 'Scored/G', group: 'Efficiency', sports: BALL, format: 'dec2', better: 'high' },
  { key: 'points_against_pg', label: 'Allowed/G', group: 'Efficiency', sports: BALL, format: 'dec2', better: 'low' },

  // ── Record ──────────────────────────────────────────────────────────────
  { key: 'win_pct', label: 'Win%', group: 'Record', sports: BALL, format: 'pct3', better: 'high',
    record: { w: 'wins', l: 'losses' } },
  { key: 'games_played', label: 'Games', group: 'Record', sports: BALL, format: 'int', better: null },

  // ── Betting ─────────────────────────────────────────────────────────────
  { key: 'ats_pct', label: 'ATS%', group: 'Betting', sports: BALL, format: 'pct3', better: 'high',
    record: { w: 'ats_w', l: 'ats_l', p: 'ats_p' },
    hint: 'Against the spread. Descriptive only — ATS records regress to about .500 once the market prices a trend in.' },
  { key: 'over_pct', label: 'Over%', group: 'Betting', sports: BALL, format: 'pct3', better: null,
    record: { w: 'ou_o', l: 'ou_u', p: 'ou_p' },
    hint: 'How often the total went over. Neither direction is "good" — it is a tendency, not a grade.' },
  { key: 'ats_home_pct', label: 'ATS% Home', group: 'Betting', sports: BALL, format: 'pct3', better: 'high' },
  { key: 'ats_away_pct', label: 'ATS% Away', group: 'Betting', sports: BALL, format: 'pct3', better: 'high' },
  { key: 'fav_ats_pct', label: 'ATS% as Fav', group: 'Betting', sports: BALL, format: 'pct3', better: 'high' },
  { key: 'dog_ats_pct', label: 'ATS% as Dog', group: 'Betting', sports: BALL, format: 'pct3', better: 'high' },
  { key: 'rest_adv_ats_pct', label: 'ATS% Rest Edge', group: 'Betting', sports: RESTFUL, format: 'pct3', better: 'high',
    sample: 'rest_adv_games',
    hint: 'Games where this team had more days off than the opponent. Rest is one of the few situational splits with a documented, repeatable effect.' },
  { key: 'short_rest_ats_pct', label: 'ATS% Short Rest', group: 'Betting', sports: RESTFUL, format: 'pct3', better: 'high',
    sample: 'short_rest_games',
    hint: 'Back-to-backs in the nightly leagues, short weeks in football.' },
];

/** Team stats this sport shows, in catalog order. */
export function teamStatsForSport(sport: Sport): TeamStatDef[] {
  return TEAM_STAT_CATALOG.filter((s) => s.sports.includes(sport));
}

/** Groups that actually have a stat for this sport (so no empty tabs render). */
export function teamGroupsForSport(sport: Sport): TeamStatGroup[] {
  const present = new Set(teamStatsForSport(sport).map((s) => s.group));
  return TEAM_GROUP_ORDER.filter((g) => present.has(g));
}

/**
 * The sport's default team stat — the most useful single number to open on.
 * Efficiency-first by design: the board should not greet you with an ATS record.
 */
export function defaultTeamStatFor(sport: Sport): TeamStatDef | null {
  const wantKey: Partial<Record<Sport, keyof TeamStatsRow>> = {
    MLB: 'wrc_plus',
    NBA: 'net_rating',
    WNBA: 'net_rating',
    NHL: 'corsi_for_pct',
    NFL: 'yards_per_play',
    NCAAF: 'sp_overall',
  };
  const list = teamStatsForSport(sport);
  const key = wantKey[sport];
  return list.find((s) => s.key === key) ?? list[0] ?? null;
}

/** Sports with a team board at all (golf and UFC have no teams). */
const TEAM_SPORTS = new Set<Sport>(BALL);
export function supportsTeamBoard(sport: Sport): boolean {
  return TEAM_SPORTS.has(sport);
}

/** Numeric value for a team row under a stat, or null when absent. */
export function teamStatValue(row: TeamStatsRow, def: TeamStatDef): number | null {
  const v = row[def.key];
  if (typeof v === 'number') return v;
  // Postgres NUMERIC can arrive as a string over PostgREST.
  if (typeof v === 'string') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function formatTeamStat(value: number | null, format: TeamStatFormat): string {
  if (value == null) return '—';
  switch (format) {
    case 'int': return String(Math.round(value));
    case 'dec1': return value.toFixed(1);
    case 'dec2': return value.toFixed(2);
    case 'dec3': return value.toFixed(3);
    case 'pct3': return `${(value * 100).toFixed(1)}%`;
  }
}

/** "67-42" or "67-42-3" when the split can push. */
export function formatRecord(row: TeamStatsRow, def: TeamStatDef): string | null {
  if (!def.record) return null;
  const w = teamStatValue(row, { ...def, key: def.record.w });
  const l = teamStatValue(row, { ...def, key: def.record.l });
  if (w == null || l == null) return null;
  const p = def.record.p ? teamStatValue(row, { ...def, key: def.record.p }) : null;
  return p != null && p > 0 ? `${w}-${l}-${p}` : `${w}-${l}`;
}
