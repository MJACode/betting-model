import { useEffect, useState } from 'react';
import { fetchTeamRecentGames } from '@/lib/queries';
import { errorText } from '@/lib/errors';
import type { GameRow, TeamGameStat, TrendBuckets } from '@/types';

function reduce(games: TeamGameStat[]): TrendBuckets {
  function bucket(slice: TeamGameStat[]) {
    const decided = slice.filter((g) => g.won !== null);
    const wins = decided.filter((g) => g.won === true).length;
    const winPct = decided.length > 0 ? wins / decided.length : null;
    const rfList = slice
      .map((g) => g.runs_for)
      .filter((v): v is number => v != null);
    const avg = rfList.length > 0 ? rfList.reduce((a, b) => a + b, 0) / rfList.length : null;
    return { winPct, avg, games: slice.length };
  }

  return {
    l3: bucket(games.slice(0, 3)),
    l5: bucket(games.slice(0, 5)),
    l10: bucket(games.slice(0, 10)),
    l20: bucket(games.slice(0, 20)),
    season: bucket(games),
  };
}

export function useTeamTrends(team: string | null, beforeDate: string | null) {
  const [games, setGames] = useState<TeamGameStat[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!team || !beforeDate) {
      setGames([]);
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);
    fetchTeamRecentGames(team, beforeDate, 25)
      .then((rows: GameRow[]) => {
        if (!mounted) return;
        const mapped = rows.map((g) => {
          const isHome = g.home_team === team;
          const won =
            g.home_win == null
              ? null
              : isHome
                ? g.home_win === 1
                : g.home_win === 0;
          const runs_for = isHome ? g.home_score : g.away_score;
          const runs_against = isHome ? g.away_score : g.home_score;
          const opponent = isHome ? g.away_team : g.home_team;
          return {
            game_id: g.game_id,
            game_date: g.game_date,
            is_home: isHome,
            won,
            runs_for,
            runs_against,
            opponent,
          };
        });
        setGames(mapped);
      })
      .catch((e: unknown) => {
        if (!mounted) return;
        setError(errorText(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [team, beforeDate]);

  return { games, trends: reduce(games), loading, error };
}
