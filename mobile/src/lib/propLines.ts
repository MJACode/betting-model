/**
 * Alternate (milestone) prop lines, folded into the market they belong to.
 *
 * Matt, 2026-09-05: "Yes to alternate lines." The ingestor now stores The
 * Odds API's `*_alternate` markets -- 2+/3+ hits, 7+/8+ strikeouts -- under
 * their OWN market key, one row per (player, line), so the models keep
 * reading exactly one standard line per player (config.PROP_ALT_MARKETS has
 * the reasoning). The app wants the opposite view: one market, every line a
 * book posts, so the Stats board's ruler can find a price at 1.5 when the
 * standard line is 0.5 and the betslip can re-price a leg at either. These
 * helpers are that fold, in one place, so every read of the prop view agrees.
 *
 * Pure (no react-native import) so the verify scripts can run it under tsx.
 */

const ALT_SUFFIX = '_alternate';

/** `batter_hits_alternate` → true. */
export function isAlternateMarket(market: string): boolean {
  return market.endsWith(ALT_SUFFIX);
}

/** `batter_hits_alternate` → `batter_hits`; a standard key is returned as is. */
export function canonicalPropMarket(market: string): string {
  return isAlternateMarket(market) ? market.slice(0, -ALT_SUFFIX.length) : market;
}

/** The alternate key a standard market's extra lines are stored under. */
export function alternateMarketFor(market: string): string {
  return isAlternateMarket(market) ? market : `${market}${ALT_SUFFIX}`;
}

type PropLineLike = {
  game_id: string;
  market: string;
  player_name: string;
  bookmaker: string;
  line: number | string | null;
};

const lineKey = (v: number | string | null): string => {
  if (v == null || v === '') return '';
  const n = typeof v === 'number' ? v : Number(v);
  return Number.isFinite(n) ? String(n) : '';
};

/** One row's identity for paging: the view can now return several lines per
 *  (game, market, player, book), so the line is part of the key. */
export function propLineRowKey(r: PropLineLike): string {
  return `${r.game_id}|${r.market}|${r.player_name}|${r.bookmaker}|${lineKey(r.line)}`;
}

/**
 * Rewrite alternate rows onto their standard market. An alternate row that
 * duplicates the same book's STANDARD row for that player and line (1+ hits
 * beside batter_hits 0.5) is dropped -- the standard row is the one the
 * models priced and the one that was there before. Order is preserved.
 */
export function foldAlternateRows<T extends PropLineLike>(rows: readonly T[]): T[] {
  const standard = new Set<string>();
  for (const r of rows) {
    if (!isAlternateMarket(r.market)) standard.add(propLineRowKey(r));
  }
  const out: T[] = [];
  for (const r of rows) {
    if (!isAlternateMarket(r.market)) {
      out.push(r);
      continue;
    }
    const folded = { ...r, market: canonicalPropMarket(r.market) };
    if (standard.has(propLineRowKey(folded))) continue;
    out.push(folded);
  }
  return out;
}
