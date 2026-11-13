/**
 * One scoped byom_record read, summed to two records: the headline
 * (official, or the close while official is empty) and the closing line beside
 * it. A null filter does not call: an empty filter is the whole season
 * and is not a model preview. A slower response does not replace a
 * newer one.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { errorText, isAbortError } from '@/lib/errors';
import { fetchByomScopedRecord, type ByomFilters, type ByomTiming } from '@/lib/byom';
import { byomFilters } from '@/lib/byomFilters';
import {
  recordFromRows,
  seasonRows,
  type ByomRecord,
  type ByomSeasonRow,
  type ByomSeasonScope,
  type ByomSport,
} from '@/lib/byomRecord';

export function useByomRecord(
  scope: ByomSeasonScope,
  filters: ByomFilters | null,
  sport: ByomSport = 'NFL',
) {
  const [record, setRecord] = useState<ByomRecord | null>(null);
  const [closeRecord, setCloseRecord] = useState<ByomRecord | null>(null);
  const [timing, setTiming] = useState<ByomTiming>('close');
  const [seasons, setSeasons] = useState<ByomSeasonRow[]>([]);
  const [loading, setLoading] = useState(filters != null);
  const [error, setError] = useState<string | null>(null);
  const filterKey = filters == null ? '' : JSON.stringify(byomFilters(filters));
  const seq = useRef(0);

  const load = useCallback(async () => {
    if (filterKey === '') {
      seq.current += 1;
      setRecord(null);
      setCloseRecord(null);
      setError(null);
      setLoading(false);
      return;
    }
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    setRecord(null);
    setCloseRecord(null);
    setSeasons([]);
    try {
      const parsed = JSON.parse(filterKey) as ByomFilters;
      const rows = await fetchByomScopedRecord(scope, parsed, new Date(), sport);
      if (seq.current !== id) return;
      const close = recordFromRows(rows.close);
      if (rows.headline === 'official') {
        setRecord(recordFromRows(rows.official));
        setCloseRecord(close);
      } else {
        setRecord(close);
        setCloseRecord(null);
      }
      setTiming(rows.headline);
      // The same timing as the headline, one row per season.
      setSeasons(seasonRows(sport, rows.seasons.map((item) => ({
        season: item.season,
        rows: rows.headline === 'official' ? item.official : item.close,
      }))));
    } catch (e: unknown) {
      if (seq.current !== id) return;
      if (!isAbortError(e)) setError(errorText(e));
    } finally {
      if (seq.current === id) setLoading(false);
    }
  }, [scope, filterKey, sport]);

  useEffect(() => {
    void load();
  }, [load]);

  return { record, closeRecord, timing, seasons, loading, error, reload: load };
}
