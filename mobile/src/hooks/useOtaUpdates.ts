import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import * as Updates from 'expo-updates';

import {
  applyPendingUpdate,
  shouldCheck,
  type CheckTrigger,
  type UpdatesApi,
} from '@/lib/otaUpdate';

/**
 * Keeps the installed app on the latest published JS bundle without anyone
 * having to force-quit it. See src/lib/otaUpdate.ts for why this is needed at
 * all — publishing an OTA is not the same as delivering it, and the gap is
 * measured in days, not minutes.
 *
 * Mounted once at the app root. Checks at cold start and on every real return
 * from the background; when a new bundle is fetched it reloads immediately.
 * A reload at those two moments is a flash, not an interruption — the parlay
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

  useEffect(() => {
    let unmounted = false;

    const run = async (trigger: CheckTrigger, awayAt: number | null): Promise<void> => {
      if (inFlight.current) return;
      const now = Date.now();
      if (!shouldCheck({
        now,
        lastCheckAt: lastCheckAt.current,
        backgroundedAt: awayAt,
        trigger,
      })) return;
      inFlight.current = true;
      lastCheckAt.current = now;
      try {
        // `Updates` is a module namespace, not a plain object — spread the
        // three calls we use so the injectable shape is explicit.
        const api: UpdatesApi = {
          isEnabled: Updates.isEnabled,
          checkForUpdateAsync: () => Updates.checkForUpdateAsync(),
          fetchUpdateAsync: () => Updates.fetchUpdateAsync(),
          reloadAsync: () => Updates.reloadAsync(),
        };
        await applyPendingUpdate(api);
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
