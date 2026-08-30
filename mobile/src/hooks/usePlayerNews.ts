import { useCallback, useEffect, useState } from 'react';
import { fetchPlayerNews } from '@/lib/queries';
import { hasFreshNews } from '@/lib/playerNews';
import type { PlayerNewsRow } from '@/types';

interface Args {
  sport: string | null;
  playerId?: string | null;
  playerName?: string | null;
  /** Skip the fetch entirely (a game-level pick has no player). */
  enabled?: boolean;
  limit?: number;
}

export interface PlayerNewsState {
  news: PlayerNewsRow[];
  loading: boolean;
  error: string | null;
  /** Whether anything landed inside NEWS_FRESH_HOURS — dots the icon. */
  fresh: boolean;
  reload: () => void;
}

const EMPTY: PlayerNewsRow[] = [];

/**
 * Recent news for one player.
 *
 * Deliberately quiet: a news outage, a missing table, or a player nobody has
 * written about all resolve to an empty list, never to a thrown screen. The
 * icon that opens the sheet hides itself when this comes back empty, so the
 * header never offers a sheet with nothing in it.
 */
export function usePlayerNews({ sport, playerId, playerName, enabled = true, limit }: Args): PlayerNewsState {
  const [news, setNews] = useState<PlayerNewsRow[]>(EMPTY);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  useEffect(() => {
    let mounted = true;
    if (!enabled || !sport || (!playerId && !playerName)) {
      setNews(EMPTY);
      setLoading(false);
      setError(null);
      return undefined;
    }

    setLoading(true);
    fetchPlayerNews({ sport, playerId, playerName, limit })
      .then((rows) => {
        if (!mounted) return;
        setNews(rows);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!mounted) return;
        setNews(EMPTY);
        setError(e instanceof Error ? e.message : 'Could not load news');
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [sport, playerId, playerName, enabled, limit, nonce]);

  return { news, loading, error, fresh: hasFreshNews(news), reload };
}
