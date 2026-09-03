/**
 * The Stats board's ODDS column — what price to put on a leaderboard row.
 *
 * WHY THIS EXISTS
 * The column used to read ONLY today's `picks`: it matched a row's `player_id`
 * against a pick from the stat's prop model, and printed a dash for everything
 * else. Two things make that wrong far more often than it looks:
 *
 *  1. A player is only SCORED once his lineup is confirmed, so every batter in
 *     a game whose lineup has not posted shows a dash — while DraftKings has
 *     been pricing him all morning.
 *  2. A model's non-BET prop rows are transient. They are deleted whenever the
 *     pre-game line poller re-scores that game (models/scorer.py's non-BET
 *     housekeeping delete is scoped by game_id, not by model), so a player who
 *     had a price at :20 has a dash at :40.
 *
 * Measured on 2026-09-03 at 14:20 ET: DraftKings priced `batter_hits` for 184
 * players across all 9 games; 60 of them held a pick. The other 124 rendered a
 * dash for a number that was on the board the whole time.
 *
 * So the column now reads the LINES, and treats a pick as an enrichment of a
 * line rather than the only way to have one. `v_latest_prop_odds_all_books` is
 * already fetched for line shopping and carries every book.
 *
 * THE LINE ON THE ROW IS THE LINE THE BOARD IS ASKING ABOUT.
 * "2+ Hits" is Over 1.5, not Over 0.5. The old cell printed the model's own
 * `scored_line` whatever the ruler said, so a 2+ board showed an `o0.5` price —
 * a different bet (docs/best_line.md §5). Matching is exact: a book that hangs
 * its price off another number is a different bet and gets no cell.
 *
 * DISPLAY ONLY. Nothing here reaches a model: `edge`, the BET/AVOID call and
 * every threshold still run on the DraftKings price the scorer stored.
 *
 * Verify with: npx tsx scripts/verify_stats_odds.ts
 */

import { MODEL_BOOK } from './markets';
import { normalizePlayerName } from './playerNews';
import type { BookPricedRow, EnrichedPick, PropOddsByBookRow } from '@/types';

/** The side of a prop the Stats board is asking about. */
export type StatsOddsSide = 'over' | 'under';

/** DraftKings' number for one player, at the line the board is showing. */
export interface StatsOddsQuote {
  /** Normalized player name — the join key, never displayed. */
  playerKey: string;
  /** The feed's own spelling, for the sheet header. */
  playerName: string;
  gameId: string;
  market: string;
  line: number;
  side: StatsOddsSide;
  /** DraftKings' American price for `side` at `line`. */
  dkPrice: number;
  /** Every book pricing this player/market/line — the sheet's books list. */
  bookRows: BookPricedRow[];
}

/**
 * What one leaderboard row's ODDS cell shows. A pick carries the model's read
 * (probability, edge, EV) and can join a betslip; a quote is a price and
 * nothing more, and says so.
 */
export type StatsOddsCell =
  | { kind: 'pick'; pick: EnrichedPick }
  | { kind: 'quote'; quote: StatsOddsQuote };

/** Supabase returns numerics as strings — coerce before comparing anything. */
function num(v: number | string | null | undefined): number | null {
  if (v == null || v === '') return null;
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

/** Lines are one decimal place; compare with a tolerance, never with ===. */
export function sameLine(a: number | null, b: number | null): boolean {
  if (a == null || b == null) return false;
  return Math.abs(a - b) < 1e-9;
}

/**
 * Fold a list of names to normalized keys, REFUSING any key two different
 * spellings share.
 *
 * This mirrors data/name_match.py::resolve_feed_name, which returns None rather
 * than guess when two candidates fold alike — the fold drops generational
 * suffixes, so "Luis Garcia" and "Luis Garcia Jr." collide, and they are two
 * people. A wrong price on the wrong player is worse than no price, and the
 * dash is what a refusal looks like.
 *
 * Returns the set of keys that are AMBIGUOUS and must not be joined on.
 */
export function ambiguousKeys(names: Iterable<string | null | undefined>): Set<string> {
  const spellings = new Map<string, Set<string>>();
  for (const raw of names) {
    if (!raw) continue;
    const key = normalizePlayerName(raw);
    if (!key) continue;
    const seen = spellings.get(key);
    if (seen) seen.add(raw);
    else spellings.set(key, new Set([raw]));
  }
  const out = new Set<string>();
  for (const [key, seen] of spellings) if (seen.size > 1) out.add(key);
  return out;
}

/**
 * DraftKings' quote per player for one market, at one line and side.
 *
 * `gameIds` bounds the rows to the sport's slate: the view has no sport column
 * and `player_points` is both an NBA and a WNBA market, so without it a WNBA
 * board could show an NBA price.
 */
export function buildQuoteIndex(
  rows: PropOddsByBookRow[],
  opts: {
    market: string;
    line: number;
    side: StatsOddsSide;
    gameIds?: Set<string> | null;
    /** The book whose price the pill prints. Defaults to MODEL_BOOK — the book
     *  the models decide on (§6) — rather than a literal, so the day the modeled
     *  book changes this column moves with it instead of quietly pricing against
     *  the old one. */
    book?: string;
  },
): Map<string, StatsOddsQuote> {
  const book = opts.book ?? MODEL_BOOK;
  const inScope = rows.filter(
    (r) =>
      r.market === opts.market &&
      sameLine(num(r.line), opts.line) &&
      (!opts.gameIds || opts.gameIds.has(r.game_id)),
  );
  const skip = ambiguousKeys(inScope.map((r) => r.player_name));

  const byPlayer = new Map<string, PropOddsByBookRow[]>();
  for (const r of inScope) {
    const key = normalizePlayerName(r.player_name);
    if (!key || skip.has(key)) continue;
    const list = byPlayer.get(key);
    if (list) list.push(r);
    else byPlayer.set(key, [r]);
  }

  const out = new Map<string, StatsOddsQuote>();
  for (const [key, list] of byPlayer) {
    const modeled = list.find((r) => r.bookmaker === book);
    // No price at the modeled book = no cell. The pill has always been the
    // DraftKings number, and a lone FanDuel price presented in its place would
    // read as DK's (the same trap displayQuoteForPick labels its way out of).
    const price = modeled ? num(opts.side === 'under' ? modeled.under_price : modeled.over_price) : null;
    if (modeled == null || price == null) continue;
    out.set(key, {
      playerKey: key,
      playerName: modeled.player_name,
      gameId: modeled.game_id,
      market: opts.market,
      line: opts.line,
      side: opts.side,
      dkPrice: price,
      bookRows: list as unknown as BookPricedRow[],
    });
  }
  return out;
}

/**
 * Today's prop picks for one model, keyed by `player_id`. A BET always wins the
 * key: a dead-zone NONE row written by a later pass must never displace the
 * signal a user was actually given (§1c).
 */
export function buildPickIndex(
  picks: EnrichedPick[],
  modelId: string | null,
): Map<string, EnrichedPick> {
  const out = new Map<string, EnrichedPick>();
  if (!modelId) return out;
  for (const ep of picks) {
    const p = ep.pick;
    if (p.model_id !== modelId || !p.player_id || p.dk_odds == null) continue;
    const existing = out.get(p.player_id);
    if (existing && p.signal_type !== 'BET') continue;
    out.set(p.player_id, ep);
  }
  return out;
}

/**
 * The cell for one leaderboard row.
 *
 * A pick wins ONLY when it was scored at the line the board is showing. The
 * models score `batter_hits` at 0.5, so on a "2+ Hits" board the pick is a
 * different bet and the 1.5 quote is the honest number — that is the second
 * half of the o0.5-on-a-2+-board bug, and it is fixed here rather than in the
 * cell, so the sheet and the pill can never disagree about which bet is on the
 * row.
 */
export function statsOddsCell(
  row: { player_id?: string | null; player_name?: string | null },
  pickIndex: Map<string, EnrichedPick>,
  quoteIndex: Map<string, StatsOddsQuote>,
  line: number,
  ambiguous?: Set<string>,
): StatsOddsCell | null {
  const pick = row.player_id ? pickIndex.get(row.player_id) : undefined;
  if (pick && sameLine(num(pick.pick.scored_line), line)) return { kind: 'pick', pick };
  const key = normalizePlayerName(row.player_name);
  if (!key || ambiguous?.has(key)) return null;
  const quote = quoteIndex.get(key);
  return quote ? { kind: 'quote', quote } : null;
}
