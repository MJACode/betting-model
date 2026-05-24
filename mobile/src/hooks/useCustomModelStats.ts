import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchSettledPicks } from '@/lib/queries';
import { todayET } from '@/lib/format';
import { pickMatchesModel } from './useCustomModels';
import type { CustomModel, Pick } from '@/types';

const PAPER_START = '2026-04-14';

export interface CustomModelStats {
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  winRate: number; // wins / (wins + losses)
  profitFlat: number;
  stakedFlat: number;
  roiFlat: number;
}

export const EMPTY_STATS: CustomModelStats = {
  picks: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  winRate: 0,
  profitFlat: 0,
  stakedFlat: 0,
  roiFlat: 0,
};

/**
 * Loads all settled picks since paper-trading start and exposes a helper to
 * compute backtest stats for any custom model against them.
 */
export function useSettledPicksSincePaperStart() {
  const [rows, setRows] = useState<Pick[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const settled = await fetchSettledPicks(PAPER_START, todayET());
      setRows(settled);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { rows, loading, error, refresh: load };
}

export function computeCustomModelStats(model: CustomModel, settled: Pick[]): CustomModelStats {
  let picks = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let profitFlat = 0;
  let stakedFlat = 0;

  for (const p of settled) {
    if (!pickMatchesModel(p, model)) continue;
    picks++;
    if (p.result === 'WIN') wins++;
    else if (p.result === 'LOSS') losses++;
    else if (p.result === 'PUSH') pushes++;
    else continue;
    profitFlat += Number(p.profit_flat ?? 0);
    stakedFlat += 100;
  }

  const decided = wins + losses;
  return {
    picks,
    wins,
    losses,
    pushes,
    winRate: decided > 0 ? wins / decided : 0,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
  };
}

export function useCustomModelStats(model: CustomModel | null) {
  const { rows, loading, error, refresh } = useSettledPicksSincePaperStart();

  const stats = useMemo(() => {
    if (!model) return EMPTY_STATS;
    return computeCustomModelStats(model, rows);
  }, [model, rows]);

  const matchingPicks = useMemo(() => {
    if (!model) return [] as Pick[];
    return rows.filter((p) => pickMatchesModel(p, model));
  }, [model, rows]);

  return { stats, matchingPicks, loading, error, refresh };
}
