import { useEffect, useState } from 'react';

import { todayET } from '@/lib/format';
import { buildModelRecords, heatWindow, type ModelRecordSummary } from '@/lib/modelHeat';
import { fetchModelDailyRecord, fetchModelTotalRecord } from '@/lib/queries';

export type ModelRecordsStatus = 'loading' | 'ready' | 'error';

export interface ModelFilterRecords {
  records: Record<string, ModelRecordSummary>;
  /**
   * Only 'ready' may print "No settled bets yet" for a model with no row: a
   * row with 61 settled bets must not say "none" while the read is in flight
   * or after it failed (UX review, 2026-11-19).
   */
  status: ModelRecordsStatus;
}

/**
 * Each model's published record and hot / cold tag, for the Picks filter's
 * Model section (lib/modelHeat.ts). Read once per mount and again when the ET
 * date changes under a mounted screen (the heat window moves at midnight).
 *
 * The two reads fail separately: no totals = no record line (status
 * 'error'), no daily rows = records without tags. The section still filters
 * either way — a filter must never stop working because a decoration did not
 * load. A plain useEffect, never useFocusEffect (.claude/rules/frontend.md).
 */
export function useModelFilterRecords(today: string = todayET()): ModelFilterRecords {
  const [state, setState] = useState<ModelFilterRecords>({ records: {}, status: 'loading' });
  useEffect(() => {
    let mounted = true;
    Promise.allSettled([fetchModelTotalRecord(), fetchModelDailyRecord(heatWindow(today).first)]).then(
      ([totals, daily]) => {
        if (!mounted) return;
        if (totals.status === 'rejected') {
          console.warn('[modelFilterRecords] totals read failed; rows show no record', totals.reason);
          setState({ records: {}, status: 'error' });
          return;
        }
        if (daily.status === 'rejected') {
          console.warn('[modelFilterRecords] daily read failed; no hot / cold tags', daily.reason);
        }
        setState({
          records: buildModelRecords(
            totals.value,
            daily.status === 'fulfilled' ? daily.value : [],
            today,
          ),
          status: 'ready',
        });
      },
    );
    return () => {
      mounted = false;
    };
  }, [today]);
  return state;
}
