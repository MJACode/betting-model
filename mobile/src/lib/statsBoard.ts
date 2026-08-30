/**
 * Pure ranking/filtering logic for the Stats tab leaderboard.
 *
 * Three concerns live here so they behave identically in every sport and in
 * both modes (Hit Rates / Averages), and so they can be verified offline:
 *
 *  1. QUALIFIER — how many games a player needs before they appear at all.
 *     A fixed "3 games" made the Season window useless: a 2-for-6 call-up
 *     outranked a 23-for-81 everyday bat. The qualifier is instead a fraction
 *     of the games the pool leader has played, so it scales with the sport and
 *     with how deep into the season we are (MLB in August ≈ 29 games, a 17-game
 *     NFL season ≈ 4, and an L10 window ≈ 3 — the old default, unchanged).
 *
 *  2. SORT — the board is ordered by the number it displays (hit rate), with
 *     sample size as the tie-break, and the user can switch to games played or
 *     average. Deliberately NOT a shrinkage-adjusted rank: when the visible
 *     column doesn't explain the order, the list reads as broken.
 *
 *  3. TONIGHT — "only players in action". Derived from the `games` table
 *     rather than the MLB/WNBA matchup views, so it works for every sport.
 *
 * Verify with: npx tsx scripts/verify_stats_board.ts
 */

import type { GameRow } from '@/types';

// ── 1. Qualifier ──

/** Share of the pool leader's games a player needs to qualify. */
export const QUALIFIER_SHARE = 0.25;
/** Never demand more than this, however long the season gets. */
export const QUALIFIER_MIN = 2;

/**
 * Auto "min games played" for a pool whose busiest player has `maxGames`.
 * Returns 0 for an empty pool so an in-flight fetch can't hide every row.
 */
export function autoMinGames(maxGames: number): number {
  if (!Number.isFinite(maxGames) || maxGames <= 0) return 0;
  return Math.max(QUALIFIER_MIN, Math.ceil(QUALIFIER_SHARE * maxGames));
}

/** Largest games-played value in the pool (0 when empty). */
export function maxGamesIn(counts: Array<number | null | undefined>): number {
  let max = 0;
  for (const c of counts) if (c != null && Number.isFinite(c) && c > max) max = c;
  return max;
}

// ── 2. Sort ──

export type SortKey = 'default' | 'games' | 'avg';

/** A row reduced to the three numbers any sort needs. */
export interface SortableRow {
  /** Hit rate 0..1 in Hit Rates mode; the ranked stat value in Averages mode. */
  primary: number;
  /** Games behind the number (hit-rate denominator / games played). */
  games: number;
  /** Per-game average of the stat. */
  avg: number;
}

export function compareRows(a: SortableRow, b: SortableRow, key: SortKey): number {
  if (key === 'games') return b.games - a.games || b.primary - a.primary;
  if (key === 'avg') return b.avg - a.avg || b.games - a.games;
  return b.primary - a.primary || b.games - a.games;
}

/** Sheet labels — the primary column means different things per mode. */
export function sortOptionsFor(mode: 'hitRate' | 'totals'): { key: SortKey; label: string }[] {
  return mode === 'hitRate'
    ? [
        { key: 'default', label: 'Hit rate' },
        { key: 'games', label: 'Games played' },
        { key: 'avg', label: 'Average' },
      ]
    : [
        { key: 'default', label: 'Stat value' },
        { key: 'games', label: 'Games played' },
      ];
}

export function sortLabel(key: SortKey, mode: 'hitRate' | 'totals'): string {
  return sortOptionsFor(mode).find((o) => o.key === key)?.label ?? 'Hit rate';
}

// ── 3. Hit-rate band ──

/**
 * Percent bounds the user typed, as a 0..1 band. Blank/garbage → unbounded.
 * An inverted band (min 80, max 60) is normalised rather than emptying the
 * board.
 */
export function hitRateBand(min: string, max: string): { lo: number; hi: number } {
  const parse = (s: string, fallback: number) => {
    const n = parseFloat(s);
    return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) / 100 : fallback;
  };
  const lo = parse(min, 0);
  const hi = parse(max, 1);
  return lo <= hi ? { lo, hi } : { lo: hi, hi: lo };
}

export function inHitRateBand(pct: number, band: { lo: number; hi: number }): boolean {
  // Tolerance absorbs float noise so "min 60" keeps an exact 0.6 (3/5).
  return pct >= band.lo - 1e-9 && pct <= band.hi + 1e-9;
}

/** Quick-pick minimums offered above the numeric fields. */
export const HIT_RATE_PRESETS = [50, 60, 70, 80];

/**
 * Does this player actually PLAY the selected stat?
 *
 * The football player logs span every position, so a kicker has a real row with
 * 0 passing yards in every game — and on an "at most N pass yards" board those
 * non-participants go 15/15 and bury the actual quarterbacks (they'd also pad
 * the bottom of every "at least" board). A player whose value is zero in EVERY
 * loaded game isn't in that stat's market at all, so football boards drop them.
 *
 * FOOTBALL-ONLY on purpose: in the single-role sports a string of zeros is a
 * real outcome of participation — a batter 0-for-his-last-10 genuinely answers
 * "at most 1 hits" and must stay on the board.
 */
const MULTI_ROLE_SPORTS = new Set(['NFL', 'NCAAF']);

export function isStatParticipant(
  sport: string,
  values: Array<number | null | undefined>,
): boolean {
  if (!MULTI_ROLE_SPORTS.has(sport)) return true;
  return values.some((v) => (v ?? 0) !== 0);
}

// ── 4. Tonight's slate ──

export interface TonightSlate {
  /** ET date the slate is for ('' when nothing is scheduled). */
  date: string;
  /** Team abbrevs in action — plus fighter names for UFC, which has no teams. */
  keys: Set<string>;
  /** True when `date` is today (vs the next scheduled day). */
  isToday: boolean;
}

export const EMPTY_SLATE: TonightSlate = { date: '', keys: new Set(), isToday: false };

/**
 * Reduce upcoming games to the slate to filter on: today's games when there
 * are any, otherwise the next scheduled day. Sports that don't play daily
 * (NFL, UFC) would otherwise have a permanently useless toggle.
 *
 * `games` may span several days and sports; both are filtered here.
 */
export function buildTonightSlate(games: GameRow[], sport: string, today: string): TonightSlate {
  const byDate = new Map<string, GameRow[]>();
  for (const g of games) {
    if (g.sport !== sport) continue;
    if (!g.game_date || g.game_date < today) continue;
    const arr = byDate.get(g.game_date);
    if (arr) arr.push(g);
    else byDate.set(g.game_date, [g]);
  }
  if (byDate.size === 0) return EMPTY_SLATE;
  const date = byDate.has(today) ? today : Array.from(byDate.keys()).sort()[0];
  const keys = new Set<string>();
  for (const g of byDate.get(date) ?? []) {
    if (g.home_team) keys.add(g.home_team);
    if (g.away_team) keys.add(g.away_team);
  }
  return { date, keys, isToday: date === today };
}

/**
 * Is this leaderboard row in the slate? Team sports match on the team abbrev
 * (`games.home_team` and every player game log use the same abbrevs). UFC has
 * no team, so its fighters match on display name — which is exactly what a UFC
 * `games` row stores.
 */
export function isOnSlate(
  row: { team?: string | null; player_name?: string | null },
  slate: TonightSlate,
): boolean {
  if (slate.keys.size === 0) return true; // nothing to filter against
  if (row.team && slate.keys.has(row.team)) return true;
  return !!row.player_name && slate.keys.has(row.player_name);
}
