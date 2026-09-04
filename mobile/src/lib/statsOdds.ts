/**
 * The Stats tab's LINE column — the selected sportsbook's current number for
 * every player and team on the board.
 *
 * WHAT MATT ASKED FOR (2026-09-03): "display all lines regardless of bet
 * status … see a current line for a player or team so that I can do research
 * on players and bet what I want off of that data. If they select FanDuel we
 * only show FanDuel, if the user had DK selected then we only show DK. Only do
 * this feature on this tab. It works separately from the models and we just
 * need to show current lines."
 *
 * So, three rules, each of which is a product decision rather than a default:
 *
 *  1. THE COLUMN IS THE USER'S BOOK, AND ONLY THAT BOOK. No DraftKings fallback
 *     when their book has not posted a line — that is what "only show FanDuel"
 *     means, and a DK price standing in for a FanDuel one is a number the user
 *     cannot get at the book they chose. Measured 2026-09-03: FanDuel posts no
 *     `batter_hits` line at all, while every book prices h2h/spread/total on
 *     all nine games. A FanDuel user's Players board is therefore honest and
 *     sparse, and the screen says why rather than showing a silent column of
 *     dashes.
 *  2. THE LINE IS THE LINE THE BOARD IS ASKING ABOUT. "2+ Hits" is Over 1.5,
 *     not Over 0.5; a price hung off another number is a different bet
 *     (docs/best_line.md §5) and gets no cell.
 *  3. NO MODEL IN THE CELL. The models decide against DraftKings (§6) and that
 *     is untouched — nothing here reaches a scorer. The one place a pick still
 *     matters on this tab is the betslip: a parlay leg IS a pick, so "Add to
 *     betslip" can only exist where the model made one at this exact line. It
 *     is offered without edge or EV, as a button, and nowhere else.
 *
 * Names: leaderboard rows carry `player_id`, prop odds carry `player_name`, so
 * the join folds through normalizePlayerName and REFUSES any key two spellings
 * share. A wrong price on the wrong player is worse than a dash.
 *
 * Verify with: npx tsx scripts/verify_stats_odds.ts
 */

import { normalizePlayerName } from './playerNews';
import type {
  BookPricedRow,
  EnrichedPick,
  GameRow,
  OddsByBookRow,
  PropOddsByBookRow,
} from '@/types';

/** The side of a line the Stats board is asking about. */
export type StatsOddsSide = 'over' | 'under';

/** One book's number for one player, at the line the board is showing. */
export interface StatsOddsQuote {
  /** Normalized player name — the join key, never displayed. */
  playerKey: string;
  /** The feed's own spelling, for the sheet header. */
  playerName: string;
  gameId: string;
  market: string;
  line: number;
  side: StatsOddsSide;
  /** The selected book. */
  book: string;
  /** That book's American price for `side` at `line`. */
  price: number;
  /** That book's betslip deep link for the side, when the feed carried one. */
  link: string | null;
  /** Every book pricing this player/market/line. Kept for the sheet's
   *  "Switch sportsbook" preview and for tests; the column never reads it. */
  bookRows: BookPricedRow[];
}

/**
 * BEST OF THE MEMBER'S BOOKS. American odds are monotonic in payout — a larger
 * number always pays more on the same stake, across the −100/+100 boundary
 * (−200 beats −300, +105 beats −105) — so the best price is the numeric max,
 * with no decimal conversion to get wrong.
 *
 * Ties go to the EARLIER book in the caller's list, which is BETTABLE_BOOKS
 * order, so DraftKings wins a tie and the board does not reshuffle its badges
 * every refresh when two books post the same number.
 *
 * The comparison is only ever between rows for the SAME side at the SAME line
 * — a price hung off another number is a different bet (docs/best_line.md §5),
 * and the callers guarantee it: props filter on `sameLine` before they get
 * here, and team lines anchor to one book's number below.
 */
function bestOf<T>(
  candidates: readonly T[],
  priceOf: (row: T) => number | null,
): { row: T; price: number } | null {
  let best: { row: T; price: number } | null = null;
  for (const row of candidates) {
    const price = priceOf(row);
    if (price == null) continue;
    if (best == null || price > best.price) best = { row, price };
  }
  return best;
}

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
 * people. Returns the set of keys that are AMBIGUOUS and must not be joined on.
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
 * The selected book's quote per player for one market, at one line and side.
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
    /** The member's sportsbooks. The ONLY books the column prints — no
     *  fallback outside the set; the best price among them wins the cell. */
    books: readonly string[];
    gameIds?: Set<string> | null;
  },
): Map<string, StatsOddsQuote> {
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

  // Candidates in the member's own order, so bestOf's tie-break is stable.
  const rank = new Map(opts.books.map((b, i) => [b, i] as const));
  const out = new Map<string, StatsOddsQuote>();
  for (const [key, list] of byPlayer) {
    const mine = list
      .filter((r) => rank.has(r.bookmaker))
      .sort((a, b) => (rank.get(a.bookmaker) ?? 0) - (rank.get(b.bookmaker) ?? 0));
    const best = bestOf(mine, (r) =>
      num(opts.side === 'under' ? r.under_price : r.over_price),
    );
    if (best == null) continue;
    out.set(key, {
      playerKey: key,
      playerName: best.row.player_name,
      gameId: best.row.game_id,
      market: opts.market,
      line: opts.line,
      side: opts.side,
      book: best.row.bookmaker,
      price: best.price,
      link: (opts.side === 'under' ? best.row.under_link : best.row.over_link) ?? null,
      bookRows: list as unknown as BookPricedRow[],
    });
  }
  return out;
}

/** The winning book's quote for one leaderboard row, or null. */
export function quoteForRow(
  row: { player_name?: string | null },
  quoteIndex: Map<string, StatsOddsQuote>,
  ambiguous?: Set<string>,
): StatsOddsQuote | null {
  const key = normalizePlayerName(row.player_name);
  if (!key || ambiguous?.has(key)) return null;
  return quoteIndex.get(key) ?? null;
}

/**
 * Does ANY of the member's books post a line for this market on the slate?
 * Drives the "FanDuel doesn't post Hits lines" note, so an empty column reads
 * as their books' coverage rather than as a broken screen (UX_REVIEW §3).
 */
export function bookPostsMarket(
  rows: PropOddsByBookRow[],
  market: string,
  books: readonly string[],
  gameIds?: Set<string> | null,
): boolean {
  const set = new Set(books);
  return rows.some(
    (r) => r.market === market && set.has(r.bookmaker) && (!gameIds || gameIds.has(r.game_id)),
  );
}

/**
 * The games on the slate that have NOT started — the only ones with a line a
 * user can still take. The "latest" pre-game row for a game in progress is a
 * live number (Pittsburgh read −50000 up four runs on 2026-09-03), and the
 * refresh keeps writing `open` rows after first pitch (CLAUDE.md §6), so a
 * date bound alone would print in-play prices under a "current line" header.
 * A game with no commence_time is kept: fail open, never blank the column.
 */
export function unstartedGameIds(games: GameRow[], nowIso: string): Set<string> {
  const now = Date.parse(nowIso);
  const out = new Set<string>();
  for (const g of games) {
    const t = g.commence_time ? Date.parse(g.commence_time) : NaN;
    if (Number.isNaN(t) || Number.isNaN(now) || t > now) out.add(g.game_id);
  }
  return out;
}

// ── The betslip's one dependence on a pick ──────────────────────────────────

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
 * The pick a row could add to the betslip: the model's pick for this player,
 * ONLY when it was scored at the line the board is showing. A parlay leg is a
 * bet of record, and Over 0.5 is not a leg on an Over 1.5 board.
 */
export function slipPickFor(
  row: { player_id?: string | null },
  pickIndex: Map<string, EnrichedPick>,
  line: number,
): EnrichedPick | null {
  const pick = row.player_id ? pickIndex.get(row.player_id) : undefined;
  return pick && sameLine(num(pick.pick.scored_line), line) ? pick : null;
}

// ── Teams ───────────────────────────────────────────────────────────────────

/** The game market a team stat is naturally read against. */
export type TeamLineMarket = 'h2h' | 'spreads' | 'totals';

/** One book's number for a team's game, from that team's side. */
export interface TeamLineQuote {
  team: string;
  opponent: string;
  isHome: boolean;
  gameId: string;
  market: TeamLineMarket;
  book: string;
  /** The team's own side: its moneyline, its spread, or the game total (over). */
  price: number;
  /** Spread from the team's side (−1.5 = favourite) or the total; null on h2h. */
  line: number | null;
  link: string | null;
}

/**
 * Which market a team stat reads against. Scoring stats → the total; margin
 * and every against-the-spread split → the spread; the rest → the moneyline.
 * A team's Over% beside the game total, its ATS% beside its spread, its Win%
 * beside its moneyline — the line the research question is about.
 */
export function teamLineMarketFor(statKey: string): TeamLineMarket {
  if (
    statKey === 'over_pct' ||
    statKey === 'points_for_pg' ||
    statKey === 'points_against_pg' ||
    statKey === 'pace'
  ) {
    return 'totals';
  }
  if (statKey === 'point_diff_pg' || statKey.includes('ats')) return 'spreads';
  return 'h2h';
}

/**
 * The best of the member's books for every team on the slate, from each team's
 * own side. One entry per team, so a game yields two — the home side and the
 * away side of the same row. Bound to `games` (the sport's slate on the date)
 * so an NBA row can never land on a WNBA team that shares an abbrev.
 *
 * SPREADS AND TOTALS ANCHOR TO ONE NUMBER BEFORE THEY SHOP. Books hang
 * different lines — −1.5 at one, −2.5 at another — and the better price on a
 * different number is a different bet (docs/best_line.md §5), so the anchor is
 * the first of the member's books (BETTABLE_BOOKS order, hence DraftKings when
 * it is selected) that posts the market, and only books on that same number
 * compete for the cell. Moneylines have no line, so they shop freely.
 */
export function buildTeamLineIndex(
  rows: OddsByBookRow[],
  games: GameRow[],
  opts: { market: TeamLineMarket; books: readonly string[]; gameIds?: Set<string> | null },
): Map<string, TeamLineQuote> {
  const out = new Map<string, TeamLineQuote>();
  const rank = new Map(opts.books.map((b, i) => [b, i] as const));
  // Every selected book's row for a game, in the member's own book order.
  const byGame = new Map<string, OddsByBookRow[]>();
  for (const r of rows) {
    if (r.market !== opts.market || !rank.has(r.bookmaker)) continue;
    const list = byGame.get(r.game_id);
    if (list) list.push(r);
    else byGame.set(r.game_id, [r]);
  }
  for (const list of byGame.values()) {
    list.sort((a, b) => (rank.get(a.bookmaker) ?? 0) - (rank.get(b.bookmaker) ?? 0));
  }
  for (const g of games) {
    if (opts.gameIds && !opts.gameIds.has(g.game_id)) continue;
    const all = byGame.get(g.game_id);
    if (!all || all.length === 0 || !g.home_team || !g.away_team) continue;

    // The anchor's number is the bet; books on any other number are a
    // different bet and do not compete.
    let candidates = all;
    let anchorSpread: number | null = null;
    let anchorTotal: number | null = null;
    if (opts.market === 'spreads') {
      const anchor = all.find((r) => num(r.spread_home) != null);
      if (!anchor) continue;
      anchorSpread = num(anchor.spread_home);
      candidates = all.filter((r) => sameLine(num(r.spread_home), anchorSpread));
    } else if (opts.market === 'totals') {
      const anchor = all.find((r) => num(r.total_line) != null);
      if (!anchor) continue;
      anchorTotal = num(anchor.total_line);
      candidates = all.filter((r) => sameLine(num(r.total_line), anchorTotal));
    }

    for (const isHome of [true, false]) {
      const team = isHome ? g.home_team : g.away_team;
      const opponent = isHome ? g.away_team : g.home_team;
      let line: number | null = null;
      let best: { row: OddsByBookRow; price: number } | null = null;
      if (opts.market === 'totals') {
        best = bestOf(candidates, (r) => num(r.over_price));
        line = anchorTotal;
      } else {
        best = bestOf(candidates, (r) => num(isHome ? r.home_price : r.away_price));
        if (opts.market === 'spreads') {
          if (anchorSpread == null) continue;
          line = isHome ? anchorSpread : -anchorSpread;
        }
      }
      if (best == null) continue;
      if (opts.market === 'totals' && line == null) continue;
      const link =
        opts.market === 'totals'
          ? best.row.over_link
          : isHome
            ? best.row.home_link
            : best.row.away_link;
      out.set(team, {
        team,
        opponent,
        isHome,
        gameId: g.game_id,
        market: opts.market,
        book: best.row.bookmaker,
        price: best.price,
        line,
        link: link ?? null,
      });
    }
  }
  return out;
}

/** "ML", "−1.5", "+1.5", "o8.5" — the caption under a team's price. Every cell
 *  carries one: the caption is what tells the user which market the column is
 *  showing, and a bare moneyline pill beside two-line spread cells left the
 *  row unbalanced and the target under 44pt (UX review, 2026-09-03). */
export function teamLineCaption(q: TeamLineQuote): string | null {
  if (q.market === 'h2h') return 'ML';
  if (q.line == null) return null;
  if (q.market === 'totals') return `o${q.line}`;
  const n = Math.abs(q.line) === 0 ? 0 : q.line;
  return `${n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n)}`;
}
