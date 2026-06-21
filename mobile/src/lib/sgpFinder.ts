/**
 * Same-game parlay (SGP) finder — pure logic (no React).
 *
 * The optimizer in parlay.ts enumerates combos across the WHOLE slate and caps
 * the candidate pool by single-leg edge, so genuinely correlated same-game combos
 * — whose value comes from the copula lift, not raw per-leg edge — frequently
 * never surface. This finder fills that gap: it groups today's eligible legs by
 * game, enumerates the within-game combinations, prices each on the Gaussian-
 * copula JOINT probability (parlayCorrelation.ts), and surfaces only the ones
 * that stay +EV after DK's (heavier) parlay hold.
 *
 * Why same-game specifically: positive correlation (two same-team bats, a
 * pitcher's Ks with the game under, an offensive prop with the game over) raises
 * the joint probability ABOVE the naïve product the books often price off — so a
 * combo that looks break-even independently can be genuinely +EV once correlation
 * is accounted for. That edge is the whole differentiator, and it only exists
 * within a single game. Cross-game stacking is already covered by optimizeParlay.
 *
 * Correlation rule is inherited from isValidCombo: at most one game-line leg
 * (ML / spread / total / F5) per game, so we never parlay RL + ML on the same
 * game. Props stack freely and may sit alongside the one game-line leg.
 */

import {
  computeCorrelatedMetrics,
  type CorrelatedMetrics,
  type RhoTable,
  type TeamResolver,
} from '@/lib/parlayCorrelation';
import { computeParlayMetrics, isValidCombo, type ParlayLeg } from '@/lib/parlay';
import type { GameRow } from '@/types';

/** One surfaced same-game parlay: its legs + correlated metrics + matchup. */
export interface SgpCandidate {
  gameId: string;
  game: GameRow | null;
  legs: ParlayLeg[];
  metrics: CorrelatedMetrics;
}

export interface SgpFinderOptions {
  minLegs?: number;
  maxLegs?: number;
  /** Resolves a prop player's team (same/opp stacking). Optional — team-agnostic without it. */
  resolveTeam?: TeamResolver;
  /** Per game, the top-N combos (by cheap independent EV) that get the MC pass. */
  scanPerGame?: number;
  /** Max surfaced combos kept per game (diversity across the slate). */
  perGameLimit?: number;
  /** Overall cap on returned candidates. */
  maxResults?: number;
  /** Monte-Carlo draws per combo (forwarded to the copula engine). */
  draws?: number;
}

export type SgpReason = 'no_eligible' | 'none_positive';

export interface SgpFinderResult {
  candidates: SgpCandidate[]; // +EV only, sorted by correlated EV desc
  gamesConsidered: number; // games with ≥ minLegs eligible legs
  reason?: SgpReason;
}

export const SGP_DEFAULTS = {
  minLegs: 2,
  maxLegs: 3,
  scanPerGame: 40,
  perGameLimit: 2,
  maxResults: 8,
} as const;

/** Group legs by game_id, preserving insertion order. */
function groupByGame(pool: ParlayLeg[]): Map<string, ParlayLeg[]> {
  const groups = new Map<string, ParlayLeg[]>();
  for (const leg of pool) {
    const arr = groups.get(leg.gameId);
    if (arr) arr.push(leg);
    else groups.set(leg.gameId, [leg]);
  }
  return groups;
}

/**
 * All valid combinations of `legs` sized [minK, maxK]. Prunes branches that
 * violate the correlation rule (two game-lines) early, so the recursion only
 * explores legal slips. Per-game leg counts are small, so this is cheap.
 */
function combosWithinGame(legs: ParlayLeg[], minK: number, maxK: number): ParlayLeg[][] {
  const out: ParlayLeg[][] = [];
  const chosen: ParlayLeg[] = [];
  const n = legs.length;

  const recurse = (start: number): void => {
    if (chosen.length >= minK) out.push(chosen.slice());
    if (chosen.length === maxK) return;
    for (let i = start; i < n; i++) {
      // Not enough remaining to reach minK — stop (legs after i are fewer still).
      if (n - i < minK - chosen.length) break;
      chosen.push(legs[i]);
      if (isValidCombo(chosen)) recurse(i + 1); // prune invalid (2 game-lines)
      chosen.pop();
    }
  };

  recurse(0);
  return out;
}

/**
 * Find the slate's best +EV same-game parlays.
 *
 * Pipeline, per game with ≥ minLegs eligible legs:
 *  1. enumerate valid within-game combos (size minLegs..maxLegs),
 *  2. rank by the cheap independent EV and keep the top `scanPerGame` as MC
 *     candidates (bounds the copula cost on leg-rich games — the correlation
 *     lift is small and bounded, so a combo good enough to surface is in the
 *     independent-EV top set),
 *  3. price those on the copula joint probability and keep the +EV ones,
 *  4. keep the best `perGameLimit` per game.
 * Then flatten, sort by correlated EV (correlated combos break ties), and cap.
 */
export function findSameGameParlays(
  pool: ParlayLeg[],
  rhoTable: RhoTable,
  opts: SgpFinderOptions = {},
): SgpFinderResult {
  const minLegs = opts.minLegs ?? SGP_DEFAULTS.minLegs;
  const maxLegs = opts.maxLegs ?? SGP_DEFAULTS.maxLegs;
  const scanPerGame = opts.scanPerGame ?? SGP_DEFAULTS.scanPerGame;
  const perGameLimit = opts.perGameLimit ?? SGP_DEFAULTS.perGameLimit;
  const maxResults = opts.maxResults ?? SGP_DEFAULTS.maxResults;

  const groups = groupByGame(pool);
  let gamesConsidered = 0;
  const surfaced: SgpCandidate[] = [];

  for (const [gameId, legs] of groups) {
    if (legs.length < minLegs) continue;
    gamesConsidered++;

    const combos = combosWithinGame(legs, minLegs, Math.min(maxLegs, legs.length));
    if (combos.length === 0) continue;

    // Cheap independent-EV prefilter → MC only the most promising combos.
    const ranked = combos
      .map((c) => ({ legs: c, indepEv: computeParlayMetrics(c).ev }))
      .sort((a, b) => b.indepEv - a.indepEv)
      .slice(0, scanPerGame);

    const priced: SgpCandidate[] = [];
    for (const { legs: comboLegs } of ranked) {
      const metrics = computeCorrelatedMetrics(comboLegs, rhoTable, opts.resolveTeam, opts.draws);
      if (metrics.ev <= 0) continue; // honest: only surface +EV slips
      priced.push({ gameId, game: comboLegs[0].game, legs: comboLegs, metrics });
    }

    priced.sort(sgpCompare);
    surfaced.push(...priced.slice(0, perGameLimit));
  }

  surfaced.sort(sgpCompare);
  const candidates = surfaced.slice(0, maxResults);

  return {
    candidates,
    gamesConsidered,
    reason: gamesConsidered === 0 ? 'no_eligible' : candidates.length === 0 ? 'none_positive' : undefined,
  };
}

/** Sort by correlated EV desc; genuinely correlated slips win ties (the point). */
function sgpCompare(a: SgpCandidate, b: SgpCandidate): number {
  const d = b.metrics.ev - a.metrics.ev;
  if (Math.abs(d) > 1e-9) return d;
  const corr = Number(b.metrics.hasCorrelation) - Number(a.metrics.hasCorrelation);
  if (corr !== 0) return corr;
  return b.metrics.edgeVsDk - a.metrics.edgeVsDk;
}
