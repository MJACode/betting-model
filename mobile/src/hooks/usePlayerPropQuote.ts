import { useEffect, useMemo, useRef, useState } from 'react';

import { fetchPropLinesForGames, fetchSlateGames } from '@/lib/queries';
import { addDays, todayET } from '@/lib/format';
import { normalizePlayerName } from '@/lib/playerNews';
import {
  anyBookPostsSide,
  bookCoverageForMarket,
  buildQuoteIndex,
  unstartedGameIds,
  type BookSideCoverage,
  type StatsOddsQuote,
} from '@/lib/statsOdds';
import type { HitDirection } from '@/lib/hitRate';
import type { GameRow, PropOddsByBookRow } from '@/types';

/**
 * The sportsbook line behind the number the PLAYER CARD is showing.
 *
 * Matt, 2026-09-18, with a competitor's player card beside ours: "When on the
 * player card. I should be able to select different bet types for a player by
 * selecting the play type and should be able to place directly with a sports
 * book." The card could already flip stat and threshold; it had no price for
 * either, and its only action was an Add-to-betslip button gated on a MODEL
 * PICK existing at exactly that line — which is nothing, for most players.
 *
 * This is the missing half, and it is deliberately the same machinery the
 * Stats board prices its LINE column with, not a second one:
 *
 *  - `buildQuoteIndex` picks the quote, so the player card and the board agree
 *    on which book wins a cell, how an off-line quote is flagged, and when a
 *    name is too ambiguous to join (a wrong price on the wrong player is worse
 *    than a dash — data/name_match.py).
 *  - The quote is the best of the MEMBER'S books and nothing outside the set,
 *    which is the rule Matt set for the board on 2026-09-03 ("If they select
 *    FanDuel we only show FanDuel"). The compare sheet still lists every
 *    bettable book — the set narrows the headline, never the options.
 *  - The join is on the NORMALIZED name, client-side. The odds view carries no
 *    `player_id` (columns checked 2026-09-18: game_id, game_date, market,
 *    player_name, team, bookmaker, line, over/under price and link,
 *    snapshot_at), so `player_name` is the only key there is.
 *
 * WHICH GAME: the player's next UNSTARTED game, never the best-priced one.
 * Which game a player is in is a fact about the schedule; choosing it by the
 * number would be choosing the bet to suit the card (statsOdds nextGameRows
 * says the same thing one level down). A started game's "latest" pre-game row
 * is an in-play number — the evening refresh keeps writing `open` rows after
 * first pitch (CLAUDE.md §6) — so `unstartedGameIds` bounds it.
 */

/** How far ahead to look for the player's next game. Books post daily-sport
 *  props about a day out and weekly-sport props about a week out (measured
 *  2026-09-12), so a week covers every sport without inventing a horizon for
 *  the ones that play tonight. */
const FORWARD_DAYS = 7;

export interface PlayerPropQuote {
  /** The winning quote at the card's line and side, or null. */
  quote: StatsOddsQuote | null;
  /** The player's next unstarted game, for the sheet header's matchup line. */
  game: GameRow | null;
  /** What each of the member's books prices for this market — drives the
   *  honest empty state, computed from the rows on screen rather than from a
   *  per-sport coverage table nobody can keep true. */
  coverage: Map<string, BookSideCoverage>;
  /** Does ANY of their books sell this side at all? A card sitting on a side
   *  none of them posts is a dead end worth naming. */
  sidePosted: boolean;
  /** True once a market exists for the stat AND the player has a game we can
   *  price — so "no line" can be told apart from "nothing to price yet". */
  hasGame: boolean;
  loading: boolean;
  error: string | null;
}

export function usePlayerPropQuote(opts: {
  sport: string;
  /** The player's team, from their most recent log row. */
  team: string | null;
  playerName: string;
  /** The book market for the selected stat chip (`propMarketForStat`), or null
   *  when no book prices the stat at all. */
  market: string | null;
  /** The half-point line and side the card is on (`hitMode.selectionFor`). */
  line: number;
  side: HitDirection;
  /** The member's sportsbooks, in BETTABLE_BOOKS order. */
  books: readonly string[];
  /** The clock, threaded in so "unstarted" re-derives on the tick rather than
   *  freezing at mount (useNow — the board learned this on 2026-09-05). */
  now: number;
}): PlayerPropQuote {
  const { sport, team, playerName, market, line, side, books, now } = opts;

  const [games, setGames] = useState<GameRow[]>([]);
  const [rows, setRows] = useState<{ market: string; rows: PropOddsByBookRow[] }>({
    market: '',
    rows: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // The player's next games, by team. `fetchSlateGames` is already the
  // sport-wide forward read the Stats board uses, so this rides a query the
  // app knows how to page rather than adding a third schedule read.
  useEffect(() => {
    if (!team || !market) {
      setGames([]);
      return;
    }
    let cancelled = false;
    const from = todayET();
    fetchSlateGames(sport, from, addDays(from, FORWARD_DAYS))
      .then((all) => {
        if (cancelled) return;
        setGames(all.filter((g) => g.home_team === team || g.away_team === team));
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      cancelled = true;
    };
  }, [sport, team, market]);

  // The next UNSTARTED game, and the ones after it. Ranked so a player with a
  // Thursday and a Sunday game is quoted from Thursday (nextGameRows does the
  // final narrowing, but bounding the READ here is what keeps it cheap).
  const { gameIds, gameOrder, nextGame } = useMemo(() => {
    const open = unstartedGameIds(games, new Date(now).toISOString());
    const upcoming = games
      .filter((g) => open.has(g.game_id))
      .sort((a, b) => {
        const ta = Date.parse(a.commence_time ?? '');
        const tb = Date.parse(b.commence_time ?? '');
        if (Number.isNaN(ta) && Number.isNaN(tb)) return a.game_id < b.game_id ? -1 : 1;
        if (Number.isNaN(ta)) return 1;
        if (Number.isNaN(tb)) return -1;
        if (ta !== tb) return ta - tb;
        return a.game_id < b.game_id ? -1 : 1;
      });
    return {
      gameIds: upcoming.map((g) => g.game_id),
      gameOrder: new Map(upcoming.map((g, i) => [g.game_id, i] as const)),
      nextGame: upcoming[0] ?? null,
    };
  }, [games, now]);

  // Only the games we will actually quote from. Two is the real ceiling — a
  // player has one next game and, in a weekly sport mid-week, at most one
  // more that the books have started pricing — and it bounds the read to the
  // ~1,258-row worst case measured per game rather than the ~13,800-row
  // whole-slate one (queries.fetchPropLinesForGames).
  //
  // KEYED ON CONTENT, NOT ON `gameIds`'s IDENTITY. `now` ticks every 60
  // seconds, which recomputes `gameIds` and hands back a NEW ARRAY holding the
  // same ids; an effect depending on that identity re-fires on every tick, so
  // the card would re-read the odds once a minute for as long as it was open.
  // Joining to a string first gives a value that only changes when the games
  // actually do, and `readIds` is then memoized on THAT — so the array handed
  // to the effect keeps its identity across a tick.
  const readIdsKey = useMemo(() => gameIds.slice(0, 2).join(','), [gameIds]);
  const readIds = useMemo(
    () => (readIdsKey === '' ? [] : readIdsKey.split(',')),
    [readIdsKey],
  );
  const readKey = `${market ?? ''}|${readIdsKey}`;
  // The in-flight read's key, so a slow response for an older stat cannot land
  // on a newer one. `cancelled` alone does not cover a re-entry that resolves
  // out of order.
  const latest = useRef('');

  useEffect(() => {
    if (!market || readIds.length === 0) {
      setRows({ market: '', rows: [] });
      setLoading(false);
      return;
    }
    latest.current = readKey;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchPropLinesForGames(readIds, market)
      .then((r) => {
        if (cancelled || latest.current !== readKey) return;
        setRows({ market, rows: r });
      })
      .catch((e: unknown) => {
        if (cancelled || latest.current !== readKey) return;
        setError(e instanceof Error ? e.message : String(e));
        setRows({ market: '', rows: [] });
      })
      .finally(() => {
        if (!cancelled && latest.current === readKey) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [readKey, market, readIds]);

  const fresh = market != null && rows.market === market;
  const gameIdSet = useMemo(() => new Set(readIds), [readIds]);

  const quote = useMemo(() => {
    if (!fresh || !market) return null;
    const index = buildQuoteIndex(rows.rows, {
      market,
      line,
      side,
      books,
      gameIds: gameIdSet,
      gameOrder,
    });
    return index.get(normalizePlayerName(playerName)) ?? null;
  }, [fresh, rows, market, line, side, books, gameIdSet, gameOrder, playerName]);

  const coverage = useMemo(
    () =>
      fresh && market
        ? bookCoverageForMarket(rows.rows, market, books, gameIdSet)
        : new Map<string, BookSideCoverage>(),
    [fresh, rows, market, books, gameIdSet],
  );

  const game = useMemo(
    () => (quote ? games.find((g) => g.game_id === quote.gameId) ?? nextGame : nextGame),
    [quote, games, nextGame],
  );

  return {
    quote,
    game,
    coverage,
    sidePosted: anyBookPostsSide(coverage, side),
    hasGame: market != null && readIds.length > 0,
    loading,
    error,
  };
}
