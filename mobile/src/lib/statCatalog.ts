import type { PlayerType, SeasonTotalsRow } from '@/types';
import type { Sport } from '@/hooks/useSportFilter';

export type StatGroup = 'Batting' | 'Pitching' | 'WNBA' | 'NBA' | 'UFC';

/**
 * A selectable leaderboard stat. `key` is the column on SeasonTotalsRow.
 * For MLB, `playerType` decides which view rows to load (batter vs pitcher).
 */
export interface StatDef {
  key: keyof SeasonTotalsRow;
  label: string;
  sport: Sport;
  group: StatGroup;
  playerType?: PlayerType;
}

export const STAT_CATALOG: StatDef[] = [
  // ── MLB batting ──
  { key: 'hits', label: 'Hits', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'home_runs', label: 'Home Runs', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'total_bases', label: 'Total Bases', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'rbi', label: 'RBI', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'runs', label: 'Runs', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'walks', label: 'Walks', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'stolen_bases', label: 'Stolen Bases', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'doubles', label: 'Doubles', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'triples', label: 'Triples', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'strikeouts', label: 'Strikeouts', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  { key: 'at_bats', label: 'At Bats', sport: 'MLB', group: 'Batting', playerType: 'batter' },
  // ── MLB pitching ──
  { key: 'p_strikeouts', label: 'Strikeouts', sport: 'MLB', group: 'Pitching', playerType: 'pitcher' },
  { key: 'p_walks', label: 'Walks', sport: 'MLB', group: 'Pitching', playerType: 'pitcher' },
  { key: 'p_hits_allowed', label: 'Hits Allowed', sport: 'MLB', group: 'Pitching', playerType: 'pitcher' },
  { key: 'p_earned_runs', label: 'Earned Runs', sport: 'MLB', group: 'Pitching', playerType: 'pitcher' },
  { key: 'p_home_runs', label: 'HR Allowed', sport: 'MLB', group: 'Pitching', playerType: 'pitcher' },
  { key: 'innings_pitched', label: 'Innings', sport: 'MLB', group: 'Pitching', playerType: 'pitcher' },
  { key: 'pitches', label: 'Pitches', sport: 'MLB', group: 'Pitching', playerType: 'pitcher' },
  // ── WNBA ──
  { key: 'points', label: 'Points', sport: 'WNBA', group: 'WNBA' },
  { key: 'rebounds', label: 'Rebounds', sport: 'WNBA', group: 'WNBA' },
  { key: 'assists', label: 'Assists', sport: 'WNBA', group: 'WNBA' },
  { key: 'threes', label: '3PM', sport: 'WNBA', group: 'WNBA' },
  { key: 'pra', label: 'PRA', sport: 'WNBA', group: 'WNBA' },
  { key: 'steals', label: 'Steals', sport: 'WNBA', group: 'WNBA' },
  { key: 'blocks', label: 'Blocks', sport: 'WNBA', group: 'WNBA' },
  { key: 'minutes', label: 'Minutes', sport: 'WNBA', group: 'WNBA' },
  // ── NBA ──
  { key: 'points', label: 'Points', sport: 'NBA', group: 'NBA' },
  { key: 'rebounds', label: 'Rebounds', sport: 'NBA', group: 'NBA' },
  { key: 'assists', label: 'Assists', sport: 'NBA', group: 'NBA' },
  { key: 'threes', label: '3PM', sport: 'NBA', group: 'NBA' },
  { key: 'pra', label: 'PRA', sport: 'NBA', group: 'NBA' },
  { key: 'steals', label: 'Steals', sport: 'NBA', group: 'NBA' },
  { key: 'blocks', label: 'Blocks', sport: 'NBA', group: 'NBA' },
  { key: 'turnovers', label: 'Turnovers', sport: 'NBA', group: 'NBA' },
  { key: 'minutes', label: 'Minutes', sport: 'NBA', group: 'NBA' },
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
  UFC: ['UFC'],
  GOLF: [], // no player-stats leaderboard for golf v1
};

export function statsForSport(sport: Sport): StatDef[] {
  return STAT_CATALOG.filter((s) => s.sport === sport);
}

export function defaultStatFor(sport: Sport): StatDef {
  const wantKey =
    sport === 'WNBA' || sport === 'NBA' ? 'points' : sport === 'UFC' ? 'wins' : 'hits';
  // Golf has no leaderboard stats — fall back to the MLB default (StatsScreen
  // short-circuits golf before this is rendered).
  return (
    statsForSport(sport).find((s) => s.key === wantKey) ??
    statsForSport(sport)[0] ??
    STAT_CATALOG[0]!
  );
}

/** Raw season total for a row under a given stat (0 if missing). */
export function statValue(row: SeasonTotalsRow, def: StatDef): number {
  const v = row[def.key];
  return typeof v === 'number' ? v : 0;
}

/**
 * Map a leaderboard stat to the prop model_id that prices it, so the Stats tab
 * can offer "Add to play" on a player when today's picks include the matching
 * prop. Keyed by StatDef.key — `home_runs` maps to the HR model even though it's
 * prob-only (null odds), so its Add button simply never shows (no priced pick).
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
export function propModelForStat(def: StatDef): string | null {
  if (def.sport === 'NBA') {
    const suffix = BASKETBALL_STAT_SUFFIX[def.key];
    return suffix ? `nba_${suffix}` : null;
  }
  if (def.sport === 'WNBA') {
    const suffix = BASKETBALL_STAT_SUFFIX[def.key];
    return suffix && WNBA_BASKETBALL_KEYS.has(def.key) ? `wnba_${suffix}` : null;
  }
  return STAT_KEY_TO_MODEL[def.key] ?? null;
}
