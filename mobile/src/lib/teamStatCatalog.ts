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
 *  - NFL DVOA / PFF grades. Proprietary and licensed. Points added per play is
 *    the free substitute; the NFL rows are in the catalog and stay hidden
 *    until a play-by-play ingest writes them. NFL still opens on yards/play.
 *  - MLB rest splits. Baseball plays daily, so a rest-day cut is noise.
 */
import type { Sport } from '@/hooks/useSportFilter';
import type { TeamStatsRow } from '@/types';

export type TeamStatGroup = 'Efficiency' | 'Record' | 'Betting';

export const TEAM_GROUP_ORDER: TeamStatGroup[] = ['Efficiency', 'Record', 'Betting'];

/**
 * `pct3` is a 0..1 rate shown as a percentage (success rate lives here —
 * measured 2026-10-06, NCAAF 2026 success_off is 0.34–0.52, not 34–52).
 * `dec2` is two decimals, minus only. Round first, so a value that rounds to
 * zero is `0.00` and never `−0.00`. A leading `+` is not used: these numbers
 * are not centred on 0, so a plus would read as "above average".
 * `fixed2` is `toFixed(2)`, ASCII hyphen included. ERA, margin, yards per play
 * and the other counting stats stay on it, so their glyphs do not change.
 */
export type TeamStatFormat = 'int' | 'dec1' | 'fixed2' | 'dec2' | 'dec3' | 'pct3';

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
  /** Short column header ("Pts added/play"). The chip uses `label`. */
  header?: string;
  /** Full words for VoiceOver ("Points added per play, offense"). */
  spoken?: string;
  /** Info sheet behind the ⓘ next to the label. */
  explain?: StatExplain;
  /** Which way is good, in words, under the chips. */
  direction?: string;
  /**
   * Hide the chip (and the matchup row that shares it) until at least one
   * team has a real value. NFL points-added and successful-plays are catalogued
   * so the row support exists, and stay hidden while the play-by-play ingest
   * has written nothing — a column of dashes would look like a measured zero.
   */
  untilData?: boolean;
}

/** The ⓘ sheet shared by the Teams board and the Matchup card. */
export interface StatExplain {
  /** The line next to the button ("Points added per play · offense"). */
  name: string;
  title: string;
  body: string;
  /** Accessibility label on the button. */
  a11y: string;
}

export const EXPLAIN_PTS_ADDED: StatExplain = {
  name: 'Points added per play',
  title: 'Points added per play',
  body:
    'How much each play helps a team score, compared with an average play in the same down, distance and field position. Higher means more points per play. Compare teams by rank. For a defense, lower is better.',
  a11y: 'About points added per play',
};

export const EXPLAIN_SUCCESS: StatExplain = {
  name: 'Successful plays',
  title: 'Successful plays',
  body:
    'The share of plays that gain 50% of the yards to go on 1st down, 70% on 2nd, and 100% on 3rd or 4th. Higher is better for an offense. For a defense, lower is better.',
  a11y: 'About successful plays',
};

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
  { key: 'team_era', label: 'Team ERA', group: 'Efficiency', sports: ['MLB'], format: 'fixed2', better: 'low' },
  { key: 'bullpen_era', label: 'Bullpen ERA', group: 'Efficiency', sports: ['MLB'], format: 'fixed2', better: 'low',
    hint: 'Relief corps only — the half of the staff the market prices least efficiently.' },
  { key: 'team_whip', label: 'WHIP', group: 'Efficiency', sports: ['MLB'], format: 'fixed2', better: 'low' },
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
  // Points added and successful plays. NCAAF is populated from CFBD; NFL is
  // listed so the same rows exist, and `untilData` hides them while every
  // value is null (no NFL play-by-play ingest yet — measured 2026-10-06,
  // team_stats_board_cache NFL 2025 and 2026: epa_off and success_off are 0
  // of 32). Never a fake 0.
  { key: 'epa_off', label: 'Pts added/play Off', header: 'Pts added/play', group: 'Efficiency', sports: ['NCAAF', 'NFL'], format: 'dec2', better: 'high',
    spoken: 'Points added per play, offense',
    explain: { ...EXPLAIN_PTS_ADDED, name: 'Points added per play · offense' },
    direction: 'Higher is better. Rank 1 = best offense.',
    untilData: true },
  { key: 'epa_def', label: 'Pts added/play Def', header: 'Pts added/play', group: 'Efficiency', sports: ['NCAAF', 'NFL'], format: 'dec2', better: 'low',
    spoken: 'Points added per play, defense',
    explain: { ...EXPLAIN_PTS_ADDED, name: 'Points added per play · defense' },
    direction: 'Lower is better. Rank 1 = best defense (allows the least).',
    untilData: true },
  { key: 'success_off', label: 'Successful plays Off', header: 'Successful plays', group: 'Efficiency', sports: ['NCAAF', 'NFL'], format: 'pct3', better: 'high',
    spoken: 'Successful plays, offense',
    explain: { ...EXPLAIN_SUCCESS, name: 'Successful plays · offense' },
    direction: 'Higher is better. Rank 1 = best offense.',
    untilData: true },
  { key: 'success_def', label: 'Successful plays Def', header: 'Successful plays', group: 'Efficiency', sports: ['NCAAF', 'NFL'], format: 'pct3', better: 'low',
    spoken: 'Successful plays, defense',
    explain: { ...EXPLAIN_SUCCESS, name: 'Successful plays · defense' },
    direction: 'Lower is better. Rank 1 = best defense (allows the fewest).',
    untilData: true },
  { key: 'explosiveness_off', label: 'Explosiveness', group: 'Efficiency', sports: ['NCAAF'], format: 'fixed2', better: 'high' },
  { key: 'havoc_rate', label: 'Havoc%', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'high',
    hint: 'Share of plays with a TFL, forced fumble, interception or pass breakup.' },
  // NFL counting stats. Points added per play is above, hidden until data exists.
  { key: 'yards_per_play', label: 'Yards/Play', group: 'Efficiency', sports: ['NFL'], format: 'fixed2', better: 'high' },
  { key: 'pass_yards_pg', label: 'Pass Yds/G', group: 'Efficiency', sports: ['NFL'], format: 'dec1', better: 'high' },
  { key: 'rush_yards_pg', label: 'Rush Yds/G', group: 'Efficiency', sports: ['NFL'], format: 'dec1', better: 'high' },
  // Every sport
  { key: 'point_diff_pg', label: 'Margin/G', group: 'Efficiency', sports: BALL, format: 'fixed2', better: 'high' },
  { key: 'points_for_pg', label: 'Scored/G', group: 'Efficiency', sports: BALL, format: 'fixed2', better: 'high' },
  { key: 'points_against_pg', label: 'Allowed/G', group: 'Efficiency', sports: BALL, format: 'fixed2', better: 'low' },

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

/**
 * Stats the board should offer. A stat flagged `untilData` stays off the chip
 * row until some team has a number, so NFL points-added does not render a
 * column of dashes while the ingest is absent.
 */
export function teamStatsForBoard(sport: Sport, rows: readonly TeamStatsRow[]): TeamStatDef[] {
  return teamStatsForSport(sport).filter((s) => !s.untilData || columnHasValue(rows, s.key));
}

/**
 * Which stat to show after the offered set changes.
 *
 * A failed load clears the rows, and that hides every `untilData` chip. Falling
 * back in that window moves a user off Points added per play onto the group
 * default, and a later retry leaves them there. Hold the selection while the
 * load is in flight or the error banner is up. A successful load that truly
 * lacks the column (NFL, while the ingest is empty) still falls back.
 */
export function teamStatAfterOffer(
  stat: TeamStatDef | null,
  offered: readonly TeamStatDef[],
  sport: Sport,
  holdSelection: boolean,
): TeamStatDef | null {
  if (!stat || holdSelection) return stat;
  if (offered.some((s) => s.key === stat.key)) return stat;
  return offered.find((s) => s.group === stat.group) ?? defaultTeamStatFor(sport);
}

/**
 * Chip row while a load is failing or still running. The selected stat stays
 * visible even when empty rows have dropped it from `offered`, so the user
 * can see the choice the error did not change. Other empty `untilData` stats
 * stay hidden.
 */
export function teamStatsShown(
  offered: readonly TeamStatDef[],
  sport: Sport,
  selected: TeamStatDef | null,
  holdSelection: boolean,
): readonly TeamStatDef[] {
  if (!holdSelection || !selected || offered.some((s) => s.key === selected.key)) return offered;
  const full = teamStatsForSport(sport);
  if (!full.some((s) => s.key === selected.key)) return offered;
  return full.filter((s) => s.key === selected.key || offered.some((o) => o.key === s.key));
}

/** Groups that actually have a stat for this sport (so no empty tabs render). */
export function teamGroupsForSport(sport: Sport): TeamStatGroup[] {
  const present = new Set(teamStatsForSport(sport).map((s) => s.group));
  return TEAM_GROUP_ORDER.filter((g) => present.has(g));
}

/**
 * What the group tab says. Football's efficiency group is offense and defense
 * rates; every other sport keeps the word "Efficiency".
 */
export function teamGroupLabel(group: TeamStatGroup, sport: Sport): string {
  if (group === 'Efficiency' && (sport === 'NFL' || sport === 'NCAAF')) return 'Offense & defense';
  return group;
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

/** True when at least one row holds a finite number for `key`. Null and '' are absent, never zero. */
export function columnHasValue(rows: readonly TeamStatsRow[], key: keyof TeamStatsRow): boolean {
  return rows.some((row) => {
    const raw = row[key];
    if (raw == null || raw === '') return false;
    return teamStatValue(row, { ...PLACEHOLDER, key }) != null;
  });
}

const PLACEHOLDER: TeamStatDef = {
  key: 'games_played',
  label: '',
  group: 'Efficiency',
  sports: [],
  format: 'dec1',
  better: null,
};

/**
 * Width of the Teams stat column. 72pt at normal type, growing with the
 * reader's font scale and stopping at 1.8. A word at 2× is wider than the
 * old 1.6 cap, so the header was truncating.
 */
export function teamStatColumnWidth(fontScale: number): number {
  return Math.round(72 * Math.min(Math.max(fontScale, 1), 1.8));
}

/**
 * Visible Teams column header. At fontScale 1.3 and above, a zero-width space
 * after each slash is a wrap point ("PTS ADDED/\u200BPLAY"). VoiceOver must
 * not read this string — the spoken label is separate and has no zero-width space.
 */
export function teamStatHeaderText(label: string, fontScale: number): string {
  const upper = label.toUpperCase();
  if (fontScale < 1.3) return upper;
  return upper.split('/').join('/\u200B');
}

/** Header line count. Three lines once type is large enough to need the slash break. */
export function teamStatHeaderLines(fontScale: number): number {
  return fontScale >= 1.3 ? 3 : 2;
}

/** "1st", "2nd", "3rd", "11th". */
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

/**
 * Two decimals, minus only. Round to the displayed precision BEFORE choosing
 * a sign, so −0.004 and +0.004 both print `0.00` and never `−0.00`. A
 * positive prints with no sign. A negative uses a true minus.
 */
export function formatDec2(value: number): string {
  const rounded = Number(value.toFixed(2));
  if (rounded === 0) return '0.00';
  const body = Math.abs(rounded).toFixed(2);
  return rounded < 0 ? `\u2212${body}` : body;
}

export function formatTeamStat(value: number | null, format: TeamStatFormat): string {
  if (value == null) return '—';
  switch (format) {
    case 'int': return String(Math.round(value));
    case 'dec1': return value.toFixed(1);
    case 'fixed2': return value.toFixed(2);
    case 'dec2': return formatDec2(value);
    case 'dec3': return value.toFixed(3);
    case 'pct3': return `${(value * 100).toFixed(1)}%`;
  }
}

/** A value in full words for VoiceOver ("0.21", "minus 0.08", "46.7 percent"). */
export function spokenTeamStat(value: number | null, format: TeamStatFormat): string {
  if (value == null) return 'not available';
  if (format === 'dec2') {
    const rounded = Number(value.toFixed(2));
    if (rounded === 0) return '0.00';
    const body = Math.abs(rounded).toFixed(2);
    return rounded < 0 ? `minus ${body}` : body;
  }
  if (format === 'pct3') return `${(value * 100).toFixed(1)} percent`;
  return formatTeamStat(value, format);
}

/**
 * VoiceOver for one board value. The team name is a separate button, so this
 * is the stat, the number, and the rank: "Points added per play, offense,
 * 0.21, ranks 1st". Pass `of` (the teams that were ranked) to say
 * "ranks 1st of 32". Null when the stat has no spoken form.
 */
export function boardValueSpeech(
  def: TeamStatDef,
  value: number | null,
  rank: number | null,
  of?: number | null,
): string | null {
  if (!def.spoken) return null;
  const num = spokenTeamStat(value, def.format);
  if (value == null || rank == null) return `${def.spoken}, ${num}`;
  const place = of != null && of > 0 ? `${ordinal(rank)} of ${of}` : ordinal(rank);
  return `${def.spoken}, ${num}, ranks ${place}`;
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
