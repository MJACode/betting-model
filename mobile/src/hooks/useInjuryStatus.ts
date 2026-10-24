import { useEffect, useMemo, useState } from 'react';
import { fetchInjuryStatus } from '@/lib/queries';
import { buildInjuryIndex, EMPTY_INJURY_INDEX, type InjuryIndex } from '@/lib/injuryStatus';
import type { InjuryStatusRow } from '@/types';

const EMPTY: InjuryStatusRow[] = [];

/**
 * Current injury tags for one sport, indexed for the Stats board.
 *
 * Deliberately quiet, like the news sheet: an outage or a sport with no
 * injury feed (NCAAF, UFC) is an empty index and the board shows no tags --
 * never an error over the leaderboard. `reloadKey` re-reads on pull-to-refresh.
 *
 * Plain useEffect, no useFocusEffect (.claude/rules/frontend.md).
 */
export function useInjuryStatus(sport: string | null, reloadKey = 0): InjuryIndex {
  const [rows, setRows] = useState<InjuryStatusRow[]>(EMPTY);
  const [loadedAt, setLoadedAt] = useState(0);

  useEffect(() => {
    let mounted = true;
    setRows(EMPTY);
    if (!sport) return undefined;
    fetchInjuryStatus(sport)
      .then((r) => {
        if (!mounted) return;
        setRows(r);
        setLoadedAt(Date.now());
      })
      .catch(() => {
        if (mounted) setRows(EMPTY);
      });
    return () => {
      mounted = false;
    };
  }, [sport, reloadKey]);

  return useMemo(
    () => (rows.length === 0 ? EMPTY_INJURY_INDEX : buildInjuryIndex(rows, loadedAt || Date.now())),
    [rows, loadedAt],
  );
}
