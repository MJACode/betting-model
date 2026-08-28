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
import { stakeFor, effectiveKellyFraction, isUnlockedPreview, KELLY_MULTIPLIER,
         type KellySizingOpts, type UnitStake } from '@/lib/thresholds';
import { linkForSide, priceForSide, MODEL_BOOK } from '@/lib/markets';
import { MODEL_META } from '@/lib/modelMeta';
import {
  computeCorrelatedMetrics,
  type CorrelatedMetrics,
  type RhoTable,
  type TeamResolver,
} from '@/lib/parlayCorrelation';
import type { Sport } from '@/hooks/useSportFilter';
import type { EnrichedPick, GameRow, Pick } from '@/types';

export type ParlayStyle = 'favorites' | 'balanced' | 'underdog';

export interface ParlayConstraints {
  legs: number; // target leg count (clamped 2–6)
  style: ParlayStyle;
  minAmerican: number | null; // combined-odds floor (American), e.g. +200
  maxAmerican: number | null; // combined-odds ceiling (American), e.g. +2000
}

/** Best across-book price for a leg's side (line shopping). Present only when a
 * non-DK book strictly beats DK for this side (game markets only — props aren't
 * shopped). The DK price stays in decimalOdds/americanOdds; this is the upside. */
export interface BestBookPrice {
  bookmaker: string; // raw key, e.g. 'fanduel' — UI maps to a label
  american: number;
  decimal: number;
  link: string | null;
}

/** One NON-DraftKings book's latest price for a leg's side. DraftKings is
 * deliberately absent: the DK number a leg uses is ALWAYS the STORED
 * `dk_odds` the model scored against (the displayQuoteForPick convention),
 * never a fresher snapshot — so the pricing helpers read it off the leg
 * itself rather than a row here. */
export interface LegBookPrice {
  bookmaker: string;
  american: number;
  decimal: number;
  link: string | null;
}

/** One eligible candidate / chosen leg. Wraps a Pick with precomputed fields. */
export interface ParlayLeg {
  pickId: number; // pick.pick_id — SESSION id only; the picks table is delete+
  //               rescored every refresh, so this is NOT stable across runs.
  //               Used for React keys, removeLeg, swap within one session.
  slipKey: string; // game_id|model_id|player_id — STABLE across refreshes; what
  //                 the persisted parlay slip stores (see slipKeyForPick).
  gameId: string; // pick.game_id — correlation grouping
  modelId: string;
  isGameLine: boolean; // MODEL_META[modelId].type === 'game'
  isFavorite: boolean; // dk_odds < 0
  label: string; // pick.pick_label
  modelProb: number; // pick.model_probability
  decimalOdds: number; // americanToDecimal(dk_odds)
  americanOdds: number; // dk_odds (non-null, validated)
  legEdge: number; // pick.edge — single-leg edge, used for pool ranking
  bestBook: BestBookPrice | null; // best non-DK price beating DK, else null
  /** Every OTHER book's latest price for this side (never DraftKings — see
   * LegBookPrice). Empty for custom/saved legs, whose entered odds are treated
   * as book-agnostic by the per-book pricing. */
  bookPrices: LegBookPrice[];
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
  metrics: ParlayMetrics; // independent (Π p) — used for the optimizer hot loop
  correlated?: CorrelatedMetrics; // copula joint metrics, attached for surfaced parlays
}

/** How many top (independent-EV) combos get the correlated Monte-Carlo pass. */
const SURFACE_FOR_CORRELATION = 12;

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
    // Unlocked look-ahead picks (future UFC/golf) aren't signals yet — a
    // parlay leg must be a locked bet of record, not a preview that can churn.
    if (isUnlockedPreview(ep.pick)) continue;
    const leg = legFromPick(ep);
    if (leg) pool.push(leg);
  }
  return pool;
}

/**
 * Stable identity for a pick across refreshes. The picks table is delete+
 * rescored every hourly run, so pick_id churns; game_id|model_id|player_id does
 * not. Mirrors opening_signals.lock_key — a market's selection is identified by
 * game+model (+player for props); the side may flip without changing identity.
 * This is what the persisted parlay slip stores.
 */
export function slipKeyForPick(p: Pick): string {
  return `${p.game_id}|${p.model_id}|${p.player_id ?? ''}`;
}

/**
 * Map a single enriched pick to a parlay leg, or null when it can't size one
 * (no DK price — prob-only HR/F5 markets). No sport / signal filter here, so
 * manual building (resolveSlipLegs) can use any pick the user selected.
 */
export function legFromPick(ep: EnrichedPick): ParlayLeg | null {
  const p = ep.pick;
  if (p.dk_odds == null) return null; // prob-only — no payout
  // bestOdds is already the best non-DK price that STRICTLY beats DK for this
  // side (game markets only — prop picks carry no bestOdds).
  const best = ep.bestOdds ?? null;
  const bestBook: BestBookPrice | null = best
    ? { bookmaker: best.bookmaker, american: best.price, decimal: americanToDecimal(best.price), link: best.link }
    : null;
  // Every non-DK book's current price for this side — the per-book betslip
  // pricing ("open this slip at your book"). DK rows are skipped: the DK
  // number is the stored dk_odds the model scored, already on the leg.
  const bookPrices: LegBookPrice[] = [];
  for (const row of ep.bookRows ?? []) {
    if (row.bookmaker === MODEL_BOOK) continue;
    const price = priceForSide(row, p.pick_side);
    if (price == null) continue;
    bookPrices.push({
      bookmaker: row.bookmaker,
      american: price,
      decimal: americanToDecimal(price),
      link: linkForSide(row, p.pick_side),
    });
  }
  return {
    pickId: p.pick_id,
    slipKey: slipKeyForPick(p),
    gameId: p.game_id,
    modelId: p.model_id,
    isGameLine: isGameLineModel(p.model_id),
    isFavorite: p.dk_odds < 0,
    label: p.pick_label,
    modelProb: p.model_probability,
    decimalOdds: americanToDecimal(p.dk_odds),
    americanOdds: p.dk_odds,
    legEdge: p.edge,
    bestBook,
    bookPrices,
    pick: p,
    game: ep.game,
  };
}

/**
 * Resolve a manual slip (ordered STABLE keys — see slipKeyForPick) against
 * today's picks. Any priced pick is eligible — BET/AVOID/NONE, MLB or WNBA
 * (legs are independent, so a mixed-sport parlay is fine). Keys with no matching
 * priced pick today (settled, de-listed, or now prob-only) come back in
 * `missingKeys` so the UI can flag and clear them. Legs come back in slip order.
 *
 * Keying on slipKey (not pick_id) is what makes a selection survive the hourly
 * delete+rescore: the new pick row carries the same game/model/player, so it
 * re-resolves to the (new pick_id) leg automatically.
 */
export function resolveSlipLegs(
  picks: EnrichedPick[],
  keys: string[],
): { legs: ParlayLeg[]; missingKeys: string[] } {
  const byKey = new Map<string, ParlayLeg>();
  for (const ep of picks) {
    const leg = legFromPick(ep);
    if (leg && !byKey.has(leg.slipKey)) byKey.set(leg.slipKey, leg);
  }
  const legs: ParlayLeg[] = [];
  const missingKeys: string[] = [];
  for (const key of keys) {
    const leg = byKey.get(key);
    if (leg) legs.push(leg);
    else missingKeys.push(key);
  }
  return { legs, missingKeys };
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

/** Parlay stake in UNITS — same tenth-Kelly basis as a straight pick's stake. */
export function parlayRecommendedUnits(
  metrics: ParlayMetrics,
  opts: KellySizingOpts,
): UnitStake {
  // Grossed up against the COMBINED parlay price, so a +600 slip correctly risks
  // a fraction of a unit to win its conviction rather than laying the full one.
  return stakeFor(metrics.kellyFraction * KELLY_MULTIPLIER, metrics.americanOdds, opts);
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
 * worst case (~C(20,6)≈39k combos) is sub-10ms.
 *
 * The hot enumeration loop ranks on the cheap independent EV (a monotone proxy).
 * When `rhoTable` is supplied, the top combos then get the correlated copula MC
 * pass and are re-sorted by correlated EV — so a positively-correlated slip can
 * outrank a higher-naive-EV uncorrelated one. We only run MC on a handful of
 * surfaced combos (best + alternatives), never the whole enumeration. */
export function optimizeParlay(
  pool: ParlayLeg[],
  constraints: ParlayConstraints,
  rhoTable?: RhoTable,
  resolveTeam?: TeamResolver,
): ParlayResult {
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

  if (rhoTable) {
    // Correlated re-rank over the surfaced subset only (keeps the optimizer fast).
    const surfaced = results.slice(0, SURFACE_FOR_CORRELATION);
    for (const r of surfaced) r.correlated = computeCorrelatedMetrics(r.legs, rhoTable, resolveTeam);
    surfaced.sort((a, b) => {
      const d = (b.correlated?.ev ?? 0) - (a.correlated?.ev ?? 0);
      if (d !== 0) return d;
      return (b.correlated?.edgeVsDk ?? 0) - (a.correlated?.edgeVsDk ?? 0);
    });
    return {
      best: surfaced[0],
      alternatives: surfaced.slice(1, 4),
      poolSize: pool.length,
    };
  }

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
    slipKey: `custom:${pickId}`, // custom legs aren't slip-tracked; field must exist
    gameId: `custom:${pickId}`, // unique; correlation never groups custom legs anyway
    modelId: CUSTOM_MODEL_ID,
    isGameLine: false,
    isFavorite: americanOdds < 0,
    label: label.trim(),
    modelProb,
    decimalOdds,
    americanOdds,
    legEdge: 0,
    bestBook: null,
    bookPrices: [],
    pick: null,
    game: null,
  };
}

// ── Line shopping ────────────────────────────────────────────────────────────

/** A parlay re-priced at the best available book per leg. */
export interface LineShop {
  decimalPayout: number; // Π best-book decimal
  americanOdds: number; // combined, American
  ev: number; // jointProb × best-book payout − 1
  evDelta: number; // ev − the all-DK EV (the improvement from shopping)
  shoppedCount: number; // legs where a non-DK book beats DK
  books: string[]; // distinct raw bookmaker keys used (UI maps to labels)
}

export function parlayHasLineShop(legs: ParlayLeg[]): boolean {
  return legs.some((l) => l.bestBook != null);
}

/**
 * Best-book pricing for a parlay, or null when no leg can be shopped (DK is best
 * on every leg, or every leg is a prop — props aren't shopped). Line shopping
 * changes only the payout, never the legs' joint probability, so we reuse the
 * card's already-computed correlated `jointProb` (and `dkEv` for the delta)
 * rather than re-running the copula MC. Prices are display-only: we have no
 * FanDuel deep link, so the DK hand-off still uses DK odds.
 */
export function lineShopParlay(legs: ParlayLeg[], jointProb: number, dkEv: number): LineShop | null {
  const shopped = legs.filter((l) => l.bestBook != null);
  if (shopped.length === 0) return null;
  let decimalPayout = 1;
  for (const l of legs) decimalPayout *= l.bestBook?.decimal ?? l.decimalOdds;
  const ev = jointProb * decimalPayout - 1;
  return {
    decimalPayout,
    americanOdds: decimalToAmerican(decimalPayout),
    ev,
    evDelta: ev - dkEv,
    shoppedCount: shopped.length,
    books: Array.from(new Set(shopped.map((l) => l.bestBook!.bookmaker))),
  };
}

// ── Per-book betslip pricing ("Open with" row) ───────────────────────────────

/** This slip priced entirely at ONE book — the tile row under the betslip. */
export interface BetslipBookQuote {
  book: string; // raw bookmaker key
  priced: number; // legs this book prices
  total: number; // legs in the slip
  /** Combined payout at this book — ONLY when it prices every leg. A partial
   * slip has no honest combined number, so these stay null and the tile shows
   * the coverage count instead. */
  decimalPayout: number | null;
  americanOdds: number | null;
  ev: number | null; // jointProb × payout − 1, same jointProb for every book
  isBest: boolean; // highest payout among fully-priced books (ties all starred)
  isModelBook: boolean; // DraftKings — the book the models score against
  /** Per-leg betslip deep links at this book, slip order; null when the book
   * doesn't price (or carry a link for) that leg. */
  links: (string | null)[];
}

/** A leg's price at one book, or null when the book doesn't price it.
 *  - DraftKings: always the STORED scored price (every leg requires dk_odds).
 *  - Custom/saved legs (no live pick): the entered odds, book-agnostic — the
 *    user quoted a market number, not one book's, so it counts at every book.
 *  - Everything else: that book's latest snapshot for the side, if any. */
function legPriceAtBook(
  leg: ParlayLeg,
  book: string,
): { decimal: number; link: string | null } | null {
  if (book === MODEL_BOOK) {
    return { decimal: leg.decimalOdds, link: leg.pick?.dk_bet_link ?? null };
  }
  if (leg.pick == null) return { decimal: leg.decimalOdds, link: null };
  const row = leg.bookPrices.find((b) => b.bookmaker === book);
  return row ? { decimal: row.decimal, link: row.link } : null;
}

/**
 * Price the whole slip at each book — the HOF-style "Open with" row: combined
 * odds where a book prices every leg, otherwise how many legs it covers.
 * `jointProb` is the slip's (correlated) win probability; it's book-independent,
 * so each fully-priced book gets an EV at ITS payout on the same probability.
 *
 * Fully-priced books sort best payout first (ties all starred), then partial
 * books by coverage — so the best place to put the slip on is always the first
 * tile. DraftKings is always fully priced by construction (legs require
 * dk_odds), so the row can never be empty.
 */
export function priceBooksForParlay(
  legs: ParlayLeg[],
  jointProb: number,
  books: string[],
): BetslipBookQuote[] {
  if (legs.length === 0) return [];
  const quotes: BetslipBookQuote[] = [];
  for (const book of books) {
    let priced = 0;
    let decimalPayout = 1;
    const links: (string | null)[] = [];
    for (const leg of legs) {
      const q = legPriceAtBook(leg, book);
      links.push(q?.link ?? null);
      if (q == null) continue;
      priced += 1;
      decimalPayout *= q.decimal;
    }
    const full = priced === legs.length;
    quotes.push({
      book,
      priced,
      total: legs.length,
      decimalPayout: full ? decimalPayout : null,
      americanOdds: full ? decimalToAmerican(decimalPayout) : null,
      ev: full ? jointProb * decimalPayout - 1 : null,
      isBest: false,
      isModelBook: book === MODEL_BOOK,
      links,
    });
  }
  quotes.sort((a, b) => {
    if ((a.decimalPayout != null) !== (b.decimalPayout != null)) {
      return a.decimalPayout != null ? -1 : 1;
    }
    if (a.decimalPayout != null && b.decimalPayout != null) {
      const d = b.decimalPayout - a.decimalPayout;
      if (d !== 0) return d;
      return a.isModelBook ? -1 : b.isModelBook ? 1 : 0; // tie → DK first
    }
    return b.priced - a.priced;
  });
  const bestDecimal = quotes[0]?.decimalPayout ?? null;
  if (bestDecimal != null) {
    for (const q of quotes) q.isBest = q.decimalPayout === bestDecimal;
  }
  return quotes;
}

/**
 * Where the betslip's main action button should hand off: the user's chosen
 * book when it prices EVERY leg, else DraftKings (which always does). Falling
 * back keeps the button label honest — "Bet on FanDuel" must never open a slip
 * FanDuel can't price.
 */
export function handoffBookFor(
  legs: ParlayLeg[],
  preferredBook: string,
): { book: string; links: (string | null)[] } {
  const quotes = priceBooksForParlay(legs, 1, [preferredBook, MODEL_BOOK]);
  const preferred = quotes.find((q) => q.book === preferredBook);
  if (preferred && preferred.decimalPayout != null) {
    return { book: preferredBook, links: preferred.links };
  }
  const dk = quotes.find((q) => q.book === MODEL_BOOK);
  return { book: MODEL_BOOK, links: dk?.links ?? legs.map(() => null) };
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

// ── Matchup label ────────────────────────────────────────────────────────────

/** Display matchup for a leg's game ("AWY @ HOM", "A vs B" for UFC, event name
 * for GOLF). Null when there's no game (custom / restored legs). */
export function matchupForLeg(game: GameRow | null): string | null {
  if (!game) return null;
  if (game.sport === 'GOLF') return game.home_team;
  const sep = game.sport === 'UFC' ? 'vs' : '@';
  return `${game.away_team} ${sep} ${game.home_team}`;
}

// ── Saved parlays (persisted snapshots) ──────────────────────────────────────

/**
 * A self-contained snapshot of one leg. Unlike ParlayLeg it carries no live Pick
 * / GameRow refs, so it survives today's picks changing — everything needed to
 * display, price, and hand off to DraftKings later is denormalized here.
 */
export interface SavedParlayLeg {
  pickId: number; // original pick_id (negative for custom legs) — session id only
  slipKey?: string; // stable game|model|player key; absent on pre-upgrade saves
  label: string;
  modelId: string;
  modelProb: number;
  americanOdds: number;
  decimalOdds: number;
  isGameLine: boolean;
  isFavorite: boolean;
  gameId: string | null; // null for custom legs
  matchup: string | null; // precomputed for display
  dkBetLink: string | null; // single-leg DK betslip link, when available
}

export interface SavedParlay {
  id: string;
  createdAt: string; // ISO timestamp
  sport: string;
  legs: SavedParlayLeg[];
}

/** Snapshot a live parlay into a persistable SavedParlay. `sport` is a display
 * label (manual plays can be cross-sport). */
export function toSavedParlay(legs: ParlayLeg[], sport: string): SavedParlay {
  return {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    createdAt: new Date().toISOString(),
    sport,
    legs: legs.map((l) => ({
      pickId: l.pickId,
      slipKey: l.slipKey,
      label: l.label,
      modelId: l.modelId,
      modelProb: l.modelProb,
      americanOdds: l.americanOdds,
      decimalOdds: l.decimalOdds,
      isGameLine: l.isGameLine,
      isFavorite: l.isFavorite,
      gameId: l.pickId < 0 ? null : l.gameId,
      matchup: matchupForLeg(l.game),
      dkBetLink: l.pick?.dk_bet_link ?? null,
    })),
  };
}

/**
 * Rebuild a minimal ParlayLeg from a saved leg (pick/game null). Lets saved legs
 * flow back through computeParlayMetrics and into the builder's manual custom
 * legs on restore.
 */
export function savedLegToParlayLeg(sl: SavedParlayLeg): ParlayLeg {
  return {
    pickId: sl.pickId,
    slipKey: sl.slipKey ?? `custom:${sl.pickId}`,
    gameId: sl.gameId ?? `custom:${sl.pickId}`,
    modelId: sl.modelId,
    isGameLine: sl.isGameLine,
    isFavorite: sl.isFavorite,
    label: sl.label,
    modelProb: sl.modelProb,
    decimalOdds: sl.decimalOdds,
    americanOdds: sl.americanOdds,
    legEdge: 0,
    bestBook: null, // saved snapshots don't carry live multi-book prices
    bookPrices: [],
    pick: null,
    game: null,
  };
}
