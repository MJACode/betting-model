/**
 * A betslip leg made from a LINE on the Stats board, not from a model pick.
 *
 * Matt, 2026-09-04, with the competitor's flow beside ours: "when you click on
 * one of the records bet lines, it shouldn't take you directly to the book, it
 * should ask you if you want to add to bet slip then bet slip should allow you
 * to add to any book." This reverses the same day's "the pill is the bet
 * link" (session 215): the pill now ASKS, the slip is where the book is chosen.
 * Team lines followed on 2026-09-05 ("Team line legs, yes build it"): the
 * Teams board's pill asks the same way, and a GAME line leg -- a moneyline, a
 * spread at the board's number, the game total -- goes through the same
 * store, the same re-price and the same per-book pricing as a player prop.
 *
 * WHAT A LINE LEG IS. The user's own research bet: a player (or a team), a
 * market, the line the board was showing and the side they asked about. No
 * model made it, so it carries NO edge and NO model probability -- its win
 * probability is the odds-implied one, exactly like a hand-entered custom leg
 * (parlay.ts makeCustomLeg), which keeps the parlay's EV honest: a line leg is
 * fair value, never a source of edge. It is NOT a pick, is never written to
 * `picks`, and §1c does not apply to it: it re-prices from the latest line
 * every time the slip resolves, because the user asked for "the current
 * line", not a locked number.
 *
 * PRICED AT DRAFTKINGS WHEN DRAFTKINGS POSTS IT, else at the best bettable book
 * that does. `dkPriced` records which, so the betslip's per-book pricing knows
 * DraftKings does NOT cover a leg it never posted (parlay.ts legPriceAtBook) --
 * the "Open with" row then shows DK at N-1/N and the hand-off button goes to a
 * book that prices every leg. Section 6's DraftKings-only rule is about what
 * the MODELS decide on; a line leg has no model decision to protect.
 *
 * PERSISTED AS A SPEC, NOT A KEY. A pick leg's stable key resolves against
 * today's picks; a line leg has no pick row to resolve against, so the slip
 * stores everything needed to re-price it (hooks/useLineLegs.ts) and the
 * betslip re-reads that player's -- or that game market's -- latest lines
 * each time (queries.ts fetchPropLineRows / fetchGameLineRows). A spec whose
 * line no book posts any more -- game started, market pulled -- resolves to
 * nothing and is pruned like a dead pick key.
 *
 * A GAME LINE LEG IS A GAME LINE. `isGameLine` is true for it, so the slip's
 * correlation guard (parlay.ts isValidCombo: one game-line leg per game) sees
 * it beside a model's moneyline on the same game and refuses the pair, the
 * way it would two model game legs.
 */

import { americanToDecimal } from '@/lib/format';
import { thresholdLabel } from '@/lib/hitMode';
import type { LegBookPrice, ParlayLeg } from '@/lib/parlay';
import { bookName, isBettableBook, linkForSide, MODEL_BOOK, priceForSide } from '@/lib/markets';
import type { StatsOddsQuote, TeamLineQuote } from '@/lib/statsOdds';
import type { GameRow, OddsByBookRow, PropOddsByBookRow } from '@/types';

export type LineSide = 'over' | 'under';
export type GameLineMarket = 'h2h' | 'spreads' | 'totals';

/** A player-prop line: everything needed to re-price the leg later. Stored on
 *  device. `kind` is absent on specs stored before team lines existed. */
export interface PropLineLegSpec {
  kind?: 'prop';
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

/** A game line from the Teams board, from one team's side. */
export interface GameLineLegSpec {
  kind: 'game';
  game_id: string;
  sport: string;
  market: GameLineMarket;
  /** The team whose row was tapped -- the selection on h2h and spreads. */
  team: string;
  opponent: string;
  isHome: boolean;
  /** The team's spread (−1.5 = favourite) or the game total; null on h2h. */
  line: number | null;
  /** Totals only: which side of the number. */
  side: LineSide | null;
}

export type LineLegSpec = PropLineLegSpec | GameLineLegSpec;

export function isGameSpec(s: LineLegSpec): s is GameLineLegSpec {
  return s.kind === 'game';
}

/** modelId every line leg carries: no model, and parlayCorrelation reads it as
 *  an offense-neutral 'other' class so a line leg never trips correlation. */
export const LINE_LEG_MODEL_ID = 'stats_line';

/**
 * Stable identity: the proposition, not any price. A game total is the game's,
 * not the tapped team's -- Over 8.5 from the home row and from the away row
 * are one bet -- so the team is left out of a totals key.
 */
export function lineLegKey(s: LineLegSpec): string {
  if (isGameSpec(s)) {
    const who = s.market === 'totals' ? '' : s.team;
    return `line:${s.game_id}|${s.market}|${who}|${s.line ?? ''}|${s.side ?? ''}`;
  }
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

const sameLine = (a: number | null, b: number | null): boolean =>
  a != null && b != null && Math.abs(a - b) < 1e-9;

/** A game number the way scorer._build_pick_label prints it: a Python float,
 *  so an integer line carries one decimal ("7.0", "+3.0"). */
const fmtLine = (n: number): string => (Number.isInteger(n) ? n.toFixed(1) : String(n));
/** "+1.5" / "-1.5" in the picks' own idiom (ASCII sign, like "WSH +1.5"). */
const signed = (n: number): string => (n > 0 ? `+${fmtLine(n)}` : fmtLine(n));

/** The proposition as the leg card and the sheet title show it. Game legs use
 *  the picks' own labels, byte for byte (models/scorer.py _build_pick_label):
 *  "LAD ML", "WSH +1.5", "SEA vs OAK Over 7.0" -- home team first on a total,
 *  one decimal on a whole number -- so a line leg beside a model's pick for
 *  the same market reads as the same game at the same number (UX review). */
export function lineLegLabel(s: LineLegSpec): string {
  if (isGameSpec(s)) {
    if (s.market === 'h2h') return `${s.team} ML`;
    if (s.market === 'spreads') return `${s.team} ${s.line == null ? '' : signed(s.line)}`.trim();
    const home = s.isHome ? s.team : s.opponent;
    const away = s.isHome ? s.opponent : s.team;
    const side = s.side === 'under' ? 'Under' : 'Over';
    return `${home} vs ${away} ${side} ${s.line == null ? '' : fmtLine(s.line)}`.trim();
  }
  const side = s.side === 'under' ? 'Under' : 'Over';
  return `${s.player_name} ${side} ${s.line} ${s.statLabel}`.trim();
}

/** The priced side of an odds row for a game spec. */
export function gameLegSide(s: GameLineLegSpec): 'home' | 'away' | 'over' | 'under' {
  if (s.market === 'totals') return s.side === 'under' ? 'under' : 'over';
  return s.isHome ? 'home' : 'away';
}

/** Is this book's row at the spec's number? A moneyline has none. */
export function gameRowAtNumber(r: OddsByBookRow, s: GameLineLegSpec): boolean {
  if (s.market === 'h2h') return true;
  if (s.line == null) return false;
  if (s.market === 'spreads') return sameLine(num(r.spread_home), s.isHome ? s.line : -s.line);
  return sameLine(num(r.total_line), s.line);
}

/**
 * The leg itself, from the rows that price this side at this number. Null when
 * NO bettable book does -- the leg cannot exist without a price, and the
 * caller prunes it.
 */
function buildLeg<R extends { bookmaker: string }>(
  spec: LineLegSpec,
  at: readonly R[],
  priceOf: (r: R) => number | null,
  linkOf: (r: R) => string | null,
  game: GameRow | null,
): ParlayLeg | null {
  if (at.length === 0) return null;
  const key = lineLegKey(spec);
  const dk = at.find((r) => r.bookmaker === MODEL_BOOK) ?? null;
  // Best bettable price otherwise -- American odds are monotonic in payout, so
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
    isGameLine: isGameSpec(spec),
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

/**
 * Price a PROP spec off the latest all-books rows for that player and market.
 * Returns null when NO bettable book posts the side at that line.
 */
export function lineLegFromRows(
  spec: PropLineLegSpec,
  rows: readonly PropOddsByBookRow[],
  game: GameRow | null,
): ParlayLeg | null {
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
  return buildLeg(spec, at, priceOf, linkOf, game);
}

/**
 * Price a GAME spec off the latest all-books rows for that game market. A book
 * on a different number (−2.5 when the board said −1.5) is a different bet
 * and is left out, the same rule as a prop line (docs/best_line.md §5).
 */
export function gameLineLegFromRows(
  spec: GameLineLegSpec,
  rows: readonly OddsByBookRow[],
  game: GameRow | null,
): ParlayLeg | null {
  const side = gameLegSide(spec);
  const priceOf = (r: OddsByBookRow) => priceForSide(r, side);
  const linkOf = (r: OddsByBookRow) => linkForSide(r, side);
  const at = rows.filter(
    (r) =>
      r.game_id === spec.game_id &&
      r.market === spec.market &&
      isBettableBook(r.bookmaker) &&
      gameRowAtNumber(r, spec) &&
      priceOf(r) != null,
  );
  return buildLeg(spec, at, priceOf, linkOf, game);
}

/** Is this leg one of ours -- a Stats line rather than a pick or a custom entry? */
export function isLineLeg(leg: Pick<ParlayLeg, 'modelId'>): boolean {
  return leg.modelId === LINE_LEG_MODEL_ID;
}

// ── What the "Add to betslip?" sheet is handed ──────────────────────────────

/** Everything AddLineSheet needs: the proposition, every bettable book's price
 *  for it (best first), and an optional line under the title. */
export interface LineSheetInput {
  spec: LineLegSpec;
  prices: { book: string; price: number }[];
  explainer?: string;
}

function bettablePrices<R extends { bookmaker: string }>(
  rows: readonly R[],
  priceOf: (r: R) => number | null,
): { book: string; price: number }[] {
  const out: { book: string; price: number }[] = [];
  for (const r of rows) {
    if (!isBettableBook(r.bookmaker)) continue;
    const price = priceOf(r);
    if (price == null) continue;
    out.push({ book: r.bookmaker, price });
  }
  // Best payout first; ties keep the board's order.
  out.sort((a, b) => b.price - a.price);
  return out;
}

/** A tapped Players-board pill. `boardHeadline` ("1+ Hits") lets an off-line
 *  quote say why the title differs from the column it was tapped in. */
export function propLineSheetInput(
  quote: StatsOddsQuote,
  sport: string,
  statLabel: string,
  boardHeadline?: string,
): LineSheetInput {
  const rows = quote.bookRows as PropOddsByBookRow[];
  const spec: PropLineLegSpec = {
    kind: 'prop',
    game_id: quote.gameId,
    sport,
    market: quote.market,
    player_name: quote.playerName,
    team: rows[0]?.team ?? null,
    line: quote.line,
    side: quote.side,
    statLabel,
  };
  const prices = bettablePrices(rows, (r) => num(quote.side === 'under' ? r.under_price : r.over_price));
  const explainer =
    quote.offLine && boardHeadline
      ? `The board is on ${boardHeadline}; ${bookName(quote.book)} only posts ${
          thresholdLabel(quote.line, quote.side)
        }. Add it to your betslip now — you’ll choose the sportsbook there.`
      : undefined;
  return { spec, prices, explainer };
}

/** A tapped Teams-board pill: the team's moneyline, its spread at the board's
 *  number, or the game total's Over. */
export function teamLineSheetInput(quote: TeamLineQuote, sport: string): LineSheetInput {
  const spec: GameLineLegSpec = {
    kind: 'game',
    game_id: quote.gameId,
    sport,
    market: quote.market,
    team: quote.team,
    opponent: quote.opponent,
    isHome: quote.isHome,
    line: quote.line,
    side: quote.market === 'totals' ? 'over' : null,
  };
  const side = gameLegSide(spec);
  const prices = bettablePrices(quote.bookRows, (r) => priceForSide(r, side));
  return { spec, prices };
}
