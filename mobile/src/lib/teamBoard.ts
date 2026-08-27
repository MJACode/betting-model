/**
 * Pure ranking + colour logic for the Stats tab's Teams board.
 *
 * Two ideas, both lifted from what the surveyed betting tools do well:
 *
 *  1. TERTILE TINT. Competitors colour a team's number by where it sits in the
 *     league (top third / middle / bottom third) rather than printing a rank
 *     number you then have to interpret. It is the single most glanceable
 *     pattern in the category, and it costs one pass over the column.
 *     Crucially the tint follows the stat's DIRECTION — a low defensive rating
 *     is good, a low Corsi is not — so `better` is required, and stats where
 *     neither end is a virtue (pace, over rate) render uncoloured rather than
 *     implying one.
 *
 *  2. SAMPLE GUARD. A 3-2 ATS split shows as 60% and would top the board on
 *     rate alone. Splits carry their sample, and anything under
 *     MIN_SPLIT_SAMPLE is tinted neutral and flagged — the number is still
 *     shown, it just stops being ranked as if it meant something.
 *
 * Verify with: npx tsx scripts/verify_team_board.ts
 */
import type { TeamStatDef } from '@/lib/teamStatCatalog';
import { teamStatValue } from '@/lib/teamStatCatalog';
import type { TeamStatsRow } from '@/types';

export type Tier = 'good' | 'mid' | 'bad' | 'none';

/**
 * Below this many games a split is shown but not trusted: no tint, and the
 * board marks it. Chosen to be small enough that it only catches genuinely
 * thin cuts (a handful of short-rest spots), not a normal season split.
 */
export const MIN_SPLIT_SAMPLE = 8;

/** Sample behind a stat: its own `sample` column, else games played. */
export function sampleFor(row: TeamStatsRow, def: TeamStatDef): number {
  if (def.sample) {
    const n = teamStatValue(row, { ...def, key: def.sample });
    return n ?? 0;
  }
  const gp = teamStatValue(row, { ...def, key: 'games_played' });
  return gp ?? 0;
}

/** True when this row's value for `def` rests on too few games to rank. */
export function isThinSample(row: TeamStatsRow, def: TeamStatDef): boolean {
  // Only the betting splits carry an explicit sample; a season-long efficiency
  // metric is not "thin" just because the season is young.
  if (!def.sample) return false;
  return sampleFor(row, def) < MIN_SPLIT_SAMPLE;
}

/**
 * Tertile cutoffs for a column. Returns null when there is too little spread
 * to split three ways (every team identical, or fewer than 3 teams), in which
 * case nothing is tinted rather than inventing a ranking.
 */
export function tertileCuts(values: number[]): { lo: number; hi: number } | null {
  const v = values.filter((n) => Number.isFinite(n)).slice().sort((a, b) => a - b);
  if (v.length < 3) return null;
  const at = (q: number) => v[Math.min(v.length - 1, Math.max(0, Math.floor(q * (v.length - 1))))];
  const lo = at(1 / 3);
  const hi = at(2 / 3);
  if (lo === hi) return null; // no spread to speak of
  return { lo, hi };
}

/**
 * Where a value sits in the league, oriented by the stat's direction.
 * 'none' means deliberately uncoloured (no value, no direction, or no spread).
 */
export function tierFor(
  value: number | null,
  cuts: { lo: number; hi: number } | null,
  better: 'high' | 'low' | null,
): Tier {
  if (value == null || cuts == null || better == null) return 'none';
  const topThird = value >= cuts.hi;
  const bottomThird = value <= cuts.lo;
  if (!topThird && !bottomThird) return 'mid';
  if (better === 'high') return topThird ? 'good' : 'bad';
  return bottomThird ? 'good' : 'bad';
}

/**
 * Sort rows by the selected stat, best first. Nulls always sink to the bottom
 * regardless of direction — a team with no value should never lead the board.
 * Ties break on sample size so the better-established number ranks first.
 */
export function compareTeams(a: TeamStatsRow, b: TeamStatsRow, def: TeamStatDef): number {
  const av = teamStatValue(a, def);
  const bv = teamStatValue(b, def);
  if (av == null && bv == null) return (a.team ?? '').localeCompare(b.team ?? '');
  if (av == null) return 1;
  if (bv == null) return -1;
  if (av !== bv) return def.better === 'low' ? av - bv : bv - av;
  return sampleFor(b, def) - sampleFor(a, def);
}

/**
 * Ranked rows plus the tertile cuts for the column, computed once per render.
 * Cuts come from the values actually on the board, so filtering to a
 * conference re-ranks within that conference — which is what a user filtering
 * to the SEC means by "top third".
 */
export function rankTeams(
  rows: TeamStatsRow[],
  def: TeamStatDef,
): { rows: TeamStatsRow[]; cuts: { lo: number; hi: number } | null } {
  const values: number[] = [];
  for (const r of rows) {
    // A thin split is shown but must not distort the league's tertiles.
    if (isThinSample(r, def)) continue;
    const v = teamStatValue(r, def);
    if (v != null) values.push(v);
  }
  return {
    rows: rows.slice().sort((a, b) => compareTeams(a, b, def)),
    cuts: tertileCuts(values),
  };
}
