import { useCallback, useEffect, useState } from 'react';
import { fetchModelFullRecords } from '@/lib/queries';
import type { CustomModelStats } from './useCustomModelStats';
import type { ModelFullRecordRow } from '@/types';

/**
 * Convert a full-outcome record row into the CustomModelStats shape the Models
 * UI already renders. The view stores P&L in flat 1-unit terms; the rest of the
 * app shows P&L on a $100 flat stake, so scale units → dollars (×100) to keep
 * the numbers consistent with the settled-BET rows. ROI is unit-independent.
 */
export function fullRecordToStats(r: ModelFullRecordRow): CustomModelStats {
  const decided = r.wins + r.losses;
  const profitFlat = r.profit_units * 100;
  const stakedFlat = r.picks * 100;
  return {
    picks: r.picks,
    wins: r.wins,
    losses: r.losses,
    pushes: r.pushes,
    winRate: decided > 0 ? r.wins / decided : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
  };
}

/**
 * Loads the FULL-outcome record per game-level model from v_model_full_record:
 * every scored pick (BET + AVOID + dead-zone NONE) since paper start, evaluated
 * at the model's current action thresholds, outcome recomputed from the final
 * game score. This is the true record at the current cut — the settled-BET-only
 * record never sees AVOID/NONE picks. Only game-level models are present (props/
 * UFC/golf can't be recomputed from games alone); callers fall back to the
 * settled-BET stats for those.
 */
export function useModelFullRecords() {
  const [records, setRecords] = useState<Record<string, ModelFullRecordRow>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setRecords(await fetchModelFullRecords());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { records, loading, error, refresh: load };
}
