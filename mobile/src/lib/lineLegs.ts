/**
 * A betslip leg made from a LINE on the Stats board, not from a model pick.
 *
 * Matt, 2026-09-04, with the competitor's flow beside ours: "when you click on
 * one of the records bet lines, it shouldn't take you directly to the book, it
 * should ask you if you want to add to bet slip then bet slip should allow you
 * to add to any book." This reverses the same day's "the pill is the bet
 * link" (session 215): the pill now ASKS, the slip is where the book is chosen.
 *
 * WHAT A LINE LEG IS. The user's own research bet: a player, a market, the line
 * the board was showing and the side they asked about. No model made it, so it
 * carries NO edge and NO model probability — its win probability is the
 * odds-implied one, exactly like a hand-entered custom leg (parlay.ts
 * makeCustomLeg), which keeps the parlay's EV honest: a line leg is fair
 * value, never a source of edge. It is NOT a pick, is never written to
 * `picks`, and §1c does not apply to it: it re-prices from the latest line
 * every time the slip resolves, because the user asked for "the current line",
 * not a locked number.
 *
 * PRICED AT DRAFTKINGS WHEN DRAFTKINGS POSTS IT, else at the best bettable book
 * that does. `dkPriced` records which, so the betslip's per-book pricing knows
 * DraftKings does NOT cover a leg it never posted (parlay.ts legPriceAtBook) —
 * the "Open with" row then shows DK at N-1/N and the hand-off button goes to a
 * book that prices every leg. Section 6's DraftKings-only rule is about what
 * the MODELS decide on; a line leg has no model decision to protect.
 *
 * PERSISTED AS A SPEC, NOT A KEY. A pick leg's stable key resolves against
 * today's picks; a line leg has no pick row to resolve against, so the slip
 * stores everything needed to re-price it (hooks/useLineLegs.ts) and the
 * betslip re-reads that player's latest lines each time (queries.ts
 * fetchPropLineRows). A spec whose line no book posts any more — game started,
 * market pulled — resolves to nothing and is pruned like a dead pick key.
 */

import { americanToDecimal } from '@/lib/format';
import type { LegBookPrice, ParlayLeg } from '@/lib/parlay';
import { isBettableBook, MODEL_BOOK } from '@/lib/markets';
import type { GameRow, PropOddsByBookRow } from '@/types';

export type LineSide = 'over' | 'under';

/** Everything needed to re-price the leg later. Stored on device. */
export interface LineLegSpec {
  game_id: string;
  sport: string;
  market: string;
  player_name: string;
  team: string | null;
  line: number;
  side: LineSide;
  /** The stat's display label ("Hits", "Strikeouts"), for the leg's label. */
  statLabel: string;
}

/** modelId every line leg carries: no model, and parlayCorrelation reads it as
 *  an offense-neutral 'other' class so a line leg never trips correlation. */
export const LINE_LEG_MODEL_ID = 'stats_line';

/** Stable identity: the proposition, not any price. */
export function lineLegKey(s: Pick<LineLegSpec, 'game_id' | 'market' | 'player_name' | 'line' | 'side'>): string {
  return `line:${s.game_id}|${s.market}|${s.player_name}|${s.line}|${s.side}`;
}

/**
 * A deterministic NEGATIVE pickId for the leg. ParlayLeg.pickId is a session id
 * used for React keys and removal; custom legs count down from -1, so line legs
 * live far below them (-1e9 and down) and two line legs can never collide with
 * a custom one. Same key → same id across resolves, so a re-priced leg keeps
 * its place in the list.
 */
export function lineLegPickId(key: string): number {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) | 0;
  return -1_000_000_000 - (Math.abs(h) % 1_000_000_000);
}

const num = (v: number | string | null | undefined): number | null => {
  if (v == null || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
};

const sameLine = (a: number | null, b: number): boolean => a != null && Math.abs(a - b) < 1e-9;

export function lineLegLabel(s: LineLegSpec): string {
  const side = s.side === 'under' ? 'Under' : 'Over';
  return `${s.player_name} ${side} ${s.line} ${s.statLabel}`.trim();
}

/**
 * Price the spec off the latest all-books rows for that player and market.
 * Returns null when NO bettable book posts the side at that line — the leg
 * cannot exist without a price, and the caller prunes it.
 */
export function lineLegFromRows(
  spec: LineLegSpec,
  rows: readonly PropOddsByBookRow[],
  game: GameRow | null,
): ParlayLeg | null {
  const key = lineLegKey(spec);
  const priceOf = (r: PropOddsByBookRow) => num(spec.side === 'under' ? r.under_price : r.over_price);
  const linkOf = (r: PropOddsByBookRow) => (spec.side === 'under' ? r.under_link : r.over_link) ?? null;
  const at = rows.filter(
    (r) =>
      r.game_id === spec.game_id &&
      r.market === spec.market &&
      r.player_name === spec.player_name &&
      sameLine(num(r.line), spec.line) &&
      isBettableBook(r.bookmaker) &&
      priceOf(r) != null,
  );
  if (at.length === 0) return null;

  const dk = at.find((r) => r.bookmaker === MODEL_BOOK) ?? null;
  // Best bettable price otherwise — American odds are monotonic in payout, so
  // the numeric max pays most (statsOdds.ts bestOf).
  const best = at.reduce((b, r) => ((priceOf(r) as number) > (priceOf(b) as number) ? r : b), at[0]!);
  const anchor = dk ?? best;
  const americanOdds = priceOf(anchor) as number;
  const decimalOdds = americanToDecimal(americanOdds);

  const bookPrices: LegBookPrice[] = [];
  for (const r of at) {
    if (r.bookmaker === MODEL_BOOK) continue;
    const price = priceOf(r) as number;
    bookPrices.push({ bookmaker: r.bookmaker, american: price, decimal: americanToDecimal(price), link: linkOf(r) });
  }

  return {
    pickId: lineLegPickId(key),
    slipKey: key,
    gameId: spec.game_id,
    modelId: LINE_LEG_MODEL_ID,
    isGameLine: false,
    isFavorite: americanOdds < 0,
    label: lineLegLabel(spec),
    modelProb: decimalOdds > 0 ? 1 / decimalOdds : 0, // odds-implied: fair value
    decimalOdds,
    americanOdds,
    legEdge: 0,
    bestBook: null,
    bookPrices,
    pick: null,
    game,
    dkPriced: dk != null,
    dkLink: dk ? linkOf(dk) : null,
    pricedAt: anchor.bookmaker,
  };
}

/** Is this leg one of ours — a Stats line rather than a pick or a custom entry? */
export function isLineLeg(leg: Pick<ParlayLeg, 'modelId'>): boolean {
  return leg.modelId === LINE_LEG_MODEL_ID;
}
