import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchPlayerGameLog } from '@/lib/queries';
import {
  logStatValue,
  supportsPlayerDetail,
  type PlayerLogEntry,
  type PlayerLogSport,
} from '@/lib/playerLog';
import { STAT_CATALOG, type StatDef } from '@/lib/statCatalog';
import { errorText } from '@/lib/errors';
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

/**
 * A stat's per-game values off a loaded log, newest first, with missing games
 * dropped rather than counted as zero. Exported because the player detail
 * screen picks its stat FROM the loaded rows (a tab it cannot fill is not
 * offered), so it resolves the stat after this hook has returned and charts
 * the result itself.
 */
export function logValues(games: PlayerLogEntry[], def: StatDef | null): number[] {
  if (!def) return [];
  const vals: number[] = [];
  for (const r of games) {
    const v = logStatValue(r, def);
    if (v != null) vals.push(v);
  }
  return vals;
}

/** L3 / L5 / L10 / L20 / all, from a values list. */
export function trendBuckets(values: number[]): TrendBuckets {
  return bucketize(values);
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
  const [loading, setLoading] = useState<boolean>(false);
  // Whether a fetch has RESOLVED for the current player — not the same as
  // "not loading", which is also true in the frame before the first one
  // starts. The player screen shows no stat controls until this is true,
  // because it cannot know which tabs a player fills until the rows land.
  const [loaded, setLoaded] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  // Loading flips true here, not only in the effect: pull-to-refresh
  // batches the nonce with this so the spinner does not clear on the
  // one frame before the effect runs (Reviewer Medium on #781).
  const reload = useCallback(() => {
    setLoading(true);
    setNonce((n) => n + 1);
  }, []);

  const key = stat?.key ?? statKey ?? null;
  // Whether a stat is selected at all gates the fetch; WHICH stat does not.
  const hasStat = key != null;

  // The FETCH does not depend on the stat. `fetchPlayerGameLog` asks for a
  // sport's whole column list (LOG_COLUMNS), so every stat this screen can
  // chart is already in the rows — re-running it on a stat change bought the
  // same 25 rows again and left `values` showing the PREVIOUS stat's numbers
  // under the new stat's label for the length of a network round trip (UX
  // review, 2026-09-20; the player screen now re-picks the stat by itself
  // after a load, so that window opened on its own). Deriving the values
  // below also makes a chip tap instant instead of a refetch.
  useEffect(() => {
    if (!beforeDate || !hasStat || !supportsPlayerDetail(sport) || (!playerId && !playerName)) {
      setGames([]);
      setLoaded(true);
      return;
    }
    let mounted = true;
    setLoading(true);
    setLoaded(false);
    setError(null);

    fetchPlayerGameLog(sport, { playerId, playerName }, beforeDate, limit)
      .then((rows) => {
        if (!mounted) return;
        setGames(rows);
      })
      .catch((e: unknown) => {
        if (!mounted) return;
        setError(errorText(e));
      })
      .finally(() => {
        if (!mounted) return;
        setLoading(false);
        setLoaded(true);
      });

    return () => {
      mounted = false;
    };
  }, [playerId, playerName, beforeDate, hasStat, sport, playerType, limit, nonce]);

  // Newest-first, missing games dropped rather than counted as zero.
  const values = useMemo(() => {
    if (key == null) return [];
    return logValues(games, stat ?? defForKey(sport, String(key), playerType));
    // `stat` is an object literal at some call sites — key it by its stat key.
  }, [games, key, sport, playerType]);

  return { games, values, trends: bucketize(values), loading, loaded, error, reload };
}
