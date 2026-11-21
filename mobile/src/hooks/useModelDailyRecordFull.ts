import { useEffect, useState } from 'react';

import { fetchModelDailyRecordFull } from '@/lib/queries';
import type { ModelDayRecord } from '@/lib/performanceInsights';

export type ModelDailyStatus = 'loading' | 'ready' | 'error';

/**
 * Every model's posted record by day, read once per mount, for the Insights
 * card's "you vs the models you follow". A failed read hides that one section
 * (status 'error'); the rest of the card never waits on it. A plain useEffect,
 * never useFocusEffect (.claude/rules/frontend.md).
 */
export function useModelDailyRecordFull(): { rows: ModelDayRecord[]; status: ModelDailyStatus } {
  const [state, setState] = useState<{ rows: ModelDayRecord[]; status: ModelDailyStatus }>({
    rows: [],
    status: 'loading',
  });
  useEffect(() => {
    let mounted = true;
    fetchModelDailyRecordFull('2000-01-01')
      .then((rows) => {
        if (mounted) setState({ rows, status: 'ready' });
      })
      .catch((err: unknown) => {
        console.warn('[modelDailyRecordFull] read failed; vs-models section hidden', err);
        if (mounted) setState({ rows: [], status: 'error' });
      });
    return () => {
      mounted = false;
    };
  }, []);
  return state;
}
