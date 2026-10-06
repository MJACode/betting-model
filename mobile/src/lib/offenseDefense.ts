/**
 * Matchup: one team's offense against the other's defense.
 *
 * Counting rows (points, yards per play, pass yards, rush yards) come from
 * `nfl_team_game_stats`. A null box score is skipped — it is not a zero, and
 * a team with no completed games ranks as unranked rather than 1st.
 *
 * Points-added and successful-plays rows come from the team-stats board.
 * They render only when some team has a real value. NCAAF does (CFBD). NFL
 * does not, until a play-by-play ingest exists: both columns were null on
 * every NFL row in team_stats_board_cache for 2025 and 2026 (2026-10-06).
 */
import type { TeamStatsRow } from '@/types';
import {
  columnHasValue,
  formatTeamStat,
  ordinal,
  spokenTeamStat,
  type StatExplain,
  type TeamStatFormat,
  EXPLAIN_PTS_ADDED,
  EXPLAIN_SUCCESS,
} from '@/lib/teamStatCatalog';

export interface OffenseBoxLine {
  game_id: string;
  team: string;
  opponent: string;
  /** Kickoff date. Absent on a fixture that is not being date-capped. */
  game_date?: string | null;
  plays: number | null;
  pass_yards: number | null;
  rush_yards: number | null;
  points_for: number | null;
  points_against: number | null;
}

/**
 * Box lines from before a pick's game date. The pick's own game and every
 * later game (a settled 2025 pick must not absorb that season's playoffs)
 * stay out. A row with no date cannot be shown to be earlier, so it stays out
 * too. No date means no cap.
 */
export function boxBefore(rows: readonly OffenseBoxLine[], beforeDate: string | null | undefined): OffenseBoxLine[] {
  if (!beforeDate) return [...rows];
  return rows.filter((row) => typeof row.game_date === 'string' && row.game_date < beforeDate);
}

export interface TeamRates {
  team: string;
  pointsFor: number | null;
  pointsAgainst: number | null;
  yardsPerPlay: number | null;
  yardsPerPlayAllowed: number | null;
  passYds: number | null;
  passYdsAllowed: number | null;
  rushYds: number | null;
  rushYdsAllowed: number | null;
  /** Completed games that contributed a points figure. */
  games: number;
}

export interface MatchupRow {
  key: string;
  label: string;
  explain: StatExplain | null;
  offValue: number | null;
  defValue: number | null;
  offRank: number | null;
  defRank: number | null;
  displayOff: string;
  displayDef: string;
  /** Per-value VoiceOver. The info button stays its own element. */
  offSpeech: string;
  defSpeech: string;
}

export interface MatchupSection {
  offenseTeam: string;
  defenseTeam: string;
  /** Completed games behind this side, or null when that side has none. */
  offenseGames: number | null;
  defenseGames: number | null;
  rows: MatchupRow[];
}

export interface MatchupModel {
  season: number | null;
  /** Distinct completed games behind the counting rows, or the board's max games. */
  games: number | null;
  /** Teams a rank is taken out of (those with a completed game, else the board). */
  teams: number;
  sections: [MatchupSection, MatchupSection];
}

function num(v: unknown): number | null {
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function avg(sum: number, n: number): number | null {
  return n > 0 ? sum / n : null;
}

/**
 * Season rates from per-game box lines. Null yardage is left out of the
 * average; it is never added as zero. Yards per play needs plays and both
 * yardage figures for that game.
 */
export function aggregateBox(rows: readonly OffenseBoxLine[]): Map<string, TeamRates> {
  const byGame = new Map<string, OffenseBoxLine[]>();
  for (const row of rows) {
    const list = byGame.get(row.game_id);
    if (list) list.push(row);
    else byGame.set(row.game_id, [row]);
  }
  type Acc = {
    sPf: number; nPf: number;
    sPa: number; nPa: number;
    yds: number; plays: number;
    dYds: number; dPlays: number;
    pass: number; nPass: number;
    dPass: number; nDPass: number;
    rush: number; nRush: number;
    dRush: number; nDRush: number;
  };
  const acc = new Map<string, Acc>();
  const ensure = (team: string): Acc => {
    let a = acc.get(team);
    if (!a) {
      a = {
        sPf: 0, nPf: 0, sPa: 0, nPa: 0, yds: 0, plays: 0, dYds: 0, dPlays: 0,
        pass: 0, nPass: 0, dPass: 0, nDPass: 0, rush: 0, nRush: 0, dRush: 0, nDRush: 0,
      };
      acc.set(team, a);
    }
    return a;
  };
  for (const row of rows) {
    const a = ensure(row.team);
    const pf = num(row.points_for);
    const pa = num(row.points_against);
    if (pf != null) { a.sPf += pf; a.nPf += 1; }
    if (pa != null) { a.sPa += pa; a.nPa += 1; }
    const py = num(row.pass_yards);
    const ry = num(row.rush_yards);
    const plays = num(row.plays);
    if (py != null && ry != null && plays != null && plays > 0) {
      a.yds += py + ry;
      a.plays += plays;
    }
    if (py != null) { a.pass += py; a.nPass += 1; }
    if (ry != null) { a.rush += ry; a.nRush += 1; }
    const opp = (byGame.get(row.game_id) ?? []).find((o) => o.team !== row.team);
    if (!opp) continue;
    const opy = num(opp.pass_yards);
    const ory = num(opp.rush_yards);
    const oplays = num(opp.plays);
    if (opy != null && ory != null && oplays != null && oplays > 0) {
      a.dYds += opy + ory;
      a.dPlays += oplays;
    }
    if (opy != null) { a.dPass += opy; a.nDPass += 1; }
    if (ory != null) { a.dRush += ory; a.nDRush += 1; }
  }
  const out = new Map<string, TeamRates>();
  for (const [team, a] of acc) {
    out.set(team, {
      team,
      pointsFor: avg(a.sPf, a.nPf),
      pointsAgainst: avg(a.sPa, a.nPa),
      yardsPerPlay: avg(a.yds, a.plays),
      yardsPerPlayAllowed: avg(a.dYds, a.dPlays),
      passYds: avg(a.pass, a.nPass),
      passYdsAllowed: avg(a.dPass, a.nDPass),
      rushYds: avg(a.rush, a.nRush),
      rushYdsAllowed: avg(a.dRush, a.nDRush),
      games: Math.max(a.nPf, a.nPa),
    });
  }
  return out;
}

/** 1 = best. Ties share the better rank. Null is unranked, not last and not zero. */
export function rankIn(values: ReadonlyMap<string, number | null>, team: string, higherBetter: boolean): number | null {
  const mine = values.get(team);
  if (mine == null) return null;
  let better = 0;
  for (const v of values.values()) {
    if (v == null) continue;
    if (higherBetter ? v > mine : v < mine) better += 1;
  }
  return better + 1;
}

function column(rates: ReadonlyMap<string, TeamRates>, key: keyof TeamRates): Map<string, number | null> {
  const out = new Map<string, number | null>();
  for (const [team, rate] of rates) {
    const v = rate[key];
    out.set(team, typeof v === 'number' ? v : null);
  }
  return out;
}

function boardColumn(rows: readonly TeamStatsRow[], key: keyof TeamStatsRow): Map<string, number | null> {
  const out = new Map<string, number | null>();
  for (const row of rows) {
    const v = row[key];
    if (typeof v === 'number' && Number.isFinite(v)) out.set(row.team, v);
    else if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) out.set(row.team, Number(v));
    else out.set(row.team, null);
  }
  return out;
}

/** Points-added / successful-plays rows exist only when the column is not all null. */
export function playRowsAvailable(rows: readonly TeamStatsRow[]): { pointsAdded: boolean; success: boolean } {
  return {
    pointsAdded: columnHasValue(rows, 'epa_off') || columnHasValue(rows, 'epa_def'),
    success: columnHasValue(rows, 'success_off') || columnHasValue(rows, 'success_def'),
  };
}

function shown(value: number | null, format: TeamStatFormat): string {
  return formatTeamStat(value, format);
}

/**
 * VoiceOver for a points-added or successful-plays cell.
 * Defense reads "allowed" so "lower is better" has a subject:
 * "JAX defense, points added per play allowed, minus 0.08, ranks 2nd".
 */
export function playCellSpeech(
  team: string,
  side: 'offense' | 'defense',
  kind: 'points-added' | 'success',
  value: number | null,
  rank: number | null,
): string {
  const format: TeamStatFormat = kind === 'points-added' ? 'sdec2' : 'pct3';
  const what = kind === 'points-added'
    ? (side === 'offense' ? 'points added per play' : 'points added per play allowed')
    : (side === 'offense' ? 'successful plays' : 'successful plays allowed');
  const rankBit = value != null && rank != null ? `, ranks ${ordinal(rank)}` : '';
  return `${team} ${side}, ${what}, ${spokenTeamStat(value, format)}${rankBit}`;
}

function boxSpeech(
  spoken: string,
  offenseTeam: string,
  defenseTeam: string,
  offValue: number | null,
  defValue: number | null,
  offRank: number | null,
  defRank: number | null,
  format: TeamStatFormat,
): { offSpeech: string; defSpeech: string } {
  const off = offValue == null ? 'not available' : formatTeamStat(offValue, format);
  const def = defValue == null ? 'not available' : formatTeamStat(defValue, format);
  const offRankBit = offRank != null ? `, ranked ${ordinal(offRank)}` : ', unranked';
  const defRankBit = defRank != null ? `, ranked ${ordinal(defRank)}` : ', unranked';
  return {
    offSpeech: `${spoken}: ${offenseTeam} offense ${off}${offRankBit}`,
    defSpeech: `${spoken}: ${defenseTeam} defense allows ${def}${defRankBit}`,
  };
}

const BOX_SPECS: {
  key: string; label: string; spoken: string;
  off: keyof TeamRates; def: keyof TeamRates; format: TeamStatFormat;
}[] = [
  { key: 'pts', label: 'Points / game', spoken: 'Points per game', off: 'pointsFor', def: 'pointsAgainst', format: 'dec1' },
  { key: 'ypp', label: 'Yards / play', spoken: 'Yards per play', off: 'yardsPerPlay', def: 'yardsPerPlayAllowed', format: 'dec2' },
  { key: 'pass', label: 'Pass yds / game', spoken: 'Passing yards per game', off: 'passYds', def: 'passYdsAllowed', format: 'dec1' },
  { key: 'rush', label: 'Rush yds / game', spoken: 'Rushing yards per game', off: 'rushYds', def: 'rushYdsAllowed', format: 'dec1' },
];

function rateRow(
  rates: ReadonlyMap<string, TeamRates>,
  spec: (typeof BOX_SPECS)[number],
  offenseTeam: string,
  defenseTeam: string,
): MatchupRow {
  const offCol = column(rates, spec.off);
  const defCol = column(rates, spec.def);
  const offValue = offCol.get(offenseTeam) ?? null;
  const defValue = defCol.get(defenseTeam) ?? null;
  const offRank = rankIn(offCol, offenseTeam, true);
  const defRank = rankIn(defCol, defenseTeam, false);
  const speech = boxSpeech(spec.spoken, offenseTeam, defenseTeam, offValue, defValue, offRank, defRank, spec.format);
  return {
    key: spec.key,
    label: spec.label,
    explain: null,
    offValue,
    defValue,
    offRank,
    defRank,
    displayOff: shown(offValue, spec.format),
    displayDef: shown(defValue, spec.format),
    offSpeech: speech.offSpeech,
    defSpeech: speech.defSpeech,
  };
}

function boardRateRow(
  rows: readonly TeamStatsRow[],
  key: string,
  label: string,
  spoken: string,
  offKey: keyof TeamStatsRow,
  defKey: keyof TeamStatsRow,
  format: TeamStatFormat,
  offenseTeam: string,
  defenseTeam: string,
): MatchupRow {
  const offCol = boardColumn(rows, offKey);
  const defCol = boardColumn(rows, defKey);
  const offValue = offCol.get(offenseTeam) ?? null;
  const defValue = defCol.get(defenseTeam) ?? null;
  const offRank = rankIn(offCol, offenseTeam, true);
  const defRank = rankIn(defCol, defenseTeam, false);
  const speech = boxSpeech(spoken, offenseTeam, defenseTeam, offValue, defValue, offRank, defRank, format);
  return {
    key,
    label,
    explain: null,
    offValue,
    defValue,
    offRank,
    defRank,
    displayOff: shown(offValue, format),
    displayDef: shown(defValue, format),
    offSpeech: speech.offSpeech,
    defSpeech: speech.defSpeech,
  };
}

function playRow(
  rows: readonly TeamStatsRow[],
  kind: 'points-added' | 'success',
  offenseTeam: string,
  defenseTeam: string,
): MatchupRow {
  const offKey = kind === 'points-added' ? 'epa_off' : 'success_off';
  const defKey = kind === 'points-added' ? 'epa_def' : 'success_def';
  const format: TeamStatFormat = kind === 'points-added' ? 'sdec2' : 'pct3';
  const explain = kind === 'points-added' ? EXPLAIN_PTS_ADDED : EXPLAIN_SUCCESS;
  const offCol = boardColumn(rows, offKey);
  const defCol = boardColumn(rows, defKey);
  const offValue = offCol.get(offenseTeam) ?? null;
  const defValue = defCol.get(defenseTeam) ?? null;
  const offRank = rankIn(offCol, offenseTeam, true);
  const defRank = rankIn(defCol, defenseTeam, false);
  return {
    key: kind,
    label: explain.name,
    explain,
    offValue,
    defValue,
    offRank,
    defRank,
    displayOff: shown(offValue, format),
    displayDef: shown(defValue, format),
    offSpeech: playCellSpeech(offenseTeam, 'offense', kind, offValue, offRank),
    defSpeech: playCellSpeech(defenseTeam, 'defense', kind, defValue, defRank),
  };
}

function sectionRows(
  offenseTeam: string,
  defenseTeam: string,
  rates: ReadonlyMap<string, TeamRates> | null,
  board: readonly TeamStatsRow[],
  plays: { pointsAdded: boolean; success: boolean },
): MatchupRow[] {
  const rows: MatchupRow[] = [];
  if (rates && [...rates.values()].some((r) => r.games > 0)) {
    for (const spec of BOX_SPECS) rows.push(rateRow(rates, spec, offenseTeam, defenseTeam));
  } else if (columnHasValue(board, 'points_for_pg') || columnHasValue(board, 'points_against_pg')) {
    // NCAAF has no per-game box in nfl_team_game_stats. Points per game are
    // on the board; yards allowed are not, so those rows stay off rather
    // than printing a league of dashes.
    const pts = BOX_SPECS[0];
    rows.push(boardRateRow(
      board, pts.key, pts.label, pts.spoken, 'points_for_pg', 'points_against_pg', pts.format,
      offenseTeam, defenseTeam,
    ));
  }
  if (plays.pointsAdded) rows.push(playRow(board, 'points-added', offenseTeam, defenseTeam));
  if (plays.success) rows.push(playRow(board, 'success', offenseTeam, defenseTeam));
  return rows;
}

/**
 * Two sections: the picked side's offense against the other defense, then
 * the reverse. Totals (no side) lead with the away offense.
 */
export function buildMatchup(args: {
  season: number | null;
  away: string;
  home: string;
  ourTeam: string | null;
  box: readonly OffenseBoxLine[];
  board: readonly TeamStatsRow[];
  /** Count only games before this date. The pick's game_date. */
  beforeDate?: string | null;
}): MatchupModel {
  const box = boxBefore(args.box, args.beforeDate);
  const rates = box.length ? aggregateBox(box) : null;
  const plays = playRowsAvailable(args.board);
  const lead = args.ourTeam === args.home || args.ourTeam === args.away ? args.ourTeam : args.away;
  const other = lead === args.home ? args.away : args.home;
  const gamesFor = (team: string): number | null => {
    if (rates) {
      const n = rates.get(team)?.games ?? 0;
      return n > 0 ? n : null;
    }
    const row = args.board.find((r) => r.team === team);
    const n = row?.games_played;
    return typeof n === 'number' && n > 0 ? n : null;
  };
  const completed = rates
    ? new Set(box.filter((r) => num(r.points_for) != null).map((r) => r.game_id)).size
    : null;
  const teamsWithGames = rates
    ? [...rates.values()].filter((r) => r.games > 0).length
    : args.board.length;
  const boardGames = args.board.reduce((m, r) => Math.max(m, typeof r.games_played === 'number' ? r.games_played : 0), 0);
  return {
    season: args.season,
    games: completed != null && completed > 0 ? completed : (boardGames || null),
    teams: teamsWithGames,
    sections: [
      {
        offenseTeam: lead,
        defenseTeam: other,
        offenseGames: gamesFor(lead),
        defenseGames: gamesFor(other),
        rows: sectionRows(lead, other, rates, args.board, plays),
      },
      {
        offenseTeam: other,
        defenseTeam: lead,
        offenseGames: gamesFor(other),
        defenseGames: gamesFor(lead),
        rows: sectionRows(other, lead, rates, args.board, plays),
      },
    ],
  };
}
