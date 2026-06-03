import type { PlayerType, SeasonTotalsRow } from '@/types';
import type { Sport } from '@/hooks/useSportFilter';

export type StatGroup = 'Batting' | 'Pitching' | 'WNBA';

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
];

export const GROUP_ORDER: Record<Sport, StatGroup[]> = {
  MLB: ['Batting', 'Pitching'],
  WNBA: ['WNBA'],
};

export function statsForSport(sport: Sport): StatDef[] {
  return STAT_CATALOG.filter((s) => s.sport === sport);
}

export function defaultStatFor(sport: Sport): StatDef {
  const wantKey = sport === 'WNBA' ? 'points' : 'hits';
  return statsForSport(sport).find((s) => s.key === wantKey) ?? statsForSport(sport)[0]!;
}

/** Raw season total for a row under a given stat (0 if missing). */
export function statValue(row: SeasonTotalsRow, def: StatDef): number {
  const v = row[def.key];
  return typeof v === 'number' ? v : 0;
}
