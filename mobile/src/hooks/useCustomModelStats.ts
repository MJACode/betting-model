import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  fetchCustomModelBacktest,
  fetchCustomModelPicks,
  fetchSettledPicks,
  fetchModelFullOutcomeRecord,
  FullOutcomeRecord,
} from '@/lib/queries';
import {
  EMPTY_STATS,
  mergeStats,
  splitRulesByCoverage,
  summaryToStats,
  type BacktestPickRow,
  type CustomModelStats,
} from '@/lib/customModelBacktest';
import {
  mergeSettled,
  readSettledCache,
  refreshFrom,
  writeSettledCache,
} from '@/lib/settledPickCache';
import { passesActionFilter } from '@/lib/thresholds';
import { todayET } from '@/lib/format';
import { pickMatchesModel } from './useCustomModels';
import type { CustomModel, SettledPick, SignalType } from '@/types';

const PAPER_START = '2026-04-14';

// Re-exported so existing `from '@/hooks/useCustomModelStats'` imports keep
// working; the definitions moved to the pure lib for testability.
export { EMPTY_STATS, mergeStats, splitRulesByCoverage, summaryToStats };
export type { BacktestPickRow, CustomModelStats };

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

// ---------------------------------------------------------------------------
// Full-universe backtest (server-graded)
// ---------------------------------------------------------------------------

/**
 * Backtest of a custom model against EVERY scored pick, not just the settled
 * BET set — so a model looser than the built-in cuts (or one watching AVOID /
 * dead-zone rows) finally has evidence to show.
 *
 * Rules on server-graded models (MLB + WNBA) go to the custom_model_backtest
 * RPC over mv_scored_pick_outcomes (~100k graded picks, refreshed daily after
 * settle). Rules on anything else (UFC/NHL/golf — no server grading yet) fall
 * back to the settled-pick cache. A pick only ever matches rules for its own
 * model_id, so summing the two halves is exact — no double counting.
 */
export function useCustomModelBacktest(
  model: CustomModel | null,
  opts?: { withPicks?: boolean; debounceMs?: number },
) {
  const withPicks = opts?.withPicks ?? false;
  const debounceMs = opts?.debounceMs ?? 0;

  const { rows: settled, loading: settledLoading } = useSettledPicksSincePaperStart();

  const [serverStats, setServerStats] = useState<CustomModelStats>(EMPTY_STATS);
  const [serverPicks, setServerPicks] = useState<BacktestPickRow[]>([]);
  const [serverLoading, setServerLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const reqId = useRef(0);

  const { covered, uncovered } = useMemo(
    () => splitRulesByCoverage(model?.rules ?? []),
    [model],
  );

  // Key on content, not identity — the edit screen recreates the draft object
  // on every keystroke, and re-firing the RPC for an unchanged query is waste.
  const serverKey = useMemo(
    () => JSON.stringify({ r: covered, f: model?.filters ?? {} }),
    [covered, model],
  );

  useEffect(() => {
    const id = ++reqId.current;
    if (covered.length === 0) {
      setServerStats(EMPTY_STATS);
      setServerPicks([]);
      setServerLoading(false);
      return;
    }
    setServerLoading(true);
    const run = () => {
      const filters = model?.filters;
      Promise.all([
        fetchCustomModelBacktest(covered, filters),
        withPicks ? fetchCustomModelPicks(covered, filters) : Promise.resolve([]),
      ])
        .then(([summary, picks]) => {
          if (reqId.current !== id) return; // a newer draft superseded this one
          setServerStats(summaryToStats(summary));
          setServerPicks(
            picks.map((p) => ({
              pick_id: p.pick_id,
              model_id: p.model_id,
              game_date: p.game_date,
              pick_label: p.pick_label,
              signal_type: p.signal_type as SignalType,
              result: p.result,
              profit_flat: p.profit_units == null ? null : Number(p.profit_units) * 100,
            })),
          );
          setError(null);
        })
        .catch((e: unknown) => {
          if (reqId.current !== id) return;
          setError(e instanceof Error ? e.message : String(e));
        })
        .finally(() => {
          if (reqId.current === id) setServerLoading(false);
        });
    };
    if (debounceMs > 0) {
      const t = setTimeout(run, debounceMs);
      return () => clearTimeout(t);
    }
    run();
    // serverKey is the content hash of covered+filters; model/covered are read
    // inside but change only when serverKey does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverKey, withPicks, debounceMs]);

  // Settled fallback for rules the server doesn't grade (UFC/NHL/golf).
  const localStats = useMemo(() => {
    if (!model || uncovered.length === 0) return EMPTY_STATS;
    return computeCustomModelStats({ ...model, rules: uncovered }, settled);
  }, [model, uncovered, settled]);

  const localPicks = useMemo<BacktestPickRow[]>(() => {
    if (!model || !withPicks || uncovered.length === 0) return [];
    const sub = { ...model, rules: uncovered };
    return settled
      .filter((p) => pickMatchesModel(p, sub) && p.result != null && p.result !== 'NO_ACTION')
      .map((p) => ({
        pick_id: p.pick_id,
        model_id: p.model_id,
        game_date: p.game_date,
        pick_label: p.pick_label,
        signal_type: p.signal_type,
        result: p.result as string,
        profit_flat: p.profit_flat == null ? null : Number(p.profit_flat),
      }));
  }, [model, withPicks, uncovered, settled]);

  const stats = useMemo(() => mergeStats(serverStats, localStats), [serverStats, localStats]);

  const picks = useMemo(() => {
    if (localPicks.length === 0) return serverPicks;
    return [...serverPicks, ...localPicks].sort(
      (a, b) => b.game_date.localeCompare(a.game_date) || b.pick_id - a.pick_id,
    );
  }, [serverPicks, localPicks]);

  const loading = serverLoading || (uncovered.length > 0 && settledLoading);

  return { stats, picks, loading, error };
}

/** Full-universe backtest stats for every saved custom model (Models list). */
export function useCustomModelBacktests(models: CustomModel[]) {
  const { rows: settled } = useSettledPicksSincePaperStart();
  const [statsById, setStatsById] = useState<Record<string, CustomModelStats>>({});
  const [loading, setLoading] = useState<boolean>(false);
  const reqId = useRef(0);

  const key = useMemo(
    () => JSON.stringify(models.map((m) => ({ i: m.id, u: m.updated_at }))),
    [models],
  );

  useEffect(() => {
    const id = ++reqId.current;
    if (models.length === 0) {
      setStatsById({});
      return;
    }
    setLoading(true);
    Promise.all(
      models.map(async (m) => {
        const { covered, uncovered } = splitRulesByCoverage(m.rules);
        const server =
          covered.length > 0
            ? summaryToStats(await fetchCustomModelBacktest(covered, m.filters))
            : EMPTY_STATS;
        const local =
          uncovered.length > 0
            ? computeCustomModelStats({ ...m, rules: uncovered }, settled)
            : EMPTY_STATS;
        return [m.id, mergeStats(server, local)] as const;
      }),
    )
      .then((entries) => {
        if (reqId.current === id) setStatsById(Object.fromEntries(entries));
      })
      .catch(() => {
        // Keep whatever rendered last — a failed refresh shouldn't blank the list.
      })
      .finally(() => {
        if (reqId.current === id) setLoading(false);
      });
    // key covers models' identity+updated_at; settled feeds the uncovered part.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, settled]);

  return { statsById, loading };
}

