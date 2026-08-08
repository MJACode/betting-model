import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchSettledPicks, fetchModelFullOutcomeRecord, FullOutcomeRecord } from '@/lib/queries';
import {
  mergeSettled,
  readSettledCache,
  refreshFrom,
  writeSettledCache,
} from '@/lib/settledPickCache';
import { passesActionFilter } from '@/lib/thresholds';
import { todayET } from '@/lib/format';
import { pickMatchesModel } from './useCustomModels';
import type { CustomModel, SettledPick } from '@/types';

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
 * Loads every settled pick since paper-trading start and exposes a helper to
 * compute backtest stats for any custom model against them.
 *
 * Cache-first: the device's cached rows render immediately, then only a
 * trailing window is refetched and merged (see settledPickCache). That keeps
 * the full history available for backtests without re-downloading it each time,
 * and the fetch itself is paginated so the set is never silently truncated.
 */
export function useSettledPicksSincePaperStart() {
  const [rows, setRows] = useState<SettledPick[]>([]);
  const [records, setRecords] = useState<Record<string, FullOutcomeRecord>>({});
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (opts?: { full?: boolean }) => {
    setLoading(true);
    setError(null);
    try {
      const cached = opts?.full ? [] : await readSettledCache();
      // Show what we already have while the network catches up.
      if (cached.length > 0) setRows(cached);

      const from = refreshFrom(cached, PAPER_START);

      // Settled picks drive custom-model backtests; the full-outcome view drives
      // built-in model records (grades dead-zone picks the settled set never has).
      // View fetch is failure-tolerant so a view error can't blank the screen.
      const [fresh, recs] = await Promise.all([
        fetchSettledPicks(from, todayET()),
        fetchModelFullOutcomeRecord().catch(() => ({} as Record<string, FullOutcomeRecord>)),
      ]);

      const merged = mergeSettled(cached, fresh, from);
      setRows(merged);
      setRecords(recs);
      void writeSettledCache(merged);
    } catch (e: unknown) {
      // Cached rows stay on screen — a failed refresh shouldn't blank the
      // backtest, it just leaves it as stale as the last successful load.
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return { rows, records, loading, error, refresh: load };
}

/** Adapt a full-outcome view row to the CustomModelStats shape the screens render.
 *  Units in the view are 1-unit (flat); screens display at a $100 notional stake,
 *  so scale by 100 to match computeBuiltInModelStats. roi_pct is NULL for prob-only
 *  HR (no real odds) — surface a record-only row (0 ROI) rather than NaN. */
export function viewRecordToStats(rec: FullOutcomeRecord): CustomModelStats {
  const decided = rec.wins + rec.losses;
  const priced = rec.priced_bets ?? 0;
  const units = Number(rec.units ?? 0);
  return {
    picks: rec.bets,
    wins: rec.wins,
    losses: rec.losses,
    pushes: rec.pushes,
    winRate: decided > 0 ? rec.wins / decided : 0,
    profitFlat: units * 100,
    stakedFlat: priced * 100,
    roiFlat: rec.roi_pct == null ? 0 : Number(rec.roi_pct) / 100,
  };
}

export function computeCustomModelStats(model: CustomModel, settled: SettledPick[]): CustomModelStats {
  let picks = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let profitFlat = 0;
  let stakedFlat = 0;

  for (const p of settled) {
    if (!pickMatchesModel(p, model)) continue;
    // Only W/L/P count as picks — NO_ACTION rows (DNP, DQ, unsettleable)
    // would otherwise inflate the count vs the displayed record.
    if (p.result === 'WIN') wins++;
    else if (p.result === 'LOSS') losses++;
    else if (p.result === 'PUSH') pushes++;
    else continue;
    picks++;
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

// Built-in model records apply the CURRENT action thresholds retroactively, so
// the record answers "how has this model's current prob/edge combo performed?"
// rather than blending picks generated under older, looser thresholds.
export function computeBuiltInModelStats(modelId: string, settled: SettledPick[]): CustomModelStats {
  let picks = 0;
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let profitFlat = 0;
  let stakedFlat = 0;

  for (const p of settled) {
    if (p.model_id !== modelId) continue;
    if (!passesActionFilter(p)) continue;
    // Only W/L/P count as picks — NO_ACTION rows (DNP, DQ, unsettleable)
    // would otherwise inflate the count vs the displayed record.
    if (p.result === 'WIN') wins++;
    else if (p.result === 'LOSS') losses++;
    else if (p.result === 'PUSH') pushes++;
    else continue;
    picks++;
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
    if (!model) return [] as SettledPick[];
    return rows.filter((p) => pickMatchesModel(p, model));
  }, [model, rows]);

  return { stats, matchingPicks, loading, error, refresh };
}
