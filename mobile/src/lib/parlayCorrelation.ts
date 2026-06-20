/**
 * Correlation-aware parlay math — Gaussian-copula Monte-Carlo joint probability.
 *
 * The naive parlay model in parlay.ts multiplies leg probabilities (`Π p`),
 * which assumes every leg is statistically independent. That is correct for legs
 * in different games (or different sports), but WRONG for same-game legs that move
 * together: a batter going over on hits and the game total going over are
 * positively correlated; a pitcher's strikeouts over and the game total under are
 * positively correlated; a pitcher's strikeouts over and an opposing batter's
 * hits over are negatively correlated. Sportsbooks price this ("the correlation
 * tax"); a naive product over/under-states the true joint probability and mis-
 * grades the parlay.
 *
 * Approach (per the approved plan):
 *  1. Each leg maps to a market class (markets.ts) + an "offense axis" polarity
 *     (+1 = bets on more offense in the game, −1 = less, 0 = offense-neutral).
 *  2. A pairwise correlation ρ between two same-game legs = a canonical magnitude
 *     for that (sport, class-pair) — looked up in PARLAY_CORRELATION_PRIORS, later
 *     overlaid by empirical estimates — times the two legs' polarities (the
 *     sign-flip rule). Different game → ρ = 0.
 *  3. Build the legs' correlation matrix, repair to positive-definite (shrink
 *     toward identity), Cholesky-factor it, and Monte-Carlo a Gaussian copula:
 *     each draw produces correlated standard normals → uniforms via Φ → a leg
 *     "hits" iff its uniform < its marginal model probability. jointProb =
 *     fraction of draws where all legs hit.
 *
 * When all ρ are 0 (every leg in a different game / sport, or offense-neutral)
 * we SHORT-CIRCUIT to the exact `Π p` — so cross-game and cross-sport parlays
 * reproduce today's math exactly and stay deterministic.
 *
 * Phase 1 ships with bundled priors only and does NOT resolve a prop leg's team
 * (picks carry no team column), so same-team-vs-opposing offensive stacking is
 * not yet distinguished — same-game offensive props get a small positive prior,
 * and game-line legs (ML/spread) are offense-neutral. Team-aware coefficients +
 * empirical estimates land in Phase 2.
 */

import { marketClassForModel, type MarketClass } from '@/lib/markets';
import type { ParlayLeg, ParlayMetrics } from '@/lib/parlay';

/** Number of Monte-Carlo draws per joint-probability estimate (±~1pp SE). */
export const MC_DRAWS = 10000;

/** ρ table: relationship key → coefficient. See `classPairKey`. */
export type RhoTable = Record<string, number>;

/** Resolves a prop leg's player_id to its team abbreviation (or null). Used to
 * tell same-team from opposing offensive stacking. Undefined → team-unaware
 * (Phase-1 behavior): same-game prop pairs fall back to the 'na' bucket. */
export type TeamResolver = (playerId: string) => string | null;

export type ParlayGrade = 'great' | 'good' | 'fair' | 'bad';

/** Correlated-EV grade cutoffs (per-$1 EV on the joint probability). */
export const PARLAY_GRADE_THRESHOLDS = { great: 0.1, good: 0.03, fair: -0.03 } as const;

export function gradeForEv(ev: number): ParlayGrade {
  if (ev >= PARLAY_GRADE_THRESHOLDS.great) return 'great';
  if (ev >= PARLAY_GRADE_THRESHOLDS.good) return 'good';
  if (ev >= PARLAY_GRADE_THRESHOLDS.fair) return 'fair';
  return 'bad';
}

export const GRADE_LABEL: Record<ParlayGrade, string> = {
  great: 'Great',
  good: 'Good',
  fair: 'Fair',
  bad: 'Bad',
};

/**
 * Canonical correlation magnitudes for the "+offense × +offense" orientation of a
 * (sport, class-pair). The actual ρ is this × polarity_a × polarity_b, so the
 * over/under and suppress/allow sides flip the sign automatically. Class pair is
 * stored lexicographically so lookups are order-independent (see classPairKey).
 *
 * Phase-1 values are priors (signs from sport structure, magnitudes deliberately
 * modest). Phase 2 overlays `source='empirical'` rows where data is abundant.
 */
/**
 * Bundled correlation priors, keyed `sport|classA|classB|teamRel` (classes
 * lexicographically ordered; teamRel ∈ 'same' | 'opp' | 'na'). These are the
 * offline fallback; `source='empirical'` rows from the `parlay_correlations`
 * table overlay them at runtime (see useParlayCorrelations). A pair falls back
 * to its 'na' bucket when the team relationship can't be resolved.
 */
export const PARLAY_CORRELATION_PRIORS: RhoTable = {
  // MLB — overlaid by empirical rows where available.
  'MLB|game_total|off_prop|na': 0.12, // a hitter producing ↔ the game total
  'MLB|game_total|pitching_prop|na': 0.13, // run suppression ↔ the game total
  'MLB|off_prop|off_prop|same': 0.05, // same-team bats in a shared run environment
  'MLB|off_prop|off_prop|opp': 0.01, // opposing bats — nearly independent
  'MLB|off_prop|off_prop|na': 0.03,
  'MLB|off_prop|pitching_prop|opp': 0.07, // pitcher dominance vs an OPPOSING hitter
  'MLB|off_prop|pitching_prop|same': 0.0, // a pitcher's own hitters — ~independent
  'MLB|off_prop|pitching_prop|na': 0.03,
  'MLB|pitching_prop|pitching_prop|same': 0.15, // same start's K / outs / hits-allowed
  'MLB|pitching_prop|pitching_prop|na': 0.05,
  // NBA / WNBA — scorers share game pace; totals models are rarely priced yet.
  'NBA|game_total|off_prop|na': 0.1,
  'NBA|off_prop|off_prop|same': 0.06,
  'NBA|off_prop|off_prop|opp': 0.02,
  'NBA|off_prop|off_prop|na': 0.04,
  'WNBA|game_total|off_prop|na': 0.1,
  'WNBA|off_prop|off_prop|same': 0.06,
  'WNBA|off_prop|off_prop|opp': 0.02,
  'WNBA|off_prop|off_prop|na': 0.04,
  // NHL — light shared-environment prior.
  'NHL|game_total|off_prop|na': 0.06,
  'NHL|off_prop|off_prop|same': 0.05,
  'NHL|off_prop|off_prop|opp': 0.02,
  'NHL|off_prop|off_prop|na': 0.04,
};

export type TeamRel = 'same' | 'opp' | 'na';

/** Order-independent key for a (sport, class-pair, team relationship). */
export function classPairKey(sport: string, a: MarketClass, b: MarketClass, rel: TeamRel): string {
  const [lo, hi] = a <= b ? [a, b] : [b, a];
  return `${sport}|${lo}|${hi}|${rel}`;
}

interface LegAttrs {
  pickId: number;
  gameId: string;
  sport: string;
  marketClass: MarketClass;
  /** +1 bets on more offense, −1 on less, 0 offense-neutral (no modeled corr). */
  polarity: -1 | 0 | 1;
  /** Player's team abbrev for a prop leg (else null) — drives same/opp. */
  team: string | null;
}

const PROP_CLASSES: ReadonlySet<MarketClass> = new Set<MarketClass>(['off_prop', 'pitching_prop']);

/** Team relationship between two legs: same/opp only when both are player props
 * with resolvable teams; otherwise 'na' (game-level legs are team-agnostic here). */
function teamRelFor(a: LegAttrs, b: LegAttrs): TeamRel {
  if (!PROP_CLASSES.has(a.marketClass) || !PROP_CLASSES.has(b.marketClass)) return 'na';
  if (a.team == null || b.team == null) return 'na';
  return a.team === b.team ? 'same' : 'opp';
}

/** Offense-axis polarity for a leg: which way its win roots on game scoring. */
function offensePolarity(leg: ParlayLeg, cls: MarketClass): -1 | 0 | 1 {
  const side = leg.pick?.pick_side; // 'over' | 'under' | 'home' | 'away' | 'draw' | undefined
  if (cls === 'game_total') return side === 'under' ? -1 : 1; // over = more offense
  if (cls === 'off_prop') return side === 'under' ? -1 : 1;
  if (cls === 'pitching_prop') {
    // Ks / outs over = suppression (less offense); hits-allowed / ER / walks over = more offense.
    const suppresses = leg.modelId.includes('_k') || leg.modelId.includes('_outs');
    const base: -1 | 1 = suppresses ? -1 : 1;
    return side === 'under' ? ((-base) as -1 | 1) : base;
  }
  return 0; // game_ml / game_spread / other / custom — offense-neutral in Phase 1
}

function legAttrs(leg: ParlayLeg, resolveTeam?: TeamResolver): LegAttrs {
  const cls = marketClassForModel(leg.modelId);
  const playerId = leg.pick?.player_id ?? null;
  const team = playerId && resolveTeam ? resolveTeam(playerId) : null;
  return {
    pickId: leg.pickId,
    gameId: leg.gameId,
    sport: leg.pick?.sport ?? leg.game?.sport ?? '',
    marketClass: cls,
    polarity: offensePolarity(leg, cls),
    team,
  };
}

/** Pairwise correlation between two legs (0 when independent). */
function pairRho(a: LegAttrs, b: LegAttrs, table: RhoTable): number {
  if (a.pickId === b.pickId) return 0;
  if (a.gameId !== b.gameId) return 0; // different game / sport → independent
  if (a.polarity === 0 || b.polarity === 0) return 0; // an offense-neutral leg
  const rel = teamRelFor(a, b);
  // Prefer the specific team-relationship bucket; fall back to 'na' when missing.
  const base =
    table[classPairKey(a.sport, a.marketClass, b.marketClass, rel)] ??
    table[classPairKey(a.sport, a.marketClass, b.marketClass, 'na')] ??
    0;
  const rho = base * a.polarity * b.polarity;
  return Math.max(-0.6, Math.min(0.6, rho)); // clamp — thin signal, keep it sane
}

function buildCorrelationMatrix(attrs: LegAttrs[], table: RhoTable): number[][] {
  const n = attrs.length;
  const m: number[][] = Array.from({ length: n }, () => new Array<number>(n).fill(0));
  for (let i = 0; i < n; i++) {
    m[i][i] = 1;
    for (let j = i + 1; j < n; j++) {
      const r = pairRho(attrs[i], attrs[j], table);
      m[i][j] = r;
      m[j][i] = r;
    }
  }
  return m;
}

function hasOffDiagonal(m: number[][]): boolean {
  for (let i = 0; i < m.length; i++) {
    for (let j = 0; j < i; j++) {
      if (Math.abs(m[i][j]) > 1e-9) return true;
    }
  }
  return false;
}

/** Lower-triangular Cholesky factor, or null if not positive-definite. */
function cholesky(m: number[][]): number[][] | null {
  const n = m.length;
  const L: number[][] = Array.from({ length: n }, () => new Array<number>(n).fill(0));
  for (let i = 0; i < n; i++) {
    for (let j = 0; j <= i; j++) {
      let sum = m[i][j];
      for (let k = 0; k < j; k++) sum -= L[i][k] * L[j][k];
      if (i === j) {
        if (sum <= 1e-12) return null; // not PD
        L[i][j] = Math.sqrt(sum);
      } else {
        L[i][j] = sum / L[j][j];
      }
    }
  }
  return L;
}

/**
 * Cholesky factor of `m`, repairing a non-PD matrix by shrinking toward the
 * identity (M' = (1−ε)M + εI). Shrinkage attenuates correlation toward
 * independence — the safe direction — and always terminates for small matrices.
 */
function choleskyWithShrink(m: number[][]): number[][] {
  const direct = cholesky(m);
  if (direct) return direct;
  const n = m.length;
  for (const eps of [0.05, 0.1, 0.2, 0.4, 0.8]) {
    const shrunk = m.map((row, i) => row.map((v, j) => (i === j ? 1 : (1 - eps) * v)));
    const L = cholesky(shrunk);
    if (L) return L;
  }
  // Fallback: identity (full independence).
  return Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => (i === j ? 1 : 0)),
  );
}

// ── RNG + normal helpers ─────────────────────────────────────────────────────

/** Deterministic per-slip seed from the (order-independent) leg id set. */
function seedFromLegs(legs: ParlayLeg[]): number {
  let h = 2166136261 >>> 0;
  for (const id of [...legs.map((l) => l.pickId)].sort((a, b) => a - b)) {
    h ^= id & 0xffff;
    h = Math.imul(h, 16777619) >>> 0;
  }
  return h >>> 0;
}

/** mulberry32 — small, fast, seedable PRNG → no grade flicker between renders. */
function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Box–Muller: fill an array with `n` iid standard normals. */
function drawNormals(n: number, rng: () => number): number[] {
  const out = new Array<number>(n);
  for (let i = 0; i < n; i += 2) {
    let u1 = rng();
    const u2 = rng();
    if (u1 < 1e-12) u1 = 1e-12;
    const r = Math.sqrt(-2 * Math.log(u1));
    const theta = 2 * Math.PI * u2;
    out[i] = r * Math.cos(theta);
    if (i + 1 < n) out[i + 1] = r * Math.sin(theta);
  }
  return out;
}

/** Standard-normal CDF via the Abramowitz & Stegun 7.1.26 erf approximation. */
function normalCdf(x: number): number {
  const z = x / Math.SQRT2;
  const t = 1 / (1 + 0.3275911 * Math.abs(z));
  const y =
    1 -
    ((((1.061405429 * t - 1.453152027) * t + 1.421413741) * t - 0.284496736) * t + 0.254829592) *
      t *
      Math.exp(-z * z);
  const erf = z >= 0 ? y : -y;
  return 0.5 * (1 + erf);
}

function clampProb(p: number): number {
  if (!Number.isFinite(p)) return 0.5;
  return Math.max(1e-6, Math.min(1 - 1e-6, p));
}

/**
 * Joint probability that ALL legs hit, accounting for same-game correlation.
 * Returns `hasCorrelation: false` (and the exact `Π p`) when no leg pair is
 * correlated — the deterministic short-circuit that keeps cross-game/cross-sport
 * parlays identical to the independent model.
 */
export function correlatedJointProb(
  legs: ParlayLeg[],
  table: RhoTable,
  resolveTeam?: TeamResolver,
  draws = MC_DRAWS,
): { jointProb: number; hasCorrelation: boolean } {
  if (legs.length === 0) return { jointProb: 1, hasCorrelation: false };
  const probs = legs.map((l) => clampProb(l.modelProb));
  const independent = probs.reduce((a, p) => a * p, 1);

  const matrix = buildCorrelationMatrix(legs.map((l) => legAttrs(l, resolveTeam)), table);
  if (!hasOffDiagonal(matrix)) return { jointProb: independent, hasCorrelation: false };

  const L = choleskyWithShrink(matrix);
  const rng = mulberry32(seedFromLegs(legs));
  const n = legs.length;
  let hits = 0;
  for (let d = 0; d < draws; d++) {
    const z = drawNormals(n, rng);
    let all = true;
    for (let i = 0; i < n; i++) {
      let x = 0;
      for (let j = 0; j <= i; j++) x += L[i][j] * z[j];
      if (normalCdf(x) >= probs[i]) {
        all = false;
        break;
      }
    }
    if (all) hits++;
  }
  return { jointProb: hits / draws, hasCorrelation: true };
}

// ── Correlated metrics ───────────────────────────────────────────────────────

export interface CorrelatedMetrics extends ParlayMetrics {
  /** Correlated P(all hit) — also mirrored into ParlayMetrics.parlayProb. */
  jointProb: number;
  /** Naive Π p, for the "correlation lift" delta shown in the UI. */
  independentProb: number;
  /** True when at least one leg pair is correlated (MC ran; not a Π p short-circuit). */
  hasCorrelation: boolean;
  /** Fair (no-vig) odds implied by jointProb. */
  fairDecimal: number;
  fairAmerican: number;
  /** DK's hold on this slip: 1 − jointProb × decimalPayout (positive = book edge). */
  dkHoldPct: number;
  grade: ParlayGrade;
}

function decimalToAmericanLocal(decimal: number): number {
  if (!Number.isFinite(decimal) || decimal <= 1) return 0;
  if (decimal >= 2) return (decimal - 1) * 100;
  return -100 / (decimal - 1);
}

/**
 * Parlay metrics computed on the CORRELATED joint probability. The inherited
 * ParlayMetrics fields (parlayProb / ev / edgeVsDk / kellyFraction) reflect the
 * correlated estimate so existing UI bound to them shows correlated numbers;
 * `independentProb` is kept alongside for the lift delta.
 */
export function computeCorrelatedMetrics(
  legs: ParlayLeg[],
  table: RhoTable,
  resolveTeam?: TeamResolver,
  draws = MC_DRAWS,
): CorrelatedMetrics {
  let decimalPayout = 1;
  for (const l of legs) decimalPayout *= l.decimalOdds;
  const { jointProb, hasCorrelation } = correlatedJointProb(legs, table, resolveTeam, draws);
  const independentProb = legs.reduce((a, l) => a * clampProb(l.modelProb), 1);

  const dkImpliedProb = decimalPayout > 0 ? 1 / decimalPayout : 0;
  const b = decimalPayout - 1;
  const q = 1 - jointProb;
  const kellyFraction = b > 0 ? Math.max(0, (b * jointProb - q) / b) : 0;
  const ev = jointProb * decimalPayout - 1;
  const fairDecimal = jointProb > 0 ? 1 / jointProb : Infinity;

  return {
    parlayProb: jointProb,
    decimalPayout,
    americanOdds: decimalToAmericanLocal(decimalPayout),
    ev,
    dkImpliedProb,
    edgeVsDk: jointProb - dkImpliedProb,
    kellyFraction,
    jointProb,
    independentProb,
    hasCorrelation,
    fairDecimal,
    fairAmerican: decimalToAmericanLocal(fairDecimal),
    dkHoldPct: 1 - jointProb * decimalPayout,
    grade: gradeForEv(ev),
  };
}
