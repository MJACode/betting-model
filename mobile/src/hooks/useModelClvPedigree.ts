import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect } from 'react';

import { fetchPublicTrackRecord } from '@/lib/queries';
import { setModelClv, type ModelClv } from '@/lib/sharpScore';
import { isModelRetired } from '@/lib/thresholds';
import type { TrackRecordRow } from '@/types';

/**
 * Hydrate the per-model CLV pedigree (beat-the-close rate) from
 * v_public_track_record into the sharpScore.ts store, so the Sharp Score can be
 * computed on every card with no per-row fetch. Mounted ONCE at the app root.
 *
 * Same cache-then-fetch pattern as useActionThresholds: prime from AsyncStorage
 * so the score is populated before the network returns, then refresh. The store
 * is optional — when absent, sharpScore() treats every model as "unproven" and
 * leans on the edge + contrarian components.
 */
const CACHE_KEY = 'modelClvPedigree.v1';

/** Aggregate the per-(sport, model) rows up to one CLV record per model_id. */
export function buildModelClvMap(rows: TrackRecordRow[]): Record<string, ModelClv> {
  const acc: Record<string, { beat: number; settled: number; clvSum: number }> = {};
  for (const r of rows) {
    if (isModelRetired(r.model_id)) continue; // never scores a card again
    const settled = Number(r.clv_settled ?? 0);
    if (settled <= 0) continue;
    const a = (acc[r.model_id] ??= { beat: 0, settled: 0, clvSum: 0 });
    a.beat += Number(r.clv_beat ?? 0);
    a.settled += settled;
    a.clvSum += Number(r.avg_clv_pct ?? 0) * settled; // sample-weighted mean
  }
  const out: Record<string, ModelClv> = {};
  for (const [modelId, a] of Object.entries(acc)) {
    out[modelId] = {
      beatRate: a.settled > 0 ? a.beat / a.settled : null,
      avgClvPct: a.settled > 0 ? a.clvSum / a.settled : null,
      settled: a.settled,
    };
  }
  return out;
}

export function useModelClvPedigree(): void {
  useEffect(() => {
    let mounted = true;

    AsyncStorage.getItem(CACHE_KEY)
      .then((raw) => {
        if (!mounted || !raw) return;
        try {
          const cached = JSON.parse(raw) as Record<string, ModelClv>;
          if (cached && typeof cached === 'object') setModelClv(cached);
        } catch {
          // ignore corrupt cache
        }
      })
      .catch(() => {});

    fetchPublicTrackRecord()
      .then((rows) => {
        if (!mounted || !rows?.length) return;
        const map = buildModelClvMap(rows);
        setModelClv(map);
        AsyncStorage.setItem(CACHE_KEY, JSON.stringify(map)).catch(() => {});
      })
      .catch((err) => {
        console.warn('[modelClvPedigree] fetch failed, using cache/none', err);
      });

    return () => {
      mounted = false;
    };
  }, []);
}
