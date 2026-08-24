import { useEffect, useState } from 'react';
import { fetchPlayerGameLog } from '@/lib/queries';
import {
  logStatValue,
  supportsPlayerDetail,
  type PlayerLogEntry,
  type PlayerLogSport,
} from '@/lib/playerLog';
import { STAT_CATALOG, type StatDef } from '@/lib/statCatalog';
import type { PlayerType, TrendBuckets } from '@/types';

/**
 * MLB prop stat keys. Kept as a named type because the prop-model registry
 * (modelMeta) maps each MLB prop model to one of these, and the pick detail
 * screen charts a pick's own stat by that key.
 */
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

/**
 * Resolves a bare stat key (what the MLB pick detail screen passes) to the
 * catalog definition the log reader needs. `outs` is derived on MLB rows by
 * normalizeLogRow and has no catalog entry of its own.
 */
function defForKey(sport: PlayerLogSport, key: string, playerType?: PlayerType | null): StatDef {
  const match = STAT_CATALOG.find(
    (s) => s.sport === sport && s.key === key && (!playerType || !s.playerType || s.playerType === playerType),
  );
  return match ?? ({ key: key as StatDef['key'], label: key, sport, group: 'Batting' } as StatDef);
}

interface Args {
  playerId: string | null;
  playerName: string | null;
  beforeDate: string | null;
  /** Either a catalog definition (player detail) or a bare key (pick detail). */
  stat?: StatDef | null;
  statKey?: PlayerStatKey | string | null;
  /** Defaults to MLB so existing MLB-only callers are unchanged. */
  sport?: PlayerLogSport;
  playerType?: PlayerType | null;
  limit?: number;
}

/**
 * A player's recent games plus the selected stat's per-game values and rolling
 * averages. Works for any sport with a per-game log; `sport` defaults to MLB.
 */
export function usePlayerTrends({
  playerId,
  playerName,
  beforeDate,
  stat,
  statKey,
  sport = 'MLB',
  playerType,
  limit,
}: Args) {
  const [games, setGames] = useState<PlayerLogEntry[]>([]);
  const [values, setValues] = useState<number[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const key = stat?.key ?? statKey ?? null;

  useEffect(() => {
    if (!beforeDate || !key || !supportsPlayerDetail(sport) || (!playerId && !playerName)) {
      setGames([]);
      setValues([]);
      return;
    }
    let mounted = true;
    setLoading(true);
    setError(null);

    const def = stat ?? defForKey(sport, String(key), playerType);

    fetchPlayerGameLog(sport, { playerId, playerName }, beforeDate, limit)
      .then((rows) => {
        if (!mounted) return;
        setGames(rows);
        const vals: number[] = [];
        for (const r of rows) {
          const v = logStatValue(r, def);
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
    // `stat` is an object literal at some call sites — key it by its stat key.
  }, [playerId, playerName, beforeDate, key, sport, playerType, limit]);

  return { games, values, trends: bucketize(values), loading, error };
}
