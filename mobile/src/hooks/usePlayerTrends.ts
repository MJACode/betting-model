import { useEffect, useState } from 'react';
import { fetchPlayerByName, fetchPlayerRecentGames } from '@/lib/queries';
import type { PlayerGameLogRow, TrendBuckets } from '@/types';

export type PlayerStatKey =
  | 'p_strikeouts'
  | 'p_hits_allowed'
  | 'p_earned_runs'
  | 'outs'
  | 'p_walks'
  | 'hits'
  | 'total_bases'
  | 'home_runs'
  | 'rbi'
  | 'runs'
  | 'stolen_bases'
  | 'walks';

function extractStat(row: PlayerGameLogRow, key: PlayerStatKey): number | null {
  if (key === 'outs') {
    const ip = row.innings_pitched;
    if (ip == null) return null;
    const whole = Math.floor(ip);
    const frac = Math.round((ip - whole) * 10);
    return whole * 3 + frac;
  }
  const v = (row as unknown as Record<string, number | null>)[key];
  return v ?? null;
}

function reduce(values: number[], n: number) {
  const slice = values.slice(0, n);
  const known = slice.filter((v) => v != null);
  const avg = known.length > 0 ? known.reduce((a, b) => a + b, 0) / known.length : null;
  return { avg, winPct: null, games: slice.length };
}

function bucketize(values: number[]): TrendBuckets {
  return {
    l3: reduce(values, 3),
    l5: reduce(values, 5),
    l10: reduce(values, 10),
    l20: reduce(values, 20),
    season: reduce(values, values.length),
  };
}

interface Args {
  playerId: string | null;
  playerName: string | null;
  beforeDate: string | null;
  statKey: PlayerStatKey | null;
}

export function usePlayerTrends({ playerId, playerName, beforeDate, statKey }: Args) {
  const [games, setGames] = useState<PlayerGameLogRow[]>([]);
  const [values, setValues] = useState<number[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!beforeDate || !statKey || (!playerId && !playerName)) {
      setGames([]);
      setValues([]);
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);

    const fetcher = playerId
      ? fetchPlayerRecentGames(playerId, beforeDate, 25)
      : fetchPlayerByName(playerName!, beforeDate, 25);

    fetcher
      .then((rows) => {
        if (!mounted) return;
        setGames(rows);
        const vals: number[] = [];
        for (const r of rows) {
          const v = extractStat(r, statKey);
          if (v != null) vals.push(v);
        }
        setValues(vals);
      })
      .catch((e: unknown) => {
        if (!mounted) return;
        setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [playerId, playerName, beforeDate, statKey]);

  return { games, values, trends: bucketize(values), loading, error };
}
