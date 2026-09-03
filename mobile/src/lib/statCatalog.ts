import type { PlayerType, RecentGameRow, SeasonTotalsRow } from '@/types';
import type { Sport } from '@/hooks/useSportFilter';
import { isModelRetired } from './thresholds';

export type StatGroup =
  | 'Batting' | 'Pitching' | 'WNBA' | 'NBA' | 'UFC'
  | 'Passing' | 'Rushing' | 'Receiving' | 'Defense';

/**
 * A selectable leaderboard stat. `key` is the column on SeasonTotalsRow.
 * For MLB, `playerType` decides which view rows to load (batter vs pitcher).
 * `defaultLine` is the threshold the Hit Rate mode uses out of the box (e.g.
 * 0.5 for counting stats → "≥1"); the user can override it per stat.
 */
export interface StatDef {
  key: keyof SeasonTotalsRow;
  label: string;
  sport: Sport;
  group: StatGroup;
  playerType?: PlayerType;
  defaultLine?: number;
}

export const STAT_CATALOG: StatDef[] = [
  // ── MLB batting ──
  { key: 'hits', label: 'Hits', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'home_runs', label: 'Home Runs', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'total_bases', label: 'Total Bases', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 1.5 },
  { key: 'rbi', label: 'RBI', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'runs', label: 'Runs', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'walks', label: 'Walks', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'stolen_bases', label: 'Stolen Bases', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'doubles', label: 'Doubles', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'triples', label: 'Triples', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'strikeouts', label: 'Strikeouts', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 0.5 },
  { key: 'at_bats', label: 'At Bats', sport: 'MLB', group: 'Batting', playerType: 'batter', defaultLine: 3.5 },
  // ── MLB pitching ──
  { key: 'p_strikeouts', label: 'Strikeouts', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 5.5 },
  { key: 'p_walks', label: 'Walks', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 1.5 },
  { key: 'p_hits_allowed', label: 'Hits Allowed', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 5.5 },
  { key: 'p_earned_runs', label: 'Earned Runs', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 2.5 },
  { key: 'p_home_runs', label: 'HR Allowed', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 0.5 },
  { key: 'innings_pitched', label: 'Innings', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 5.5 },
  { key: 'pitches', label: 'Pitches', sport: 'MLB', group: 'Pitching', playerType: 'pitcher', defaultLine: 89.5 },
  // ── WNBA ──
  { key: 'points', label: 'Points', sport: 'WNBA', group: 'WNBA', defaultLine: 14.5 },
  { key: 'rebounds', label: 'Rebounds', sport: 'WNBA', group: 'WNBA', defaultLine: 5.5 },
  { key: 'assists', label: 'Assists', sport: 'WNBA', group: 'WNBA', defaultLine: 3.5 },
  { key: 'threes', label: '3PM', sport: 'WNBA', group: 'WNBA', defaultLine: 1.5 },
  { key: 'pra', label: 'PRA', sport: 'WNBA', group: 'WNBA', defaultLine: 24.5 },
  { key: 'steals', label: 'Steals', sport: 'WNBA', group: 'WNBA', defaultLine: 0.5 },
  { key: 'blocks', label: 'Blocks', sport: 'WNBA', group: 'WNBA', defaultLine: 0.5 },
  { key: 'minutes', label: 'Minutes', sport: 'WNBA', group: 'WNBA', defaultLine: 27.5 },
  // ── NBA ──
  { key: 'points', label: 'Points', sport: 'NBA', group: 'NBA', defaultLine: 14.5 },
  { key: 'rebounds', label: 'Rebounds', sport: 'NBA', group: 'NBA', defaultLine: 5.5 },
  { key: 'assists', label: 'Assists', sport: 'NBA', group: 'NBA', defaultLine: 3.5 },
  { key: 'threes', label: '3PM', sport: 'NBA', group: 'NBA', defaultLine: 1.5 },
  { key: 'pra', label: 'PRA', sport: 'NBA', group: 'NBA', defaultLine: 24.5 },
  { key: 'steals', label: 'Steals', sport: 'NBA', group: 'NBA', defaultLine: 0.5 },
  { key: 'blocks', label: 'Blocks', sport: 'NBA', group: 'NBA', defaultLine: 0.5 },
  { key: 'turnovers', label: 'Turnovers', sport: 'NBA', group: 'NBA', defaultLine: 1.5 },
  { key: 'minutes', label: 'Minutes', sport: 'NBA', group: 'NBA', defaultLine: 27.5 },
  // ── NFL (nflverse weekly stats — rush_rec_tds = rushing + receiving TDs) ──
  { key: 'passing_yards', label: 'Pass Yards', sport: 'NFL', group: 'Passing', defaultLine: 224.5 },
  { key: 'passing_tds', label: 'Pass TDs', sport: 'NFL', group: 'Passing', defaultLine: 1.5 },
  { key: 'completions', label: 'Completions', sport: 'NFL', group: 'Passing', defaultLine: 19.5 },
  { key: 'attempts', label: 'Pass Attempts', sport: 'NFL', group: 'Passing', defaultLine: 29.5 },
  { key: 'interceptions', label: 'INTs Thrown', sport: 'NFL', group: 'Passing', defaultLine: 0.5 },
  { key: 'rushing_yards', label: 'Rush Yards', sport: 'NFL', group: 'Rushing', defaultLine: 49.5 },
  { key: 'rushing_tds', label: 'Rush TDs', sport: 'NFL', group: 'Rushing', defaultLine: 0.5 },
  { key: 'carries', label: 'Carries', sport: 'NFL', group: 'Rushing', defaultLine: 12.5 },
  { key: 'rush_rec_tds', label: 'Rush+Rec TDs', sport: 'NFL', group: 'Rushing', defaultLine: 0.5 },
  { key: 'receptions', label: 'Receptions', sport: 'NFL', group: 'Receiving', defaultLine: 3.5 },
  { key: 'receiving_yards', label: 'Rec Yards', sport: 'NFL', group: 'Receiving', defaultLine: 49.5 },
  { key: 'receiving_tds', label: 'Rec TDs', sport: 'NFL', group: 'Receiving', defaultLine: 0.5 },
  { key: 'targets', label: 'Targets', sport: 'NFL', group: 'Receiving', defaultLine: 5.5 },
  { key: 'def_sacks', label: 'Sacks', sport: 'NFL', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_interceptions', label: 'Interceptions', sport: 'NFL', group: 'Defense', defaultLine: 0.5 },
  // ── NCAAF (CFBD box scores — same column keys as the NFL log wherever the
  //    two sports share a stat, so one catalog key means one thing in both.
  //    No targets: CFBD's box score does not report them.) ──
  { key: 'passing_yards', label: 'Pass Yards', sport: 'NCAAF', group: 'Passing', defaultLine: 224.5 },
  { key: 'passing_tds', label: 'Pass TDs', sport: 'NCAAF', group: 'Passing', defaultLine: 1.5 },
  { key: 'completions', label: 'Completions', sport: 'NCAAF', group: 'Passing', defaultLine: 17.5 },
  { key: 'attempts', label: 'Pass Attempts', sport: 'NCAAF', group: 'Passing', defaultLine: 27.5 },
  { key: 'interceptions', label: 'INTs Thrown', sport: 'NCAAF', group: 'Passing', defaultLine: 0.5 },
  { key: 'rushing_yards', label: 'Rush Yards', sport: 'NCAAF', group: 'Rushing', defaultLine: 49.5 },
  { key: 'rushing_tds', label: 'Rush TDs', sport: 'NCAAF', group: 'Rushing', defaultLine: 0.5 },
  { key: 'carries', label: 'Carries', sport: 'NCAAF', group: 'Rushing', defaultLine: 10.5 },
  { key: 'rush_rec_tds', label: 'Rush+Rec TDs', sport: 'NCAAF', group: 'Rushing', defaultLine: 0.5 },
  { key: 'receptions', label: 'Receptions', sport: 'NCAAF', group: 'Receiving', defaultLine: 3.5 },
  { key: 'receiving_yards', label: 'Rec Yards', sport: 'NCAAF', group: 'Receiving', defaultLine: 44.5 },
  { key: 'receiving_tds', label: 'Rec TDs', sport: 'NCAAF', group: 'Receiving', defaultLine: 0.5 },
  { key: 'def_tackles', label: 'Tackles', sport: 'NCAAF', group: 'Defense', defaultLine: 4.5 },
  { key: 'def_solo', label: 'Solo Tackles', sport: 'NCAAF', group: 'Defense', defaultLine: 2.5 },
  { key: 'def_sacks', label: 'Sacks', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_tfl', label: 'TFL', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_pd', label: 'Passes Defended', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  { key: 'def_interceptions', label: 'Interceptions', sport: 'NCAAF', group: 'Defense', defaultLine: 0.5 },
  // ── UFC (games_played = fights in the window; team column = weight class) ──
  { key: 'wins', label: 'Wins', sport: 'UFC', group: 'UFC' },
  { key: 'ko_wins', label: 'KO/TKO Wins', sport: 'UFC', group: 'UFC' },
  { key: 'sub_wins', label: 'Sub Wins', sport: 'UFC', group: 'UFC' },
  { key: 'sig_strikes', label: 'Sig Strikes', sport: 'UFC', group: 'UFC' },
  { key: 'takedowns', label: 'Takedowns', sport: 'UFC', group: 'UFC' },
  { key: 'knockdowns', label: 'Knockdowns', sport: 'UFC', group: 'UFC' },
  { key: 'sub_attempts', label: 'Sub Attempts', sport: 'UFC', group: 'UFC' },
];

export const GROUP_ORDER: Record<Sport, StatGroup[]> = {
  MLB: ['Batting', 'Pitching'],
  WNBA: ['WNBA'],
  NBA: ['NBA'],
  NFL: ['Passing', 'Rushing', 'Receiving', 'Defense'],
  NCAAF: ['Passing', 'Rushing', 'Receiving', 'Defense'],
  UFC: ['UFC'],
  // No per-player leaderboard for these (NHL: team+goalie only; Golf: v1).
  NHL: [],
  GOLF: [],
};

export function statsForSport(sport: Sport): StatDef[] {
  return STAT_CATALOG.filter((s) => s.sport === sport);
}

/** Sport's default leaderboard stat, or null when the sport has no leaderboard (NHL, Golf). */
export function defaultStatFor(sport: Sport): StatDef | null {
  const wantKey =
    sport === 'WNBA' || sport === 'NBA' ? 'points'
    : sport === 'UFC' ? 'wins'
    : sport === 'NFL' || sport === 'NCAAF' ? 'passing_yards'
    : 'hits';
  const list = statsForSport(sport);
  return list.find((s) => s.key === wantKey) ?? list[0] ?? null;
}

/**
 * Any row carrying stat columns: season totals, a raw Hit-Rate game row, or a
 * single player's normalized game-log entry. Structural so all three qualify
 * without this module having to import each of their types.
 */
export type StatValueSource =
  | SeasonTotalsRow
  | RecentGameRow
  | { [key: string]: number | string | boolean | null | undefined };

/** Stat value for a row under a given stat (0 if missing). Works on season-total
 * rows and raw per-game rows (Hit Rate mode) alike. */
export function statValue(row: StatValueSource, def: StatDef): number {
  const v = row[def.key];
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    // NUMERIC Postgres columns (NFL yards, sacks) can arrive as strings.
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }
  return 0;
}

/** Default Hit Rate line for a stat (0.5 = "≥1" fallback for counting stats). */
export function defaultThresholdFor(def: StatDef | null): number {
  return def?.defaultLine ?? 0.5;
}

// Sports that support the Hit Rate view (have per-game player logs + RPCs).
const HIT_RATE_SPORTS = new Set<Sport>(['MLB', 'WNBA', 'NBA', 'NFL', 'NCAAF']);

/** Whether a sport can show the Hit Rate mode (UFC/NHL/Golf cannot). */
export function supportsHitRate(sport: Sport): boolean {
  return HIT_RATE_SPORTS.has(sport);
}

/**
 * Map a leaderboard stat to the prop model_id that prices it, so the Stats tab
 * can offer "Add to play" on a player when today's picks include the matching
 * prop. Keyed by StatDef.key. `home_runs` and `rbi` still map to their models
 * so a historical pick resolves back to its stat (statForPropModel), but both
 * models are RETIRED, so propModelForStat returns null for them: the STAT stays
 * on the leaderboard (Matt, 2026-09-02: "you should still see home runs on the
 * stats page"), the odds pill and Add button do not.
 * Stats with no prop model (doubles, triples, pitches, steals, …) return null.
 */
const STAT_KEY_TO_MODEL: Partial<Record<keyof SeasonTotalsRow, string>> = {
  // MLB batting
  hits: 'mlb_prop_batter_hits',
  total_bases: 'mlb_prop_batter_tb',
  home_runs: 'mlb_prop_batter_hr',
  rbi: 'mlb_prop_batter_rbi',
  runs: 'mlb_prop_batter_runs',
  walks: 'mlb_prop_batter_walks',
  stolen_bases: 'mlb_prop_batter_sb',
  // MLB pitching
  p_strikeouts: 'mlb_prop_pitcher_k',
  p_walks: 'mlb_prop_pitcher_walks',
  p_hits_allowed: 'mlb_prop_pitcher_hits',
  p_earned_runs: 'mlb_prop_pitcher_er',
  innings_pitched: 'mlb_prop_pitcher_outs',
  // WNBA / NBA share these column keys — resolved per sport in propModelForStat,
  // NOT here (a bare key can't disambiguate the two basketball leagues).
};

// Basketball stat key → prop-model suffix. WNBA and NBA reuse the same column
// keys, so the prefix is chosen from def.sport. NBA-only keys (turnovers) map
// only under NBA.
const BASKETBALL_STAT_SUFFIX: Partial<Record<keyof SeasonTotalsRow, string>> = {
  points: 'prop_player_points',
  rebounds: 'prop_player_rebounds',
  assists: 'prop_player_assists',
  threes: 'prop_player_threes',
  pra: 'prop_player_pra',
  blocks: 'prop_player_blocks',
  steals: 'prop_player_steals',
  turnovers: 'prop_player_turnovers',
};

// Suffixes WNBA actually models (NBA additionally has blocks/steals/turnovers).
const WNBA_BASKETBALL_KEYS = new Set<keyof SeasonTotalsRow>([
  'points', 'rebounds', 'assists', 'threes', 'pra',
]);

/** The prop model_id whose pick can be added from this stat's leaderboard, or null. */
export function propModelForStat(def: StatDef | null): string | null {
  if (!def) return null;
  // NCAAF shares its column keys with the NFL but has no prop models of its
  // own — returning early keeps a shared key (passing_yards) from resolving to
  // an NFL model on a college player.
  if (def.sport === 'NCAAF') return null;
  if (def.sport === 'NBA') {
    const suffix = BASKETBALL_STAT_SUFFIX[def.key];
    return suffix ? `nba_${suffix}` : null;
  }
  if (def.sport === 'WNBA') {
    const suffix = BASKETBALL_STAT_SUFFIX[def.key];
    return suffix && WNBA_BASKETBALL_KEYS.has(def.key) ? `wnba_${suffix}` : null;
  }
  const id = STAT_KEY_TO_MODEL[def.key] ?? null;
  // Retirement is about the model tracker, not the stat: the leaderboard keeps
  // the column, the Stats tab just never offers a retired model's pick on it.
  return id != null && isModelRetired(id) ? null : id;
}

/**
 * Inverse of propModelForStat — the leaderboard stat a prop model prices, so a
 * pick can open its player's detail screen on the stat the pick is about.
 * Derived from the forward map, so the two can never disagree. Returns null for
 * game markets and for prop models with no leaderboard stat.
 */
export function statForPropModel(modelId: string): StatDef | null {
  for (const def of STAT_CATALOG) {
    if (propModelForStat(def) === modelId) return def;
  }
  return null;
}
