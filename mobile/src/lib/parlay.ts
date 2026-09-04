/**
 * Betslip pricing — pure logic (no React).
 *
 * Prices the user's betslip. A parlay combines several legs into one wager: all
 * must hit. We multiply the per-leg decimal odds for the payout and the per-leg
 * model probabilities for our win estimate, giving Expected Value =
 * parlayProb × decimalPayout − 1.
 *
 * There is no auto-builder: the slip holds what the user added and nothing else.
 * (An optimizer and a same-game finder used to live here — both proposed parlays
 * the user never asked for, and both were removed with the modes they fed.)
 *
 * Correlation rule: at most ONE game-line leg (moneyline / runline / over-under /
 * F5 / WNBA ml-ou-spread — i.e. MODEL_META[id].type === 'game') per game_id.
 * Props may stack freely within a game and may combine with the one game-line leg.
 * So RL + ML in the same game is never allowed; ML + multiple same-game props is.
 *
 * All numbers are pure functions of the leg array, so adding or removing a leg
 * recomputes everything synchronously.
 */

import { americanToDecimal } from '@/lib/format';
import { stakeFor, effectiveKellyFraction, KELLY_MULTIPLIER,
         type KellySizingOpts, type UnitStake } from '@/lib/thresholds';
import { isBettableBook, linkForSide, marketForPick, priceForSide, rowIsSameBet, MODEL_BOOK } from '@/lib/markets';
import { MODEL_META } from '@/lib/modelMeta';
import type { EnrichedPick, GameRow, Pick } from '@/types';

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
/** How many top (independent-EV) combos get the correlated Monte-Carlo pass. */
/** modelId sentinel for user-entered custom legs (not a real model). */
export const CUSTOM_MODEL_ID = 'custom';
/** Cap on the candidate pool fed to enumeration — keeps the combinatorics bounded. */
/** Style bonus added to a candidate's pool-ranking score when its sign matches. */
/** Decimal odds (>1) back to American. Inverse of americanToDecimal. */
export function decimalToAmerican(decimal: number): number {
  if (decimal >= 2) return (decimal - 1) * 100;
  return -100 / (decimal - 1);
}

function isGameLineModel(modelId: string): boolean {
  return MODEL_META[modelId]?.type === 'game';
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
  // number is the stored dk_odds the model scored, already on the leg. Same
  // bet only (rowIsSameBet — a book at a different line is a different bet)
  // and bettable books only: an "Open with" tile is an invitation to bet.
  const market = marketForPick(p);
  const bookPrices: LegBookPrice[] = [];
  for (const row of ep.bookRows ?? []) {
    if (row.bookmaker === MODEL_BOOK) continue;
    if (!isBettableBook(row.bookmaker)) continue;
    if (!rowIsSameBet(p, row, market)) continue;
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


/**
 * What the persistent betslip bar shows: the slip's size and its combined
 * price. `selectionCount` is every selection the user made (slip keys),
 * `legs` only the ones that resolve to a priced pick today — they differ when a
 * selection has settled or gone prob-only, which is exactly why the bar reports
 * both (the badge counts what you picked; the odds only what's actually
 * priceable).
 *
 * Payout is correlation-independent: correlation moves a parlay's win
 * probability, never its price, so the bar's number always equals the headline
 * odds on the betslip screen without paying for the copula pass.
 */
export interface BetslipSummary {
  /** Selections in the slip, including ones with no priced pick today. */
  count: number;
  /** Of those, how many resolved to a priced leg. */
  resolved: number;
  /** Combined American odds across the resolved legs; null when none resolve. */
  americanOdds: number | null;
  /** Total return on a $10 stake (stake included); null when none resolve. */
  payoutPerTen: number | null;
  /** 2+ resolved legs — the price is a parlay rather than a single bet. */
  isParlay: boolean;
}

export const BETSLIP_BAR_STAKE = 10;

export function betslipSummary(legs: ParlayLeg[], selectionCount: number): BetslipSummary {
  if (legs.length === 0) {
    return {
      count: selectionCount,
      resolved: 0,
      americanOdds: null,
      payoutPerTen: null,
      isParlay: false,
    };
  }
  const m = computeParlayMetrics(legs);
  return {
    count: selectionCount,
    resolved: legs.length,
    americanOdds: m.americanOdds,
    payoutPerTen: BETSLIP_BAR_STAKE * m.decimalPayout,
    isParlay: legs.length >= 2,
  };
}

/**
 * Is the board trustworthy enough to declare a slip selection dead?
 *
 * A key that resolves to nothing looks identical whether the pick genuinely
 * went away or the fetch simply failed — so pruning is only safe against a
 * board we know landed: the slip has been read from storage, the fetch is
 * finished, it did not error, and it came back with picks in it. Anything else
 * and the keys are held, because silently wiping a real slip is far worse than
 * carrying a stale one for another minute.
 */
export function canPruneSlip(board: {
  slipReady: boolean;
  loading: boolean;
  error: string | null;
  boardSize: number;
}): boolean {
  return board.slipReady && !board.loading && board.error == null && board.boardSize > 0;
}

/**
 * Should the persistent betslip bar render at all?
 *
 * Only when there is a real bet to show — at least one selection that resolved
 * to a priceable leg — or while we are still finding out, which is the moment
 * right after the first add and needs to feel responsive. A slip whose
 * selections have all gone stale shows NOTHING: the pruner is about to empty
 * it, and a bar advertising selections that no card on screen reads as selected
 * is the exact confusion this replaced.
 */
export function shouldShowBetslipBar(summary: BetslipSummary, resolving: boolean): boolean {
  if (summary.resolved > 0) return true;
  return resolving && summary.count > 0;
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
 * Where the betslip's main action button should hand off: the BEST-PAYING of
 * the member's own books that prices EVERY leg, else DraftKings (which always
 * does). Falling back keeps the button label honest — "Bet on FanDuel" must
 * never open a slip FanDuel can't price — and the screen says when it happens.
 *
 * The member's books come from `usePreferredBooks` (Matt, 2026-09-04: "the
 * parlay button … should change to match the Sportsbook the user selects as
 * their preferred", and the picker is now a set). With two selected this is the
 * same rule the Stats board uses on a single line, applied to the whole slip.
 *
 * This is the hand-off only — the slip is priced and modeled at DraftKings
 * either way (§6) — and it narrows the DEFAULT, never the options: the "Open
 * with" row beside it still lists every bettable book with its coverage, so a
 * member can always place at a book they have not selected.
 */
export function handoffBookFor(
  legs: ParlayLeg[],
  preferredBooks: readonly string[],
): { book: string; links: (string | null)[] } {
  // priceBooksForParlay sorts fully-priced books best payout first, ties to DK.
  const quotes = priceBooksForParlay(legs, 1, [...preferredBooks, MODEL_BOOK]);
  const mine = new Set(preferredBooks);
  const best = quotes.find((q) => q.decimalPayout != null && mine.has(q.book));
  if (best) return { book: best.book, links: best.links };
  const dk = quotes.find((q) => q.book === MODEL_BOOK);
  return { book: MODEL_BOOK, links: dk?.links ?? legs.map(() => null) };
}

// ── Edit helpers (pure) ──────────────────────────────────────────────────────

/** Remove a leg by pickId; recompute metrics on the remainder. */
/** Append a leg; recompute metrics. */
/** Replace one leg with another; recompute metrics. */
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
  /** Per-book single-leg betslip links snapshotted at save time, keyed by
   * bookmaker. A KEY being present means that book priced the leg when it was
   * saved (its value is the link, or null when the book carried none) — the
   * saved-parlay hand-off uses this the way the live betslip uses bookPrices,
   * so a FanDuel user's saved parlay can still hand off to FanDuel. Absent on
   * custom legs and pre-upgrade saves (those hand off at DraftKings). */
  bookLinks?: Record<string, string | null>;
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
      bookLinks:
        l.pick != null && l.bookPrices.length > 0
          ? Object.fromEntries(l.bookPrices.map((b) => [b.bookmaker, b.link]))
          : undefined,
    })),
  };
}

/**
 * Where a SAVED parlay's bet button hands off: the first of the member's books
 * (their own order) whose links the snapshot carries for every real leg, else
 * DraftKings — same honesty rule as the live betslip's handoffBookFor: "Bet on
 * FanDuel" must never open a slip FanDuel couldn't price. Custom legs are
 * book-agnostic (the user quoted a market number, not one book's), so they
 * never disqualify a book — they just carry no link there. Pre-upgrade saves
 * have no bookLinks at all, so they keep handing off at DraftKings.
 *
 * Order, not payout, decides between two covered books: a save stores links,
 * not prices, so there is no honest way to rank them by what they pay now.
 */
export function savedHandoffBookFor(
  legs: SavedParlayLeg[],
  preferredBooks: readonly string[],
): { book: string; links: (string | null)[] } {
  const dk = { book: MODEL_BOOK, links: legs.map((l) => l.dkBetLink) };
  if (legs.length === 0) return dk;
  const isCustom = (l: SavedParlayLeg) => l.pickId < 0 || l.gameId == null;
  for (const book of preferredBooks) {
    if (book === MODEL_BOOK) return dk;
    const covered = legs.every(
      (l) => isCustom(l) || (l.bookLinks != null && book in l.bookLinks),
    );
    if (!covered) continue;
    return {
      book,
      links: legs.map((l) => (isCustom(l) ? null : l.bookLinks?.[book] ?? null)),
    };
  }
  return dk;
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
