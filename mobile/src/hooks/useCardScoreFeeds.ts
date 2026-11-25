// useCardScoreFeeds — the live and final score for every started non-MLB game
// on the Picks board, read from the SAME feeds the Scoreboard tab reads.
//
// Matt, 2026-11-24: a Queens @ Wofford card said LIVE with no score while the
// Scoreboard tab had it at 35–39, halftime. The card only read
// v_live_game_state_latest, which the MLB poller alone writes, so every other
// sport drew a bare LIVE badge. MLB keeps that path (it carries inning, outs
// and bases); this hook covers the rest: live_scoreboard for the ESPN sports
// and the NCAAF scoreboard for college football.
//
// Polls every 30s while the screen is focused, like useLiveGameStates. Only
// games that have started are asked for, so the read is one row per started
// game on the board — never the whole slate.

import { useCallback, useMemo, useRef, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import { fetchLiveScoreboard, fetchNcaafScoreboard } from '@/lib/queries';
import { ESPN_LIVE_SPORTS, feedFromEspn, feedFromNcaaf, type ScoreboardFeed } from '@/lib/scoreboard';
import type { GameRow } from '@/types';

const POLL_INTERVAL_MS = 30_000;
/** Same lead the Scoreboard uses: a game can tip a few minutes early. */
const START_LEAD_MS = 10 * 60 * 1000;

type GameLike = Pick<GameRow, 'game_id' | 'sport' | 'commence_time' | 'home_score' | 'away_score'>;

function started(game: GameLike, now: number): boolean {
  const t = game.commence_time ? Date.parse(game.commence_time) : NaN;
  return Number.isFinite(t) && t <= now + START_LEAD_MS;
}

/** Games with a stored final score need no feed: `games` already has it. */
function needsFeed(game: GameLike): boolean {
  return game.home_score == null || game.away_score == null;
}

export function useCardScoreFeeds(games: readonly (GameLike | null | undefined)[]) {
  const [feeds, setFeeds] = useState<Map<string, ScoreboardFeed>>(new Map());
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Keyed on the VALUE of the id lists, so a re-render that builds a new array
  // does not restart the poll. Recomputed each render; started-ness moves with
  // the clock, and the poll tick re-renders.
  const now = Date.now();
  const espnIds: string[] = [];
  const ncaafIds: string[] = [];
  const seen = new Set<string>();
  for (const g of games) {
    if (!g || seen.has(g.game_id) || !needsFeed(g) || !started(g, now)) continue;
    seen.add(g.game_id);
    if (g.sport === 'NCAAF') ncaafIds.push(g.game_id);
    else if (ESPN_LIVE_SPORTS.includes(g.sport)) espnIds.push(g.game_id);
  }
  const espnKey = espnIds.sort().join(',');
  const ncaafKey = ncaafIds.sort().join(',');

  const refresh = useCallback(async () => {
    const espn = espnKey ? espnKey.split(',') : [];
    const ncaaf = ncaafKey ? ncaafKey.split(',') : [];
    if (espn.length === 0 && ncaaf.length === 0) {
      setFeeds((prev) => (prev.size === 0 ? prev : new Map()));
      return;
    }
    // Enrichment only: a failed read keeps the last known scores (each feed
    // decays on its own freshness rule) and never blanks the board.
    const [espnRows, ncaafRows] = await Promise.all([
      fetchLiveScoreboard(espn).catch(() => null),
      fetchNcaafScoreboard(ncaaf).catch(() => null),
    ]);
    setFeeds((prev) => {
      const at = Date.now();
      const next = new Map<string, ScoreboardFeed>();
      if (espnRows) {
        for (const row of espnRows) {
          const feed = feedFromEspn(row, at);
          if (feed) next.set(row.game_id, feed);
        }
      } else {
        for (const id of espn) { const f = prev.get(id); if (f) next.set(id, f); }
      }
      if (ncaafRows) {
        for (const row of ncaafRows) {
          const feed = feedFromNcaaf(row, at);
          if (feed) next.set(row.game_id, feed);
        }
      } else {
        for (const id of ncaaf) { const f = prev.get(id); if (f) next.set(id, f); }
      }
      return next;
    });
  }, [espnKey, ncaafKey]);

  useFocusEffect(
    useCallback(() => {
      void refresh();
      timerRef.current = setInterval(() => void refresh(), POLL_INTERVAL_MS);
      return () => {
        if (timerRef.current) clearInterval(timerRef.current);
        timerRef.current = null;
      };
    }, [refresh]),
  );

  return useMemo(() => ({ byGame: feeds, refresh }), [feeds, refresh]);
}
