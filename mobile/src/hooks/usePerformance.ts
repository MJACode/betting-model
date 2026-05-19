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
    const modelRollup = new Map<string, { picks: number; profit: number; staked: number }>();

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

      const m = modelRollup.get(p.model_id) ?? { picks: 0, profit: 0, staked: 0 };
      m.picks++;
      m.profit += pk;
      m.staked += Number(p.recommended_bet ?? 0);
      modelRollup.set(p.model_id, m);
    }

    // Best model — needs ≥10 placed picks
    let bestModel: PerformanceSummary['bestModel'] = null;
    for (const [modelId, agg] of modelRollup.entries()) {
      if (agg.picks < 10 || agg.staked === 0) continue;
      const roi = agg.profit / agg.staked;
      if (!bestModel || roi > bestModel.roi) {
        bestModel = { model_id: modelId, roi, picks: agg.picks };
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
    };
  }, [placedRows]);

  return { summary, loading: loading || !placedReady, error, refresh: load, range, placedRows };
}
