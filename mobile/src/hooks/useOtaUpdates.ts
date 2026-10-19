import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import * as Updates from 'expo-updates';

import { markOtaReload } from '@/lib/crashLog';
import {
  applyPendingUpdate,
  nextAction,
  reloadDownloaded,
  type CheckTrigger,
  type UpdatesApi,
} from '@/lib/otaUpdate';

/**
 * Keeps the installed app on the latest published JS bundle without anyone
 * having to force-quit it. See src/lib/otaUpdate.ts for why this is needed at
 * all — publishing an OTA is not the same as delivering it, and the gap is
 * measured in days, not minutes.
 *
 * Mounted once at the app root. At cold start it only DOWNLOADS a new bundle
 * (a reload mid-startup was the first-open crash, 2026-10-19). On a real
 * return from the background it applies a bundle already downloaded, or
 * checks, fetches and applies one. A reload at that moment is a flash, not an
 * interruption — the parlay
 * slip and every other persisted preference survive it (they are restored from
 * storage on mount, exactly as they are on a normal launch).
 *
 * Silent by design: an update check is not something a user asked for, and the
 * failure modes (offline, EAS unreachable) resolve themselves. The running
 * bundle's build date is shown on the Settings screen so "am I current?" is
 * still answerable.
 */
export function useOtaUpdates(): void {
  const inFlight = useRef(false);
  const lastCheckAt = useRef<number | null>(null);
  const backgroundedAt = useRef<number | null>(null);
  /** A bundle was downloaded at launch and is waiting for a real return. */
  const pending = useRef(false);

  useEffect(() => {
    let unmounted = false;

    const run = async (trigger: CheckTrigger, awayAt: number | null): Promise<void> => {
      if (inFlight.current) return;
      const now = Date.now();
      const action = nextAction({
        now,
        lastCheckAt: lastCheckAt.current,
        backgroundedAt: awayAt,
        trigger,
        pending: pending.current,
      });
      if (action === 'skip') return;
      inFlight.current = true;
      if (action !== 'reload') lastCheckAt.current = now;
      try {
        // `Updates` is a module namespace, not a plain object — spread the
        // three calls we use so the injectable shape is explicit.
        const api: UpdatesApi = {
          isEnabled: Updates.isEnabled,
          checkForUpdateAsync: () => Updates.checkForUpdateAsync(),
          fetchUpdateAsync: () => Updates.fetchUpdateAsync(),
          // Mark the stage first: if the app dies during the reload, the next
          // launch reports an early_exit at "ota_reload" (src/lib/crashLog.ts).
          reloadAsync: async () => {
            await markOtaReload();
            await Updates.reloadAsync();
          },
        };
        if (action === 'reload') {
          await reloadDownloaded(api);
        } else {
          // Launch only downloads: reloading mid-startup was the first-open
          // crash (src/lib/otaUpdate.ts header).
          const out = await applyPendingUpdate(api, action === 'download' ? 'download' : 'apply');
          if (out === 'downloaded') pending.current = true;
        }
      } finally {
        if (!unmounted) inFlight.current = false;
      }
    };

    void run('launch', null);

    const sub = AppState.addEventListener('change', (state: AppStateStatus) => {
      if (state === 'active') {
        // Read and clear together: how long we were away is the input to the
        // decision, and it must not survive into the next foreground event.
        const awayAt = backgroundedAt.current;
        backgroundedAt.current = null;
        void run('foreground', awayAt);
      } else if (state === 'background') {
        backgroundedAt.current = Date.now();
      }
    });

    return () => {
      unmounted = true;
      sub.remove();
    };
  }, []);
}
