/**
 * Everything the team page needs, loaded as INDEPENDENT sections.
 *
 * Six reads feed one screen, and they must not share a fate: the public
 * splits view being empty (every sport but MLB today), the odds history being
 * slow, or the picks table timing out, none of it may cost the form strip or
 * the league ranks. Each section carries its own loading / error / data, and
 * the screen renders what has arrived.
 *
 * Plain `useEffect`, never `useFocusEffect` — this hook is only ever mounted
 * on a pushed screen, but the app-root rule (.claude/rules/frontend.md) is
 * cheaper to follow everywhere than to reason about per call site.
 */
import { useEffect, useMemo, useState } from 'react';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { useNow } from '@/hooks/useNow';
import { errorText } from '@/lib/errors';
import { addDays, todayET } from '@/lib/format';
import { MODEL_BOOK } from '@/lib/markets';
import {
  fetchGameLineRowsAllMarkets,
  fetchHeadToHead,
  fetchNflTeamGameStats,
  fetchOpeningLine,
  fetchPublicSplits,
  fetchSettledGamePicksForGames,
  fetchSlateGames,
  fetchTeamRecentGamesForSport,
  fetchTeamStats,
} from '@/lib/queries';
import { buildSlateGameIndex, buildTonightSlate, slateGameFor, type SlateGame } from '@/lib/statsBoard';
import { unstartedGameIds } from '@/lib/statsOdds';
import {
  formFromGames,
  headToHead,
  lineMove,
  nflCoverMarks,
  publicRead,
  sharpRead,
  teamPickRecords,
  withCoverMarks,
  type FormGame,
  type HeadToHead,
  type LineMove,
  type PublicRead,
  type SharpRead,
  type TeamMarket,
} from '@/lib/teamDetail';
import type {
  GameRow,
  OddsByBookRow,
  OddsSnapshotRow,
  PublicBettingRow,
  TeamSport,
  TeamStatsRow,
} from '@/types';

export interface Section<T> {
  data: T;
  loading: boolean;
  error: string | null;
}

const MARKETS: TeamMarket[] = ['h2h', 'spreads', 'totals'];

/** How many finished games the form strip and the pick record look back over. */
export const FORM_GAMES = 10;
export const RECORD_GAMES = 40;

export interface NextGame {
  entry: SlateGame;
  /** False once the game has started — no line a user can still take. */
  unstarted: boolean;
  /** Every book's latest row for the game's three markets. */
  lines: OddsByBookRow[];
  /** DraftKings' opening snapshot per market; null where none is stored. */
  opening: Partial<Record<TeamMarket, OddsSnapshotRow | null>>;
  splits: PublicBettingRow[];
  moves: Partial<Record<TeamMarket, LineMove | null>>;
  sharp: Partial<Record<TeamMarket, SharpRead | null>>;
  publicSide: Partial<Record<TeamMarket, PublicRead | null>>;
}

function useSection<T>(
  initial: T,
  load: (() => Promise<T>) | null,
  deps: readonly unknown[],
): Section<T> {
  const [state, setState] = useState<Section<T>>({ data: initial, loading: load != null, error: null });
  useEffect(() => {
    if (!load) {
      setState({ data: initial, loading: false, error: null });
      return undefined;
    }
    let cancelled = false;
    setState((s) => ({ ...s, loading: true, error: null }));
    load()
      .then((data) => {
        if (!cancelled) setState({ data, loading: false, error: null });
      })
      .catch((e: unknown) => {
        if (!cancelled) setState({ data: initial, loading: false, error: errorText(e) });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return state;
}

export function useTeamDetail(sport: TeamSport, team: string, season: number | null) {
  const { books, ready: booksReady } = usePreferredBooks();
  const today = todayET();
  const now = useNow();
  // Pull-to-refresh: bumping this re-runs every section. Sections key their
  // effects on it rather than on a shared promise so one slow read still
  // cannot hold the others back.
  const [nonce, setNonce] = useState(0);
  const refresh = () => setNonce((n) => n + 1);

  // ── The board's own row, and the league it ranks in ─────────────────────
  // fetchTeamStats owns the football season fallback and reports the season
  // it used; the page labels its numbers from that, never from the request.
  const board = useSection<{ season: number | null; rows: TeamStatsRow[] }>(
    { season: null, rows: [] },
    // The ET year, never a bare new Date(): CLAUDE.md §7's "today is ET".
    () => fetchTeamStats(sport, season ?? Number(today.slice(0, 4))),
    [sport, season, nonce],
  );
  const row = useMemo(() => board.data.rows.find((r) => r.team === team) ?? null, [board.data.rows, team]);

  // ── Recent finished games (form + the pick-record window) ───────────────
  const recent = useSection<GameRow[]>(
    [],
    () => fetchTeamRecentGamesForSport(sport, team, addDays(today, 1), RECORD_GAMES),
    [sport, team, today, nonce],
  );

  // NFL closing lines per game, for the cover / over marks on the form strip.
  const nflSeason = board.data.season;
  const nflLines = useSection(
    [] as Awaited<ReturnType<typeof fetchNflTeamGameStats>>,
    sport === 'NFL' && nflSeason != null ? () => fetchNflTeamGameStats(team, nflSeason) : null,
    [sport, team, nflSeason, nonce],
  );

  const form: FormGame[] = useMemo(() => {
    const base = formFromGames(recent.data, team);
    if (sport !== 'NFL' || nflLines.data.length === 0) return base;
    return withCoverMarks(base, nflCoverMarks(nflLines.data));
  }, [recent.data, team, sport, nflLines.data]);

  // ── Our record on this team, over the same games ────────────────────────
  const gameIds = useMemo(() => recent.data.map((g) => g.game_id), [recent.data]);
  const picks = useSection(
    [] as Awaited<ReturnType<typeof fetchSettledGamePicksForGames>>,
    gameIds.length > 0 ? () => fetchSettledGamePicksForGames(gameIds) : null,
    [gameIds.join('|'), nonce],
  );
  const pickRecords = useMemo(
    () => teamPickRecords(picks.data, recent.data, team),
    [picks.data, recent.data, team],
  );

  // ── The next game: fixture, lines, movement, sharp read, public read ────
  const slate = useSection<{ date: string; isToday: boolean; games: GameRow[]; window: GameRow[] }>(
    { date: '', isToday: false, games: [], window: [] },
    async () => {
      const games = await fetchSlateGames(sport, today, addDays(today, 7));
      const t = buildTonightSlate(games, sport, today);
      return { date: t.date, isToday: t.isToday, games: games.filter((g) => g.game_date === t.date), window: games };
    },
    [sport, today, nonce],
  );
  // The NEXT game is the first one in the window that has not started; only
  // when the team has none left this week does the page fall back to today's
  // slate entry (a game in progress or just finished), which the card then
  // labels Live / Final rather than "next" (UX review, 2026-09-20).
  const entry = useMemo(() => {
    const nowIso = new Date(now).toISOString();
    const upcoming = slate.data.window
      .filter((g) => (g.home_team === team || g.away_team === team) && !!g.commence_time && g.commence_time > nowIso)
      .sort((a, b) => String(a.commence_time).localeCompare(String(b.commence_time)))[0];
    if (upcoming) {
      const isHome = upcoming.home_team === team;
      return { game: upcoming, opponent: isHome ? upcoming.away_team : upcoming.home_team, isHome } as SlateGame;
    }
    const idx = buildSlateGameIndex(
      slate.data.games,
      { date: slate.data.date, isToday: slate.data.isToday, keys: new Set<string>() },
      nowIso,
    );
    return slateGameFor({ team }, idx)?.game ?? null;
  }, [slate.data, team, now]);
  const gameId = entry?.game.game_id ?? null;
  const isHome = entry?.isHome === true;

  const market = useSection<{
    lines: OddsByBookRow[];
    opening: Partial<Record<TeamMarket, OddsSnapshotRow | null>>;
    splits: PublicBettingRow[];
  }>(
    { lines: [], opening: {}, splits: [] },
    gameId
      ? async () => {
          // Four small reads, in parallel, none allowed to sink the others:
          // the opening line is history (odds), the current lines are the
          // all-books view, the splits are one sport's table.
          const [lines, openRows, splits] = await Promise.all([
            fetchGameLineRowsAllMarkets(gameId),
            Promise.all(MARKETS.map((m) => fetchOpeningLine(gameId, m, MODEL_BOOK).catch(() => null))),
            fetchPublicSplits(gameId).catch(() => [] as PublicBettingRow[]),
          ]);
          const opening: Partial<Record<TeamMarket, OddsSnapshotRow | null>> = {};
          MARKETS.forEach((m, i) => {
            opening[m] = openRows[i];
          });
          return { lines, opening, splits };
        }
      : null,
    [gameId, nonce],
  );

  const nextGame: NextGame | null = useMemo(() => {
    if (!entry) return null;
    const nowIso = new Date(now).toISOString();
    const unstarted = unstartedGameIds([entry.game], nowIso).has(entry.game.game_id);
    const dk = (m: TeamMarket) =>
      market.data.lines.find((r) => r.market === m && r.bookmaker === MODEL_BOOK) ?? null;
    const moves: NextGame['moves'] = {};
    const sharp: NextGame['sharp'] = {};
    const publicSide: NextGame['publicSide'] = {};
    for (const m of MARKETS) {
      moves[m] = lineMove(market.data.opening[m] ?? null, dk(m), m, isHome);
      sharp[m] = sharpRead(market.data.lines, m, isHome, books);
      publicSide[m] = publicRead(market.data.splits, m, isHome);
    }
    return { entry, unstarted, lines: market.data.lines, opening: market.data.opening, splits: market.data.splits, moves, sharp, publicSide };
  }, [entry, now, market.data, isHome, books]);

  // ── Head-to-head with the next opponent ─────────────────────────────────
  const opponent = entry?.opponent ?? null;
  const h2hGames = useSection<GameRow[]>(
    [],
    opponent ? () => fetchHeadToHead(sport, team, opponent, 10) : null,
    [sport, team, opponent, nonce],
  );
  const h2h: HeadToHead | null = useMemo(
    () => (opponent ? headToHead(h2hGames.data, team, opponent) : null),
    [h2hGames.data, team, opponent],
  );

  const loading = board.loading || recent.loading || slate.loading;
  // The picks read waits on the recent-games read, so "loading" is both — or
  // the card prints its empty sentence for a frame before the spinner.
  const picksLoading = recent.loading || picks.loading;

  return {
    refresh,
    loading,
    books,
    booksReady,
    board,
    row,
    recent,
    form,
    picks,
    picksLoading,
    pickRecords,
    slate,
    nextGame,
    marketLoading: market.loading,
    marketError: market.error,
    h2h,
    h2hLoading: h2hGames.loading,
  };
}
