import { useCallback, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';

import { errorText, isAbortError } from '@/lib/errors';
import {
  fetchDkInplayForGame,
  fetchLiveGameStates,
  fetchNcaafScoreboard,
  fetchNextScoreboardGame,
  fetchScoreboardDkOdds,
  fetchScoreboardGames,
  type NcaafScoreboardRow,
} from '@/lib/queries';
import {
  feedFromMlb,
  feedFromNcaaf,
  scoreboardPhase,
  type ScoreboardFeed,
  type ScoreboardQuote,
} from '@/lib/scoreboard';
import type { GameRow, LatestDkOddsRow, LiveGameStateRow, OddsSnapshotRow } from '@/types';

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

function newestByMarket(rows: readonly OddsSnapshotRow[]): ScoreboardQuote[] {
  const by = new Map<string, OddsSnapshotRow>();
  for (const row of rows) {
    const prev = by.get(row.market);
    if (!prev || row.snapshot_at > prev.snapshot_at) by.set(row.market, row);
  }
  return [...by.values()];
}

async function inplayFor(ids: readonly string[]): Promise<Map<string, ScoreboardQuote[]>> {
  const out = new Map<string, ScoreboardQuote[]>();
  const size = 6;
  for (let i = 0; i < ids.length; i += size) {
    const chunk = ids.slice(i, i + size);
    const rows = await Promise.all(
      chunk.map(async (id) => {
        try {
          return [id, newestByMarket(await fetchDkInplayForGame(id))] as const;
        } catch {
          return [id, [] as ScoreboardQuote[]] as const;
        }
      }),
    );
    for (const [id, quotes] of rows) if (quotes.length > 0) out.set(id, quotes);
  }
  return out;
}

/**
 * Games, DK lines and stored live state for the Scoreboard segment.
 * Fetches only while the segment is open and the screen is focused.
 * A missing NCAAF view leaves that sport without live scores. It does
 * not invent them.
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
  const loadGen = useRef(0);
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
      const [oddsRes, mlbRes, ncaafRes, nextRes] = await Promise.all([
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
        fetchNcaafScoreboard(slate).then(
          (rows) => ({ rows, missing: false, error: null as string | null }),
          (e: unknown) => ({
            rows: [] as NcaafScoreboardRow[],
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
      const feedMap = new Map<string, ScoreboardFeed>();
      for (const game of gs) {
        const feed = game.sport === 'MLB'
          ? feedFromMlb(mlbById.get(game.game_id), now)
          : game.sport === 'NCAAF'
            ? feedFromNcaaf(ncaafById.get(game.game_id), now)
            : null;
        if (feed) feedMap.set(game.game_id, feed);
      }
      const liveIds = gs
        .filter((game) => scoreboardPhase(game, feedMap.get(game.game_id) ?? null) === 'live')
        .map((game) => game.game_id);
      const liveLines = await inplayFor(liveIds);
      if (gen !== loadGen.current) return;

      setGames(gs);
      setQuotes(groupQuotes(oddsRes.rows));
      setFeeds(feedMap);
      setInplay(liveLines);
      setNextGame(nextRes);
      setLinesError(oddsRes.error);
      setNcaafUnavailable(ncaafRes.missing);
      setLiveError(sport === 'MLB' ? mlbRes.error : sport === 'NCAAF' ? ncaafRes.error : null);
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
    refresh: load,
  };
}
