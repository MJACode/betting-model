import { useEffect, useState } from 'react';

import { todayET } from '@/lib/format';
import { buildModelRecords, heatWindow, type ModelRecordSummary } from '@/lib/modelHeat';
import { fetchModelDailyRecord, fetchModelTotalRecord } from '@/lib/queries';

/**
 * Each model's published record and hot / cold tag, for the Picks filter's
 * Model section (lib/modelHeat.ts). Read once per mount. A failed read leaves
 * the map empty: the section still filters, its rows just carry no record —
 * a filter must never stop working because a decoration did not load.
 *
 * A plain useEffect, never useFocusEffect (.claude/rules/frontend.md).
 */
export function useModelFilterRecords(): Record<string, ModelRecordSummary> {
  const [records, setRecords] = useState<Record<string, ModelRecordSummary>>({});
  useEffect(() => {
    let mounted = true;
    const today = todayET();
    Promise.all([fetchModelTotalRecord(), fetchModelDailyRecord(heatWindow(today).first)])
      .then(([totals, daily]) => {
        if (mounted) setRecords(buildModelRecords(totals, daily, today));
      })
      .catch((err) => {
        console.warn('[modelFilterRecords] fetch failed; Model rows show no record', err);
      });
    return () => {
      mounted = false;
    };
  }, []);
  return records;
}
