/**
 * The player page's added sections, loaded INDEPENDENTLY of the chart.
 *
 * usePlayerTrends owns the game log and the chart; this hook adds what a
 * bettor checks around it — tonight's posted line and its movement, the
 * sharp book's read, the home/away and head-to-head splits behind the same
 * threshold, our settled record on the player, and (MLB) the Statcast and
 * lineup context the prop models already train on. Each section carries its
 * own loading / error, so a books view being down never blanks the chart.
 *
 * Plain `useEffect` only (.claude/rules/frontend.md).
 */
import { useEffect, useMemo, useState } from 'react';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { useNow } from '@/hooks/useNow';
import { errorText } from '@/lib/errors';
import { addDays, todayET, yearET } from '@/lib/format';
import { MODEL_BOOK } from '@/lib/markets';
import type { PlayerLogEntry, PlayerLogSport } from '@/lib/playerLog';
import {
  fetchGamesByIds,
  fetchH2HStatValues,
  fetchLineupSlot,
  fetchPropLineRows,
  fetchPropOddsHistory,
  fetchSavantStats,
  fetchSettledPropPicksForPlayer,
  fetchSlateGames,
} from '@/lib/queries';
import { propMarketForStat, type StatDef } from '@/lib/statCatalog';
import { earliestUpcomingGame, type SlateGame } from '@/lib/statsBoard';
import { unstartedGameIds } from '@/lib/statsOdds';
import {
  playerHeadToHead,
  playerPickRecord,
  propLineMove,
  statSplits,
  tonightLine,
  type PlayerHeadToHead,
  type PlayerPickRecord,
  type PropLineMove,
  type StatSplits,
  type TonightLine,
} from '@/lib/playerDetail';
import type { HitDirection } from '@/lib/hitRate';
import type {
  GameRow,
  H2HStatValuesRow,
  LineupSlotRow,
  PlayerType,
  PropOddsByBookRow,
  PropOddsSnapshotRow,
  SavantStatsRow,
} from '@/types';

export interface Section<T> {
  data: T;
  loading: boolean;
  error: string | null;
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

export interface PlayerNextGame {
  entry: SlateGame;
  unstarted: boolean;
}

/**
 * The season label the H2H read starts from — the same value the Stats
 * board uses, so the two surfaces cannot disagree about which two seasons
 * "the last 2 years" means. Football's start-year label falls back a season
 * inside fetchH2HStatValues, as every other football read does.
 */
const SEASON = yearET();

export function usePlayerDetail(args: {
  sport: PlayerLogSport;
  playerId: string | null;
  playerName: string;
  playerType?: PlayerType | null;
  /** The log the chart is built from — newest first. */
  games: PlayerLogEntry[];
  stat: StatDef | null;
  /** The page's "at least" threshold; the book's line is the half-point below. */
  threshold: number | null;
  /**
   * The page's RESOLVED bet \u2014 `selectionFor(threshold, mode)`. Separate from
   * `threshold` because they are two idioms for one number and only this one
   * carries the SIDE: in Under mode `threshold` alone counts the over
   * (lib/hitMode, and playerDetail.bucket's note).
   */
  selection: { line: number; side: HitDirection };
}) {
  const { sport, playerId, playerName, playerType, games, stat, threshold, selection } = args;
  const { books, ready: booksReady } = usePreferredBooks();
  const today = todayET();
  const now = useNow();
  const team = games[0]?.team ?? null;
  const market = useMemo(() => propMarketForStat(stat), [stat]);
  // Pull-to-refresh: every section keys on this, so one slow read still
  // cannot hold the others back (UX review: an error with no retry).
  const [nonce, setNonce] = useState(0);
  const reload = () => setNonce((n) => n + 1);

  // ── Next game, from the player's current team ────────────────────────────
  // Same 7-day window as the team page. earliestUpcomingGame, not tonight's
  // slate date: a player whose team kicks off Thursday must still get a line
  // when the board's "tonight" is Sunday.
  const slate = useSection<GameRow[]>(
    [],
    () => fetchSlateGames(sport, today, addDays(today, 7)),
    [sport, today, nonce],
  );
  const nextGame: PlayerNextGame | null = useMemo(() => {
    if (!team) return null;
    const entry = earliestUpcomingGame(slate.data, team, new Date(now).toISOString());
    if (!entry) return null;
    return { entry, unstarted: unstartedGameIds([entry.game], new Date(now).toISOString()).has(entry.game.game_id) };
  }, [slate.data, team, now]);
  const gameId = nextGame?.entry.game.game_id ?? null;
  const opponent = nextGame?.entry.opponent ?? null;

  // ── Tonight's line for the selected stat, and its movement ───────────────
  // fetchPropLineRows is bounded by (game, market, player): a few dozen rows.
  // The history read is capped at 50 oldest-first, which is enough for the
  // OPENING row; the latest comes from the all-books view.
  const lines = useSection<{ rows: PropOddsByBookRow[]; history: PropOddsSnapshotRow[] }>(
    { rows: [], history: [] },
    gameId && market
      ? async () => {
          const [rows, history] = await Promise.all([
            fetchPropLineRows(gameId, market, playerName),
            fetchPropOddsHistory(gameId, market, playerName, MODEL_BOOK).catch(() => [] as PropOddsSnapshotRow[]),
          ]);
          return { rows, history };
        }
      : null,
    [gameId, market, playerName, nonce],
  );
  const tonight: TonightLine | null = useMemo(
    () => (market ? tonightLine(lines.data.rows, market, books, MODEL_BOOK) : null),
    [lines.data.rows, market, books],
  );
  const move: PropLineMove | null = useMemo(() => {
    const dk = lines.data.rows.find((r) => r.bookmaker === MODEL_BOOK && (tonight ? Number(r.line) === tonight.line : true)) ?? null;
    return propLineMove(lines.data.history, dk);
  }, [lines.data, tonight]);

  // ── Splits: home / away / vs tonight's opponent / starter ────────────────
  // The MLB and basketball logs carry no opponent or venue; the games table
  // does, and every log game_id joins to it (measured 2026-09-20: 5,000 of
  // 5,000 on each log). One chunked read of the log's ids.
  const logIds = useMemo(() => games.map((g) => g.game_id), [games]);
  const logGames = useSection<GameRow[]>(
    [],
    logIds.length > 0 ? () => fetchGamesByIds(logIds) : null,
    [logIds.join('|'), nonce],
  );
  const gamesById = useMemo(() => new Map(logGames.data.map((g) => [g.game_id, g] as const)), [logGames.data]);
  const splits: StatSplits | null = useMemo(() => {
    if (!stat || threshold == null || games.length === 0) return null;
    return statSplits(games, gamesById, stat, selection.line, selection.side, sport === 'NBA' || sport === 'WNBA');
  }, [games, gamesById, stat, threshold, selection.line, selection.side, sport]);

  // ── Head-to-head with the next opponent, last two seasons ─────────────
  // Its own read rather than a slice of `games` above, and the difference is
  // SPAN: that log is 25 rows in football and 50 elsewhere, so a "vs KC" cut
  // out of it answers "inside the last fifty games", not "in the last two
  // seasons" (playerDetail.playerHeadToHead). The RPC is bounded to the two
  // seasons server-side and returns one compact row.
  //
  // Keyed on the STAT as well as the opponent: the RPC returns one stat's
  // values, so a chip tap refetches here where it does not for the chart.
  const h2hRow = useSection<H2HStatValuesRow | null>(
    null,
    team && opponent && stat
      ? async () => {
          const rows = await fetchH2HStatValues(
            sport,
            SEASON,
            String(stat.key),
            { teams: [team], opponents: [opponent] },
            playerType ?? undefined,
          );
          // The read is narrowed to one fixture, but a fixture is a TEAM pair:
          // it comes back with every player on that team who has met them.
          return rows.find((r) => r.player_id === playerId) ?? null;
        }
      : null,
    [sport, team, opponent, playerId, stat?.key, playerType, nonce],
  );
  const h2h: PlayerHeadToHead | null = useMemo(() => {
    if (!opponent || threshold == null) return null;
    const row = h2hRow.data;
    // An opponent with no stored meeting is still an answer — "they have not
    // played" is what the card says, and it needs the opponent's name to say
    // it. A null row is therefore an EMPTY head-to-head, not a missing one.
    return playerHeadToHead(opponent, row?.values ?? [], row?.dates ?? [], selection.line, selection.side);
  }, [h2hRow.data, opponent, threshold, selection.line, selection.side]);

  // ── Our record on this player ────────────────────────────────────────────
  const picks = useSection(
    [] as Awaited<ReturnType<typeof fetchSettledPropPicksForPlayer>>,
    () => fetchSettledPropPicksForPlayer({ sport, playerId, playerName }),
    [sport, playerId, playerName, nonce],
  );
  const record: PlayerPickRecord = useMemo(() => playerPickRecord(picks.data), [picks.data]);

  // ── MLB context: Statcast season line, tonight's lineup slot ─────────────
  const season = Number(today.slice(0, 4));
  const savant = useSection<SavantStatsRow | null>(
    null,
    sport === 'MLB' && playerId && playerType ? () => fetchSavantStats(playerId, playerType, season) : null,
    [sport, playerId, playerType, season, nonce],
  );
  const lineup = useSection<LineupSlotRow | null>(
    null,
    sport === 'MLB' && playerId && gameId ? () => fetchLineupSlot(gameId, playerId) : null,
    [sport, playerId, gameId, nonce],
  );

  return {
    reload,
    loading: slate.loading || lines.loading || logGames.loading || picks.loading,
    books,
    booksReady,
    market,
    nextGame,
    h2h,
    h2hLoading: h2hRow.loading,
    slateLoading: slate.loading,
    tonight,
    move,
    linesLoading: lines.loading,
    linesError: lines.error,
    splits,
    splitsLoading: logGames.loading,
    record,
    picksLoading: picks.loading,
    picksError: picks.error,
    savant: savant.data,
    lineup: lineup.data,
  };
}
