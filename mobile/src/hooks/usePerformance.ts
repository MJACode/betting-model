import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchSettledPicks } from '@/lib/queries';
import { addDays, todayET } from '@/lib/format';
import { isPlaced, usePlacedPicks } from './usePlacedPicks';
import type { Pick } from '@/types';

export type Range = '7d' | '30d' | '90d' | 'season' | 'all';
export type SizingMode = 'kelly' | 'flat';

function startDateFor(range: Range): string {
  const today = todayET();
  switch (range) {
    case '7d':
      return addDays(today, -7);
    case '30d':
      return addDays(today, -30);
    case '90d':
      return addDays(today, -90);
    case 'season':
      return `${new Date().getUTCFullYear()}-01-01`;
    case 'all':
      return '2026-04-14'; // PAPER_TRADING_START
  }
}

export interface DayBucket {
  date: string;
  picks: Pick[];
  netFlat: number;
  netKelly: number;
  wins: number;
  losses: number;
  pushes: number;
}

export interface ModelStats {
  model_id: string;
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  profitFlat: number;
  profitKelly: number;
  stakedFlat: number;
  stakedKelly: number;
  roiFlat: number;
  roiKelly: number;
}

/**
 * Calibration on placed-and-settled picks for a single model.
 * `gap = avgPredicted - actualWinRate` (positive = overconfident).
 * `absGap` is what we compare against the 5% gate from CLAUDE.md §17.
 * `bins` is empty if there aren't enough decided picks to bin meaningfully.
 */
export interface ModelCalibration {
  model_id: string;
  decided: number;          // wins + losses (pushes excluded)
  wins: number;
  losses: number;
  avgPredicted: number;     // mean model_probability across decided picks
  actualWinRate: number;    // wins / decided
  gap: number;              // avgPredicted - actualWinRate
  absGap: number;
  bins: CalibrationBin[];
}

export interface CalibrationBin {
  lower: number;            // e.g. 0.60
  upper: number;            // e.g. 0.70
  n: number;
  meanPredicted: number;
  actualWinRate: number;
}

/** Probability buckets used for binned calibration view. */
const CAL_BIN_EDGES = [0.0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0001];

export const CAL_ERROR_GATE = 0.05;

export interface PerformanceSummary {
  totalPicks: number;
  wins: number;
  losses: number;
  pushes: number;
  totalFlat: number;
  totalKelly: number;
  stakedFlat: number;
  stakedKelly: number;
  roiFlat: number;
  roiKelly: number;
  units: number;
  avgEdge: number;
  streak: { kind: 'W' | 'L' | 'none'; count: number };
  bestModel: { model_id: string; roi: number; picks: number } | null;
  byDay: Map<string, DayBucket>;
  byModel: ModelStats[];
  calibration: ModelCalibration[];
}

export function usePerformance(range: Range) {
  const { overrides, ready: placedReady } = usePlacedPicks();
  const [rows, setRows] = useState<Pick[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const start = useMemo(() => startDateFor(range), [range]);
  const end = todayET();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const settled = await fetchSettledPicks(start, end);
      setRows(settled);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [start, end]);

  useEffect(() => {
    void load();
  }, [load]);

  const placedRows = useMemo(
    () => rows.filter((p) => isPlaced(p.pick_id, p.signal_type, overrides)),
    [rows, overrides],
  );

  const summary = useMemo<PerformanceSummary>(() => {
    const byDay = new Map<string, DayBucket>();
    let wins = 0;
    let losses = 0;
    let pushes = 0;
    let totalFlat = 0;
    let totalKelly = 0;
    let stakedFlat = 0;
    let stakedKelly = 0;
    let edgeSum = 0;
    const modelRollup = new Map<
      string,
      {
        picks: number;
        wins: number;
        losses: number;
        pushes: number;
        profitFlat: number;
        profitKelly: number;
        stakedFlat: number;
        stakedKelly: number;
      }
    >();

    for (const p of placedRows) {
      if (p.result === 'WIN') wins++;
      else if (p.result === 'LOSS') losses++;
      else if (p.result === 'PUSH') pushes++;
      else continue; // NO_ACTION

      const pf = Number(p.profit_flat ?? 0);
      const pk = Number(p.profit_kelly ?? 0);
      totalFlat += pf;
      totalKelly += pk;
      stakedFlat += 100;
      stakedKelly += Number(p.recommended_bet ?? 0);
      edgeSum += Number(p.edge ?? 0);

      const bucket = byDay.get(p.game_date) ?? {
        date: p.game_date,
        picks: [],
        netFlat: 0,
        netKelly: 0,
        wins: 0,
        losses: 0,
        pushes: 0,
      };
      bucket.picks.push(p);
      bucket.netFlat += pf;
      bucket.netKelly += pk;
      if (p.result === 'WIN') bucket.wins++;
      else if (p.result === 'LOSS') bucket.losses++;
      else if (p.result === 'PUSH') bucket.pushes++;
      byDay.set(p.game_date, bucket);

      const m = modelRollup.get(p.model_id) ?? {
        picks: 0,
        wins: 0,
        losses: 0,
        pushes: 0,
        profitFlat: 0,
        profitKelly: 0,
        stakedFlat: 0,
        stakedKelly: 0,
      };
      m.picks++;
      if (p.result === 'WIN') m.wins++;
      else if (p.result === 'LOSS') m.losses++;
      else if (p.result === 'PUSH') m.pushes++;
      m.profitFlat += pf;
      m.profitKelly += pk;
      m.stakedFlat += 100;
      m.stakedKelly += Number(p.recommended_bet ?? 0);
      modelRollup.set(p.model_id, m);
    }

    const byModel: ModelStats[] = Array.from(modelRollup.entries())
      .map(([model_id, agg]) => ({
        model_id,
        ...agg,
        roiFlat: agg.stakedFlat > 0 ? agg.profitFlat / agg.stakedFlat : 0,
        roiKelly: agg.stakedKelly > 0 ? agg.profitKelly / agg.stakedKelly : 0,
      }))
      .sort((a, b) => b.roiKelly - a.roiKelly);

    const calibration = computeCalibration(placedRows);

    // Best model — needs ≥10 placed picks
    let bestModel: PerformanceSummary['bestModel'] = null;
    for (const ms of byModel) {
      if (ms.picks < 10 || ms.stakedKelly === 0) continue;
      if (!bestModel || ms.roiKelly > bestModel.roi) {
        bestModel = { model_id: ms.model_id, roi: ms.roiKelly, picks: ms.picks };
      }
    }

    // Current streak — walk most-recent placed bets (pushes/no_action skipped)
    const ordered = [...placedRows]
      .filter((p) => p.result === 'WIN' || p.result === 'LOSS')
      .sort((a, b) => (b.settled_at ?? b.game_date).localeCompare(a.settled_at ?? a.game_date));
    let streak: PerformanceSummary['streak'] = { kind: 'none', count: 0 };
    if (ordered.length > 0) {
      const first = ordered[0]!.result === 'WIN' ? 'W' : 'L';
      let count = 0;
      for (const p of ordered) {
        const kind = p.result === 'WIN' ? 'W' : 'L';
        if (kind !== first) break;
        count++;
      }
      streak = { kind: first, count };
    }

    const decided = wins + losses;
    return {
      totalPicks: placedRows.length,
      wins,
      losses,
      pushes,
      totalFlat,
      totalKelly,
      stakedFlat,
      stakedKelly,
      roiFlat: stakedFlat > 0 ? totalFlat / stakedFlat : 0,
      roiKelly: stakedKelly > 0 ? totalKelly / stakedKelly : 0,
      units: totalFlat / 100,
      avgEdge: placedRows.length > 0 ? edgeSum / placedRows.length : 0,
      streak,
      bestModel,
      byDay,
      byModel,
      calibration,
    };
  }, [placedRows]);

  return { summary, loading: loading || !placedReady, error, refresh: load, range, placedRows };
}

function computeCalibration(rows: Pick[]): ModelCalibration[] {
  const byModel = new Map<string, { decided: number; wins: number; losses: number; predSum: number; picks: Pick[] }>();
  for (const p of rows) {
    if (p.result !== 'WIN' && p.result !== 'LOSS') continue;
    const m = byModel.get(p.model_id) ?? { decided: 0, wins: 0, losses: 0, predSum: 0, picks: [] };
    m.decided++;
    m.predSum += Number(p.model_probability ?? 0);
    if (p.result === 'WIN') m.wins++;
    else m.losses++;
    m.picks.push(p);
    byModel.set(p.model_id, m);
  }

  const result: ModelCalibration[] = [];
  for (const [model_id, agg] of byModel.entries()) {
    if (agg.decided === 0) continue;
    const avgPredicted = agg.predSum / agg.decided;
    const actualWinRate = agg.wins / agg.decided;
    const gap = avgPredicted - actualWinRate;
    result.push({
      model_id,
      decided: agg.decided,
      wins: agg.wins,
      losses: agg.losses,
      avgPredicted,
      actualWinRate,
      gap,
      absGap: Math.abs(gap),
      bins: binCalibration(agg.picks),
    });
  }
  return result.sort((a, b) => a.absGap - b.absGap);
}

function binCalibration(picks: Pick[]): CalibrationBin[] {
  const bins: CalibrationBin[] = [];
  for (let i = 0; i < CAL_BIN_EDGES.length - 1; i++) {
    const lower = CAL_BIN_EDGES[i]!;
    const upper = CAL_BIN_EDGES[i + 1]!;
    const inBin = picks.filter(
      (p) => Number(p.model_probability) >= lower && Number(p.model_probability) < upper,
    );
    if (inBin.length === 0) continue;
    const wins = inBin.filter((p) => p.result === 'WIN').length;
    const meanPredicted =
      inBin.reduce((s, p) => s + Number(p.model_probability ?? 0), 0) / inBin.length;
    bins.push({
      lower,
      upper: Math.min(upper, 1),
      n: inBin.length,
      meanPredicted,
      actualWinRate: wins / inBin.length,
    });
  }
  return bins;
}
