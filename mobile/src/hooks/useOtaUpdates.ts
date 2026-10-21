import { useEffect, useRef } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import * as Updates from 'expo-updates';

import { showToast } from '@/components/Toast';
import { markUpdateReady, UPDATE_READY_MESSAGE } from '@/lib/updateReady';
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
 * newest downloaded bundle at the next cold start; a later return that finds
 * a newer one downloads it over the first. If a download is still running
 * when a return arrives, that return is skipped.
 *
 * Quiet by design: a check is silent, and so are its failures (offline, EAS
 * unreachable). When a newer bundle lands, the member gets one toast per
 * session saying it loads the next time the app starts (Matt, 2026-10-19), and Settings
 * adds "update ready" beside the running bundle's build date.
 */
const showUpdateNote = (): void =>
  showToast(UPDATE_READY_MESSAGE, { durationMs: 6_000, announce: true });

export function useOtaUpdates(): void {
  const inFlight = useRef(false);
  const lastCheckAt = useRef<number | null>(null);
  const backgroundedAt = useRef<number | null>(null);
  /** The update note is owed: a download landed while the app was away. */
  const noteOwed = useRef(false);

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
        // Tell the member once, quietly: no button, because applying it now
        // would mean the in-process reload this hook no longer does. If the
        // download finished while the app was in the background, hold the
        // note for the next return so it is not spent unseen.
        if ((await downloadUpdate(api)) === 'downloaded' && markUpdateReady() && !unmounted) {
          if (AppState.currentState === 'active') showUpdateNote();
          else noteOwed.current = true;
        }
      } finally {
        if (!unmounted) inFlight.current = false;
      }
    };

    void run('launch', null);

    const sub = AppState.addEventListener('change', (state: AppStateStatus) => {
      if (state === 'active') {
        if (noteOwed.current) {
          noteOwed.current = false;
          showUpdateNote();
        }
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
