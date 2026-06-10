/**
 * Parlay builder — pure logic (no React).
 *
 * Builds an optimized parlay from today's BET picks. A parlay combines several
 * independent legs into one wager: all must hit. We multiply the per-leg decimal
 * odds for the payout and the per-leg model probabilities for our win estimate,
 * then maximize Expected Value = parlayProb × decimalPayout − 1.
 *
 * Correlation rule: at most ONE game-line leg (moneyline / runline / over-under /
 * F5 / WNBA ml-ou-spread — i.e. MODEL_META[id].type === 'game') per game_id.
 * Props may stack freely within a game and may combine with the one game-line leg.
 * So RL + ML in the same game is never allowed; ML + multiple same-game props is.
 *
 * All numbers are pure functions of the leg array, so the screen's remove/swap
 * edits recompute everything synchronously.
 */

import { americanToDecimal } from '@/lib/format';
import { effectiveKellyFraction, KELLY_MULTIPLIER, type KellySizingOpts } from '@/lib/thresholds';
import { MODEL_META } from '@/lib/modelMeta';
import type { Sport } from '@/hooks/useSportFilter';
import type { EnrichedPick, GameRow, Pick } from '@/types';

export type ParlayStyle = 'favorites' | 'balanced' | 'underdog';

export interface ParlayConstraints {
  legs: number; // target leg count (clamped 2–6)
  style: ParlayStyle;
  minAmerican: number | null; // combined-odds floor (American), e.g. +200
  maxAmerican: number | null; // combined-odds ceiling (American), e.g. +2000
}

/** One eligible candidate / chosen leg. Wraps a Pick with precomputed fields. */
export interface ParlayLeg {
  pickId: number; // pick.pick_id — stable key
  gameId: string; // pick.game_id — correlation grouping
  modelId: string;
  isGameLine: boolean; // MODEL_META[modelId].type === 'game'
  isFavorite: boolean; // dk_odds < 0
  label: string; // pick.pick_label
  modelProb: number; // pick.model_probability
  decimalOdds: number; // americanToDecimal(dk_odds)
  americanOdds: number; // dk_odds (non-null, validated)
  legEdge: number; // pick.edge — single-leg edge, used for pool ranking
  pick: Pick | null; // original Pick; null for user-entered custom legs
  game: GameRow | null; // matchup for the leg card
}

export interface ParlayMetrics {
  parlayProb: number; // Π modelProb
  decimalPayout: number; // Π decimalOdds
  americanOdds: number; // combined, converted back to American
  ev: number; // parlayProb × decimalPayout − 1
  dkImpliedProb: number; // 1 / decimalPayout
  edgeVsDk: number; // parlayProb − dkImpliedProb
  kellyFraction: number; // full Kelly f (pre-multiplier), clamped ≥ 0
}

export interface Parlay {
  legs: ParlayLeg[];
  metrics: ParlayMetrics;
}

export type ParlayReason = 'no_eligible' | 'too_few_legs' | 'no_combo_in_range';

export interface ParlayResult {
  best: Parlay | null;
  alternatives: Parlay[]; // next-best, distinct leg sets
  poolSize: number; // eligible candidates after filtering
  reason?: ParlayReason;
}

export const MIN_LEGS = 2;
export const MAX_LEGS = 6;
/** modelId sentinel for user-entered custom legs (not a real model). */
export const CUSTOM_MODEL_ID = 'custom';
/** Cap on the candidate pool fed to enumeration — keeps the combinatorics bounded. */
export const POOL_CAP = 20;
/** Style bonus added to a candidate's pool-ranking score when its sign matches. */
const STYLE_BONUS = 0.05;

/** Decimal odds (>1) back to American. Inverse of americanToDecimal. */
export function decimalToAmerican(decimal: number): number {
  if (decimal >= 2) return (decimal - 1) * 100;
  return -100 / (decimal - 1);
}

function isGameLineModel(modelId: string): boolean {
  return MODEL_META[modelId]?.type === 'game';
}

/**
 * (a) Build the eligible candidate pool from today's enriched picks.
 *
 * Only `signal_type === 'BET'` picks for the active sport (the looser filter,
 * NOT passesActionFilter). Picks with null dk_odds are excluded — HR / F5 and
 * other prob-only markets (see PROB_ONLY_MODELS in thresholds.ts) have no DK
 * price, so their decimal payout is undefined and they can't size a parlay leg.
 */
export function buildCandidatePool(picks: EnrichedPick[], sport: Sport): ParlayLeg[] {
  const pool: ParlayLeg[] = [];
  for (const ep of picks) {
    if (ep.pick.sport !== sport) continue;
    if (ep.pick.signal_type !== 'BET') continue;
    const leg = legFromPick(ep);
    if (leg) pool.push(leg);
  }
  return pool;
}

/**
 * Map a single enriched pick to a parlay leg, or null when it can't size one
 * (no DK price — prob-only HR/F5 markets). No sport / signal filter here, so
 * manual building (resolveSlipLegs) can use any pick the user selected.
 */
export function legFromPick(ep: EnrichedPick): ParlayLeg | null {
  const p = ep.pick;
  if (p.dk_odds == null) return null; // prob-only — no payout
  return {
    pickId: p.pick_id,
    gameId: p.game_id,
    modelId: p.model_id,
    isGameLine: isGameLineModel(p.model_id),
    isFavorite: p.dk_odds < 0,
    label: p.pick_label,
    modelProb: p.model_probability,
    decimalOdds: americanToDecimal(p.dk_odds),
    americanOdds: p.dk_odds,
    legEdge: p.edge,
    pick: p,
    game: ep.game,
  };
}

/**
 * Resolve a manual slip (ordered pick_ids) against today's picks. Any priced
 * pick is eligible — BET/AVOID/NONE, MLB or WNBA (legs are independent, so a
 * mixed-sport parlay is fine). Ids with no matching priced pick today (settled,
 * de-listed, or now prob-only) are returned in `missingIds` so the UI can flag
 * and clear them. Legs come back in slip order.
 */
export function resolveSlipLegs(
  picks: EnrichedPick[],
  ids: number[],
): { legs: ParlayLeg[]; missingIds: number[] } {
  const byId = new Map<number, ParlayLeg>();
  for (const ep of picks) {
    const leg = legFromPick(ep);
    if (leg) byId.set(leg.pickId, leg);
  }
  const legs: ParlayLeg[] = [];
  const missingIds: number[] = [];
  for (const id of ids) {
    const leg = byId.get(id);
    if (leg) legs.push(leg);
    else missingIds.push(id);
  }
  return { legs, missingIds };
}

/** (b) Pure metric calculation for an arbitrary leg set. */
export function computeParlayMetrics(legs: ParlayLeg[]): ParlayMetrics {
  let parlayProb = 1;
  let decimalPayout = 1;
  for (const l of legs) {
    parlayProb *= l.modelProb;
    decimalPayout *= l.decimalOdds;
  }
  const dkImpliedProb = decimalPayout > 0 ? 1 / decimalPayout : 0;
  const b = decimalPayout - 1;
  const p = parlayProb;
  const q = 1 - p;
  const kellyFraction = b > 0 ? Math.max(0, (b * p - q) / b) : 0;
  return {
    parlayProb,
    decimalPayout,
    americanOdds: decimalToAmerican(decimalPayout),
    ev: parlayProb * decimalPayout - 1,
    dkImpliedProb,
    edgeVsDk: parlayProb - dkImpliedProb,
    kellyFraction,
  };
}

/** Correlation guard: ≤ 1 game-line leg per game_id (props stack freely). */
export function isValidCombo(legs: ParlayLeg[]): boolean {
  const gameLinesPerGame = new Map<string, number>();
  for (const l of legs) {
    if (!l.isGameLine) continue;
    const n = (gameLinesPerGame.get(l.gameId) ?? 0) + 1;
    if (n > 1) return false;
    gameLinesPerGame.set(l.gameId, n);
  }
  return true;
}

/**
 * (3) Parlay Kelly sizing. `metrics.kellyFraction` is FULL Kelly; we pre-scale
 * by KELLY_MULTIPLIER (0.10) so a parlay defaults to tenth-Kelly — matching the
 * single-pick path, where the server already stored tenth-Kelly in
 * pick.kelly_fraction. The user's multiplier + cap then apply identically on top
 * (multiplier 1.0 = tenth-Kelly; 2.5 ≈ quarter-Kelly; 10 = full Kelly).
 */
export function parlayRecommendedBet(
  metrics: ParlayMetrics,
  bankroll: number,
  opts: KellySizingOpts,
): number {
  const f = effectiveKellyFraction(metrics.kellyFraction * KELLY_MULTIPLIER, opts);
  return Math.round(f * bankroll * 100) / 100;
}

/** Style-aware pool ranking: bias which legs even enter enumeration. */
function styleScore(leg: ParlayLeg, style: ParlayStyle): number {
  if (style === 'favorites') return leg.legEdge + (leg.isFavorite ? STYLE_BONUS : 0);
  if (style === 'underdog') return leg.legEdge + (!leg.isFavorite ? STYLE_BONUS : 0);
  return leg.legEdge; // balanced — no sign bias
}

function styleRankAndCap(pool: ParlayLeg[], style: ParlayStyle, cap: number): ParlayLeg[] {
  return [...pool]
    .sort((a, b) => {
      const d = styleScore(b, style) - styleScore(a, style);
      if (d !== 0) return d;
      return b.modelProb - a.modelProb; // tiebreak
    })
    .slice(0, cap);
}

/**
 * Enumerate all valid k-combinations of `pool`, returning every parlay whose
 * combined decimal payout falls within [minDec, maxDec]. Pass null bounds to
 * ignore the odds range. Pruned on the correlation rule and the odds ceiling
 * (decimal product is monotonic, so once it exceeds maxDec the branch is dead).
 */
function enumerateCombos(
  pool: ParlayLeg[],
  k: number,
  minDec: number | null,
  maxDec: number | null,
): Parlay[] {
  const out: Parlay[] = [];
  const chosen: ParlayLeg[] = [];

  const recurse = (start: number, runningDecimal: number): void => {
    if (chosen.length === k) {
      const metrics = computeParlayMetrics(chosen);
      if (minDec != null && metrics.decimalPayout < minDec) return;
      if (maxDec != null && metrics.decimalPayout > maxDec) return;
      out.push({ legs: chosen.slice(), metrics });
      return;
    }
    for (let i = start; i < pool.length; i++) {
      const cand = pool[i];
      // Not enough remaining candidates to reach k.
      if (pool.length - i < k - chosen.length) break;
      // Correlation prune: one game-line per game_id.
      if (
        cand.isGameLine &&
        chosen.some((l) => l.isGameLine && l.gameId === cand.gameId)
      ) {
        continue;
      }
      const nextDecimal = runningDecimal * cand.decimalOdds;
      // Odds-ceiling prune: product only grows as legs are added.
      if (maxDec != null && nextDecimal > maxDec) continue;
      chosen.push(cand);
      recurse(i + 1, nextDecimal);
      chosen.pop();
    }
  };

  recurse(0, 1);
  return out;
}

/** Pick up to `count` distinct alternatives that differ from `best`. */
function pickAlternatives(sorted: Parlay[], count: number): Parlay[] {
  // All enumerated combos are unique leg-sets, so slicing past the best is
  // already distinct. Keep it simple and stable.
  return sorted.slice(1, 1 + count);
}

/** (c) The optimizer. Exact bounded brute-force — at pool≤20 / legs 2–6 the
 * worst case (~C(20,6)≈39k combos) is sub-10ms. */
export function optimizeParlay(pool: ParlayLeg[], constraints: ParlayConstraints): ParlayResult {
  const k = Math.max(MIN_LEGS, Math.min(MAX_LEGS, Math.round(constraints.legs)));

  if (pool.length === 0) {
    return { best: null, alternatives: [], poolSize: 0, reason: 'no_eligible' };
  }
  if (pool.length < k) {
    return { best: null, alternatives: [], poolSize: pool.length, reason: 'too_few_legs' };
  }

  const capped = styleRankAndCap(pool, constraints.style, POOL_CAP);
  const minDec = constraints.minAmerican != null ? americanToDecimal(constraints.minAmerican) : null;
  const maxDec = constraints.maxAmerican != null ? americanToDecimal(constraints.maxAmerican) : null;

  const results = enumerateCombos(capped, k, minDec, maxDec);

  if (results.length === 0) {
    // Re-run without the odds range to distinguish the cause.
    const relaxed = enumerateCombos(capped, k, null, null);
    const reason: ParlayReason = relaxed.length > 0 ? 'no_combo_in_range' : 'too_few_legs';
    return { best: null, alternatives: [], poolSize: pool.length, reason };
  }

  results.sort((a, b) => {
    const d = b.metrics.ev - a.metrics.ev;
    if (d !== 0) return d;
    return b.metrics.edgeVsDk - a.metrics.edgeVsDk; // tiebreak
  });

  return {
    best: results[0],
    alternatives: pickAlternatives(results, 3),
    poolSize: pool.length,
  };
}

// ── Custom legs (user-entered) ───────────────────────────────────────────────

/** Monotonically decreasing synthetic id source. Real pick_ids are positive DB
 * ints, so negative ids never collide and the decrement guarantees uniqueness. */
let customLegSeq = -1;

/**
 * Build a hand-entered leg from a description + American odds. Win probability is
 * the odds-implied probability (1 / decimal), so a custom leg is fair-value: it
 * leaves the parlay's EV unchanged and shrinks the combined edge proportionally.
 * isGameLine is false, so custom legs stack freely and never trip correlation.
 */
export function makeCustomLeg(label: string, americanOdds: number): ParlayLeg {
  const decimalOdds = americanToDecimal(americanOdds);
  const modelProb = decimalOdds > 0 ? 1 / decimalOdds : 0; // odds-implied
  const pickId = customLegSeq--;
  return {
    pickId,
    gameId: `custom:${pickId}`, // unique; correlation never groups custom legs anyway
    modelId: CUSTOM_MODEL_ID,
    isGameLine: false,
    isFavorite: americanOdds < 0,
    label: label.trim(),
    modelProb,
    decimalOdds,
    americanOdds,
    legEdge: 0,
    pick: null,
    game: null,
  };
}

// ── Edit helpers (pure) ──────────────────────────────────────────────────────

/** Remove a leg by pickId; recompute metrics on the remainder. */
export function removeLeg(parlay: Parlay, pickId: number): Parlay {
  const legs = parlay.legs.filter((l) => l.pickId !== pickId);
  return { legs, metrics: computeParlayMetrics(legs) };
}

/** Append a leg; recompute metrics. */
export function addLeg(parlay: Parlay, leg: ParlayLeg): Parlay {
  const legs = [...parlay.legs, leg];
  return { legs, metrics: computeParlayMetrics(legs) };
}

/**
 * Candidates the user may swap a slot to: pool legs not already in the parlay
 * that keep the combo valid when substituted, ranked by resulting parlay EV.
 */
export function swapCandidatesFor(
  parlay: Parlay,
  pool: ParlayLeg[],
  replacePickId: number,
  _constraints: ParlayConstraints,
): ParlayLeg[] {
  const inParlay = new Set(parlay.legs.map((l) => l.pickId));
  const remaining = parlay.legs.filter((l) => l.pickId !== replacePickId);
  const scored: { leg: ParlayLeg; ev: number }[] = [];
  for (const cand of pool) {
    if (inParlay.has(cand.pickId)) continue;
    const trial = [...remaining, cand];
    if (!isValidCombo(trial)) continue;
    scored.push({ leg: cand, ev: computeParlayMetrics(trial).ev });
  }
  scored.sort((a, b) => b.ev - a.ev);
  return scored.map((s) => s.leg);
}

/** Replace one leg with another; recompute metrics. */
export function applySwap(parlay: Parlay, replacePickId: number, withLeg: ParlayLeg): Parlay {
  const legs = parlay.legs.map((l) => (l.pickId === replacePickId ? withLeg : l));
  return { legs, metrics: computeParlayMetrics(legs) };
}
