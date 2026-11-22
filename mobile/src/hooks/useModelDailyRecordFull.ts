import { useCallback, useEffect, useRef, useState } from 'react';

import { fetchModelDailyRecordFull } from '@/lib/queries';
import type { ModelDayRecord } from '@/lib/performanceInsights';

export type ModelDailyStatus = 'loading' | 'ready' | 'error';

/**
 * Every model's posted record by day, for the Insights card's "you vs the
 * models you follow". Read on mount and again on `reload()` (the screen calls
 * it on pull-to-refresh and on focus), so the models' side settles as games
 * do, like the member's own. A failed first read hides that one section
 * (status 'error'); a failed reload keeps the last rows. A plain useEffect,
 * never useFocusEffect (.claude/rules/frontend.md): focus belongs to the screen.
 */
export function useModelDailyRecordFull(): {
  rows: ModelDayRecord[];
  status: ModelDailyStatus;
  reload: () => void;
} {
  const [state, setState] = useState<{ rows: ModelDayRecord[]; status: ModelDailyStatus }>({
    rows: [],
    status: 'loading',
  });
  const mounted = useRef(true);
  const reload = useCallback(() => {
    fetchModelDailyRecordFull('2000-01-01')
      .then((rows) => {
        if (mounted.current) setState({ rows, status: 'ready' });
      })
      .catch((err: unknown) => {
        console.warn('[modelDailyRecordFull] read failed', err);
        if (mounted.current) setState((s) => (s.status === 'ready' ? s : { rows: [], status: 'error' }));
      });
  }, []);
  useEffect(() => {
    mounted.current = true;
    reload();
    return () => {
      mounted.current = false;
    };
  }, [reload]);
  return { ...state, reload };
}
