import { useCallback, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';

import { errorText, isAbortError } from '@/lib/errors';
import {
  fetchDkInplayForGames,
  fetchLiveGameStates,
  fetchLiveScoreboard,
  fetchNcaafScoreboard,
  fetchNextScoreboardGame,
  fetchScoreboardDkOdds,
  fetchScoreboardGames,
  type LiveScoreboardRow,
  type NcaafScoreboardRow,
} from '@/lib/queries';
import {
  ESPN_LIVE_SPORTS,
  feedFromEspn,
  feedFromMlb,
  feedFromNcaaf,
  mergeDkInplay,
  scoreboardPhase,
  type ScoreboardFeed,
  type ScoreboardQuote,
} from '@/lib/scoreboard';
import type { GameRow, LatestDkOddsRow, LiveGameStateRow } from '@/types';

const POLL_MS = 30_000;

function missingRelation(e: unknown): boolean {
  const msg = errorText(e, '');
  return /schema cache|does not exist|could not find the table|PGRST205/i.test(msg);
}

function groupQuotes(rows: readonly LatestDkOddsRow[]): Map<string, ScoreboardQuote[]> {
  const out = new Map<string, ScoreboardQuote[]>();
  for (const row of rows) {
    const list = out.get(row.game_id) ?? [];
    list.push(row);
    out.set(row.game_id, list);
  }
  return out;
}

/**
 * Games, DK lines and stored live state for the Scoreboard segment.
 * Fetches only while the segment is open and the screen is focused.
 * A missing NCAAF view, or a live_scoreboard table that is not created
 * yet, leaves that sport without live scores. It does not invent them.
 */
export function useScoreboard(enabled: boolean, dates: readonly string[], sport: string, anchorDate: string) {
  const [games, setGames] = useState<GameRow[]>([]);
  const [quotes, setQuotes] = useState<Map<string, ScoreboardQuote[]>>(new Map());
  const [feeds, setFeeds] = useState<Map<string, ScoreboardFeed>>(new Map());
  const [inplay, setInplay] = useState<Map<string, ScoreboardQuote[]>>(new Map());
  const [nextGame, setNextGame] = useState<GameRow | null>(null);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [linesError, setLinesError] = useState<string | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const [ncaafUnavailable, setNcaafUnavailable] = useState(false);
  const [liveScoresUnavailable, setLiveScoresUnavailable] = useState(false);
  const loadGen = useRef(0);
  const inplayRef = useRef<Map<string, ScoreboardQuote[]>>(new Map());
  const dateKey = dates.join(',');

  const load = useCallback(async () => {
    if (!enabled) return;
    const gen = ++loadGen.current;
    const slate = dateKey.split(',').filter((d) => d.length > 0);
    setLoading(true);
    setError(null);
    try {
      const gs = await fetchScoreboardGames(slate);
      if (gen !== loadGen.current) return;
      const ncaafIds = gs.filter((game) => game.sport === 'NCAAF').map((game) => game.game_id);
      // Only games that have started can have a live row.
      const startedIds = gs
        .filter((game) => ESPN_LIVE_SPORTS.includes(game.sport))
        .filter((game) => {
          const t = game.commence_time ? Date.parse(game.commence_time) : NaN;
          return Number.isFinite(t) && t <= Date.now() + 10 * 60 * 1000;
        })
        .map((game) => game.game_id);
      const [oddsRes, mlbRes, ncaafRes, espnRes, nextRes] = await Promise.all([
        fetchScoreboardDkOdds(slate).then(
          (rows) => ({ rows, error: null as string | null }),
          (e: unknown) => ({ rows: [] as LatestDkOddsRow[], error: isAbortError(e) ? null : errorText(e) }),
        ),
        fetchLiveGameStates(slate).then(
          (rows) => ({ rows, error: null as string | null }),
          (e: unknown) => ({
            rows: [] as LiveGameStateRow[],
            error: isAbortError(e) ? null : errorText(e),
          }),
        ),
        fetchNcaafScoreboard(ncaafIds).then(
          (rows) => ({ rows, missing: false, error: null as string | null }),
          (e: unknown) => ({
            rows: [] as NcaafScoreboardRow[],
            missing: missingRelation(e),
            error: isAbortError(e) || missingRelation(e) ? null : errorText(e),
          }),
        ),
        fetchLiveScoreboard(startedIds).then(
          (rows) => ({ rows, missing: false, error: null as string | null }),
          (e: unknown) => ({
            rows: [] as LiveScoreboardRow[],
            missing: missingRelation(e),
            error: isAbortError(e) || missingRelation(e) ? null : errorText(e),
          }),
        ),
        gs.some((g) => g.sport === sport && g.game_date === anchorDate)
          ? Promise.resolve(null)
          : fetchNextScoreboardGame(sport, anchorDate).catch(() => null),
      ]);
      if (gen !== loadGen.current) return;

      const now = Date.now();
      const mlbById = new Map(mlbRes.rows.map((row) => [row.game_id, row]));
      const ncaafById = new Map(ncaafRes.rows.map((row) => [row.game_id, row]));
      const espnById = new Map(espnRes.rows.map((row) => [row.game_id, row]));
      const feedMap = new Map<string, ScoreboardFeed>();
      for (const game of gs) {
        const feed = game.sport === 'MLB'
          ? feedFromMlb(mlbById.get(game.game_id), now)
          : game.sport === 'NCAAF'
            ? feedFromNcaaf(ncaafById.get(game.game_id), now)
            : ESPN_LIVE_SPORTS.includes(game.sport)
              ? feedFromEspn(espnById.get(game.game_id), now)
              : null;
        if (feed) feedMap.set(game.game_id, feed);
      }
      const liveIds = gs
        .filter((game) => scoreboardPhase(game, feedMap.get(game.game_id) ?? null) === 'live')
        .map((game) => game.game_id);
      const merged = mergeDkInplay(inplayRef.current, liveIds, await fetchDkInplayForGames(liveIds));
      const liveLines = merged.lines;
      const inplayError = merged.error;
      if (gen !== loadGen.current) return;

      setGames(gs);
      setQuotes(groupQuotes(oddsRes.rows));
      setFeeds(feedMap);
      inplayRef.current = liveLines;
      setInplay(liveLines);
      setNextGame(nextRes);
      setLinesError(oddsRes.error ?? inplayError);
      setNcaafUnavailable(ncaafRes.missing);
      setLiveScoresUnavailable(espnRes.missing);
      setLiveError(
        sport === 'MLB'
          ? mlbRes.error
          : sport === 'NCAAF'
            ? ncaafRes.error
            : ESPN_LIVE_SPORTS.includes(sport)
              ? espnRes.error
              : null,
      );
      setLoaded(true);
    } catch (e: unknown) {
      if (gen !== loadGen.current) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (gen === loadGen.current) setLoading(false);
    }
  }, [enabled, dateKey, sport, anchorDate]);

  useFocusEffect(
    useCallback(() => {
      if (!enabled) return;
      void load();
      const id = setInterval(() => void load(), POLL_MS);
      return () => clearInterval(id);
    }, [enabled, load]),
  );

  return {
    games,
    quotes,
    feeds,
    inplay,
    nextGame,
    loading,
    loaded,
    error,
    linesError,
    liveError,
    ncaafUnavailable,
    liveScoresUnavailable,
    refresh: load,
  };
}
