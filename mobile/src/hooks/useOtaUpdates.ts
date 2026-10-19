import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import * as Updates from 'expo-updates';

import {
  downloadUpdate,
  nextAction,
  type CheckTrigger,
  type UpdatesApi,
} from '@/lib/otaUpdate';

/**
 * Keeps the installed app's NEXT launch on the latest published JS bundle.
 * See src/lib/otaUpdate.ts for why it checks at all (publishing is not
 * delivering) and why it never applies a bundle to a running app (the
 * 2026-10-19 crash: a reload inside a running process).
 *
 * Mounted once at the app root. Checks at cold start and on every real
 * return from the background, and only downloads. expo-updates launches the
 * downloaded bundle at the next cold start. Once a bundle is downloaded, no
 * further checks run this session. If a launch download is still running
 * when a return arrives, that return is skipped.
 *
 * Silent by design: an update check is not something a user asked for, and
 * the failure modes (offline, EAS unreachable) resolve themselves. The
 * running bundle's build date is shown on the Settings screen so "am I
 * current?" is still answerable.
 */
export function useOtaUpdates(): void {
  const inFlight = useRef(false);
  const lastCheckAt = useRef<number | null>(null);
  const backgroundedAt = useRef<number | null>(null);
  /** A bundle is downloaded and waiting for the next cold start. */
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
      lastCheckAt.current = now;
      try {
        // `Updates` is a module namespace, not a plain object — name the two
        // calls used so the injectable shape is explicit. No reloadAsync.
        const api: UpdatesApi = {
          isEnabled: Updates.isEnabled,
          checkForUpdateAsync: () => Updates.checkForUpdateAsync(),
          fetchUpdateAsync: () => Updates.fetchUpdateAsync(),
        };
        if ((await downloadUpdate(api)) === 'downloaded') pending.current = true;
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
