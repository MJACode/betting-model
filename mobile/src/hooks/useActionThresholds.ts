import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useSyncExternalStore } from 'react';

import { fetchActionThresholds } from '@/lib/queries';
import {
  markThresholdsFetched,
  setServerThresholds,
  subscribeThresholds,
  thresholdsRevisionNow,
  type ServerThreshold,
} from '@/lib/thresholds';

/**
 * Hydrate the live action thresholds from the model_action_thresholds table
 * (synced from config.py by data/threshold_sync.py) into the thresholds.ts
 * server store. Mounted ONCE at the app root.
 *
 * Flow: on mount, immediately push any cached copy (so the action filter uses
 * server values even offline / before the network returns), then fetch the
 * table and update both the store and the cache. If the fetch fails, the store
 * keeps the cached map; if there's no cache either, passesActionFilter falls
 * back to the bundled thresholds.ts constants. Net effect: threshold changes
 * land on the next app open with NO rebuild.
 */
const CACHE_KEY = 'actionThresholds.v1';

/** The store revision. A screen that filters with isModelPaused during render
 *  passes this into its useMemo deps so the fetch finishing re-renders it. */
export function useThresholdsRevision(): number {
  return useSyncExternalStore(subscribeThresholds, thresholdsRevisionNow, thresholdsRevisionNow);
}

export function useActionThresholds(): void {
  useEffect(() => {
    let mounted = true;

    // 1. Prime from cache so the filter is server-driven before the fetch lands.
    AsyncStorage.getItem(CACHE_KEY)
      .then((raw) => {
        if (!mounted || !raw) return;
        try {
          const cached = JSON.parse(raw) as Record<string, ServerThreshold>;
          if (cached && typeof cached === 'object') setServerThresholds(cached);
        } catch {
          // ignore corrupt cache
        }
      })
      .catch(() => {});

    // 2. Fetch the live table and overwrite the store + cache.
    fetchActionThresholds()
      .then((map) => {
        if (!mounted || !map || Object.keys(map).length === 0) return;
        setServerThresholds(map);
        // After the store is the live table. The cache prime above is not
        // this call: a stale cache must not be the history mark's answer.
        markThresholdsFetched();
        AsyncStorage.setItem(CACHE_KEY, JSON.stringify(map)).catch(() => {});
      })
      .catch((err) => {
        console.warn('[actionThresholds] fetch failed, using cache/bundled', err);
      });

    return () => {
      mounted = false;
    };
  }, []);
}
